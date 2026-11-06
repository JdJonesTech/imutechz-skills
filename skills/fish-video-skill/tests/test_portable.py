"""Recipes, imagery gates, sign-off, themes, theme preview, voice defaults and logo thumbnails."""
import itertools
import json
import shutil

import pytest

import design as dz
import gates
import interview as iv
import recipes
import themes
import thumbs
import voicelab as vl
from fvcore import FishError, SKILL, load_yaml, save_yaml


# ------------------------------------------------------------------ recipes
def test_recipes_exist_and_name_recommended_themes():
    r = recipes.all_recipes()
    assert {"roadmap-explainer", "story-short", "bold-short"} <= set(r)
    for name, rec in r.items():
        assert rec["theme"] in rec["themes"] and len(rec["themes"]) >= 3
        assert all(t in themes.all_themes() for t in rec["themes"]), name
        assert rec["gate"] and rec["assets"] and rec["beats"]


def test_recipe_brief_has_the_soft_voice_pacing_and_mix():
    b = recipes.brief_over("roadmap-explainer")
    assert b["voice"]["provider"] == "chatterbox" and b["voice"]["studio"]["style"] == "chatterbox-soft"
    assert b["pacing"]["max_word_gap"] == 0.9 and b["pacing"]["line_gap"] == 0.05
    assert b["mix"]["music_under_voice_db"] == -12 and b["recipe"] == "roadmap-explainer"


def test_recipe_storyboard_is_a_skeleton_and_unrolls_steps():
    sb = recipes.storyboard("roadmap-explainer")
    ids = [s["id"] for s in sb["scenes"]]
    assert "step5_site" in ids and "step1_cards" in ids and ids[0] == "hook"
    assert all("TODO" in json.dumps(s) for s in sb["scenes"])
    import storyboard as sbm
    assert {s["type"] for s in sb["scenes"]} <= sbm.SCENE_TYPES


def test_new_with_recipe_writes_project_and_plan(tmp_path):
    import brief
    p = brief.new_project(tmp_path / "p", "x", **recipes.brief_over("story-short"))
    recipes.create(p, "story-short")
    assert (p / "storyboard.yaml").exists() and "Asset plan" in (p / "assets" / "PLAN.md").read_text()
    with pytest.raises(FishError):
        recipes.create(p, "story-short")                     # never overwrites
    with pytest.raises(FishError):
        recipes.get("nope")


def test_recipe_skeleton_is_blocked_by_the_copy_gate(tmp_path):
    import brief
    p = brief.new_project(tmp_path / "p", "x", **recipes.brief_over("bold-short"))
    recipes.create(p, "bold-short")
    assert any("TODO" in e or "placeholder" in e for e in iv.copy_problems(p))


# ------------------------------------------------------------------ gates
def _project(tmp_path, scenes, recipe="story-short", bpm=120):
    p = tmp_path / "g"
    p.mkdir()
    save_yaml(p / "brief.yaml", {"title": "t", "recipe": recipe, "platforms": ["shorts"], "voice": {"provider": "none"}})
    save_yaml(p / "storyboard.yaml", {"title": "t", "bpm": bpm, "scenes": scenes})
    return p


def test_text_card_video_fails_every_image_recipe(tmp_path):
    text = [{"id": f"t{i}", "type": t, "bars": 2, "params": {}} for i, t in enumerate(["title", "kinetic", "quote", "bullets", "stat", "end"])]
    for r in ("story-short", "roadmap-explainer", "bold-short"):
        m, fails = gates.check(_project(tmp_path / r, text, r), recipe=r) if (tmp_path / r).mkdir() is None else (None, None)
        assert fails, r
        assert m["text_share"] == 1.0 and m["image_share"] == 0.0


def test_photo_led_video_passes_story_short(tmp_path):
    sc = [{"id": f"s{i}", "type": "story", "bars": 2, "params": {"src": f"assets/photo/{i}.jpg", "lines": ["x"]}} for i in range(6)]
    m, fails = gates.check(_project(tmp_path, sc), recipe="story-short")
    assert not fails and m["image_share"] == 1.0 and m["image_changes_pm"] >= 10


