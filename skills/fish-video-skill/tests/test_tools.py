"""Offline unit tests for youtube.py, trends.py, assets.py, screenrec.py (no network, no real recording)."""
import io
import json
import subprocess
import urllib.request
import zipfile
from pathlib import Path

import pytest

import assets
import fvnet
import screenrec
import trends
import youtube
from fvcore import FishError, ffmpeg_bin


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def mock_urlopen(monkeypatch, routes, seen=None):
    """routes: {substring: bytes|dict}; first match wins."""
    def fake(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        if seen is not None:
            seen.append((url, dict(req.header_items()) if hasattr(req, "header_items") else {}, timeout))
        for k, v in routes.items():
            if k in url:
                return FakeResp(v if isinstance(v, bytes) else json.dumps(v).encode())
        raise urllib.error.URLError("no route in test")
    monkeypatch.setattr(urllib.request, "urlopen", fake)


@pytest.fixture
def proj(tmp_path):
    (tmp_path / "brief.yaml").write_text("title: t\n", encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------------ fvnet
def test_fetch_sends_ua_and_timeout_and_redacts_key(monkeypatch):
    seen = []
    mock_urlopen(monkeypatch, {"ok.example": {"a": 1}}, seen)
    assert fvnet.fetch_json("https://ok.example/x", {"q": "hi"}) == {"a": 1}
    url, hdrs, to = seen[0]
    assert "FishVideoSkill/2.0" in hdrs["User-agent"] and to == 20
    with pytest.raises(fvnet.NetError) as e:
        fvnet.fetch("https://nope.example/y", {"key": "SECRET123"})
    assert "SECRET123" not in str(e.value)


def test_norm_license():
    assert fvnet.norm_license("CC0")["ok"] and not fvnet.norm_license("CC0")["attribution"]
    assert fvnet.norm_license("CC BY-SA 4.0")["label"] == "CC BY-SA 4.0"
    assert fvnet.norm_license("CC BY 4.0")["attribution"]
    assert not fvnet.norm_license("CC BY-NC 4.0")["ok"]
    assert not fvnet.norm_license("CC BY-ND 2.0")["ok"]
    assert not fvnet.norm_license("All rights reserved")["ok"]
    assert fvnet.norm_license("Public domain")["ok"]


# ------------------------------------------------------------------ youtube
def test_yt_licence_guard_refuses_non_cc(monkeypatch, proj):
    monkeypatch.setattr(youtube, "info", lambda url: {"id": "abc", "title": "T", "license": "Standard YouTube License"})
    with pytest.raises(FishError, match="Creative Commons"):
        youtube.download("https://youtu.be/abc", proj / "assets" / "video", "asset", project=proj)
    with pytest.raises(FishError, match="Creative Commons"):
        youtube.clip("https://youtu.be/abc", 0, 5, proj / "assets" / "video", project=proj)
    assert youtube.is_creative_commons({"license": "Creative Commons Attribution license (reuse allowed)"})
    assert not youtube.is_creative_commons({"license": None})


def test_yt_download_bad_purpose():
    with pytest.raises(FishError):
        youtube.download("u", "d", "stealing")


def test_yt_normalize_and_short():
    r = youtube.normalize({"id": "x", "title": "T", "view_count": 1000, "upload_date": "20200101", "duration": 30, "width": 720, "height": 1280, "tags": ["a"]})
    assert r["is_short"] and r["views_per_day"] > 0 and r["url"].endswith("x")
    assert not youtube.is_short(600, 1920, 1080)
    assert not youtube.is_short(100, 1920, 1080)  # horizontal
    assert youtube.is_short(100, None, None)


def test_yt_api_search_and_suggest(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "K")
    mock_urlopen(monkeypatch, {
        "googleapis.com/youtube/v3/search?": {"items": [{"id": {"videoId": "v1"}}]},
        "googleapis.com/youtube/v3/videos?": {"items": [{"id": "v1", "snippet": {"title": "Hi", "channelTitle": "C", "publishedAt": "2024-01-01T00:00:00Z", "tags": ["t"]},
                               "statistics": {"viewCount": "5000"}, "contentDetails": {"duration": "PT1M5S"}}]},
        "suggestqueries": b'["q", ["motion graphics", "motion graphics after effects"]]'})
    r = youtube.search("q", 3)
    assert r[0]["id"] == "v1" and r[0]["duration"] == 65 and r[0]["views"] == 5000
    assert youtube.suggest("q") == ["motion graphics", "motion graphics after effects"]


def test_vtt_parse_dedupes_rolling_captions():
    vtt = """WEBVTT

00:00:00.000 --> 00:00:02.000
hello <00:00:01.000><c>world</c>

00:00:02.000 --> 00:00:02.010
hello world

00:00:02.010 --> 00:00:04.000
hello world
this is the hook. And more
"""
    cues = youtube.parse_vtt(vtt)
    assert [c["text"] for c in cues] == ["hello world", "this is the hook. And more"]
    assert youtube.first_sentence(" ".join(c["text"] for c in cues)) == "hello world this is the hook."


def test_parse_time():
    assert youtube.parse_time("1:02:03") == 3723 and youtube.parse_time("1:30") == 90 and youtube.parse_time(5) == 5.0


# ------------------------------------------------------------------ trends
def _v(i, title, vpd, dur=600, tags=()):
    return {"id": str(i), "title": title, "channel": "c", "views": 1000, "upload_date": "20260101", "duration": dur, "views_per_day": vpd,
            "tags": list(tags), "url": f"u{i}", "is_short": dur <= 60}


def test_trends_analysis():
    vids = [_v(1, "7 Mistakes Every Beginner Makes", 900, 480, ["motion", "after effects"]), _v(2, "How to Animate Logos in 10 Minutes", 500, 600, ["motion"]),
            _v(3, "Why is Motion Design so hard?", 300, 300), _v(4, "Stop Doing THIS", 100, 50)]
    p = trends.title_patterns([v["title"] for v in vids])
    assert p["pct_number"] == 50 and p["pct_question"] >= 50 and p["pct_caps_word"] == 25
    names = [f["formula"] for f in trends.detect_formulas(vids)]
    assert "number-list" in names and "how-to" in names
    kws, tags = trends.keywords_and_tags(vids, "motion design")
    assert tags[0] == "motion design" and len(tags) <= 15 and "motion" in tags
    ht = trends.make_hashtags("motion design", kws)
    assert 3 <= len(ht) <= 5 and all(h.startswith("#") for h in ht)


def test_trends_end_to_end_mocked(monkeypatch, proj):
    vids = [_v(i, f"{i} tips for motion design", 1000 - i * 10, 120 + i) for i in range(12)]
    monkeypatch.setattr(youtube, "search", lambda q, n=20, recent_days=None: vids if recent_days else vids[:6])
    monkeypatch.setattr(youtube, "suggest", lambda q: ["motion design tutorial"])
    monkeypatch.setattr(youtube, "most_popular", lambda r, n=25, category=None: [])
    monkeypatch.setattr(youtube, "subs", lambda url, lang="en": {"hook": "Here is the hook."})
    d = trends.trends(proj, "motion design")
    assert (proj / "research" / "trends.json").exists() and (proj / "research" / "trends.md").exists()
    assert len(d["top10"]) == 10 and d["top10"][0]["hook"] == "Here is the hook." and d["top10"][9]["hook"] == ""
    assert len(d["recommendations"]["tags"]) <= 15 and "Recommendations" in (proj / "research" / "trends.md").read_text(encoding="utf-8")


# ------------------------------------------------------------------ assets
def test_openverse_filters_licences(monkeypatch):
    mock_urlopen(monkeypatch, {"openverse": {"results": [
        {"id": "a", "title": "Brain", "url": "https://x/a.jpg", "thumbnail": "t", "license": "cc0", "license_version": "1.0", "creator": "Z", "foreign_landing_url": "l"},
        {"id": "b", "title": "NC", "url": "https://x/b.jpg", "license": "by-nc", "license_version": "4.0"},
        {"id": "c", "title": "ND", "url": "https://x/c.jpg", "license": "by-nd", "license_version": "4.0"},
        {"id": "d", "title": "BY", "url": "https://x/d.jpg", "license": "by", "license_version": "4.0", "creator": "Q"}]}})
    res = assets.search_providers("brain", "photo", ["openverse"], 10)
    assert [r["id"] for r in res] == ["openverse-a", "openverse-d"]
    assert not res[0]["attribution_required"] and res[1]["attribution_required"] and res[1]["license"] == "CC BY 4.0"
    assert "_ok" not in res[0]


def test_wikimedia_drops_nc_nd(monkeypatch):
    def page(i, lic):
        return {"pageid": i, "title": f"File:{i}.jpg", "index": i, "imageinfo": [{"url": f"https://u/{i}.jpg", "mime": "image/jpeg", "descriptionurl": "d", "width": 9, "height": 9,
                "extmetadata": {"LicenseShortName": {"value": lic}, "LicenseUrl": {"value": ""}, "Artist": {"value": "<b>Bob</b>"}}}]}
    mock_urlopen(monkeypatch, {"commons.wikimedia": {"query": {"pages": {"1": page(1, "CC BY-SA 4.0"), "2": page(2, "CC BY-NC 2.0"), "3": page(3, "CC0"), "4": page(4, "CC BY-ND 2.0"), "5": page(5, "Public domain")}}}})
    res = assets.search_providers("x", "photo", ["wikimedia"], 10)
    assert [r["id"] for r in res] == ["wikimedia-1", "wikimedia-3", "wikimedia-5"]
    assert res[0]["author"] == "Bob"


def test_keyed_providers_skip_without_key(monkeypatch, capsys):
    for k in ("PEXELS_API_KEY", "PIXABAY_API_KEY", "FREESOUND_API_KEY"):
        monkeypatch.setenv(k, "")
    monkeypatch.setattr(assets, "secret", lambda n, p=None: "")
    assert assets.search_providers("x", "photo", ["pexels", "pixabay"], 3) == []
    assert "PEXELS_API_KEY not set" in capsys.readouterr().out


def test_pexels_and_freesound_mapping(monkeypatch):
    monkeypatch.setattr(assets, "secret", lambda n, p=None: "K")
    mock_urlopen(monkeypatch, {
        "videos/search": {"videos": [{"id": 7, "url": "pu", "image": "img", "duration": 9, "user": {"name": "U", "url": "uu"},
                                      "video_files": [{"file_type": "video/mp4", "width": 640, "height": 360, "link": "lo"}, {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "hd"}]}]},
        "freesound.org": {"results": [{"id": 5, "name": "whoosh", "previews": {"preview-hq-mp3": "https://f/5.mp3"}, "username": "me", "duration": 1.2}]}})
    v = assets.search_providers("x", "video", ["pexels"], 3)[0]
    assert v["download_url"] == "hd" and v["license"] == "Pexels License" and not v["attribution_required"]
    s = assets.search_providers("whoosh", "sfx", ["freesound"], 3)[0]
    assert s["download_url"].endswith("5.mp3") and s["license"] == "CC0"


def test_search_get_credits_dedupe(monkeypatch, proj):
    mock_urlopen(monkeypatch, {
        "openverse": {"results": [{"id": "a", "title": "Brain", "url": "https://x/a.jpg", "thumbnail": "https://x/t.jpg", "license": "by", "license_version": "4.0",
                                   "creator": "Zed", "license_url": "https://creativecommons.org/licenses/by/4.0/", "foreign_landing_url": "https://src/a"}]},
        "x/t.jpg": b"thumb", "x/a.jpg": b"fullimage"})
    res = assets.search(proj, "brain", "photo", ["openverse"], 5)
    cand = proj / "assets" / "_candidates"
    assert (cand / "photo-brain.json").exists() and (cand / "openverse-a.jpg").read_bytes() == b"thumb"
    got = assets.get(proj, ["openverse-a"])
    assert got[0].read_bytes() == b"fullimage" and got[0].parent.name == "photo"
    assets.get(proj, ["openverse-a"])  # again: no duplicate ledger line
    ledger = json.loads((proj / "assets" / "credits.json").read_text(encoding="utf-8"))
    assert len(ledger) == 1 and ledger[0]["file"] == "assets/photo/openverse-a.jpg"
    txt = assets.credits_text(proj)
    assert "Zed" in txt and "CC BY 4.0" in txt and txt.startswith("Credits:")


def test_credits_cc0_goes_to_thanks(proj):
    fvnet.add_credit(proj, {"id": "pexels-1", "provider": "pexels", "title": "Sky", "url": "u", "author": "Ann", "license": "Pexels License", "attribution_required": False})
    assert fvnet.add_credit(proj, {"id": "pexels-1", "provider": "pexels"}) is False
    t = assets.credits_text(proj)
    assert t.startswith("Also thanks to:") and "Ann" in t


def test_cutout_refuses_bria_and_soft_fails(monkeypatch, tmp_path):
    with pytest.raises(FishError, match="non-commercial"):
        assets.cutout("a.png", "b.png", "bria-rmbg")
    import builtins
    real = builtins.__import__

    def no_rembg(name, *a, **k):
        if name == "rembg":
            raise ImportError
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_rembg)
    assert assets.cutout("a.png", tmp_path / "b.png") is None


def test_sfx_index_keywords(tmp_path):
    for n in ("click_001.ogg", "impactMetal_heavy_000.ogg", "drop_002.ogg", "maximize_003.ogg", "tick_001.ogg", "readme.txt"):
        (tmp_path / "pack").mkdir(exist_ok=True)
        (tmp_path / "pack" / n).write_bytes(b"x")
    idx = assets.build_sfx_index(tmp_path)
    assert "pack/click_001.ogg" in idx["click"] and "pack/impactMetal_heavy_000.ogg" in idx["impact"] and "pack/impactMetal_heavy_000.ogg" in idx["boom"]
    assert "pack/drop_002.ogg" in idx["pop"] and "pack/maximize_003.ogg" in idx["whoosh"] and set(idx) >= {"riser", "chime", "typing", "paper"}
    assert (tmp_path / "index.json").exists()


def test_sfx_pack_fails_soft(monkeypatch, tmp_path):
    mock_urlopen(monkeypatch, {})
    idx = assets.sfx_pack(tmp_path)  # every download fails -> empty index, no exception
    assert idx["click"] == []


def test_sfx_pack_extracts_cc0_zip(monkeypatch, tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("License.txt", "License: (Creative Commons Zero, CC0)")
        z.writestr("Audio/click_001.ogg", b"ogg")
    monkeypatch.setattr(assets, "KENNEY_PACKS", ["interface-sounds"])
    monkeypatch.setattr(assets, "_kenney_zip", lambda slug: buf.getvalue())
    idx = assets.sfx_pack(tmp_path)
    assert idx["click"] == ["interface-sounds/click_001.ogg"]


# ------------------------------------------------------------------ screenrec / prep_clip
def make_video(path: Path, secs=2, size="320x180", rate=30):
    subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate={rate}:duration={secs}",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


def test_import_meta_schema_matches_recorder(proj, tmp_path):
    mp4 = tmp_path / "t.mp4"
    make_video(mp4)
    meta = screenrec.import_video(proj, "shot1", mp4)
    d = proj / "build" / "cap" / "shot1"
    assert (d / "00000.jpg").exists() and (d / f"{meta['count'] - 1:05d}.jpg").exists()
    m = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    # recorder.mjs keys: id, fps, w, h, dpr, count, marks, frames, errors
    assert {"id", "fps", "w", "h", "dpr", "count", "marks", "frames", "errors"} <= set(m)
    assert m["id"] == "shot1" and m["fps"] == 30 and (m["w"], m["h"]) == (320, 180) and m["count"] == len(m["frames"]) in range(58, 62)
    assert set(m["frames"][0]) == {"x", "y", "d", "c", "k", "s"}


def test_import_with_cursor_json(proj, tmp_path):
    mp4 = tmp_path / "t.mp4"
    make_video(mp4)
    cj = tmp_path / "c.json"
    cj.write_text(json.dumps({"cursor": [{"t": 0, "x": 0, "y": 0}, {"t": 1, "x": 200, "y": 100, "c": 1, "d": 1}, {"t": 1.2, "x": 200, "y": 100, "d": 0}], "marks": {"m1": 1.0}}), encoding="utf-8")
    m = screenrec.import_video(proj, "s2", mp4, cj)
    assert m["marks"] == {"m1": 30}
    assert abs(m["frames"][15]["x"] - 100) < 8 and m["frames"][30]["c"] + m["frames"][29]["c"] >= 1
    assert sum(f["c"] for f in m["frames"]) == 1


def test_build_frames_scale_and_region():
    s = [{"t": 0, "x": 1000, "y": 500, "d": 0, "c": 0, "k": None}, {"t": 1, "x": 1100, "y": 600, "d": 1, "c": 1, "k": "ctrl+c"}]
    fr = screenrec.build_frames(s, 31, 30, (100, 100, 1920, 1080), 2, 960, 540)
    assert fr[0]["x"] == 450 and fr[0]["y"] == 200  # (1000-100)/2
    assert fr[30]["x"] == 500 and fr[30]["c"] == 1 and fr[30]["k"] == "ctrl+c" and fr[30]["d"] == 1
    assert all(0 <= f["x"] <= 960 for f in fr)


def test_key_name_privacy_only_named_keys():
    assert screenrec.key_name(0x43) == "c" and screenrec.key_name(0x70) == "f1" and screenrec.key_name(0x0D) == "enter"
    assert screenrec.parse_region("10,20,300,200") == (10, 20, 300, 200)
    with pytest.raises(FishError):
        screenrec.parse_region("1,2,3")


def test_prep_clip_layout(proj, tmp_path):
    mp4 = tmp_path / "t.mp4"
    make_video(mp4, secs=2, size="640x360")
    meta = assets.prep_clip(proj, mp4, "c1", start=0.5, dur=1, fps=10, width=320)
    d = proj / "build" / "clips" / "c1"
    assert (d / "f_00001.jpg").exists() and meta == json.loads((d / "meta.json").read_text(encoding="utf-8"))
    assert meta["frames"] in (10, 11) and meta["fps"] == 10 and (meta["W"], meta["H"]) == (320, 180) and "src" in meta
