"""Offline tests for design.py and thumbs.py: every measurement on synthetic images, plus pick and package."""
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

import design as dz
import thumbs
from fvcore import FishError, save_json


def solid(w, h, rgb):
    return np.full((h, w, 3), rgb, dtype=np.uint8)


def with_block(img, box, rgb):
    x, y, w, h = box
    out = img.copy()
    out[y:y + h, x:x + w] = rgb
    return out


def text_el(text, box, px, color="rgb(255, 255, 255)", **kw):
    return {"text": text, "words": len(text.split()), "box": box, "px": px, "weight": 800, "color": color, "family": "Inter", "upper": False, "free": False, **kw}


def kinds(findings):
    return {f["kind"] for f in findings}


COLORS = {"bg": "#101010", "ink": "#f5f5f5", "accent": "#ff5a1f", "muted": "#888888"}


def analyse(img, texts, **kw):
    H, W = img.shape[:2]
    return dz.analyse_frame(img, {"scene": "s", "t": 1.0, "type": "title", "texts": texts, "issues": []}, W=W, H=H, colors=COLORS, **kw)


# ---------------------------------------------------------------- contrast
def test_wcag_contrast_known_values():
    assert dz.contrast((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0, abs=0.01)
    assert dz.contrast((119, 119, 119), (255, 255, 255)) == pytest.approx(4.48, abs=0.05)
    assert dz.contrast((10, 10, 10), (10, 10, 10)) == pytest.approx(1.0)


def test_text_contrast_reads_the_pixels_behind_the_text():
    img = solid(400, 200, (245, 245, 245))
    img = with_block(img, (100, 90, 200, 12), (20, 20, 20))      # the "glyphs": a stroke across the box
    good = dz.text_contrast(img, [100, 80, 200, 40], (20, 20, 20))
    assert good["ratio"] > 12
    # the same declared colour on a background that is almost the same: it cannot be read
    bad_img = with_block(solid(400, 200, (120, 120, 120)), (100, 90, 200, 12), (140, 140, 140))
    bad = dz.text_contrast(bad_img, [100, 80, 200, 40], (140, 140, 140))
    assert bad["ratio"] < 1.5


def test_text_contrast_without_a_declared_colour_splits_luminance():
    img = solid(300, 100, (250, 250, 250))
    img = with_block(img, (50, 45, 200, 8), (10, 10, 10))
    r = dz.text_contrast(img, [50, 40, 200, 20], None)
    assert r["method"] == "pixels" and r["ratio"] > 10


def test_low_contrast_text_is_reported_with_a_fix():
    img = solid(1920, 1080, (120, 120, 120))
    img = with_block(img, (300, 400, 600, 120), (135, 135, 135))
    f = analyse(img, [text_el("QUIET", [300, 400, 600, 120], 120, "rgb(135, 135, 135)")])
    low = [x for x in f if x["kind"] == "low-contrast"]
    assert low and low[0]["text"] == "QUIET" and low[0]["fix"]


def test_high_contrast_text_passes():
    img = solid(1920, 1080, (16, 16, 16))
    img = with_block(img, (300, 430, 600, 30), (245, 245, 245))
    f = analyse(img, [text_el("LOUD", [300, 400, 600, 120], 120, "rgb(245, 245, 245)")])
    assert "low-contrast" not in kinds(f)


# ---------------------------------------------------------------- hierarchy, words, edges, empty
def test_flat_hierarchy_when_hero_is_not_larger_than_small_text():
    img = solid(1920, 1080, (16, 16, 16))
    flat = analyse(img, [text_el("ONE", [100, 100, 300, 70], 64), text_el("TWO", [100, 300, 300, 60], 56)])
    assert "flat-hierarchy" in kinds(flat)
    ok = analyse(img, [text_el("ONE", [100, 100, 600, 200], 180), text_el("TWO", [100, 400, 300, 40], 40)])
    assert "flat-hierarchy" not in kinds(ok)


def test_wall_of_text():
    img = solid(1920, 1080, (16, 16, 16))
    t = [text_el(" ".join(["word"] * 14), [100, 100 + i * 120, 1500, 80], 60) for i in range(3)]
    assert "wall-of-text" in kinds(analyse(img, t))


def test_edge_crowding():
    img = solid(1920, 1080, (16, 16, 16))
    assert "edge-crowding" in kinds(analyse(img, [text_el("EDGE", [4, 500, 400, 100], 100)]))
    assert "edge-crowding" not in kinds(analyse(img, [text_el("MID", [700, 500, 400, 100], 100)]))


def test_empty_quadrants_found_on_a_flat_corner_only():
    img = np.zeros((400, 600, 3), dtype=np.uint8)
    for i in range(0, 600, 40):                                 # coarse stripes everywhere: content
        img[:, i:i + 20] = 220
    img[:200, :300] = 40                                       # top-left is flat
    assert dz.empty_quadrants(img) == ["top-left"]
    grain = np.random.default_rng(1).integers(30, 50, (400, 600, 3), dtype=np.uint8)
    assert len(dz.empty_quadrants(grain)) == 4                 # grain alone is not content


def test_too_many_type_sizes():
    img = solid(1920, 1080, (16, 16, 16))
    t = [text_el(f"S{i}", [100, 80 + i * 150, 300, 100], 40 + i * 20) for i in range(6)]
    assert "too-many-sizes" in kinds(analyse(img, t))


def test_ignored_kinds_are_silenced():
    img = solid(1920, 1080, (16, 16, 16))
    rules = dict(dz.RULES, ignore=["edge-crowding"])
    assert "edge-crowding" not in kinds(analyse(img, [text_el("EDGE", [4, 500, 400, 100], 100)], rules=rules))


# ---------------------------------------------------------------- palette and difference
def test_palette_extraction_and_theme_proposal():
    img = solid(300, 300, (19, 17, 16))
    img[20:60, 20:260] = (255, 90, 31)                       # a small strong accent
    img[100:200, 100:200] = (245, 245, 245)
    pal = dz.extract_palette(img)
    hexes = [p["hex"] for p in pal]
    assert hexes[0] == "#131110"
    assert any(dz.delta_e(p["rgb"], (255, 90, 31)) < 6 for p in pal)
    th = dz.propose_theme(pal)
    assert th["mode"] == "dark"
    assert th["contrast"]["ink_on_bg"] >= 7 and th["contrast"]["accent_on_bg"] >= 3
    assert dz.delta_e(dz.parse_color(th["accent"]), (255, 90, 31)) < 8


def test_theme_for_a_mid_tone_background_moves_it_until_ink_reads():
    th = dz.propose_theme(dz.extract_palette(solid(100, 100, (128, 128, 128))))
    assert th["contrast"]["ink_on_bg"] >= 7 and th["bg_adjusted"]


def test_palette_written_to_the_brief(tmp_path):
    img = Image.new("RGB", (120, 120), (19, 17, 16))
    ImageDraw.Draw(img).rectangle([10, 10, 60, 40], fill=(255, 90, 31))
    src = tmp_path / "x.png"
    img.save(src)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "brief.yaml").write_text("title: T\nplatforms: [youtube]\n", encoding="utf-8")
    res = dz.palette(src, write=proj, out=tmp_path / "pal.png")
    assert Path(res["sheet"]).exists() and res["written"]
    import yaml
    brief = yaml.safe_load((proj / "brief.yaml").read_text(encoding="utf-8"))
    assert brief["brand"]["colors"]["accent"].startswith("#") and brief["brand"]["mode"] == "dark"