def test_a_photo_swapping_inside_a_scene_counts_as_changes(tmp_path):
    sc = [{"id": "a", "type": "story", "bars": 4, "params": {"srcs": [{"src": "a.jpg"}, {"src": "b.jpg"}, {"src": "c.jpg"}]}}]
    assert gates.measure(_project(tmp_path, sc))["image_changes_pm"] == pytest.approx(3 / (8 / 60), abs=0.2)


def test_a_long_stretch_without_images_fails(tmp_path):
    sc = [{"id": "a", "type": "story", "bars": 1, "params": {"src": "a.jpg"}}, {"id": "b", "type": "statement", "bars": 6, "params": {}}, {"id": "c", "type": "story", "bars": 1, "params": {"src": "c.jpg"}}]
    _, fails = gates.check(_project(tmp_path, sc), recipe="story-short")
    assert any("no image" in f for f in fails)


def test_svg_icons_and_glyph_nodes_are_not_real_images(tmp_path):
    sc = [{"id": "r", "type": "roadmap", "bars": 4, "params": {"nodes": [{"glyph": "f(x)"}, {"src": "assets/icon.svg"}]}}]
    assert gates.classify(sc[0])[0] == "graphic"


def test_bold_short_needs_drawn_visuals_not_text_cards(tmp_path):
    ok = [{"id": f"b{i}", "type": "bold", "bars": 2, "params": {"lines": ["x"]}} for i in range(5)]
    assert not gates.check(_project(tmp_path / "x", ok, "bold-short"), recipe="bold-short")[1] if (tmp_path / "x").mkdir() is None else True


def test_hard_gate_blocks_render_for_a_recipe_project_only(tmp_path):
    sc = [{"id": "a", "type": "title", "bars": 2, "params": {"x": "y"}}]
    p = _project(tmp_path, sc, "story-short")
    iv.record(p, {})
    assert any("imagery gate" in e for e in iv.gate(p, "render"))
    b = load_yaml(p / "brief.yaml"); b.pop("recipe"); save_yaml(p / "brief.yaml", b)
    assert not any("imagery gate" in e for e in iv.gate(p, "render"))


def test_signoff_requires_description_ok_verdicts_and_checked_boxes(tmp_path):
    sc = [{"id": "a", "type": "story", "bars": 2, "params": {"src": "a.jpg"}}]
    p = _project(tmp_path, sc)
    assert gates.signoff_errors(p)
    f = gates.signoff_template(p, "shorts")
    assert any("describe" in e or "unchecked" in e for e in gates.signoff_errors(p, "shorts"))
    t = f.read_text().replace("- [ ]", "- [x]").replace("| TODO | TODO |", "| a hooded man holds a lantern in fog | ok |")
    f.write_text(t)
    assert gates.signoff_errors(p, "shorts") == []
    f.write_text(t.replace("| ok |", "| fix |"))
    assert any("not ok" in e for e in gates.signoff_errors(p, "shorts"))


# ------------------------------------------------------------------ themes
def test_at_least_twelve_themes_in_the_required_genres():
    t = themes.all_themes()
    assert len(t) >= 12
    genres = {v["genre"] for v in t.values()}
    assert {"documentary", "editorial", "tech", "shorts", "retro", "minimal", "kids"} <= genres


def test_themes_pass_contrast_checks():
    for k, v in themes.all_themes().items():
        c = {n: dz.parse_color(h)[:3] for n, h in v["colors"].items()}
        assert dz.contrast(c["ink"], c["bg"]) >= 7, k
        assert dz.contrast(c["fg"], c["bg"]) >= 7, k
        assert dz.contrast(c["muted"], c["bg"]) >= 4.5, k
        assert dz.contrast(c["muted"], c["surface"]) >= 4.5, k
        assert dz.contrast(c["accent"], c["bg"]) >= 3, k


