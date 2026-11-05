"""Offline tests for the 2.3 tools: risk gate, memes, sounds, icons, QA and package credits, the meme scene.

The network is mocked the way test_tools.py does it. Nothing here needs a key or the internet."""
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest
import yaml

import assets
import fvnet
import icons
import memes
import package
import qa
import sfx
import sounds
import storyboard
from fvcore import FishError, ffmpeg_bin, load_json
from test_tools import mock_urlopen

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def proj(tmp_path):
    (tmp_path / "brief.yaml").write_text("title: t\n", encoding="utf-8")
    return tmp_path


def set_policy(proj, policy):
    (proj / "brief.yaml").write_text(yaml.safe_dump({"title": "t", "memes": {"policy": policy}}), encoding="utf-8")


def ff(*args):
    subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def wav_stats(path):
    w = wave.open(str(path))
    a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, 2) / 32768.0
    return w.getnframes() / w.getframerate(), float(np.abs(a).max()), float(np.sqrt((a ** 2).mean())), a


# ------------------------------------------------------------------ fvnet: safety helpers
def test_http_only_and_safe_name():
    for bad in ("file:///etc/passwd", "ftp://x/y", "javascript:alert(1)"):
        with pytest.raises(fvnet.NetError):
            fvnet.http_only(bad)
    assert fvnet.http_only("https://a.example/x") == "https://a.example/x"
    n = fvnet.safe_name("../../etc/passwd")
    assert "/" not in n and ".." not in n and not n.startswith(".")
    assert fvnet.safe_name("") == "x" and len(fvnet.safe_name("a" * 500)) <= 80


def test_download_caps_and_content_type(monkeypatch, tmp_path):
    mock_urlopen(monkeypatch, {"big": b"x" * 5000, "ok": b"fine"})
    with pytest.raises(fvnet.NetError, match="cap"):
        fvnet.download_file("https://h.example/big", tmp_path / "a.bin", max_bytes=1000)
    assert not list(tmp_path.glob("a.bin*"))            # no half file left behind
    assert fvnet.download_file("https://h.example/ok", tmp_path / "b.bin", max_bytes=1000).read_bytes() == b"fine"
    with pytest.raises(fvnet.NetError):
        fvnet.download_file("file:///etc/hostname", tmp_path / "c.bin")


def test_download_refuses_wrong_content_type(monkeypatch, tmp_path):
    import urllib.request
    from test_tools import FakeResp

    class Typed(FakeResp):
        headers = {"Content-Type": "text/html; charset=utf-8"}

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: Typed(b"<html>"))
    with pytest.raises(fvnet.NetError, match="content type"):
        fvnet.download_file("https://h.example/p.png", tmp_path / "p.png", types=("image/",))