def test_difference_map_finds_the_changed_block():
    a = solid(320, 320, (30, 30, 30))
    b = with_block(a, (64, 64, 80, 80), (250, 250, 250))
    d = dz.diff_regions(a, b)
    assert 0.04 < d["changed"] < 0.08
    x, y, w, h = d["boxes"][0]
    assert x <= 64 and y <= 64 and x + w >= 144 and y + h >= 144
    assert dz.diff_regions(a, a)["changed"] == 0 and dz.diff_regions(a, a)["boxes"] == []


# ---------------------------------------------------------------- thumbnail checks
def gradient_thumb(path, W=1280, H=720, noise=False):
    """A bold synthetic thumbnail: dark ground, big light title block, saturated shape."""
    img = Image.new("RGB", (W, H), (14, 14, 18))
    d = ImageDraw.Draw(img)
    d.ellipse([W * 0.62, H * 0.1, W * 0.95, H * 0.7], fill=(255, 90, 31))
    d.rectangle([60, 120, 700, 330], fill=(245, 245, 245))
    img.save(path)
    return path


def test_thumb_check_passes_a_good_thumbnail(tmp_path):
    f = gradient_thumb(tmp_path / "t.png")
    side = {"texts": [{"text": "BIG WORDS", "words": 2, "box": [60, 120, 640, 210], "px": 180, "color": "rgb(14, 14, 18)"}]}
    rows = thumbs.check_image(f, side)
    bad = [r for r in rows if r["status"] != "PASS"]
    assert not bad, bad
    names = {r["check"] for r in rows}
    assert {"file size", "dimensions", "brightness", "timestamp zone", "words on screen"} <= names