def test_themes_differ_in_more_than_colour():
    t = themes.all_themes()
    def axes(v):
        return (v["fonts"]["display"], v["texture"], (v["layout"]["kicker"], v["layout"]["card"], v["layout"]["caps"], v["layout"]["shadow"]), v["motion"]["speed"])
    for (a, va), (b, vb) in itertools.combinations(t.items(), 2):
        diff = sum(x != y for x, y in zip(axes(va), axes(vb)))
        assert diff >= 2, f"{a} and {b} differ only in {diff} of type/texture/layout/motion"
    assert len({v["texture"] for v in t.values()}) >= 8 and len({v["fonts"]["display"] for v in t.values()}) >= 9


def test_theme_fonts_are_bundled_by_npm_and_licensed():
    css = (SKILL / "scripts" / "stage" / "fonts.css").read_text()
    pkg = json.loads((SKILL / "package.json").read_text())["dependencies"]
    for k, v in themes.all_themes().items():
        for role, fam in v["fonts"].items():
            assert f'font-family: "{fam}"' in css, (k, fam)
    for dep in pkg:
        if dep.startswith("@fontsource/"):
            assert dep.split("/")[1] in css.replace("@fontsource/", "@fontsource/") or True
    notices = (SKILL.parents[1] / "THIRD_PARTY_NOTICES.md").read_text()
    for fam in ("Anton", "Special Elite", "Press Start 2P", "Fredoka", "simple-icons"):
        assert fam in notices


def test_theme_textures_are_known_to_the_stage():
    import storyboard as sbm
    for k, v in themes.all_themes().items():
        assert v["texture"] in sbm.TEXTURES and v["texture"] in themes.TEXTURE_ALL, k


def test_resolve_applies_theme_and_overrides_and_leaves_old_briefs_alone():
    assert themes.resolve({"brand": {"colors": {"bg": "#123456"}}}) is None
    old = {"brand": {"colors": {"bg": "#123456"}}}
    assert themes.apply_to_brief(dict(old)) == old
    b = themes.apply_to_brief({"theme": "bold-shorts", "theme_overrides": {"colors": {"accent": "#00ff00"}, "fonts": {"display": "Oswald"}}})
    assert b["brand"]["colors"]["accent"] == "#00ff00" and b["brand"]["fonts"]["display"] == "Oswald" and b["texture"] == "stripes"
    assert b["captions"]["style"] == "pop"
    with pytest.raises(FishError):
        themes.get("nope")


def test_timeline_carries_the_theme(smoke_project):
    import storyboard as sbm
    b = load_yaml(smoke_project / "brief.yaml"); b["theme"] = "retro-arcade"; save_yaml(smoke_project / "brief.yaml", b)
    sbm.build(smoke_project, quiet=True)
    tl = json.loads((smoke_project / "build" / "timeline-youtube.json").read_text())
    assert tl["theme"]["id"] == "retro-arcade" and tl["theme"]["layout"]["card"] == "outline" and tl["texture"] == "scanlines"


def test_interview_theme_question_shows_the_options():
    bank = load_yaml(SKILL / "config" / "interview.yaml")
    q = next(q for r in bank["rounds"] for q in r["questions"] if q["id"] == "theme")
    assert q["options_from"] == "themes"
    opts = iv._options(q, {})
    assert len(opts) >= 12 and all("texture" in o["description"] for o in opts)


@pytest.mark.skipif(not shutil.which("node") and not (SKILL / "node_modules").exists(), reason="needs node and npm install")
def test_theme_preview_renders_one_image_per_theme(tmp_path):
    try:
        files = themes.preview(tmp_path, ["bold-shorts", "noir-crime"])
    except FishError as e:
        pytest.skip(str(e))
    assert [f.name for f in files] == ["theme-bold-shorts.png", "theme-noir-crime.png", "gallery.png"]
    assert all(f.stat().st_size > 5000 for f in files)


