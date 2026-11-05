"""Use your own recorded narration instead of a synthetic voice.

    python scripts/voiceover.py <project> <recording.wav|mp3|m4a> [--model small] [--words words.json]

`--words` skips transcription and uses a word list made elsewhere (another machine or Python, where faster-whisper
works): a JSON list of {"text", "start", "end"} in seconds of THIS recording (whisper-style "word" is accepted for "text";
a {"words": [...]} wrapper is accepted too).

Record yourself reading the storyboard's narration lines in order (one take; retakes of a line are
not detected). The recording is transcribed with faster-whisper (word timestamps, int8, CPU), the
storyboard lines are aligned to the transcript words, and every line is cut out into
build/voice/recording/<line>-<hash>.wav. build/voice/clips.json is written with provider "recording"
in the same format `voice` produces, so `fishvideo storyboard` re-times every scene to your voice
and `render` places your clips. Lines that matched the transcript poorly (< 0.7) are reported by
name: listen to those. The recording is used as is (no post chain); pacing.max_word_gap still trims
long pauses inside a line.
"""
from __future__ import annotations

import argparse
import difflib
import re
import struct
from pathlib import Path

from fvcore import FishError, ensure_project, load_yaml, log, main_guard, project_config, save_json, sha1, warn
from storyboard import scene_lines
from voice import decode_wav, tighten

SR = 48000
PAD = 0.12          # seconds kept around each cut line
MIN_SCORE = 0.7


def norm(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower().replace("’", "").replace("'", ""))


