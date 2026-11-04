"""Offline tests for voiceover.py, beats.py, screenrec tighten, dissect cut detection, assets prep_clip looks."""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

import assets
import beats
import dissect
import render
import screenrec
import voiceover
from fvcore import ffmpeg_bin, load_json, load_yaml
from storyboard import scene_lines

SR = 48000


def ff(*args):
    subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def write_f32(path: Path, x, sr=SR):
    import struct
    pcm = np.asarray(x, dtype="<f4").tobytes()
    path.write_bytes(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 3, 1, sr, sr * 4, 4, 32) + b"data" + struct.pack("<I", len(pcm)) + pcm)


# ------------------------------------------------------------------ voiceover
def project_lines(project):
    from fvcore import project_config
    pron = (project_config(project)["brief"].get("voice") or {}).get("pronunciations") or {}
    return [ln for s in load_yaml(project / "storyboard.yaml")["scenes"] for ln in scene_lines(s, pron)]


def fake_words(lines, skip=None, step=0.4, gap=0.9):
    """Pretend transcript: every script word of every line, `step` s apart, `gap` s between lines."""
    words, t = [], 1.0
    for ln in lines:
        for w in ln["say"].split():
            if skip == ln["id"]:
                continue
            words.append({"text": w.lower().strip(".,"), "start": t, "end": t + step * 0.8})
            t += step
        t += gap
    return words, t


def test_voiceover_aligns_and_writes_clips(smoke_project, tmp_path, monkeypatch):
    lines = project_lines(smoke_project)
    words, total = fake_words(lines)
    rec = tmp_path / "rec.wav"
    write_f32(rec, np.random.default_rng(0).normal(0, 0.1, int((total + 1) * SR)))
    monkeypatch.setattr(voiceover, "transcribe", lambda audio, model="small": words)
    res = voiceover.import_recording(smoke_project, rec)
    clips = load_json(smoke_project / "build" / "voice" / "clips.json")
    assert clips["provider"] == "recording" and clips["post"] == ""
    assert set(clips["clips"]) == {ln["id"] for ln in lines} and res["poor"] == []
    for ln in lines:
        c = clips["clips"][ln["id"]]
        assert c["say"] == ln["say"] and c["wav"].startswith("build/voice/recording/")
        assert (smoke_project / c["wav"]).exists()
        assert 0 <= c["speech_start"] < c["speech_end"] <= c["duration"] + 0.01
        assert [w["char"] for w in c["words"]] == [m.start() for m in __import__("re").finditer(r"\S+", ln["say"])]
        data = (smoke_project / c["wav"]).read_bytes()
        assert abs((len(data) - 44) / 4 / SR - c["duration"]) < 0.01   # 48 kHz mono float wav
    import storyboard
    tl = storyboard.build(smoke_project, quiet=True)  # re-times to the recording without touching TTS
    assert tl is not None


def test_voiceover_reports_poor_line(smoke_project, tmp_path, monkeypatch):
    lines = project_lines(smoke_project)
    words, total = fake_words(lines)
    # garble most words of the second line
    second = lines[1]["id"]
    n0 = len(lines[0]["say"].split())
    for w in words[n0:n0 + 12]:
        w["text"] = "zzz"
    rec = tmp_path / "rec.wav"
    write_f32(rec, np.zeros(int((total + 1) * SR)))
    monkeypatch.setattr(voiceover, "transcribe", lambda audio, model="small": words)
    res = voiceover.import_recording(smoke_project, rec)
    assert any(p.startswith(second) for p in res["poor"])


def test_align_interpolates_and_scores():
    lines = [{"id": "a-1", "say": "Hello there big world."}, {"id": "b-1", "say": "Second line here"}]
    words = [{"text": "hello", "start": 0, "end": 0.3}, {"text": "big", "start": 1.0, "end": 1.3}, {"text": "world", "start": 1.4, "end": 1.8},
             {"text": "second", "start": 3, "end": 3.4}, {"text": "line", "start": 3.5, "end": 3.8}, {"text": "here", "start": 3.9, "end": 4.2}]
    al = voiceover.align(lines, words)
    assert al[0]["score"] == 0.75 and al[1]["score"] == 1.0
    there = al[0]["words"][1]
    assert 0.3 <= there["start"] <= 1.0


