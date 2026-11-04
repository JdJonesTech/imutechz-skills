import subprocess

import pytest

import fvcore
import review


def make_project(tmp_path, with_audio=True, dur=4):
    p = tmp_path / "proj"
    b = p / "build" / "shorts"
    b.mkdir(parents=True)
    (p / "brief.yaml").write_text("length: 4\npacing: {change_every: 1.0}\n", encoding="utf-8")
    cmd = [fvcore.ffmpeg_bin(), "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size=180x320:rate=25:duration={dur}"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}"]
    cmd += ["-pix_fmt", "yuv420p", str(b / "final.mp4")]
    subprocess.run(cmd, check=True)
    tl = {"W": 180, "H": 320, "duration": dur,
          "scenes": [{"id": "a", "t0": 0, "t1": 2, "type": "hero"}, {"id": "b", "t0": 2, "t1": dur, "type": "hero"}],
          "voice_lines": [{"at": 0.3, "dur": 2.0, "display": "hello there world"}, {"at": 3.0, "dur": 0.9, "display": "second line"}],
          "words": [{"w": "hello", "t0": 0.3, "t1": 0.7}, {"w": "there", "t0": 1.4, "t1": 1.8}, {"w": "world", "t0": 1.85, "t1": 2.3}],
          "captions": {"cues": [{"start": 0.3, "end": 0.6, "text": "hello there world"}]}}
    fvcore.save_json(p / "build" / "timeline-shorts.json", tl)
    return p


def test_review_outputs(tmp_path):
    p = make_project(tmp_path)
    r = review.review(p, "shorts")
    d = p / "build" / "shorts" / "review"
    for f in ("sheet-beats.jpg", "sheet-cuts.jpg", "sheet-hook.jpg", "checks.json"):
        assert (d / f).exists()
    checks = {f["check"] for f in r["findings"]}
    assert {"cut_on_word", "repeated_layout", "inner_voice_gaps", "dead_air_after_voice"} <= checks
    assert "Never score the film out of 10" in (p / "REVIEW.md").read_text(encoding="utf-8")


def test_preserves_looked_at(tmp_path):
    p = make_project(tmp_path)
    review.review(p, "shorts")
    md = p / "REVIEW.md"
    txt = md.read_text(encoding="utf-8").replace("(One sentence", "MY NOTES about the kettle.\n(One sentence")
    md.write_text(txt, encoding="utf-8")
    review.review(p, "shorts")
    assert "MY NOTES about the kettle." in md.read_text(encoding="utf-8")


def test_no_audio_short_and_cli(tmp_path):
    p = make_project(tmp_path, with_audio=False, dur=1)
    assert review.cli([str(p)]) == 0
    assert "no_audio" in {f["check"] for f in review.review(p, "shorts")["findings"]}


def test_missing_video(tmp_path):
    p = tmp_path / "x"
    p.mkdir()
    (p / "brief.yaml").write_text("a: 1\n")
    with pytest.raises(fvcore.FishError):
        review.review(p)