def transcribe(audio: Path, model: str = "small") -> list[dict]:
    """faster-whisper word list [{text, start, end}] (int8 on CPU)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise FishError("faster-whisper is not installed: .venv pip install faster-whisper")
    import numpy as np
    import subprocess
    from fvcore import ffmpeg_bin
    # decode with our ffmpeg (16 kHz mono float) so faster-whisper's PyAV decoder is not needed
    raw = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True)
    pcm = np.frombuffer(raw.stdout, dtype=np.float32).copy()
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(pcm, word_timestamps=True)
    words = []
    for sg in segs:
        for w in (sg.words or []):
            if norm(w.word):
                words.append({"text": w.word.strip(), "start": float(w.start), "end": float(w.end)})
    return words


def load_words(path) -> list[dict]:
    """Read a transcript made elsewhere. Strict: a wrong shape would silently mis-time every line."""
    import json
    f = Path(path)
    if not f.is_file():
        raise FishError(f"--words file not found: {f}")
    try:
        data = json.loads(f.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise FishError(f"--words file is not valid JSON: {e}") from None
    if isinstance(data, dict):
        data = data.get("words")
    if not isinstance(data, list) or not data:
        raise FishError('--words must be a non-empty JSON list of {"text", "start", "end"} (or {"words": [...]})')
    out = []
    for i, w in enumerate(data):
        try:
            text = str(w.get("text", w.get("word", ""))).strip()
            a, b = float(w["start"]), float(w["end"])
        except (AttributeError, KeyError, TypeError, ValueError):
            raise FishError(f'--words entry {i} needs "text", "start", "end" (seconds): {str(w)[:80]}') from None
        if not norm(text):
            continue                                     # punctuation-only tokens carry no timing
        if not (0 <= a <= b):
            raise FishError(f"--words entry {i} ({text!r}): need 0 <= start <= end, got {a}..{b}")
        if out and a < out[-1]["start"] - 0.5:
            raise FishError(f"--words entry {i} ({text!r}) starts at {a}s, before the previous word: words must be in spoken order")
        out.append({"text": text, "start": a, "end": b})
    if not out:
        raise FishError("--words has no usable words")
    return out


def align(lines: list[dict], words: list[dict]) -> list[dict]:
    """Sequentially align narration lines to transcript words (difflib on normalised words).

    Returns per line {id, say, words:[{text,start,end,char}] (absolute recording seconds), score, matched, total}.
    Script words with no transcript match get times interpolated between their matched neighbours.
    """
    script, owner = [], []   # (norm, text, char) per script word; owner = line index
    for k, ln in enumerate(lines):
        for m in re.finditer(r"\S+", ln["say"]):
            n = norm(m.group(0))
            if n:
                script.append((n, m.group(0), m.start()))
                owner.append(k)
    sm = difflib.SequenceMatcher(None, [s[0] for s in script], [norm(w["text"]) for w in words], autojunk=False)
    hit = {}
    for a, b, size in sm.get_matching_blocks():
        for i in range(size):
            hit[a + i] = b + i
    out = []
    for k, ln in enumerate(lines):
        idx = [i for i, o in enumerate(owner) if o == k]
        rec = [None] * len(idx)
        for j, i in enumerate(idx):
            if i in hit:
                w = words[hit[i]]
                rec[j] = (w["start"], w["end"])
        got = [j for j, r in enumerate(rec) if r]
        score = len(got) / len(idx) if idx else 0.0
        if got:
            for j in range(len(idx)):
                if rec[j]:
                    continue
                prev = next((q for q in range(j - 1, -1, -1) if rec[q]), None)
                nxt = next((q for q in range(j + 1, len(idx)) if rec[q]), None)
                if prev is not None and nxt is not None:
                    t0, t1 = rec[prev][1], rec[nxt][0]
                    span = nxt - prev
                    a = t0 + (t1 - t0) * (j - prev) / span
                    rec[j] = (a, a + max(0.05, (t1 - t0) / span))
                elif prev is not None:
                    rec[j] = (rec[prev][1], rec[prev][1] + 0.2)
                else:
                    rec[j] = (max(0.0, rec[nxt][0] - 0.2), rec[nxt][0])
        ws = [{"text": script[i][1], "start": r[0], "end": r[1], "char": script[i][2]} for i, r in zip(idx, rec) if r]
        out.append({"id": ln["id"], "say": ln["say"], "words": ws, "score": round(score, 3), "matched": len(got), "total": len(idx)})
    return out


def read_wav(path: Path):
    import numpy as np
    data = path.read_bytes()
    i = data.find(b"data")
    n = int.from_bytes(data[i + 4:i + 8], "little")
    return np.frombuffer(data[i + 8:i + 8 + n], dtype=np.float32).copy()


def write_wav(path: Path, x) -> None:
    pcm = x.astype("<f4").tobytes()
    hdr = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 3, 1, SR, SR * 4, 4, 32) + b"data" + struct.pack("<I", len(pcm))
    path.write_bytes(hdr + pcm)


def import_recording(project, recording, model: str = "small", words: list[dict] | None = None) -> dict:
    """Align + cut + write clips.json. `words` skips transcription (tests, or a cached transcript)."""
    import numpy as np
    project = ensure_project(project)
    recording = Path(recording)
    if not recording.exists():
        raise FishError(f"missing file: {recording}")
    cfg = project_config(project)
    sb = load_yaml(project / "storyboard.yaml")
    pron = (cfg["brief"].get("voice") or {}).get("pronunciations") or {}
    lines = [ln for s in sb["scenes"] for ln in scene_lines(s, pron)]
    if not lines:
        raise FishError("the storyboard has no narration lines")
    out = project / "build" / "voice" / "recording"
    out.mkdir(parents=True, exist_ok=True)
    full = out / "_recording.wav"
    decode_wav(recording, full)
    x = read_wav(full)
    total = len(x) / SR
    if words is None:
        log(f"transcribing {recording.name} ({total:.1f}s) with faster-whisper {model} ...")
        words = transcribe(full, model)
    al = align(lines, words)
    max_gap = (cfg.get("pacing") or {}).get("max_word_gap")
    spans = [(a["words"][0]["start"], a["words"][-1]["end"]) if a["words"] else None for a in al]
    clips, poor = {}, []
    rec_key = {"file": recording.name, "size": recording.stat().st_size}
    for k, a in enumerate(al):
        if a["score"] < MIN_SCORE:
            poor.append(f"{a['id']} ({a['score']:.2f})")
        if not spans[k]:
            warn(f"{a['id']}: nothing matched in the recording; the line was skipped (re-record it)")
            continue
        s0, s1 = spans[k]
        prev_end = next((spans[q][1] for q in range(k - 1, -1, -1) if spans[q]), None)
        next_start = next((spans[q][0] for q in range(k + 1, len(spans)) if spans[q]), None)
        c0 = max(0.0, s0 - PAD)
        if prev_end is not None:
            c0 = max(c0, min(s0, (prev_end + s0) / 2))
        c1 = min(total, s1 + PAD)
        if next_start is not None:
            c1 = min(c1, max(s1, (s1 + next_start) / 2))
        seg = x[int(c0 * SR):int(c1 * SR)].copy()
        f = min(240, len(seg) // 4)
        if f:
            seg[:f] *= np.linspace(0, 1, f)
            seg[-f:] *= np.linspace(1, 0, f)
        ws = [{"text": w["text"], "start": round(max(0.0, w["start"] - c0), 3), "end": round(max(0.0, w["end"] - c0), 3), "char": w["char"]}
              for w in a["words"]]
        h = sha1({"say": a["say"], "rec": rec_key, "c0": round(c0, 3), "c1": round(c1, 3), "max_gap": max_gap})
        wav = out / f"{a['id']}-{h}.wav"
        write_wav(wav, seg)
        dur = len(seg) / SR
        if max_gap:
            ws, dur = tighten(wav, ws, float(max_gap))
        clips[a["id"]] = {"say": a["say"], "provider": "recording", "hash": h, "wav": str(wav.relative_to(project)).replace("\\", "/"),
                          "duration": round(dur, 3), "speech_start": round(ws[0]["start"], 3), "speech_end": round(ws[-1]["end"], 3),
                          "words": ws, "match": a["score"]}
        log(f"  {a['id']:<18} {dur:5.2f}s  match {a['score']:.2f}  {a['say'][:60]}")
    res = {"provider": "recording", "voice": {"provider": "recording", "file": recording.name}, "post": "", "clips": clips}
    save_json(project / "build" / "voice" / "clips.json", res)
    if poor:
        warn("poor match (< 0.7), listen to: " + ", ".join(poor))
    log(f"voiceover: {len(clips)}/{len(lines)} lines cut from {recording.name} -> build/voice/clips.json")
    res["poor"] = poor
    return res


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("recording")
    ap.add_argument("--model", default="small")
    ap.add_argument("--words", default=None, help="JSON transcript made elsewhere; skips transcription")
    ns = ap.parse_args(argv)
    import_recording(Path(ns.project), ns.recording, ns.model, words=load_words(ns.words) if ns.words else None)
    return 0


if __name__ == "__main__":
    main_guard(cli)