EVIL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10" onload="alert(1)">
<script>alert(1)</script><foreignObject><div>x</div></foreignObject><a xlink:href="https://evil.example"><g/></a><circle cx="5" cy="5" r="4" onclick="x()" fill="url(https://evil.example/f)"/>
<image href="https://evil.example/t.png"/><use xlink:href="https://evil.example/x.svg#a"/><use href="#ok"/><style>@import url(https://evil.example/c.css)</style>
<rect width="3" height="3" style="fill:url(http://evil.example)" fill="red"/><animate attributeName="x"/><path d="M0 0L5 5" fill="javascript:1"/></svg>"""


def test_sanitize_svg_strips_everything_active():
    out = fvnet.sanitize_svg(EVIL_SVG)
    low = out.lower()
    for bad in ("script", "foreignobject", "onload", "onclick", "evil.example", "javascript", "<image", "<style", "animate", "<a "):
        assert bad not in low, bad
    assert "<circle" in out and "<rect" in out and "<path" in out and 'href="#ok"' in out
    assert low.count("<use") == 1                        # the one that points inside the file stays; the external one is gone


def test_sanitize_svg_refuses_doctype_entities_and_junk():
    for bad in ('<!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>', "<svg", "<html></html>", "x" * (600 * 1024)):
        with pytest.raises(FishError):
            fvnet.sanitize_svg(bad)


# ------------------------------------------------------------------ the risk gate
def test_risk_default_is_safe_so_old_ledgers_behave_as_before(proj):
    assert fvnet.risk_of({"license": "CC BY 4.0"}) == "safe" and fvnet.risk_of({"risk": "nonsense"}) == "safe"
    fvnet.add_credit(proj, {"id": "old-1", "provider": "pexels", "title": "Sky", "author": "Ann", "license": "Pexels License"})
    assert fvnet.risky(proj) == [] and qa.asset_licences(proj)["status"] == "PASS"
    assert "LICENCE NOT VERIFIED" not in fvnet.credits_text(proj)


def test_gate_refuses_by_default_and_opens_with_policy_or_flag(proj):
    rec = {"id": "imgflip-1", "risk": "unverified"}
    with pytest.raises(FishError, match="not verified"):
        fvnet.check_risk(proj, rec)
    fvnet.check_risk(proj, rec, accept_risk=True)
    fvnet.check_risk(proj, {"id": "x", "risk": "platform"})   # platform is allowed (it shows in QA)
    set_policy(proj, "none")
    with pytest.raises(FishError):
        fvnet.check_risk(proj, rec)
    set_policy(proj, "viral")
    fvnet.check_risk(proj, rec)
    assert fvnet.memes_policy(proj) == "viral" and fvnet.memes_policy(proj / "missing") == "safe"


def test_claim_license():
    assert fvnet.claim_license(None, "CC BY 4.0")[0] == "safe"
    assert fvnet.claim_license("x", "All rights reserved")[0] == "unverified"
    assert fvnet.claim_license("own", None)[0] == "safe"
    assert fvnet.claim_license("myinstants", None) == ("unverified", "No licence evidence", "", False)


IMGFLIP = {"success": True, "data": {"memes": [
    {"id": "181913649", "name": "Drake Hotline Bling", "url": "https://i.imgflip.com/30b1gx.jpg", "width": 1200, "height": 1200, "box_count": 2, "captions": 1500000},
    {"id": "87743020", "name": "Two Buttons", "url": "https://i.imgflip.com/1g8my4.jpg", "width": 600, "height": 908, "box_count": 3, "captions": 1200000}]}}


def test_non_safe_download_refuses_then_proceeds_with_opt_in_and_shows_in_qa_and_credits(monkeypatch, proj):
    mock_urlopen(monkeypatch, {"api.imgflip.com": IMGFLIP, "i.imgflip.com": b"\xff\xd8jpegbytes"})
    res = memes.templates(proj, "drake")
    assert len(res) == 1 and res[0]["risk"] == "unverified" and res[0]["id"] == "imgflip-181913649"
    # default project: refused, nothing downloaded, nothing credited
    assert assets.get(proj, ["imgflip-181913649"]) == []
    assert fvnet.load_credits(proj) == [] and not list((proj / "assets").glob("meme/*"))
    # opt in with the flag
    got = assets.get(proj, ["imgflip-181913649"], accept_risk=True)
    assert got and got[0].read_bytes().startswith(b"\xff\xd8")
    led = fvnet.load_credits(proj)
    assert led[0]["risk"] == "unverified" and led[0]["provider"] == "imgflip"
    # QA warns and names it; the credits put it under its own heading
    chk = qa.asset_licences(proj)
    assert chk["status"] == "WARN" and "Drake Hotline Bling" in chk["detail"] and "unverified" in chk["detail"]
    txt = fvnet.credits_text(proj)
    assert "LICENCE NOT VERIFIED" in txt and "Drake Hotline Bling" in txt
    ptxt = package.credits_text(proj, {"provider": "none"}, "synth")
    assert "LICENCE NOT VERIFIED" in ptxt and ptxt.index("LICENCE NOT VERIFIED") < ptxt.index("Music:") and "Drake" in ptxt


def test_project_policy_viral_downloads_without_flag(monkeypatch, proj):
    set_policy(proj, "viral")
    mock_urlopen(monkeypatch, {"api.imgflip.com": IMGFLIP, "i.imgflip.com": b"\xff\xd8x"})
    memes.templates(proj, "two buttons")
    assert assets.get(proj, ["imgflip-87743020"])


def test_package_credits_unchanged_for_safe_only_ledger(proj):
    fvnet.add_credit(proj, {"id": "a", "provider": "pexels", "title": "Sky", "author": "Ann", "license": "Pexels License", "url": "u"})
    t = package.credits_text(proj, {"provider": "none"}, "synth")
    assert t.splitlines()[:2] == ["CREDITS", '- "Sky" by Ann (pexels), licence: Pexels License u'] and "NOT VERIFIED" not in t


def test_credits_dedupe_identical_lines(proj):
    for i in (1, 2):
        fvnet.add_credit(proj, {"id": f"w{i}", "provider": "wikimedia", "title": "Film", "author": "A", "license": "Public Domain", "url": "u"})
    assert fvnet.credits_text(proj).count("Film") == 1


# ------------------------------------------------------------------ memes
def test_imgflip_templates_use_key_only_in_a_header(monkeypatch, proj):
    seen = []
    monkeypatch.setenv("IMGFLIP_API_KEY", "SECRETKEY")
    monkeypatch.setattr(memes, "secret", lambda n, p=None: "SECRETKEY")
    mock_urlopen(monkeypatch, {"search_memes": IMGFLIP}, seen)
    assert memes.template_search("drake")
    url, hdrs, _ = seen[0]
    assert "SECRETKEY" not in url and hdrs["Authorization"] == "Bearer SECRETKEY"


def test_imgflip_without_key_filters_the_public_list_and_hints(monkeypatch, proj, capsys):
    monkeypatch.setattr(memes, "secret", lambda n, p=None: "")
    mock_urlopen(monkeypatch, {"get_memes": IMGFLIP})
    assert [r["title"] for r in memes.templates(proj, "button")] == ["Two Buttons"]
    assert memes.templates(proj, "kabhi khushi kabhie gham") == []
    assert "IMGFLIP_API_KEY" in capsys.readouterr().out


def test_films_wikimedia_and_archive_with_region_and_year(monkeypatch, proj):
    seen = []
    mock_urlopen(monkeypatch, {
        "commons.wikimedia": {"query": {"pages": {"1": {"pageid": 1, "title": "File:Old.webm", "index": 1, "videoinfo": [{"url": "https://u/old.webm", "mime": "video/webm", "mediatype": "VIDEO", "descriptionurl": "d", "width": 320,
                              "height": 240, "duration": 10, "extmetadata": {"LicenseShortName": {"value": "Public domain"}, "Artist": {"value": "Bob"}, "DateTimeOriginal": {"value": "1914-02-02"}}}]}}}},
        "advancedsearch": {"response": {"docs": [
            {"identifier": "pd1", "title": "Open film", "year": "1955", "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/", "creator": "Raj"},
            {"identifier": "nolic", "title": "Unknown film", "year": "1950"},
            {"identifier": "nc", "title": "NC film", "licenseurl": "https://creativecommons.org/licenses/by-nc/4.0/"}]}}}, seen)
    res = memes.films(proj, "comedy", region="in", before=1960)
    ids = {r["id"]: r for r in res}
    assert ids["wikimedia-1"]["risk"] == "safe" and ids["archive-pd1"]["risk"] == "safe"
    assert "archive-nolic" not in ids, "unverified results stay hidden in a licence-safe project"
    assert "archive-nc" not in ids
    q = next(u for u, *_ in seen if "advancedsearch" in u)
    assert "1959" in q and "language" in q
    res = memes.films(proj, "comedy", region="in", before=1960, unverified=True)
    assert {r["id"]: r for r in res}["archive-nolic"]["risk"] == "unverified"
    with pytest.raises(FishError):
        memes.films(proj, "x", region="zz")


def make_video(path, secs=4, size="320x180"):
    ff("-f", "lavfi", "-i", f"testsrc=duration={secs}:size={size}:rate=10", "-f", "lavfi", "-i", "sine=frequency=440:duration=%d" % secs, "-shortest", "-pix_fmt", "yuv420p", str(path))
    return path


def test_sheet_cut_and_lint_chain(proj, tmp_path):
    from PIL import Image
    v = make_video(tmp_path / "in.mp4")
    sheet = memes.sheet(v, tmp_path / "s.png", every=1.0, cols=4, width=160)
    assert Image.open(sheet).width >= 160 * 4 - 4
    # a clip cut from an unlicensed file: refused, then allowed with the flag, sound dropped, licence carried
    with pytest.raises(FishError, match="not verified"):
        memes.cut(proj, v, "c1", start=1, dur=1)
    meta = memes.cut(proj, v, "c1", start=1, dur=1, source="myinstants-film", accept_risk=True)
    assert meta["frames"] >= 20 and meta["audio"] == "dropped" and meta["risk"] == "unverified"
    cl = [c for c in fvnet.load_credits(proj) if c["id"] == "clip-c1"][0]
    assert cl["risk"] == "unverified" and cl["file"] == "build/clips/c1"
    sb = {"scenes": [{"id": "m1", "type": "meme", "params": {"clip": "c1"}}, {"id": "m2", "type": "meme", "params": {"clip": "ghost"}},
                     {"id": "m3", "type": "meme", "params": {"src": "assets/meme/none.png"}}, {"id": "m4", "type": "meme", "params": {}}]}
    (proj / "storyboard.yaml").write_text(yaml.safe_dump(sb), encoding="utf-8")
    found = memes.lint(proj)
    msgs = " | ".join(f"{f['scene']}:{f['level']}:{f['msg']}" for f in found)
    assert "m2:FAIL" in msgs and "m3:FAIL" in msgs and "m4:FAIL" in msgs and "m1:FAIL" not in msgs
    set_policy(proj, "none")
    assert any(f["level"] == "WARN" and "no memes" in f["msg"] for f in memes.lint(proj))
    chk = qa.meme_checks(proj)[0]
    assert chk["status"] == "FAIL" and chk["check"] == "meme lint"


def test_cut_keeps_a_cut_from_a_downloaded_file_safe(monkeypatch, proj, tmp_path):
    v = make_video(tmp_path / "x.mp4")
    dst = proj / "assets" / "video" / "wikimedia-9.mp4"
    dst.parent.mkdir(parents=True)
    dst.write_bytes(v.read_bytes())
    fvnet.add_credit(proj, {"id": "wikimedia-9", "provider": "wikimedia", "title": "Old film", "author": "A", "license": "Public Domain", "risk": "safe", "file": "assets/video/wikimedia-9.mp4"})
    meta = memes.cut(proj, dst, "c2", start=0, dur=1)
    assert meta["risk"] == "safe" and meta["credit"] == "clip-c2"


def test_memes_add_the_manual_route(proj, tmp_path):
    from PIL import Image
    img = tmp_path / "m.png"
    Image.new("RGB", (40, 30), "red").save(img)
    with pytest.raises(FishError, match="not verified"):
        memes.add(proj, str(img), title="Hit", source="vlipsy", source_url="https://vlipsy.com/x")
    dest = memes.add(proj, str(img), title="Hit", source="vlipsy", source_url="https://vlipsy.com/x", accept_risk=True)
    rec = fvnet.load_credits(proj)[0]
    assert dest.parent.name == "meme" and rec["url"] == "https://vlipsy.com/x" and rec["risk"] == "unverified"
    with pytest.raises(FishError, match="image or a video"):
        memes.add(proj, str(tmp_path / "s.mp3"), title="x", accept_risk=True)
    # own work and a stated open licence are safe
    assert memes.add(proj, str(img), title="Mine", source="own", name="mine") and fvnet.load_credits(proj)[-1]["risk"] == "safe"
    memes.add(proj, str(img), title="Free", license="CC BY 4.0", author="Z", name="free")
    assert fvnet.load_credits(proj)[-1]["attribution_required"] is True
    # a hostile name cannot leave assets/meme
    d = memes.add(proj, str(img), title="x", source="own", name="../../evil")
    assert d.resolve().parent == (proj / "assets" / "meme").resolve()


def test_memes_add_refuses_non_http_url(proj):
    with pytest.raises(FishError):
        memes.add(proj, "file:///etc/passwd.png", title="x", source="own")


@pytest.mark.skipif(not Path("/usr/bin/google-chrome").exists() and not __import__("os").environ.get("CHROME"), reason="needs Chrome")
def test_caption_renders_latin_and_devanagari_and_escapes_markup(tmp_path):
    from PIL import Image
    src = tmp_path / "b.png"
    Image.new("RGB", (400, 300), (60, 60, 60)).save(src)
    out = memes.caption(src, tmp_path / "o.png", top="<b>HELLO</b> & co", bottom="नमस्ते दुनिया", width=600)
    a = np.asarray(Image.open(out).convert("L"))
    assert a.shape[1] == 600 and (a > 230).sum() > 500, "white caption pixels expected"
    assert (a[: a.shape[0] // 3] > 230).any() and (a[-a.shape[0] // 3:] > 230).any()
    with pytest.raises(FishError):
        memes.caption(src, tmp_path / "o2.png")


def test_meme_html_escapes_caption_text():
    node = subprocess.run(["node", "-e", """import('./scripts/memecap.mjs').then(m => console.log(m.captionHtml({img:'/x.png', top:'<img src=x onerror=1>', bottom:'"q"'})))"""],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "<img src=x" not in node and "&lt;img src=x onerror=1&gt;" in node


# ------------------------------------------------------------------ sounds
def test_every_synth_type_renders_audible_unclipped_and_finite():
    assert len(sounds.SYNTH) == 17
    for name in sounds.SYNTH:
        a = sounds.render(name)
        assert a.ndim == 2 and a.shape[1] == 2 and np.isfinite(a).all(), name
        pk = float(np.abs(a).max())
        assert 0.85 < pk <= 0.9 + 1e-3, (name, pk)                          # peak near -1 dBFS, never clipped
        assert 0.3 < len(a) / sounds.SR < 4.0, name
        assert float(np.sqrt((a ** 2).mean())) > 0.01, f"{name} is nearly silent"


def test_synth_names_do_not_claim_trademarks():
    for banned in ("wilhelm", "vine", "tiktok", "mario", "nokia", "windows", "intel", "netflix", "taco", "duolingo", "tudum"):
        assert not any(banned in n for n in sounds.SYNTH), banned


def test_synth_writes_wavs_levels_and_a_safe_credit_and_skips_what_exists(proj):
    files = sounds.synth(proj, ["rimshot", "sting"])
    assert {f.parent.name for f in files} == {"rimshot", "sting"}
    assert load_json(proj / "assets" / "sfx" / "pack.json")["levels"]["sting"] == sounds.SYNTH["sting"][1]
    c = fvnet.load_credits(proj)[0]
    assert c["risk"] == "safe" and c["license"] == "CC0" and c["provider"] == "synth"
    again = sounds.synth(proj)                                              # the others only; the two present are skipped
    assert {f.parent.name for f in again} == set(sounds.SYNTH) - {"rimshot", "sting"} or {f.parent.name for f in again} >= {"airhorn"}
    assert "rimshot" not in {f.parent.name for f in again}
    with pytest.raises(FishError):
        sounds.synth(proj, ["nope"])


def test_sounds_add_trims_levels_gate_and_pack_json(proj, tmp_path):
    src = tmp_path / "in.wav"
    sounds.write_wav(src, np.concatenate([np.zeros((24000, 2)), 0.5 * np.sin(np.linspace(0, 400, 48000))[:, None].repeat(2, 1), np.zeros((24000, 2))]))
    with pytest.raises(FishError, match="not verified"):
        sounds.add(proj, src, "hit1", source="myinstants", source_url="https://www.myinstants.com/en/instant/x/")
    out = sounds.add(proj, src, "hit1", source="myinstants", source_url="https://www.myinstants.com/en/instant/x/", level=-12, accept_risk=True)
    dur, pk, _, a = wav_stats(out)
    assert 0.9 < dur < 1.2, "silence around the hit is trimmed"
    assert 0.85 < pk <= 0.9 + 1e-3 and abs(a[0]).max() < 0.05 and abs(a[-1]).max() < 0.05
    assert sfx.levels(proj)["hit1"] == -12.0 and sfx.library(proj)["hit1"]
    rec = fvnet.load_credits(proj)[0]
    assert rec["risk"] == "unverified" and rec["url"].startswith("https://www.myinstants.com")
    for bad in ("../x", "a b", "a/b"):
        with pytest.raises(FishError):
            sounds.add(proj, src, bad, source="own")
    with pytest.raises(FishError):
        sounds.add(proj, tmp_path / "missing.wav", "ok", source="own")
    sounds.add(proj, src, "hit2", source="own", start=0.5, dur=0.4)
    assert wav_stats(proj / "assets" / "sfx" / "hit2" / "in.wav")[0] < 0.5


def test_sfx_levels_precedence_and_pack_library(proj, tmp_path, monkeypatch):
    lib = tmp_path / "skill" / "sfx" / "library"
    (lib / "pk").mkdir(parents=True)
    sounds.write_wav(lib / "pk" / "a.wav", np.ones((4800, 2)) * 0.3)
    (lib / "pk" / "pack.json").write_text(json.dumps({"cues": {"zap2": ["a.wav", "missing.wav"]}, "levels": {"zap2": -9, "swish": -10}}), encoding="utf-8")
    monkeypatch.setattr(sfx, "SKILL", tmp_path / "skill")
    assert sfx.levels(proj)["swish"] == -10 and sfx.levels(proj)["zap2"] == -9       # the pack beats the built-in table
    assert [p.name for p in sfx.library(proj)["zap2"]] == ["a.wav"]
    sounds.set_level(proj, "swish", -11)
    assert sfx.levels(proj)["swish"] == -11                                           # the project's pack.json beats the pack
    (proj / "brief.yaml").write_text(yaml.safe_dump({"title": "t", "mix": {"sfx_levels": {"swish": -12}}}), encoding="utf-8")
    assert sfx.levels(proj)["swish"] == -12                                           # the brief wins


def test_sfx_index_skips_committed_packs(tmp_path):
    (tmp_path / "meme").mkdir()
    (tmp_path / "meme" / "pack.json").write_text("{}", encoding="utf-8")
    (tmp_path / "meme" / "whoosh-big.ogg").write_bytes(b"x")
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "whoosh-small.ogg").write_bytes(b"x")
    idx = assets.build_sfx_index(tmp_path)
    assert idx["whoosh"] == ["ui/whoosh-small.ogg"]


def test_audition_writes_montage_and_index(proj):
    sounds.synth(proj, ["rimshot", "ding"])
    out = sounds.audition(proj, proj / "a.wav")
    assert out.exists() and "rimshot" in out.with_suffix(".txt").read_text(encoding="utf-8")
    dur, pk, *_ = wav_stats(out)
    assert dur > 2 and pk <= 1.0


def test_sounds_search_reads_commons_audio_and_drops_midi(monkeypatch, proj):
    def page(i, name, mime, lic):
        return {"pageid": i, "title": f"File:{name}", "index": i, "videoinfo": [{"url": f"https://u/{name}", "mime": mime, "mediatype": "AUDIO", "descriptionurl": "d", "duration": 2,
                "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": "Ann"}}}]}
    mock_urlopen(monkeypatch, {"commons.wikimedia": {"query": {"pages": {"1": page(1, "a.ogg", "application/ogg", "CC0"), "2": page(2, "b.mid", "audio/midi", "CC0"), "3": page(3, "c.ogg", "application/ogg", "CC BY-NC 4.0")}}}})
    res = assets.search_providers("laugh", "sfx", ["wikimedia"], 10)
    assert [r["id"] for r in res] == ["wikimedia-1"]


# ------------------------------------------------------------------ icons and logos
SI_DATA = {"icons": [{"title": "Python", "slug": "python", "hex": "3776AB", "source": "https://www.python.org/community/logos/", "license": {"type": "CC0-1.0"}}]}


def test_logo_icon_emoji_sanitise_and_credit(monkeypatch, proj):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><script>1</script><path d="M0 0h24v24z" onclick="x()"/></svg>'
    mock_urlopen(monkeypatch, {"simple-icons.json": SI_DATA, "icons/python.svg": svg.encode(), "api.iconify.design/search": {"icons": ["ic:round-rocket", "bad:rocket"],
              "collections": {"ic": {"name": "Material Icons", "license": {"spdx": "Apache-2.0", "title": "Apache 2.0", "url": "u"}, "author": {"name": "G"}},
                              "bad": {"name": "Bad", "license": {"spdx": "CC-BY-NC-4.0", "title": "NC"}}}},
              "api.iconify.design/collections": {"ic": {"name": "Material Icons", "license": {"spdx": "Apache-2.0", "title": "Apache 2.0", "url": "u"}, "author": {"name": "G"}},
                                                 "bad": {"name": "Bad", "license": {"spdx": "CC-BY-NC-4.0", "title": "NC"}}},
              "api.iconify.design/ic/round-rocket.svg": svg.encode(), "api.iconify.design/bad/": svg.encode(), "openmoji": svg.encode(), "twemoji": svg.encode()})
    p = icons.logo(proj, "python")
    body = p.read_text(encoding="utf-8")
    assert "script" not in body and "onclick" not in body and p.parent.name == "icons"
    assert icons.icon(proj, "rocket", n=5)[0]["id"] == "ic:round-rocket"
    assert [r["id"] for r in icons.icon(proj, "rocket", n=5)] == ["ic:round-rocket"]      # the non-commercial set is filtered out
    assert icons.icon(proj, "ic:round-rocket").exists()
    with pytest.raises(FishError, match="not on the open list"):
        icons.icon(proj, "bad:rocket")
    assert icons.emoji(proj, "😂").name == "emoji-openmoji-1f602.svg"
    assert icons.emoji(proj, "face with tears of joy", "twemoji").exists()
    with pytest.raises(FishError):
        icons.logo(proj, "zzz no such brand")
    ids = {c["id"]: c for c in fvnet.load_credits(proj)}
    assert ids["simpleicons-python"]["risk"] == "safe" and ids["openmoji-1f602"]["license"] == "CC BY-SA 4.0" and ids["openmoji-1f602"]["attribution_required"]


def test_emoji_codes():
    assert icons.emoji_codes("😂") == [0x1F602] and icons.emoji_codes("FACE WITH TEARS OF JOY") == [0x1F602]
    with pytest.raises(FishError):
        icons.emoji_codes("   ")


@pytest.mark.skipif(not Path("/usr/bin/google-chrome").exists() and not __import__("os").environ.get("CHROME"), reason="needs Chrome")
def test_shot_is_credited_as_platform_tier(proj, tmp_path):
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "index.html").write_text("<html><body style='background:#eee'><div id=cookie class='cookie-banner'>cookies</div><h1>Hello</h1></body></html>", encoding="utf-8")
    import http.server
    import threading
    import functools
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path / "site")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        out = assets.shot(proj, [f"http://127.0.0.1:{srv.server_port}/"], width=640, height=360)
    finally:
        srv.shutdown()
    rec = fvnet.load_credits(proj)[0]
    assert out and rec["risk"] == "platform" and rec["provider"] == "screenshot"
    assert qa.asset_licences(proj)["status"] == "WARN" and "Shown under the source's own terms" in fvnet.credits_text(proj)


# ------------------------------------------------------------------ QA, interview, storyboard, scene
def test_cue_sounds_check_flags_silent_types(proj, tmp_path):
    assert "swish" in qa.synth_cue_types() and "typing" in qa.synth_cue_types()
    sb = {"scenes": [{"id": "a", "cues": [{"type": "swish"}, {"type": "airhorn"}]}]}
    r = qa.cue_sounds(proj, sb)
    assert r["status"] == "WARN" and "airhorn" in r["detail"] and "swish" not in r["detail"]
    sounds.synth(proj, ["airhorn"])
    assert qa.cue_sounds(proj, sb)["status"] == "PASS"


def test_interview_question_is_optional_and_defaults_to_safe():
    cfg = yaml.safe_load((ROOT / "config" / "interview.yaml").read_text(encoding="utf-8"))
    q = next(q for r in cfg["rounds"] for q in r["questions"] if q["id"] == "memes")
    assert q["required"] is False and q["maps_to"] == "memes.policy"
    assert [o["value"] for o in q["options"]] == ["safe", "none", "viral"] and "Recommended" in q["options"][0]["label"]


def test_meme_scene_validates_and_fills_clip_frames(proj):
    (proj / "build" / "clips" / "c").mkdir(parents=True)
    (proj / "build" / "clips" / "c" / "meta.json").write_text(json.dumps({"frames": 77, "fps": 24}), encoding="utf-8")
    p = storyboard._meme_params(proj, {"clip": "c", "inset": {"clip": "c", "pos": "tl"}, "fps": 30})
    assert p["frames"] == 77 and p["fps"] == 30 and p["inset"]["frames"] == 77      # an explicit value wins
    sb = {"scenes": [{"id": "a", "type": "meme", "params": {}}, {"id": "b", "type": "meme", "params": {"src": "../secret.png"}},
                     {"id": "c", "type": "meme", "params": {"src": "/etc/x.png"}}, {"id": "d", "type": "meme", "params": {"src": "assets/meme/ok.png"}}]}
    errs, _ = storyboard.validate(sb, None)
    assert len([e for e in errs if "meme" in e]) == 3 and not any("d:" in e or "scene d" in e for e in errs)


def test_meme_scene_is_a_pure_function_of_time():
    src = (ROOT / "scripts" / "stage" / "scenes" / "meme.js").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    for banned in ("Math.random", "Date.", "setTimeout", "setInterval", "requestAnimationFrame", "animation:", "@keyframes", "transition:", "innerHTML"):
        assert banned not in code, banned
    assert "meme.js" in (ROOT / "scripts" / "stage" / "index.html").read_text(encoding="utf-8")
    assert "meme" in storyboard.SCENE_TYPES


def test_memes_yaml_has_the_named_sources_and_only_manual_routes_for_blocked_ones():
    cfg = yaml.safe_load((ROOT / "config" / "memes.yaml").read_text(encoding="utf-8"))
    by = {s["id"]: s for s in cfg["sources"]}
    assert {"imgflip", "vlipsy", "myinstants", "memeinstants"} <= set(by)
    assert by["imgflip"]["access"] == "api" and by["vlipsy"]["access"] != "api"
    assert by["myinstants"]["access"] == "manual" and by["memeinstants"]["access"] == "manual"
    assert all(s["risk"] == "unverified" for s in cfg["sources"] if s["id"] in ("imgflip", "vlipsy", "myinstants", "memeinstants"))
    assert not any(k in json.dumps(cfg).lower() for k in ("giphy.com/v1", "api.tenor", "reddit.com/r/"))
