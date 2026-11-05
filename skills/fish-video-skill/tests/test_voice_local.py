"""Offline tests for the local voice studio (voicelab.py). A stub worker stands in for the engines: no models, no network."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

import fishvideo
import voicelab as vl
import voice as voicemod
from fvcore import FishError, load_json, load_yaml, save_yaml

STUB = Path(__file__).parent / "stub_voice_worker.py"


@pytest.fixture
def stub(tmp_path, monkeypatch):
    """Point every engine at the stub worker run by this interpreter."""
    monkeypatch.setenv("FISH_VOICELAB_WORKER", str(STUB))
    for e in ("CHATTERBOX", "KOKORO", "WHISPER"):
        monkeypatch.setenv(f"FISH_{e}_PYTHON", sys.executable)
    monkeypatch.setenv("FISH_TTS_HOME", str(tmp_path / "tts"))
    monkeypatch.setenv("STUB_LOG", str(tmp_path / "jobs.log"))
    monkeypatch.setattr(vl, "_PROBE", {})
    return tmp_path / "jobs.log"


def jobs(log):
    return log.read_text().split() if log.exists() else []


def tone(f0, secs=2.0, sr=48000, amp=0.2):
    t = np.arange(int(secs * sr)) / sr
    return (sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 10)) * amp).astype("float32"), sr


# ------------------------------------------------------------------ presets
def test_preset_grid_resolves_for_both_engines():
    cfg = vl.config()
    for eng in ("chatterbox", "kokoro"):
        for g in ("male", "female"):
            for s in cfg["styles"]:
                for p in ("slow", "natural", "fast", 3.1):
                    S = vl.studio_settings({"studio": {"gender": g, "style": s, "pace": p}}, eng)
                    assert S["gender"] == g and S["style"] == s and 1.5 <= S["target_wps"] <= 4.5


def test_pace_ordering_and_numeric_pace_interpolates():
    sl, na, fa = (vl._pace(p) for p in ("slow", "natural", "fast"))
    assert sl["wps"] < na["wps"] < fa["wps"] and sl["cfg_weight"] < na["cfg_weight"] < fa["cfg_weight"]
    mid = vl._pace(2.7)
    assert sl["cfg_weight"] < mid["cfg_weight"] < na["cfg_weight"] and mid["wps"] == 2.7


@pytest.mark.parametrize("bad", [{"gender": "robot"}, {"style": "angry"}, {"pace": "warp"}, {"pace": 9}])
def test_bad_preset_values_are_refused(bad):
    with pytest.raises(FishError):
        vl.studio_settings({"studio": {"gender": "male", "style": "soft", "pace": "natural", **bad}}, "chatterbox")


def test_gender_reference_routing():
    male = vl.studio_settings({"studio": {"gender": "male", "style": "soft"}}, "chatterbox")
    female = vl.studio_settings({"studio": {"gender": "female", "style": "soft"}}, "chatterbox")
    assert male["ref"] is None                                          # Chatterbox's built-in voice is the male one
    assert female["ref"] == {"kind": "kokoro", "voice": "af_heart"}     # made at run time, never shipped
    assert vl.studio_settings({"studio": {"gender": "female"}, "language": "en-GB"}, "kokoro")["voice"] == "bf_emma"


def test_style_and_mood_move_emotion_and_pause():
    S = vl.studio_settings({"studio": {"gender": "male", "style": "soft", "pace": "natural"}}, "chatterbox")
    calm = vl.plan_line("This is a calm sentence here.", None, S)[0]
    glad = vl.plan_line("This is a happy sentence here!", "excited", S)[0]
    sad = vl.plan_line("This is a quiet sentence here.", "reflective", S)[0]
    assert glad["exaggeration"] > calm["exaggeration"] > sad["exaggeration"]
    assert sad["pause"] > calm["pause"] > glad["pause"]
    assert 0.25 <= S["exaggeration"] <= 0.7 and S["temperature"] == 0.75 and S["cfg_weight"] <= 0.3


def test_sentences_are_split_and_fragments_merged():
    t = "Short one. This is a longer second sentence here. Ok. Then a third sentence follows."
    parts = [t[a:b] for a, b in vl.split_sentences(t)]
    assert parts == ["Short one. This is a longer second sentence here.", "Ok. Then a third sentence follows."]
    u = "One two three four. Five six seven eight."
    assert [u[a:b] for a, b in vl.split_sentences(u)] == ["One two three four.", "Five six seven eight."]


# ------------------------------------------------------------------ text checks
def test_wer_and_normalisation():
    assert vl.wer("a b c d".split(), "a b c d".split()) == 0
    assert vl.wer("a b c d".split(), "a b d".split()) == 0.25
    assert vl.norm_words("Seven steps, 20% faster!") == ["seven", "steps", "twenty", "percent", "faster"]
    assert vl.norm_words("In 2026 it's") == ["in", "twenty", "twenty", "six", "its"]
    assert vl.norm_words("Q Laura works", {"q laura": "qlora"}) == ["qlora", "works"]


def test_text_match_levels():
    assert vl.text_match("Use GenAI today.", "Use Gen AI today")["exact"]                   # spacing only
    v = vl.text_match("Try LlamaIndex now.", "Try Lama Index now.")
    assert v["ok"] and not v["exact"]                                                        # "Lama Index": a spelling variant, flagged
    v = vl.text_match("Try QLoRA now please.", "Try Qlura now please.")
    assert v["ok"] and not v["exact"]                                                        # a spelling variant: flagged, not retried
    bad = vl.text_match("This is the whole sentence.", "This is the sentence.")
    assert not bad["ok"] and bad["wer"] > 0.15
    assert vl.text_match("Q Laura", "QLoRA", {"qlora": "q laura"})["exact"]                  # respelling normalised by alias


# ------------------------------------------------------------------ measurements
def test_pitch_labels_gender_from_measurement():
    m, sr = tone(110)
    f, _ = vl.pitch(m, sr)
    assert abs(f - 110) < 6 and vl.gender_of(f) == "male"
    w, sr = tone(215)
    f, _ = vl.pitch(w, sr)
    assert abs(f - 215) < 10 and vl.gender_of(f) == "female"
    assert vl.gender_of(None) is None


def test_measure_pauses_edges_clipping_and_air():
    x, sr = tone(120, 1.0)
    sil = np.zeros(int(0.5 * sr), dtype="float32")
    y = np.concatenate([sil[:int(0.1 * sr)], x, sil, x, sil[:int(0.2 * sr)]])
    m = vl.measure(y, sr, 8)
    assert m["pauses"] == [0.5] and abs(m["head"] - 0.1) < 0.03 and abs(m["tail"] - 0.2) < 0.03
    assert abs(m["wps"] - 8 / 2.5) < 0.1
    assert vl.measure(np.zeros(sr, dtype="float32"), sr).get("silent")
    clipped = np.clip(y * 8, -1, 1)
    assert vl.measure(clipped, sr)["clip_run"] >= 8
    rng = np.random.default_rng(0)
    hissy = (x + rng.normal(0, 0.05, len(x))).astype("float32")
    assert vl.air_db(hissy, sr) > vl.air_db(x, sr) + 6


# ------------------------------------------------------------------ pace loop
def test_solve_pace_uses_pauses_then_stretch_then_regen():
    words, durs = 30, [3.0, 3.0, 3.0]                                    # 9 s of speech, 3.33 wps articulated
    r = vl.solve_pace(words, durs, [0.4, 0.4], 2.8, "chatterbox", 0.28)  # 30/2.8 = 10.7 s: needs 1.7 s of pause
    assert r["converged"] and abs(r["wps"] - 2.8) <= 0.15 and r["stretch"] == 1.0 and sum(r["pauses"]) > 1.5
    r = vl.solve_pace(words, durs, [0.4, 0.4], 3.2, "chatterbox", 0.28)  # 9.4 s: pauses shrink to the floor, then a small stretch
    assert r["converged"] and r["stretch"] >= 1.0 and all(p >= 0.15 for p in r["pauses"])
    r = vl.solve_pace(words, durs, [0.4, 0.4], 1.8, "chatterbox", 0.28)  # 16.7 s: far too slow to reach with pauses and 6% stretch
    assert not r["converged"] and r["regen"] and r["regen"]["cfg_weight"] < 0.28 and r["stretch"] <= 1.06
    r = vl.solve_pace(words, durs, [0.4, 0.4], 4.0, "kokoro", 1.0)
    assert r["regen"] and r["regen"]["speed"] > 1.0
    short = vl.solve_pace(3, [1.0], [], 2.8, "chatterbox", 0.28)         # too short to steer
    assert short["converged"] is None and short["regen"] is None


# ------------------------------------------------------------------ consent guard
def test_reference_guard(tmp_path):
    ok = tmp_path / "me.wav"; ok.write_bytes(b"x")
    with pytest.raises(FishError, match="consent"):
        vl.check_reference(ok, False)
    assert vl.check_reference(ok, True) == ok
    for bad in (tmp_path / "build" / "voice" / "elevenlabs" / "l1.wav", tmp_path / "narration-edge-tts.wav", tmp_path / "build" / "auditions" / "x.mp3"):
        bad.parent.mkdir(parents=True, exist_ok=True); bad.write_bytes(b"x")
        with pytest.raises(FishError, match="hosted provider"):
            vl.check_reference(bad, True)                                   # consent does not unlock a hosted provider's output
    with pytest.raises(FishError, match="not found"):
        vl.check_reference(tmp_path / "none.wav", True)


def test_user_reference_needs_consent_flag(stub, tmp_path):
    ref = tmp_path / "mine.wav"; ref.write_bytes(b"x")
    S = vl.studio_settings({"studio": {"gender": "female", "reference": str(ref)}}, "chatterbox")
    assert S["ref"]["kind"] == "user" and not S["ref"]["consent"]
    with pytest.raises(FishError, match="consent"):
        vl.resolve_reference(S, tmp_path)


# ------------------------------------------------------------------ synthesis with the stub
TEXT = "The first sentence has seven words in it. The second sentence has some words too. And a third one closes the line nicely."


def run_line(tmp_path, pace, gender="male", force=True, text=TEXT, extra=None):
    studio = {"gender": gender, "style": "soft", "pace": pace, **(extra or {})}
    out = tmp_path / "out"
    return vl.synth_lines([{"id": "l1", "say": text}], {"studio": studio}, "chatterbox", out, force=force)["l1"]


def test_pace_loop_lands_inside_the_band_at_two_targets(stub, tmp_path):
    slow, fast = run_line(tmp_path, 2.4), run_line(tmp_path, 3.2)
    for cl, tgt in ((slow, 2.4), (fast, 3.2)):
        assert cl["studio"]["target_wps"] == tgt and abs(cl["studio"]["wps"] - tgt) <= 0.15, cl["studio"]
    assert slow["duration"] > fast["duration"]
    assert slow["studio"]["pauses"] == 2 and slow["studio"]["voice_source"].startswith("reference made locally") is False


def test_word_timings_follow_the_script_words(stub, tmp_path):
    cl = run_line(tmp_path, "natural")
    assert [w["text"] for w in cl["words"]][:3] == ["The", "first", "sentence"]
    t = [w["start"] for w in cl["words"]]
    assert t == sorted(t) and cl["speech_end"] <= cl["duration"] and not cl["estimated_timing"]
    assert cl["words"][0]["char"] == 0


def test_cache_regenerates_nothing_on_second_run(stub, tmp_path):
    run_line(tmp_path, "natural", force=False)
    n = len(jobs(stub))
    run_line(tmp_path, "natural", force=False)
    assert len(jobs(stub)) == n                                             # not one worker call
    run_line(tmp_path, "natural", force=False, text=TEXT + " One more sentence appears at the end.")
    assert len(jobs(stub)) > n                                              # changed text re-voices
    run_line(tmp_path, "natural", force=True)
    assert len(jobs(stub)) > n + 2


def test_wrong_words_trigger_a_new_seed(stub, tmp_path, monkeypatch):
    monkeypatch.setenv("STUB_BAD_SEEDS", "11")                              # the first seed drops a word, the next one does not
    cl = run_line(tmp_path, "natural")
    assert all(s["ok"] for s in cl["studio"]["sentences"]) and {s["seed"] for s in cl["studio"]["sentences"]} == {12}
    monkeypatch.setenv("STUB_BAD_SEEDS", "11,12,13,14,15,16")               # never right: the closest take is kept and flagged
    cl = run_line(tmp_path / "b", "natural")
    assert any(s["ok"] is False for s in cl["studio"]["sentences"])


def test_female_chatterbox_makes_its_reference_with_kokoro(stub, tmp_path):
    cl = run_line(tmp_path, "natural", gender="female")
    assert "Kokoro" in cl["studio"]["voice_source"] and list((tmp_path / "out" / "refs").glob("kokoro-af_heart-*.wav"))


def test_no_engine_gives_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("FISH_CHATTERBOX_PYTHON", raising=False)
    monkeypatch.setenv("FISH_TTS_HOME", str(tmp_path / "empty"))
    monkeypatch.setattr(vl, "_PROBE", {})
    with pytest.raises(FishError, match="voice setup --engine chatterbox"):
        vl.synth_lines([{"id": "a", "say": TEXT}], {"studio": {}}, "chatterbox", tmp_path / "o")


# ------------------------------------------------------------------ project flow, voice check, qa
def studio_project(smoke_project, provider="chatterbox"):
    b = load_yaml(smoke_project / "brief.yaml")
    b.setdefault("voice", {}).update({"provider": provider, "studio": {"gender": "male", "style": "soft", "pace": "natural"}})
    save_yaml(smoke_project / "brief.yaml", b)
    return smoke_project


def add_sidecars(project):
    """The stub 'hears' a finished clip only when it has a sidecar: give each the script's own words."""
    data = load_json(project / "build" / "voice" / "clips.json")
    for cl in data["clips"].values():
        (project / (cl["wav"] + ".txt")).write_text(json.dumps({"text": cl["say"], "seed": -1}))
    return data