def test_thumb_check_catches_tiny_text(tmp_path):
    f = gradient_thumb(tmp_path / "t.png")
    side = {"texts": [{"text": "tiny", "words": 1, "box": [60, 120, 100, 28], "px": 26, "color": "rgb(14, 14, 18)"}]}
    rows = {r["check"]: r for r in thumbs.check_image(f, side)}
    assert rows["text size at 320x180"]["status"] in ("WARN", "FAIL")
    assert rows["text size at 168x94"]["status"] == "FAIL"


def test_thumb_check_catches_words_that_vanish_when_shrunk(tmp_path):
    img = Image.new("RGB", (1280, 720), (128, 128, 128))
    ImageDraw.Draw(img).rectangle([60, 120, 700, 330], fill=(138, 138, 138))
    img.save(tmp_path / "v.png")
    side = {"texts": [{"text": "FAINT", "words": 1, "box": [60, 120, 640, 210], "px": 180, "color": "rgb(138, 138, 138)"}]}
    rows = {r["check"]: r for r in thumbs.check_image(tmp_path / "v.png", side)}
    assert rows["words survive at 320x180"]["status"] in ("WARN", "FAIL")


def test_thumb_check_word_count(tmp_path):
    f = gradient_thumb(tmp_path / "t.png")
    side = {"texts": [{"text": "one two three four five six seven eight nine ten", "words": 10, "box": [60, 120, 640, 210], "px": 100, "color": "rgb(14, 14, 18)"}]}
    assert {r["check"]: r for r in thumbs.check_image(f, side)}["words on screen"]["status"] == "WARN"


def test_thumb_check_timestamp_zone(tmp_path):
    f = gradient_thumb(tmp_path / "t.png")
    side = {"texts": [{"text": "CORNER", "words": 1, "box": [1100, 640, 160, 60], "px": 100, "color": "rgb(14, 14, 18)"}]}
    assert {r["check"]: r for r in thumbs.check_image(f, side)}["timestamp zone"]["status"] == "WARN"
    img = Image.open(f).convert("RGB")
    ImageDraw.Draw(img).rectangle([1100, 640, 1270, 710], fill=(255, 255, 255))
    for x in range(1100, 1270, 6):                               # fine detail in the corner
        ImageDraw.Draw(img).line([x, 640, x, 710], fill=(0, 0, 0), width=2)
    img.save(tmp_path / "busy.png")
    assert {r["check"]: r for r in thumbs.check_image(tmp_path / "busy.png", None)}["timestamp zone"]["status"] == "WARN"
    assert {r["check"]: r for r in thumbs.check_image(f, None)}["timestamp zone"]["status"] == "PASS"


def test_thumb_check_size_and_shape_are_hard_failures(tmp_path):
    rng = np.random.default_rng(0)
    Image.fromarray(rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)).save(tmp_path / "noise.png")
    rows = {r["check"]: r for r in thumbs.check_image(tmp_path / "noise.png", None)}
    assert rows["file size"]["status"] == "FAIL" and rows["file size"]["hard"]
    Image.new("RGB", (1000, 1000), (200, 50, 50)).save(tmp_path / "sq.png")
    rows = {r["check"]: r for r in thumbs.check_image(tmp_path / "sq.png", None)}
    assert rows["dimensions"]["status"] == "FAIL" and rows["dimensions"]["hard"]


def test_thumb_check_brightness_and_saturation(tmp_path):
    Image.new("RGB", (1280, 720), (4, 4, 4)).save(tmp_path / "dark.png")
    rows = {r["check"]: r for r in thumbs.check_image(tmp_path / "dark.png", None)}
    assert rows["brightness"]["status"] == "WARN" and rows["tonal range"]["status"] == "WARN" and rows["saturation"]["status"] == "WARN"