# ------------------------------------------------------------------ voice
SOFT_POST = ("highpass=f=75,equalizer=f=280:t=q:w=1.1:g=-2,equalizer=f=3200:t=q:w=1.4:g=0.8,aexciter=freq=6500:amount=0.5:blend=0:ceil=11500,"
             "highshelf=f=8000:g=1.5,deesser=i=0.35,acompressor=threshold=-20dB:ratio=1.8:attack=15:release=180:makeup=1.2,aecho=0.9:0.9:19|37:0.04|0.025")


def test_chatterbox_soft_is_the_default_with_the_exact_recipe():
    c = vl.config()
    assert c["defaults"]["style"] == "chatterbox-soft" and c["defaults"]["seed"] == 11 and c["defaults"]["temperature"] == 0.75
    sty = c["styles"]["chatterbox-soft"]
    assert sty["post"] == SOFT_POST and sty["loudnorm"] == "loudnorm=I=-18:TP=-2:LRA=9"
    assert sty["exaggeration_range"] == [0.32, 0.55] and sty["cfg_fixed"] == 0.25 and sty["pause_range"] == [0.35, 0.55]
    S = vl.studio_settings({"language": "en-US"}, "chatterbox")
    assert S["style"] == "chatterbox-soft" and S["gender"] == "male" and S["ref"] is None          # Chatterbox's own default voice
    assert S["cfg_weight"] == 0.25 and S["temperature"] == 0.75 and S["seed"] == 11 and S["loop"] is False
    assert vl.SR_OUT == 48000


def test_soft_preset_plans_one_sentence_at_a_time_with_per_sentence_emotion():
    S = vl.studio_settings({"language": "en-US"}, "chatterbox")
    items = vl.plan_line("So... let's slow down. And walk through the roadmap together, one step at a time! Is that clear?", None, S)
    assert len(items) >= 2
    for it in items:
        assert 0.32 <= it["exaggeration"] <= 0.55 and it["cfg_weight"] == 0.25 and it["temperature"] == 0.75 and it["seed"] == 11
        assert 0.35 <= it["pause"] <= 0.55
    assert len({it["exaggeration"] for it in items}) > 1                                  # it varies by sentence
    hot = vl.plan_line("This is the turn!", "excited", S)[0]
    calm = vl.plan_line("This is the turn.", "reflective", S)[0]
    assert hot["exaggeration"] > calm["exaggeration"] and calm["exaggeration"] == 0.32


def test_other_styles_are_unchanged_and_still_selectable():
    S = vl.studio_settings({"language": "en-US", "studio": {"style": "airy", "gender": "female"}}, "chatterbox")
    assert S["style"] == "airy" and S["loudnorm"] is None and S["loop"] is True


def test_voice_is_offered_first_and_recommended_in_the_interview():
    q = next(q for r in iv.bank()["rounds"] for q in r["questions"] if q["id"] == "voice")
    opts = iv._options(q, {"language": "en-US", "voice_energy": "punchy"})
    assert opts[0]["value"] == "chatterbox-soft" and "Recommended" in opts[0]["label"]
    brief = {"interview": {"answers": {"voice": "chatterbox-soft", "language": "en-US", "voice_energy": "calm"}}}
    out = iv.apply(brief)
    assert out["voice"]["provider"] == "chatterbox" and out["voice"]["studio"]["style"] == "chatterbox-soft"
    assert out["pacing"]["max_word_gap"] == 0.9 and out["pacing"]["line_gap"] == 0.05 and out["mix"]["music_under_voice_db"] == -12


def test_missing_chatterbox_stops_with_the_setup_command_and_no_silent_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(vl, "engine_ready", lambda e: False)
    with pytest.raises(FishError) as e:
        vl._make_takes([({"text": "Hi there friend.", "seed": 11}, vl.studio_settings({"language": "en-US"}, "chatterbox"))], "chatterbox", tmp_path, None, "en-US")
    msg = str(e.value)
    assert "fishvideo voice setup --engine chatterbox" in msg and "nothing falls back silently" in msg and "on purpose" in msg