def test_project_voice_check_and_qa_rows(stub, smoke_project):
    p = studio_project(smoke_project)
    cfg = fishvideo.project_config(p)
    res = voicemod.synthesize(p, "chatterbox")                              # the normal entry point routes to the studio
    assert res["provider"] == "chatterbox" and res["voice"]["watermark"] is True and res["clips"]
    assert all((p / cl["wav"]).exists() for cl in res["clips"].values())
    add_sidecars(p)
    rep = vl.check_project(p)
    rows = {r["check"]: r for r in rep["rows"]}
    assert rows["voice words"]["status"] == "PASS" and rows["voice signal"]["status"] == "PASS", rows
    assert [r["check"] for r in vl.qa_rows(p)] == [r["check"] for r in rep["rows"]]


def test_check_catches_a_deliberate_failure(stub, smoke_project):
    p = studio_project(smoke_project)
    res = voicemod.synthesize(p, "chatterbox")
    data = add_sidecars(p)
    lid = next(iter(data["clips"]))
    cl = data["clips"][lid]
    (p / (cl["wav"] + ".txt")).write_text(json.dumps({"text": cl["say"] + " and then a whole extra clause nobody wrote", "seed": -1}))
    clipped = np.clip(tone(120, 1.0)[0] * 9, -1, 1)
    other = list(data["clips"])[1] if len(data["clips"]) > 1 else None
    if other:
        vl.write_wav(p / data["clips"][other]["wav"], clipped, 48000)
    rep = vl.check_project(p)
    rows = {r["check"]: r for r in rep["rows"]}
    assert rows["voice words"]["status"] == "FAIL" and lid in rows["voice words"]["detail"]
    if other:
        assert rows["voice signal"]["status"] == "FAIL" and "clipping" in rows["voice signal"]["detail"]