def test_render_skips_tts_post_for_recording():
    src = Path(render.__file__).read_text(encoding="utf-8")
    assert 'clips.get("provider") == "recording"' in src


# ------------------------------------------------------------------ beats
def wavdata(path: Path):
    b = path.read_bytes()
    i = b.find(b"data")
    n = int.from_bytes(b[i + 4:i + 8], "little")
    return np.frombuffer(b[i + 8:i + 8 + n // 4 * 4], dtype="<f4")


def click_track(path: Path, bpm=120, secs=24, quiet=10):
    t = np.arange(int(secs * SR)) / SR
    x = np.zeros_like(t)
    period = 60 / bpm
    for k in range(int(secs / period)):
        s = int(k * period * SR)
        n = int(0.08 * SR)
        env = np.exp(-np.arange(n) / (0.02 * SR))
        x[s:s + n] += 0.9 * np.sin(2 * np.pi * 60 * np.arange(n) / SR) * env * (1.0 if t[s] >= quiet else 0.04)
    x[t >= quiet] += 0.25 * np.sin(2 * np.pi * 220 * t[t >= quiet])
    write_f32(path, x * 0.8)


def test_beats_bpm_and_drop(tmp_path):
    p = tmp_path / "t.wav"
    click_track(p)
    r = beats.analyse(p)
    assert set(r) >= {"bpm", "first_downbeat", "beats", "drop"}
    assert abs(r["bpm"] - 120) < 6 or abs(r["bpm"] - 60) < 3 or abs(r["bpm"] - 240) < 12
    assert r["drop"] is not None and abs(r["drop"] - 10) < 1.5
    y = beats.load(p)
    bpm, bt = beats._numpy_beats(y)
    assert abs(bpm - 120) < 6 and len(bt) > 20


def test_prepare_track_offset(tmp_path):
    x = np.r_[np.zeros(SR), 0.5 * np.sin(2 * np.pi * 440 * np.arange(2 * SR) / SR)]   # 1 s silence then tone
    src = tmp_path / "m.wav"
    write_f32(src, x)
    build = tmp_path / "b"
    build.mkdir()
    out = render.prepare_track(src, build, 1.0, fade=0.1)                 # no offset: starts silent
    a = wavdata(out)
    assert np.abs(a[:SR // 2 * 2]).max() < 0.01
    out = render.prepare_track(src, build, 1.0, fade=0.1, offset=1.0)     # offset: starts in the tone
    a = wavdata(out)
    assert np.abs(a[:SR]).max() > 0.2


# ------------------------------------------------------------------ screenrec tighten
def make_capture(project: Path, fps=10, w=64, h=36):
    from PIL import Image
    cap = project / "build" / "cap" / "s1"
    cap.mkdir(parents=True)
    n = 100
    frames = []
    for i in range(n):
        v = (i * 25) % 256 if (i < 10 or i >= 90) else 120   # 0-9 and 90-99 change, 10-89 static (8 s)
        Image.new("RGB", (w, h), (v, v, v)).save(cap / f"{i:05d}.jpg", quality=95)
        frames.append({"x": 10, "y": 10, "d": 0, "c": 1 if i == 50 else 0, "k": None, "s": 0})
    meta = {"id": "s1", "fps": fps, "w": w, "h": h, "dpr": 1, "count": n, "marks": {"m1": 20, "m2": 95}, "frames": frames, "errors": []}
    (cap / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def test_tighten_idle(smoke_project):
    make_capture(smoke_project)
    out = screenrec.tighten_idle(smoke_project, "s1", idle_speed=6)
    assert 0 < out["count"] < 100 and out["count"] == len(out["frames"])
    cap = smoke_project / "build" / "cap" / "s1"
    assert len(list(cap.glob("[0-9]*.jpg"))) == out["count"]
    clicks = [i for i, f in enumerate(out["frames"]) if f["c"]]
    assert len(clicks) == 1
    # at least 0.3 s (3 frames) of real-time frames on each side of the click survive
    assert all(out["frames"][clicks[0] + d]["x"] == 10 for d in range(-3, 4))
    assert out["marks"]["m1"] <= 20 and out["marks"]["m2"] < 95 and out["marks"]["m2"] > out["marks"]["m1"]
    assert out["marks"]["m1"] == 20 - 0 or out["marks"]["m1"] <= 20
    # the original capture is preserved and re-running starts from it
    assert (smoke_project / "build" / "cap" / "s1.orig" / "meta.json").exists()
    again = screenrec.tighten_idle(smoke_project, "s1", idle_speed=3)
    assert again["count"] > out["count"]
    # click frames count the same number of real frames: 7 around the click kept at 1x
    kept = screenrec.plan_tighten([0.0] * 100, [{"c": 1 if i == 50 else 0} for i in range(100)], {}, 10, 6, 0.6, 1.5, 0.3)
    assert all(i in kept for i in range(47, 54))


# ------------------------------------------------------------------ dissect cuts
def test_detect_cuts_ignores_pans():
    pan = np.full(60, 14.0)                        # a steady pan: high change everywhere
    assert dissect.detect_cuts(pan, fps=30, src_fps=30) == []
    d = np.full(60, 1.0)
    d[20] = 40
    d[22] = 40                                      # too close to the last cut (< 15 frames)
    d[45] = 40
    assert dissect.detect_cuts(d, fps=30, src_fps=30) == [20, 45]
    assert dissect.detect_cuts(d, fps=4, src_fps=30) == [20, 22, 45]   # at 4 fps the gap is ~2 frames


# ------------------------------------------------------------------ assets looks
def lavfi_clip(path: Path):
    ff("-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15", "-t", "1", "-pix_fmt", "yuv420p", str(path))


def cube(path: Path):
    lines = ["LUT_3D_SIZE 2"]
    for b in (0, 1):
        for g in (0, 1):
            for r in (0, 1):
                lines.append(f"{1 - r} {1 - g} {1 - b}")   # invert
    path.write_text("\n".join(lines) + "\n")


@pytest.mark.parametrize("grade", ["warm", "cool", "teal-orange", "bw"])
def test_prep_clip_grades(smoke_project, tmp_path, grade):
    src = tmp_path / "c.mp4"
    lavfi_clip(src)
    m = assets.prep_clip(smoke_project, src, "g", grade=grade, sharpen=True, width=320)
    assert m["frames"] >= 14 and m["look"]["grade"] == grade
    from PIL import Image
    im = Image.open(smoke_project / "build" / "clips" / "g" / "f_00001.jpg").convert("RGB")
    px = np.asarray(im, dtype=float)
    if grade == "bw":
        assert np.abs(px[..., 0] - px[..., 2]).mean() < 4


def test_prep_clip_lut_and_errors(smoke_project, tmp_path):
    src = tmp_path / "c.mp4"
    lavfi_clip(src)
    lut = tmp_path / "inv.cube"
    cube(lut)
    assets.prep_clip(smoke_project, src, "plain", width=320)
    assets.prep_clip(smoke_project, src, "inv", width=320, lut=lut)
    from PIL import Image
    a = np.asarray(Image.open(smoke_project / "build" / "clips" / "plain" / "f_00003.jpg").convert("RGB"), dtype=float)
    b = np.asarray(Image.open(smoke_project / "build" / "clips" / "inv" / "f_00003.jpg").convert("RGB"), dtype=float)
    assert np.abs((255 - a) - b).mean() < 12
    with pytest.raises(Exception):
        assets.clip_filters(30, 320, grade="sepia")
    with pytest.raises(Exception):
        assets.clip_filters(30, 320, lut=tmp_path / "missing.cube")