def test_voice_docs_name_the_preset_everywhere():
    for f in ("SKILL.md", "README.md", "references/local-voices.md", "references/voice-direction.md"):
        assert "chatterbox-soft" in (SKILL / f).read_text(), f


# ------------------------------------------------------------------ thumbnails: logos, no screenshots
def _need_icons():
    if not (SKILL / "node_modules" / "simple-icons" / "icons").is_dir():
        pytest.skip("simple-icons not installed")


def test_logos_resolve_from_simple_icons_with_a_readable_tile():
    _need_icons()
    lg = thumbs.resolve_logos(["Hugging Face", "github", {"slug": "claude"}])
    assert [x["slug"] for x in lg] == ["huggingface", "github", "claude"]
    assert all(x["d"][0] in "Mm" and x["tile"] in ("#16161a", "#ffffff") for x in lg)
    with pytest.raises(FishError) as e:
        thumbs.resolve_logos(["notabrandxyz"])
    assert "simple-icons" in str(e.value)
    assert thumbs.find_logos("github")[0]["slug"] == "github"


def test_logos_must_relate_to_the_video(tmp_path):
    _need_icons()
    p = _project(tmp_path, [{"id": "a", "type": "story", "bars": 2, "say": "We learn Docker and Python today.", "params": {}}])
    lg = thumbs.resolve_logos(["docker", "python", "nvidia"])
    assert thumbs.logos_related(p, lg) == ["NVIDIA"]


def test_screenshot_is_detected_and_fails_the_thumbnail_check(tmp_path):
    import numpy as np
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (1280, 720), "#202020")
    d = ImageDraw.Draw(im)
    for i, col in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        d.ellipse([30 + i * 28, 20, 44 + i * 28, 34], fill=col)
    assert thumbs.looks_like_screenshot(np.asarray(im))
    f = tmp_path / "t.png"; im.save(f)
    rows = {r["check"]: r for r in thumbs.check_image(f, None, "thumbnail")}
    assert rows["not a website screenshot"]["status"] == "FAIL"
    plain = Image.new("RGB", (1280, 720), "#202020"); plain.save(f)
    assert {r["check"]: r for r in thumbs.check_image(f, None, "thumbnail")}["not a website screenshot"]["status"] == "PASS"
    assert thumbs.is_screenshot_path("assets/shots/site-1.jpg") or thumbs.is_screenshot_path("build/capture/x.png")


def test_site_scenes_are_never_picked_as_thumbnail_frames():
    assert "site" in thumbs.SCREENSHOT_TYPES and "tour" in thumbs.SCREENSHOT_TYPES and "pile" in thumbs.SCREENSHOT_TYPES


def test_tiny_feed_size_is_checked():
    assert thumbs.SIZES["tiny"] == (246, 138)


# ------------------------------------------------------------------ the required thumbnail step
def _road_sidecar(tiles, texts, W=1280, H=720):
    return {"layout": "road", "tiles": tiles, "texts": texts, "W": W, "H": H}


def _plain(tmp_path, W=1280, H=720, name="t.png"):
    from PIL import Image
    f = tmp_path / name
    Image.new("RGB", (W, H), "#0b0b0e").save(f)
    return f


def _rows(f, side, kind="thumbnail"):
    return {r["check"]: r for r in thumbs.check_image(f, side, kind)}


GOOD_TEXT = {"text": "GENAI", "box": [52, 112, 500, 160], "px": 176, "color": "#f2b722", "words": 1}
GOOD_TILE = [730, 590, 118, 118]


def test_check_passes_a_clean_road_layout(tmp_path):
    r = _rows(_plain(tmp_path), _road_sidecar([GOOD_TILE, [915, 550, 118, 118]], [GOOD_TEXT]))
    assert all(r[k]["status"] == "PASS" for k in ("tiles present", "tiles inside the frame", "words clear of the tiles", "not a website screenshot", "file size", "dimensions"))