def test_qa_rows_skip_when_not_studio_or_no_engine(smoke_project, tmp_path, monkeypatch):
    assert vl.qa_rows(smoke_project) == []                                  # no clips at all
    d = smoke_project / "build" / "voice"; d.mkdir(parents=True, exist_ok=True)
    (d / "clips.json").write_text(json.dumps({"provider": "edge-tts", "clips": {"a": {"say": "x", "wav": "a.wav"}}}))
    assert vl.qa_rows(smoke_project) == []                                  # other providers: existing QA is unchanged
    (d / "clips.json").write_text(json.dumps({"provider": "chatterbox", "studio": {"engine": "chatterbox"}, "clips": {"a": {"say": "x y z", "wav": "a.wav"}}}))
    rows = vl.qa_rows(smoke_project)                                        # missing file: a WARN row, never an exception
    assert rows and rows[0]["status"] == "WARN"


def test_redo_changes_one_line_only(stub, smoke_project):
    p = studio_project(smoke_project)
    res = voicemod.synthesize(p, "chatterbox")
    ids = list(res["clips"])
    before = {i: res["clips"][i]["hash"] for i in ids}
    cl = vl.redo(p, ids[0], seed=99)
    after = load_json(p / "build" / "voice" / "clips.json")["clips"] if (p / "build" / "voice" / "clips.json").exists() else {}
    assert cl["hash"] != before[ids[0]]
    assert all(after[i]["hash"] == before[i] for i in ids[1:])
    assert load_yaml(p / "brief.yaml")["voice"]["studio"]["lines"][ids[0]]["seed"] == 99
    with pytest.raises(FishError, match="no narration line"):
        vl.redo(p, "nope")