def test_save_small_converts_a_heavy_png_to_jpeg(tmp_path):
    rng = np.random.default_rng(0)
    p = tmp_path / "big.png"
    Image.fromarray(rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)).save(p)
    out = thumbs.save_small(p)
    assert out.suffix == ".jpg" and out.stat().st_size < thumbs.MAX_BYTES and not p.exists()


def test_frame_score_prefers_detail_over_emptiness():
    rng = np.random.default_rng(2)
    busy = rng.integers(0, 255, (300, 500, 3), dtype=np.uint8)
    assert thumbs.frame_score(busy) > thumbs.frame_score(solid(500, 300, (30, 30, 30)))


# ---------------------------------------------------------------- cut-out with outline and glow
def test_glow_cutout_adds_outline_and_glow(tmp_path):
    subj = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    ImageDraw.Draw(subj).ellipse([20, 20, 80, 80], fill=(30, 140, 220, 255))
    src = tmp_path / "s.png"
    subj.save(src)
    out = thumbs.glow_cutout(src, tmp_path / "o.png", outline=6, glow=20, color="#ff5a1f")
    im = Image.open(out)
    assert im.mode == "RGBA" and im.width > 100 and im.height > 100          # grew by the outline and the glow
    a = np.asarray(im.getchannel("A"))
    assert a.min() == 0 and a.max() == 255
    rgb = np.asarray(im.convert("RGB"))
    cy = im.height // 2
    assert np.abs(rgb[cy, im.width // 2].astype(int) - (30, 140, 220)).max() < 12   # the subject is untouched
    edge = np.nonzero(a[cy] > 250)[0][0]
    assert rgb[cy, edge].min() > 200                                        # a white outline right outside the subject


# ---------------------------------------------------------------- pick, ship, qa rows
def fake_project(tmp_path, big=False):
    proj = tmp_path / "p"
    (proj / "build" / "thumbnail" / "variants").mkdir(parents=True)
    vs = []
    for i, name in enumerate(["subject", "caption"], 1):
        f = proj / "build" / "thumbnail" / "variants" / f"thumb-{i}-{name}.png"
        gradient_thumb(f)
        save_json(f.with_suffix(".json"), {"texts": [{"text": "BIG WORDS", "words": 2, "box": [60, 120, 640, 210], "px": 180, "color": "rgb(14, 14, 18)"}]})
        vs.append({"n": i, "layout": name, "file": str(f.relative_to(proj)), "bytes": f.stat().st_size, "note": "", "W": 1280, "H": 720})
    (proj / "brief.yaml").write_text("title: T\n", encoding="utf-8")
    save_json(proj / "build" / "thumbnail" / "variants.json", {"variants": vs, "covers": []})
    return proj


def test_pick_records_and_ship_copies_the_pick(tmp_path):
    proj = fake_project(tmp_path)
    rec = thumbs.pick(proj, 2)
    assert rec["layout"] == "caption" and json.loads((proj / "build" / "thumbnail" / "pick.json").read_text())["n"] == 2
    with pytest.raises(FishError):
        thumbs.pick(proj, 9)
    dest = tmp_path / "pkg"
    shipped = thumbs.ship(proj, dest)
    assert "thumbnail-1280x720.png" in shipped and "thumbnail-check.md" in shipped
    assert (dest / "thumbnails" / "thumbnail-1280x720.png").read_bytes() == (proj / "build" / "thumbnail" / "variants" / "thumb-2-caption.png").read_bytes()


def test_ship_without_variants_changes_nothing(tmp_path):
    (tmp_path / "q" / "build").mkdir(parents=True)
    assert thumbs.ship(tmp_path / "q", tmp_path / "pkg") == []


def test_qa_rows_are_warn_for_looks_and_fail_for_facts(tmp_path):
    proj = fake_project(tmp_path)
    rows = thumbs.qa_rows(proj)
    assert rows and all(r["status"] == "PASS" for r in rows)
    rng = np.random.default_rng(0)                                           # over 2 MB: a fact
    Image.fromarray(rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)).save(proj / "build" / "thumbnail" / "variants" / "thumb-1-subject.png")
    rows = {r["check"]: r for r in thumbs.qa_rows(proj)}
    assert rows["thumbnail 1 subject"]["status"] == "FAIL"
    assert thumbs.qa_rows(tmp_path) == []                                    # nothing made: no rows