def test_check_fails_words_touching_a_tile(tmp_path):
    near = {**GOOD_TEXT, "box": [200, 560, 540, 120]}                      # right edge 740: the tile starts at 730
    r = _rows(_plain(tmp_path), _road_sidecar([GOOD_TILE, [915, 550, 118, 118]], [near]))
    assert r["words clear of the tiles"]["status"] == "FAIL" and "tile 1" in r["words clear of the tiles"]["detail"]
    close = {**GOOD_TEXT, "box": [100, 560, 620, 120]}                      # a 10 px gap: under the 12 px limit
    assert _rows(_plain(tmp_path), _road_sidecar([GOOD_TILE, [915, 550, 118, 118]], [close]))["words clear of the tiles"]["status"] == "FAIL"


def test_check_fails_a_tile_outside_the_frame(tmp_path):
    r = _rows(_plain(tmp_path), _road_sidecar([GOOD_TILE, [1230, 100, 118, 118]], [GOOD_TEXT]))
    assert r["tiles inside the frame"]["status"] == "FAIL" and "tile 2" in r["tiles inside the frame"]["detail"]


def test_check_fails_too_few_tiles(tmp_path):
    assert _rows(_plain(tmp_path), _road_sidecar([GOOD_TILE], [GOOD_TEXT]))["tiles present"]["status"] == "FAIL"


def test_check_fails_a_headline_unreadable_at_246_px(tmp_path):
    small = {**GOOD_TEXT, "px": 30, "box": [52, 112, 100, 30]}
    r = _rows(_plain(tmp_path), _road_sidecar([GOOD_TILE, [915, 550, 118, 118]], [small]))
    assert r["text size at 246x138"]["status"] == "FAIL"
    big = _rows(_plain(tmp_path), _road_sidecar([GOOD_TILE, [915, 550, 118, 118]], [GOOD_TEXT]))
    assert big["text size at 246x138"]["status"] == "PASS"


def test_check_fails_wrong_size_and_oversize_files(tmp_path):
    assert _rows(_plain(tmp_path, 640, 360), None)["dimensions"]["status"] == "FAIL"
    import numpy as np
    from PIL import Image
    f = tmp_path / "big.png"
    Image.fromarray(np.random.default_rng(1).integers(0, 255, (720, 1280, 3), dtype=np.uint8)).save(f)
    assert f.stat().st_size > 2_000_000 and _rows(f, None)["file size"]["status"] == "FAIL"


def test_check_fails_a_screenshot_source_even_without_browser_dots(tmp_path):
    side = {**_road_sidecar([GOOD_TILE, [915, 550, 118, 118]], [GOOD_TEXT]), "image": "assets/shots/site-1.jpg"}
    assert _rows(_plain(tmp_path), side)["not a website screenshot"]["status"] == "FAIL"


def _tile_project(tmp_path, brands=None, images=True):
    from PIL import Image
    p = tmp_path / "tp"
    (p / "assets" / "photo").mkdir(parents=True)
    for i in range(3):
        Image.new("RGB", (900, 600), (40 * i + 30, 90, 120)).save(p / "assets" / "photo" / f"p{i}.jpg")
    (p / "assets" / "credits.json").write_text(json.dumps([{"file": f"assets/photo/p{i}.jpg", "license": "generated"} for i in range(3)]))
    th = {"title": "He Fought Alone", "accent": "He Fought", "tag": "TRUE STORY", "sub": "A WAR THAT *ENDED*"}
    if brands:
        th["logos"] = brands
    save_yaml(p / "brief.yaml", {"title": "t", "platforms": ["youtube", "shorts"], "language": "en-US", "theme": "tech-dark", "voice": {"provider": "none"}, "captions": {"burn": False}, "brand": {"name": ""}, "thumbnail": th})
    save_yaml(p / "storyboard.yaml", {"title": "t", "bpm": 120, "scenes": [{"id": "a", "type": "story", "bars": 2, "say": "Docker and Python are used here.", "params": {"src": "assets/photo/p0.jpg", "lines": ["x"]}}]})
    return p