def test_audition_matrix_writes_index(stub, tmp_path):
    rows = vl.audition_matrix(tmp_path / "aud", "chatterbox", ["male", "female"], ["airy", "soft"], "natural", "Here is a short line to audition. It has two sentences in it.")
    assert len(rows) == 4 and (tmp_path / "aud" / "index.md").exists()
    idx = load_json(tmp_path / "aud" / "index.json")
    assert {(r["gender"], r["style"]) for r in idx["samples"]} == {(g, s) for g in ("male", "female") for s in ("airy", "soft")}
    assert all(r["wps"] and r["f0"] for r in idx["samples"]) and "Nobody has listened" in (tmp_path / "aud" / "index.md").read_text()


# ------------------------------------------------------------------ setup and wiring
def test_setup_commands_are_pinned_cpu_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.shutil, "which", lambda n: "/usr/bin/uv" if n == "uv" else None)
    dest, cmds = vl.setup_commands("chatterbox", tmp_path)
    flat = " ".join(" ".join(c) for c in cmds)
    assert "setuptools<81" in flat and "chatterbox-tts==" in flat and "torch==" in flat and "whl/cpu" in flat and str(dest).startswith(str(tmp_path))
    _, gpu = vl.setup_commands("chatterbox", tmp_path, gpu=True)
    assert "whl/cpu" not in " ".join(" ".join(c) for c in gpu)
    assert "kokoro==" in " ".join(" ".join(c) for c in vl.setup_commands("kokoro", tmp_path)[1])
    monkeypatch.setattr(vl.shutil, "which", lambda n: "/usr/bin/" + n if n.startswith("python") else None)
    assert vl.setup_commands("kokoro", tmp_path)[1][-1][1:4] == ["-m", "pip", "install"]
    with pytest.raises(FishError):
        vl.setup("nope")


@pytest.mark.skipif(sys.platform == "win32", reason="uses a shell wrapper as the environment's python")
def test_setup_skips_a_finished_environment(stub, tmp_path):
    dest = tmp_path / "home" / "chatterbox"
    py = vl.env_python(dest); py.parent.mkdir(parents=True)
    py.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n'); py.chmod(0o755)
    spec = vl.config()["engines"]["chatterbox"]
    (dest / "fish-engine.json").write_text(json.dumps({"engine": "chatterbox", "packages": spec["packages"] + spec["torch"], "gpu": False}))
    # the marker matches and the stub probe reports the module: nothing is run
    r = vl.setup("chatterbox", tmp_path / "home", False, False)
    assert r["changed"] is False and "dry_run" not in r


def test_cli_routes_voice_subcommands(stub, capsys):
    assert fishvideo.cli(["voice", "engines"]) == 0
    c = capsys.readouterr()
    assert json.loads(c.err + c.out)["chatterbox"]["installed"] is True
    assert voicemod.pick_provider({"voice": {"provider": "chatterbox"}}, None)[0] == "chatterbox"