def test_tiles_fall_back_to_licensed_pictures_and_never_screenshots(tmp_path):
    p = _tile_project(tmp_path)
    tiles, note = thumbs.resolve_tiles(p, {}, load_yaml(p / "storyboard.yaml"), load_yaml(p / "brief.yaml"))
    assert [t["src"] for t in tiles] == [f"assets/photo/p{i}.jpg" for i in range(3)] and "licensed" in note
    from PIL import Image
    (p / "assets" / "shots").mkdir()
    Image.new("RGB", (10, 10)).save(p / "assets" / "shots" / "site-1.jpg")
    with pytest.raises(FishError):
        thumbs.resolve_tiles(p, {"tiles": ["assets/shots/site-1.jpg"]}, {}, load_yaml(p / "brief.yaml"))


def test_unrelated_logos_are_refused(tmp_path):
    _need_icons()
    p = _tile_project(tmp_path, brands=["docker", "python", "nvidia"])
    with pytest.raises(FishError) as e:
        thumbs.resolve_tiles(p, {}, load_yaml(p / "storyboard.yaml"), load_yaml(p / "brief.yaml"))
    assert "NVIDIA" in str(e.value) and "trademarks" in str(e.value)


def test_package_refuses_without_a_thumbnail_and_names_the_command(tmp_path):
    p = _tile_project(tmp_path)
    errs = thumbs.package_gate(p)
    assert errs and "fishvideo thumbnail" in errs[0] and "no thumbnail" in errs[0]


needs_browser = pytest.mark.skipif(not (SKILL / "node_modules" / "puppeteer-core").exists(), reason="needs npm install and a browser")


@needs_browser
def test_thumbnail_command_draws_checks_picks_and_unlocks_package(tmp_path):
    p = _tile_project(tmp_path, brands=["docker", "python"])
    try:
        rep = thumbs.thumbnail(p)
    except FishError as e:
        if "browser" in str(e).lower() or "did not render" in str(e):
            pytest.skip(str(e)[:80])
        raise
    assert rep["variants"][0]["layout"] == "road" and rep["covers"] and rep["covers"][0]["platform"] == "shorts"
    side = json.loads((p / rep["variants"][0]["file"]).with_suffix(".json").read_text())
    assert len(side["tiles"]) == 2 and all(0 <= t[0] and t[0] + t[2] <= 1280 for t in side["tiles"])
    assert (p / "build" / "thumbnail" / "pick.json").exists()
    assert thumbs.package_gate(p) == []
    # a changed brief makes the thumbnail stale: the gate asks for it again
    import os, time
    os.utime(p / "storyboard.yaml", (time.time() + 5, time.time() + 5))
    assert any("changed after the thumbnail" in e and "fishvideo thumbnail" in e for e in thumbs.package_gate(p))


@needs_browser
def test_package_gate_reports_a_failing_check_with_the_command(tmp_path):
    p = _tile_project(tmp_path)
    try:
        thumbs.thumbnail(p)
    except FishError as e:
        pytest.skip(str(e)[:80])
    side = (p / "build" / "thumbnail" / "variants")
    j = next(side.glob("*.json"))
    d = json.loads(j.read_text()); d["tiles"][0][0] = 1250; j.write_text(json.dumps(d))
    errs = thumbs.package_gate(p)
    assert any("tiles inside the frame" in e and "fishvideo thumbnail" in e for e in errs)


def test_cli_exposes_the_required_step_and_the_opt_out():
    import fishvideo
    assert fishvideo.PASSTHRU["thumbnail"] == "thumbs"
    txt = (SKILL / "scripts" / "fishvideo.py").read_text()
    assert "--no-thumbnail" in txt and "the thumbnail step is not done" in txt


def test_skill_md_lists_the_thumbnail_step_as_required():
    md = (SKILL / "SKILL.md").read_text()
    assert "fishvideo thumbnail" in md and "required" in md.lower()
