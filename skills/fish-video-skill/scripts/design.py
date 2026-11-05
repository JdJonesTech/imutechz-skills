"""Frame design tools: look at single frames the way a designer would, and measure them.

    fishvideo frame sheet <dir> [--platform p]                      one labelled hero frame per scene
    fishvideo frame lint <dir> [--platform p] [--scene id,id] [--strict]
    fishvideo frame guides <dir> --scene id [--platform p] [--bands shorts,reels,tiktok]
    fishvideo frame variants <dir> --scene id --vary palette|texture|type [--apply N]
    fishvideo frame palette <image|video> [--write <dir>] [--colors 8]
    fishvideo frame compare <a> <b> [--at 2,8] [--out sheet.png]

`frame lint` combines two sources: the stage's DOM (which words are on screen, where, at what
size and in which colour: scripts/designprobe.mjs) and the pixels of the rendered still (what is
actually behind those words). It reports per scene, names the element, and suggests a fix:

  low-contrast        WCAG contrast of the text against the pixels behind it
  busy-background     the median contrast passes, the worst part of the background does not
  flat-hierarchy      the hero text is not clearly larger than the small text (the bible asks ~3x)
  too-many-sizes      more than four type sizes in one frame
  wall-of-text        too many words on screen, or one element with a sentence in it
  off-palette-text    a coloured text that is neither in the palette nor set by the scene
  no-accent           the accent colour is absent from the frame (bible: it appears in every scene)
  empty-quadrant      a quarter of the frame is flat
  edge-crowding       text almost touching the frame edge
  text-collision      two text blocks of different sizes overlap
  stage:*             everything the stage's own legibility lint found (size, safe area, clipping)

Every finding is advice: `frame lint` exits 0 unless --strict, and the QA row it feeds is a WARN.
Thresholds live in RULES; a project overrides them with brief.design.lint, and silences a kind
with brief.design.lint.ignore: [kind, ...].
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

from fvcore import FishError, SKILL, ensure_project, ffmpeg_bin, ffprobe_bin, last_json_line, load_json, load_yaml, log, main_guard, node, \
    project_config, save_json, save_yaml, warn

RULES = {
    "contrast_large": 3.0,      # WCAG AA for large text
    "contrast_small": 4.5,      # WCAG AA for body text
    "large_px": 40,             # text at or above this size (at 1080 on the short side) counts as large
    "busy_worst": 2.0,          # the worst tenth of the background must still clear this
    "hierarchy_warn": 1.5,      # hero / small below this is flat
    "hierarchy_note": 2.5,      # below this it is mentioned, not warned (the bible asks for about 3x)
    "max_sizes": 4,
    "max_words": {"land": 24, "square": 18, "port": 16},
    "max_words_one": 12,
    "accent_share": 0.0015,     # the accent must cover at least this share of the frame
    "flat_std": 3.0,            # a quadrant of the 32-step greyscale proxy below this is empty
    "edge": 0.025,              # text nearer than this share of the short side to an edge
    "ignore": [],
}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".ogv", ".gif"}


# ------------------------------------------------------------------ colour
def parse_color(s) -> tuple[float, float, float, float] | None:
    """A CSS colour as (r, g, b, a) with 0-255 channels, or None."""
    s = str(s or "").strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3,8})", s)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            return None
        v = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
        return (v[0], v[1], v[2], v[3] / 255 if len(v) == 4 else 1.0)
    m = re.match(r"rgba?\(([^)]+)\)", s)
    if m:
        p = [x for x in re.split(r"[,\s/]+", m.group(1).strip()) if x]
        if len(p) >= 3:
            ch = [float(x[:-1]) * 2.55 if x.endswith("%") else float(x) for x in p[:3]]
            a = (float(p[3][:-1]) / 100 if p[3].endswith("%") else float(p[3])) if len(p) > 3 else 1.0
            return (ch[0], ch[1], ch[2], a)
    m = re.match(r"color\(srgb\s+([^)]+)\)", s)
    if m:
        p = [x for x in re.split(r"[\s/]+", m.group(1).strip()) if x]
        if len(p) >= 3:
            return (float(p[0]) * 255, float(p[1]) * 255, float(p[2]) * 255, float(p[3]) if len(p) > 3 else 1.0)
    return None


def hex_of(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, int(round(float(c))))):02x}" for c in rgb[:3])


def rel_lum(rgb) -> float:
    """WCAG 2 relative luminance of an sRGB colour (0-255 channels)."""
    out = []
    for c in rgb[:3]:
        c = max(0.0, min(255.0, float(c))) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a, b) -> float:
    """WCAG contrast ratio of two colours, 1.0 to 21.0."""
    la, lb = rel_lum(a), rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def mix(a, b, t: float):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def chroma(rgb) -> float:
    return max(rgb[:3]) - min(rgb[:3])


def saturation(rgb) -> float:
    mx, mn = max(rgb[:3]), min(rgb[:3])
    return 0.0 if mx <= 0 else (mx - mn) / mx


def lab(rgb):
    """sRGB (0-255) -> CIE L*a*b* (D65)."""
    lin = []
    for c in rgb[:3]:
        c = max(0.0, min(255.0, float(c))) / 255
        lin.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    x = (0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2]) / 0.95047
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    z = (0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2]) / 1.08883
    f = [v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116 for v in (x, y, z)]
    return (116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2]))


def delta_e(a, b) -> float:
    la, lb = lab(a), lab(b)
    return sum((la[i] - lb[i]) ** 2 for i in range(3)) ** 0.5


def best_ink(bg, candidates) -> tuple[str, float]:
    """The candidate colour with the highest contrast against bg: (hex, ratio)."""
    best = max(candidates, key=lambda c: contrast(c, bg))
    return hex_of(best), round(contrast(best, bg), 2)


# ------------------------------------------------------------------ pixels
def load_rgb(path: Path | str):
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def text_contrast(img, box, color=None, tol: int = 44) -> dict:
    """Contrast of a text against the pixels actually behind it.

    img is an HxWx3 uint8 array, box is [x, y, w, h] in pixels, color the declared text colour
    (r, g, b[, a]). Pixels near the declared colour are the glyphs; the rest of the box is the
    background. When the declared colour is not found in the box (gradient or image-filled type,
    a covered element) the box is split into its two luminance groups instead.
    Returns {ratio, worst, text, bg, method, glyph_share}: `ratio` is against the median
    background, `worst` against the tenth of the background closest to the text.
    """
    import numpy as np
    H, W = img.shape[:2]
    x0, y0 = max(0, int(box[0]) - 2), max(0, int(box[1]) - 2)
    x1, y1 = min(W, int(box[0] + box[2]) + 2), min(H, int(box[1] + box[3]) + 2)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return {"ratio": None, "method": "off-frame"}
    px = img[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
    lum = _lum(px)
    if color is not None and (len(color) < 4 or color[3] >= 0.5):
        d = np.abs(px - np.asarray(color[:3], dtype=np.float32)).max(axis=1)
        glyph = d < tol
        share = float(glyph.mean())
        if share > 0.85:
            # the declared colour fills the box: the text sits on (almost) its own colour
            return {"ratio": round(contrast(color, np.median(px, axis=0)), 2), "worst": round(contrast(color, np.median(px, axis=0)), 2),
                    "text": hex_of(color), "bg": hex_of(np.median(px, axis=0)), "method": "declared", "glyph_share": round(share, 3)}
        if share >= 0.01:
            far = d > tol * 2
            bg = px[far] if far.mean() >= 0.02 else px[~glyph]
            bl = _lum(bg)
            tl = rel_lum(np.median(px[glyph], axis=0))
            near = float(np.percentile(bl, 90 if tl > float(np.median(bl)) else 10))
            return {"ratio": round(contrast(np.median(px[glyph], axis=0), np.median(bg, axis=0)), 2), "worst": round((max(tl, near) + 0.05) / (min(tl, near) + 0.05), 2),
                    "text": hex_of(np.median(px[glyph], axis=0)), "bg": hex_of(np.median(bg, axis=0)), "method": "declared", "glyph_share": round(share, 3)}
    # two luminance groups (Otsu): the smaller one is taken as the glyphs
    thr = _otsu(lum)
    a, b = px[lum <= thr], px[lum > thr]
    if not len(a) or not len(b):
        return {"ratio": 1.0, "worst": 1.0, "text": hex_of(np.median(px, axis=0)), "bg": hex_of(np.median(px, axis=0)), "method": "pixels", "glyph_share": 0.0}
    fg, bg = (a, b) if len(a) <= len(b) else (b, a)
    r = contrast(np.median(fg, axis=0), np.median(bg, axis=0))
    return {"ratio": round(r, 2), "worst": round(r, 2), "text": hex_of(np.median(fg, axis=0)), "bg": hex_of(np.median(bg, axis=0)), "method": "pixels",
            "glyph_share": round(len(fg) / len(px), 3)}


def _lum(px):
    """Relative luminance of an Nx3 float array of 0-255 sRGB values."""
    import numpy as np
    c = np.clip(px, 0, 255) / 255
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return lin @ np.asarray([0.2126, 0.7152, 0.0722], dtype=lin.dtype)


def _otsu(v) -> float:
    import numpy as np
    hist, edges = np.histogram(v, bins=64, range=(0.0, 1.0))
    total, best, thr = hist.sum(), -1.0, 0.5
    mids = (edges[:-1] + edges[1:]) / 2
    w0 = s0 = 0.0
    s_all = float((hist * mids).sum())
    for i in range(63):
        w0 += hist[i]
        s0 += hist[i] * mids[i]
        w1 = total - w0
        if w0 == 0 or w1 == 0:
            continue
        m0, m1 = s0 / w0, (s_all - s0) / w1
        var = w0 * w1 * (m0 - m1) ** 2
        if var > best:
            best, thr = var, float(edges[i + 1])
    return thr


def empty_quadrants(img, flat: float = 3.0) -> list[str]:
    """Quarters of the frame that are flat. Measured on a small greyscale proxy (32 steps on the
    long side), so background grid lines and grain do not count as content."""
    import numpy as np
    from PIL import Image
    H, W = img.shape[:2]
    gw, gh = (32, max(8, round(32 * H / W))) if W >= H else (max(8, round(32 * W / H)), 32)
    g = np.asarray(Image.fromarray(img).convert("L").resize((gw, gh), Image.BOX), dtype=np.float32)
    parts = {"top-left": g[1:gh // 2 - 1, 1:gw // 2 - 1], "top-right": g[1:gh // 2 - 1, gw // 2 + 1:-1],
             "bottom-left": g[gh // 2 + 1:-1, 1:gw // 2 - 1], "bottom-right": g[gh // 2 + 1:-1, gw // 2 + 1:-1]}
    return [k for k, v in parts.items() if v.size and float(v.std()) < flat]


def color_share(img, rgb, tol: int = 40) -> float:
    """Share of the frame within `tol` (per channel) of a colour."""
    import numpy as np
    small = img[::4, ::4].astype(np.int16)
    return float((np.abs(small - np.asarray(rgb[:3], dtype=np.int16)).max(axis=2) < tol).mean())


def extract_palette(img, colors: int = 8, merge: float = 12.0) -> list[dict]:
    """Dominant colours of an image: [{hex, rgb, share}], largest first. Median cut on a small copy,
    then near-identical colours (delta E below `merge`) are folded together."""
    import numpy as np
    from PIL import Image
    im = Image.fromarray(img)
    im.thumbnail((200, 200))
    q = im.quantize(colors=max(2, colors), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    idx = np.asarray(q)
    pal = np.asarray(q.getpalette()[: 3 * (int(idx.max()) + 1)], dtype=np.float32).reshape(-1, 3)
    counts = np.bincount(idx.ravel(), minlength=len(pal)).astype(np.float64)
    out: list[dict] = []
    for i in np.argsort(-counts):
        if counts[i] <= 0:
            continue
        rgb, n = pal[i], counts[i]
        for o in out:
            if delta_e(o["rgb"], rgb) < merge:
                tot = o["n"] + n
                o["rgb"] = tuple((o["rgb"][k] * o["n"] + rgb[k] * n) / tot for k in range(3))
                o["n"] = tot
                break
        else:
            out.append({"rgb": tuple(float(c) for c in rgb), "n": float(n)})
    total = sum(o["n"] for o in out) or 1
    out.sort(key=lambda o: -o["n"])
    res = [{"hex": hex_of(o["rgb"]), "rgb": [round(c) for c in o["rgb"]], "share": round(float(o["n"] / total), 4)} for o in out]
    # a small, strong accent is averaged away by median cut: look for it among the saturated pixels
    for acc in saturated_accents(np.asarray(im.convert("RGB"), dtype=np.uint8)):
        near = [r for r in res if delta_e(acc["rgb"], r["rgb"]) < merge * 2]
        if near:   # the median-cut colour is the accent diluted by its glow: keep the true one
            near[0].update(hex=acc["hex"], rgb=acc["rgb"], accent=True)
        else:
            res.append({**acc, "accent": True})
    return res


def saturated_accents(img, min_share: float = 0.003, n: int = 2) -> list[dict]:
    """The strongest saturated colours of an image, by hue: [{hex, rgb, share}] (at most n).
    Only pixels with saturation >= 0.45 and value >= 0.3 count, and a hue needs min_share of the frame."""
    import numpy as np
    px = img.reshape(-1, 3).astype(np.float32)
    mx, mn = px.max(axis=1), px.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    keep = (sat >= 0.45) & (mx >= 77)
    if keep.mean() < min_share:
        return []
    p, d = px[keep], (mx - mn)[keep]
    r, g, b = p[:, 0], p[:, 1], p[:, 2]
    m = p.max(axis=1)
    hue = np.where(m == r, ((g - b) / d) % 6, np.where(m == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
    bins = np.minimum((hue * 24).astype(int), 23)
    weight = np.bincount(bins, weights=sat[keep] * m, minlength=24)
    out, used = [], []
    for i in np.argsort(-weight):
        if weight[i] <= 0 or len(out) >= n:
            break
        if any(min(abs(i - j), 24 - abs(i - j)) < 3 for j in used):
            continue
        sel = bins == i
        share = float(sel.sum()) / len(px)
        if share < min_share:
            continue
        used.append(int(i))
        core = p[sel][m[sel] >= np.percentile(m[sel], 70)]   # the flat colour, not its dim glow
        rgb = np.median(core, axis=0)
        out.append({"hex": hex_of(rgb), "rgb": [round(float(c)) for c in rgb], "share": round(share, 4)})
    return out


def propose_theme(palette: list[dict]) -> dict:
    """A background, ink and accent from an extracted palette, with their contrast ratios.
    The background is the largest colour; the ink is the palette colour that clears 7:1 on it,
    else near-black or near-white; the accent is the most saturated colour, pushed lighter or
    darker until it clears 3:1 on the background."""
    main = [p for p in palette if not p.get("accent")] or palette
    bg = tuple(float(c) for c in main[0]["rgb"])
    dark = contrast((245, 245, 245), bg) >= contrast((17, 17, 17), bg)
    inks = [p["rgb"] for p in main[1:] if contrast(p["rgb"], bg) >= 7 and saturation(p["rgb"]) < 0.35]
    ink = max(inks, key=lambda c: contrast(c, bg)) if inks else ((245, 245, 245) if dark else (17, 17, 17))
    # a mid-tone background cannot carry text: move it away from the ink until the ink clears 7:1
    bg_adjusted, t = False, 0.0
    away = (0, 0, 0) if dark else (255, 255, 255)
    while contrast(ink, mix(bg, away, t)) < 7 and t < 0.95:
        t += 0.05
        bg_adjusted = True
    bg = mix(bg, away, t)
    cands = [p for p in palette[1:] if saturation(p["rgb"]) >= 0.25 and chroma(p["rgb"]) >= 40]
    cands = [p for p in cands if p.get("accent")] or cands
    adjusted = False
    if cands:
        acc = max(cands, key=lambda p: saturation(p["rgb"]) * (max(p["share"], 0.003) ** 0.25))["rgb"]
        target = (255, 255, 255) if dark else (0, 0, 0)
        t = 0.0
        while contrast(mix(acc, target, t), bg) < 3 and t < 0.9:
            t += 0.05
            adjusted = True
        acc = mix(acc, target, t)
    else:
        acc = ink
    out = {"bg": hex_of(bg), "ink": hex_of(ink), "accent": hex_of(acc), "mode": "dark" if dark else "light", "accent_adjusted": adjusted, "bg_adjusted": bg_adjusted,
           "accent_found": bool(cands),
           "contrast": {"ink_on_bg": round(contrast(ink, bg), 2), "accent_on_bg": round(contrast(acc, bg), 2),
                        "ink_on_accent": round(contrast(ink, acc), 2), "bg_on_accent": round(contrast(bg, acc), 2)}}
    out["colors"] = {"bg": out["bg"], "surface": hex_of(mix(bg, ink, 0.06)), "paper": hex_of(mix(bg, ink, 0.03)), "ink": out["ink"], "fg": hex_of(mix(ink, bg, 0.06)),
                     "muted": hex_of(mix(ink, bg, 0.45)), "dim": hex_of(mix(ink, bg, 0.65)), "accent": out["accent"]}
    return out


def diff_regions(a, b, tol: int = 24, cell: int = 16) -> dict:
    """What changed between two same-size frames: the share of changed pixels, a boolean mask,
    and the boxes [x, y, w, h] of the changed areas (changed cells merged when they touch)."""
    import numpy as np
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > tol
    H, W = d.shape
    gh, gw = -(-H // cell), -(-W // cell)
    grid = np.zeros((gh, gw), dtype=bool)
    for gy in range(gh):
        for gx in range(gw):
            grid[gy, gx] = d[gy * cell:(gy + 1) * cell, gx * cell:(gx + 1) * cell].mean() > 0.04
    seen, boxes = np.zeros_like(grid), []
    for gy in range(gh):
        for gx in range(gw):
            if not grid[gy, gx] or seen[gy, gx]:
                continue
            stack, x0, y0, x1, y1 = [(gy, gx)], gx, gy, gx, gy
            seen[gy, gx] = True
            while stack:
                cy, cx = stack.pop()
                x0, y0, x1, y1 = min(x0, cx), min(y0, cy), max(x1, cx), max(y1, cy)
                for ny in (cy - 1, cy, cy + 1):
                    for nx in (cx - 1, cx, cx + 1):
                        if 0 <= ny < gh and 0 <= nx < gw and grid[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            boxes.append([x0 * cell, y0 * cell, min(W, (x1 + 1) * cell) - x0 * cell, min(H, (y1 + 1) * cell) - y0 * cell])
    boxes.sort(key=lambda r: -r[2] * r[3])
    return {"changed": round(float(d.mean()), 4), "mask": d, "boxes": boxes}


# ------------------------------------------------------------------ drawing helpers
def font(size: int, weight: int = 700):
    """The skill's own Inter (from node_modules) for labels; Pillow's built-in font when it is missing."""
    from PIL import ImageFont
    for ext in ("woff2", "woff"):
        f = SKILL / "node_modules" / "@fontsource" / "inter" / "files" / f"inter-latin-{weight}-normal.{ext}"
        if f.exists():
            try:
                return ImageFont.truetype(str(f), size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def text_w(draw, s: str, f) -> int:
    b = draw.textbbox((0, 0), s, font=f)
    return b[2] - b[0]


def fit_label(draw, s: str, f, width: int) -> str:
    if text_w(draw, s, f) <= width:
        return s
    while len(s) > 1 and text_w(draw, s + "…", f) > width:
        s = s[:-1]
    return s + "…"


def dashed(draw, p0, p1, fill, width: int = 2, dash: int = 14, gap: int = 10) -> None:
    (x0, y0), (x1, y1) = p0, p1
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if length <= 0:
        return
    dx, dy = (x1 - x0) / length, (y1 - y0) / length
    t = 0.0
    while t < length:
        e = min(length, t + dash)
        draw.line([(x0 + dx * t, y0 + dy * t), (x0 + dx * e, y0 + dy * e)], fill=fill, width=width)
        t = e + gap


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


# ------------------------------------------------------------------ probe
def ensure_timeline(project: Path, platform: str) -> dict:
    f = project / "build" / f"timeline-{platform}.json"
    srcs = [project / n for n in ("storyboard.yaml", "brief.yaml") if (project / n).exists()]
    if not f.exists() or any(x.stat().st_mtime > f.stat().st_mtime for x in srcs):     # never judge a stale timeline
        import storyboard as sbmod
        sbmod.build(project, quiet=True)
    if not f.exists():
        raise FishError(f"no timeline for {platform!r}: is it in brief.platforms?")
    return load_json(f)


def probe(project: Path, platform: str, *, scenes: list[str] | None = None, at: list[float] | None = None, k: float = 0.8,
          scale: float = 1.0, mode: str = "lint", out: Path | None = None) -> dict:
    """Render stills and collect their text elements (designprobe.mjs)."""
    args = [project, "--platform", platform, "--mode", mode, "--scale", scale, "--k", k]
    args += ["--at", ",".join(str(t) for t in at)] if at else ["--scenes"]
    if scenes:
        args += ["--scene", ",".join(scenes)]
    if out:
        args += ["--out", out]
    r = node("designprobe.mjs", *args, capture=True, check=False)
    res = last_json_line(r.stdout or "") or {}
    if r.returncode != 0 or not res.get("probe"):
        raise FishError(f"design probe failed: {((r.stderr or '') + (r.stdout or ''))[-600:]}")
    return load_json(res["probe"])


def first_platform(project: Path, platform: str | None) -> str:
    import storyboard as sbmod
    return platform or sbmod.platforms_of(project_config(project))[0]


# ------------------------------------------------------------------ frame lint
def rules_for(brief: dict) -> dict:
    over = ((brief.get("design") or {}).get("lint") or {}) if isinstance(brief.get("design"), dict) else {}
    r = copy.deepcopy(RULES)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(r.get(k), dict):
            r[k].update(v)
        else:
            r[k] = v
    return r


def _hexes(obj) -> list[tuple]:
    """Every hex colour written anywhere in a scene (its params, its accent)."""
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += _hexes(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out += _hexes(v)
    elif isinstance(obj, str):
        out += [parse_color(m)[:3] for m in re.findall(r"#[0-9a-fA-F]{6}\b", obj)]
    return out


def analyse_frame(img, frame: dict, *, W: int, H: int, colors: dict, scene: dict | None = None, rules: dict | None = None) -> list[dict]:
    """The findings for one probed frame. `img` is the still at stage size (HxWx3), `frame` one
    entry of probe.json, `colors` the theme palette, `scene` the timeline scene (for its own colours)."""
    R = rules or RULES
    u = min(W, H) / 1080
    mode = "land" if W > H * 1.05 else "port" if H > W * 1.05 else "square"
    sid, t = frame.get("scene"), frame.get("t")
    out: list[dict] = []

    def add(kind, sev, text, detail, fix, **kw):
        out.append({"scene": sid, "t": t, "kind": kind, "severity": sev, "text": text, "detail": detail, "fix": fix, **kw})

    texts = [x for x in frame.get("texts", []) if x.get("px", 0) > 0 and x.get("box")]
    pal = {k: parse_color(v)[:3] for k, v in (colors or {}).items() if isinstance(v, str) and parse_color(v)}
    inks = [pal[k] for k in ("ink", "fg", "bg") if k in pal] + [(255, 255, 255), (11, 11, 11)]
    scene_cols = _hexes(scene or {})

    # contrast against the pixels behind each text
    seen = set()
    for x in texts:
        col = parse_color(x.get("color"))
        m = text_contrast(img, x["box"], col)
        if m.get("ratio") is None:
            continue
        large = x["px"] >= R["large_px"] * u
        need = R["contrast_large"] if large else R["contrast_small"]
        key = (x["text"], m.get("text"), m.get("bg"))
        if key in seen:
            continue
        seen.add(key)
        if m["ratio"] < need:
            bgc = parse_color(m["bg"])[:3]
            hx, r = best_ink(bgc, inks)
            add("low-contrast", "warn", x["text"], f"{m['ratio']}:1 ({m['text']} on {m['bg']}); {'large' if large else 'small'} text needs {need}:1",
                f"use {hx} ({r}:1 on that background), or put a solid plate behind the words", ratio=m["ratio"], box=x["box"])
        elif m.get("worst") is not None and m["worst"] < R["busy_worst"]:
            add("busy-background", "note", x["text"], f"median {m['ratio']}:1, but the worst tenth of the background is {m['worst']}:1",
                "add a plate, a scrim or a text shadow so every part of the word clears the picture", ratio=m["worst"], box=x["box"])

    # hierarchy
    sizes = sorted({round(x["px"]) for x in texts})
    if len(sizes) >= 2:
        hero, small = sizes[-1], sizes[0]
        ratio = hero / max(1, small)
        if ratio < R["hierarchy_warn"]:
            add("flat-hierarchy", "warn", f"{hero} px vs {small} px", f"hero text is {ratio:.1f}x the small text; the bible asks for about 3x",
                f"raise the hero to about {small * 3} px, or drop the small text to about {max(1, round(hero / 3))} px", ratio=round(ratio, 2))
        elif ratio < R["hierarchy_note"]:
            add("flat-hierarchy", "note", f"{hero} px vs {small} px", f"hero text is {ratio:.1f}x the small text; the bible asks for about 3x",
                "consider one clearly dominant word", ratio=round(ratio, 2))
    if len(sizes) > R["max_sizes"]:
        add("too-many-sizes", "note", ", ".join(f"{s} px" for s in sizes), f"{len(sizes)} type sizes in one frame", f"use at most {R['max_sizes']}: hero, sub, label, small")

    # words on screen
    words = sum(x.get("words", 0) for x in texts)
    if words > R["max_words"][mode]:
        add("wall-of-text", "warn", f"{words} words", f"{words} words on screen (limit {R['max_words'][mode]} for this shape)",
            "on-screen text is a subset of the narration: cut to the hero words, split the scene, or reveal lines one at a time")
    for x in texts:
        if x.get("words", 0) > R["max_words_one"]:
            add("wall-of-text", "warn", x["text"], f"one element holds {x['words']} words", "no sentence on screen: keep each line to 6 words or fewer")

    # palette discipline
    allowed = list(pal.values()) + scene_cols
    seen_cols = set()
    for x in texts:
        col = parse_color(x.get("color"))
        if not col or col[3] < 0.5 or chroma(col) < 28:
            continue
        hx = hex_of(col)
        if hx in seen_cols:
            continue
        seen_cols.add(hx)
        if allowed and min(delta_e(col, a) for a in allowed) > 22:
            near = min(pal.items(), key=lambda kv: delta_e(col, kv[1])) if pal else None
            add("off-palette-text", "warn", x["text"], f"{hx} is not in the palette" + (f" (nearest: {near[0]} {hex_of(near[1])})" if near else ""),
                "use the accent, or set the colour on the scene on purpose (accent: '#rrggbb')", color=hx)
    acc = [c for c in ([pal.get("accent")] + scene_cols) if c]
    if acc and all(color_share(img, c, 70) < R["accent_share"] for c in acc):
        add("no-accent", "note", "", f"the accent {hex_of(acc[0])} is not visible in this frame", "bible: the accent appears in every scene, on the word or shape that matters")

    # empty quarters
    for q in empty_quadrants(img, R["flat_std"]):
        add("empty-quadrant", "warn", q, f"the {q} quarter of the frame is flat", "scale the subject up, move an element into the gap, or reframe")

    # edges and collisions
    edge = R["edge"] * min(W, H)
    for x in texts:
        if x.get("free"):
            continue
        bx, by, bw, bh = x["box"]
        gap = min(bx, by, W - (bx + bw), H - (by + bh))
        if 0 <= gap < edge:
            add("edge-crowding", "warn", x["text"], f"{gap:.0f} px from the frame edge (keep at least {edge:.0f})", "pull the text inside the safe area", box=x["box"])
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            if round(a["px"]) == round(b["px"]):
                continue  # words and lines of one headline share a size and overlap by design
            ax, ay, aw, ah = a["box"]
            bx, by, bw, bh = b["box"]
            ox, oy = min(ax + aw, bx + bw) - max(ax, bx), min(ay + ah, by + bh) - max(ay, by)
            if ox > 0 and oy > 0 and ox * oy > 0.15 * min(aw * ah, bw * bh):
                add("text-collision", "warn", a["text"], f"overlaps \"{b['text'][:30]}\"", "give each text block its own space", box=a["box"])

    # the stage's own legibility lint
    fixes = {"too-small": "raise the size to the platform minimum", "outside-safe-area": "move it inside the platform safe area", "off-stage": "it leaves the frame: move or shrink it",
             "clipped": "the text is cut by its own box: shorten it or widen the box", "text-overlap": "two labels overlap: move one", "text-over-item": "a label sits on the subject: move it off",
             "outside-title-safe": "keep titles inside the title-safe area (the inner 80%): a TV or an app bar can trim the rest"}
    for it in frame.get("issues", []):
        add("stage:" + it["kind"], "note" if it.get("severity") == "warn" else "warn", it.get("text", ""),
            (("px " + str(it["px"])) if it.get("px") else f"at x {it['box'][0]:.0f}, y {it['box'][1]:.0f}" if it.get("box") else it["kind"]), fixes.get(it["kind"], "see the scene catalogue"))
    return [f for f in out if f["kind"] not in set(R.get("ignore") or [])]


def lint(project: Path, platform: str | None = None, scenes: list[str] | None = None, k: float = 0.8) -> dict:
    """Probe every scene of one platform and write build/<platform>/design-lint.json and .md."""
    project = ensure_project(project)
    cfg = project_config(project)
    platform = first_platform(project, platform)
    tl = ensure_timeline(project, platform)
    rules = rules_for(cfg["brief"])
    pr = probe(project, platform, scenes=scenes, k=k)
    by_id = {s["id"]: s for s in tl["scenes"]}
    colors = (tl.get("theme") or {}).get("colors") or {}
    findings, frames = [], []
    for fr in pr["frames"]:
        img = load_rgb(fr["file"])
        fs = analyse_frame(img, fr, W=pr["W"], H=pr["H"], colors=colors, scene=by_id.get(fr["scene"]), rules=rules)
        findings += fs
        frames.append({"scene": fr["scene"], "type": fr["type"], "t": fr["t"], "file": fr["file"], "texts": len(fr["texts"]),
                       "warn": sum(1 for f in fs if f["severity"] == "warn"), "note": sum(1 for f in fs if f["severity"] == "note")})
    counts: dict[str, int] = {}
    for f in findings:
        if f["severity"] == "warn":
            counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    rep = {"platform": platform, "W": pr["W"], "H": pr["H"], "scenes": len(frames), "frames": frames, "findings": findings, "warnings": counts,
           "status": "WARN" if counts else "PASS", "stage_errors": pr.get("errors") or []}
    b = project / "build" / platform
    save_json(b / "design-lint.json", rep)
    md = [f"# Frame lint: {platform} ({pr['W']}x{pr['H']})", "", f"{len(frames)} scenes, {sum(counts.values())} warnings, {sum(1 for f in findings if f['severity'] == 'note')} notes.", ""]
    for fr in frames:
        fs = [f for f in findings if f["scene"] == fr["scene"]]
        md += [f"## {fr['scene']} ({fr['type']}, {mmss(fr['t'])})", ""]
        md += [f"- **{f['severity']}** `{f['kind']}` {('“' + f['text'] + '”: ') if f['text'] else ''}{f['detail']}. Fix: {f['fix']}." for f in fs] or ["- nothing found"]
        md.append("")
    (b / "design-lint.md").write_text("\n".join(md), encoding="utf-8")
    return rep


def qa_row(project: Path, platform: str) -> dict:
    """The `frame lint` row of the QA report. Advice only: never a FAIL."""
    try:
        rep = lint(project, platform)
    except Exception as e:  # a design probe must never break QA
        return {"check": "frame lint", "status": "WARN", "detail": f"could not run: {str(e)[:120]}"}
    if not rep["warnings"]:
        return {"check": "frame lint", "status": "PASS", "detail": f"{rep['scenes']} scenes, no design warnings"}
    top = ", ".join(f"{n} {k}" for k, n in sorted(rep["warnings"].items(), key=lambda kv: -kv[1])[:5])
    return {"check": "frame lint", "status": "WARN", "detail": f"{sum(rep['warnings'].values())} design warnings ({top}); see build/{platform}/design-lint.md"}


# ------------------------------------------------------------------ frame sheet
def sheet(project: Path, platform: str | None = None, cols: int | None = None, k: float = 0.8) -> Path:
    """One labelled hero frame per scene: build/<platform>/design/sheet.png."""
    from PIL import Image, ImageDraw
    project = ensure_project(project)
    platform = first_platform(project, platform)
    tl = ensure_timeline(project, platform)
    W, H = tl["W"], tl["H"]
    cw = 480 if W > H * 1.05 else 270 if H > W * 1.05 else 360
    pr = probe(project, platform, k=k, scale=round(cw / W, 4), mode="render", out=project / "build" / platform / "design" / "sheet")
    frames = pr["frames"]
    cols = cols or (4 if W > H * 1.05 else 6 if H > W * 1.05 else 5)
    cols = max(1, min(cols, len(frames)))
    ch, pad, lab, head = round(cw * H / W), 18, 54, 78
    rows = -(-len(frames) // cols)
    out = Image.new("RGB", (pad + cols * (cw + pad), head + rows * (ch + lab + pad) + pad), (20, 20, 22))
    d = ImageDraw.Draw(out)
    f1, f2, f3 = font(26, 800), font(17, 700), font(14, 500)
    d.text((pad, 20), fit_label(d, tl.get("title") or project.name, f1, out.width - 2 * pad - 360), font=f1, fill=(245, 245, 245))
    meta = f"{platform} · {W}x{H} · {len(frames)} scenes · {mmss(tl['duration'])}"
    d.text((out.width - pad - text_w(d, meta, f3), 30), meta, font=f3, fill=(160, 160, 165))
    for i, fr in enumerate(frames):
        x, y = pad + (i % cols) * (cw + pad), head + (i // cols) * (ch + lab + pad)
        with Image.open(fr["file"]) as im:
            out.paste(im.convert("RGB").resize((cw, ch), Image.LANCZOS), (x, y))
        d.rectangle([x - 1, y - 1, x + cw, y + ch], outline=(70, 70, 76))
        d.text((x, y + ch + 8), fit_label(d, f"{i + 1:02d} · {fr['scene']}", f2, cw), font=f2, fill=(245, 245, 245))
        d.text((x, y + ch + 31), fit_label(d, f"{fr['type']} · {mmss(fr['t'])} · {fr['t1'] - fr['t0']:.1f} s", f3, cw), font=f3, fill=(160, 160, 165))
    dest = project / "build" / platform / "design" / "sheet.png"
    out.save(dest)
    return dest


# ------------------------------------------------------------------ frame guides
BAND_COLORS = [(255, 92, 92), (92, 200, 255), (170, 255, 120), (255, 200, 80), (220, 140, 255)]


def draw_guides(img, safe: dict, *, bands: dict[str, dict] | None = None, caption_h: int = 0, label: str = ""):
    """Overlay the safe area, action-safe 90 %, title-safe 80 %, thirds and UI bands on a frame.
    img is a PIL image at stage size; safe is {top, right, bottom, left} in px. Returns a new image."""
    from PIL import Image, ImageDraw
    W, H = img.size
    u = min(W, H) / 1080
    base = img.convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f = font(max(14, round(22 * u)), 700)
    sx0, sy0, sx1, sy1 = safe["left"], safe["top"], W - safe["right"], H - safe["bottom"]
    # the platform's UI bands: everything outside the safe area
    for box in ([0, 0, W, sy0], [0, sy1, W, H], [0, sy0, sx0, sy1], [sx1, sy0, W, sy1]):
        if box[2] > box[0] and box[3] > box[1]:
            d.rectangle(box, fill=(255, 60, 60, 34))
    lw = max(2, round(3 * u))
    for i in (1, 2):
        d.line([(W * i / 3, 0), (W * i / 3, H)], fill=(255, 255, 255, 110), width=max(1, lw // 2))
        d.line([(0, H * i / 3), (W, H * i / 3)], fill=(255, 255, 255, 110), width=max(1, lw // 2))
    for share, col in ((0.05, (255, 210, 60, 230)), (0.10, (120, 220, 255, 230))):
        x0, y0, x1, y1 = W * share, H * share, W * (1 - share), H * (1 - share)
        for p0, p1 in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            dashed(d, p0, p1, col, lw, round(18 * u), round(12 * u))
    d.rectangle([sx0, sy0, sx1, sy1], outline=(80, 255, 140, 255), width=lw + 1)
    if caption_h:
        d.rectangle([sx0, sy1 - caption_h, sx1, sy1], fill=(80, 140, 255, 60), outline=(80, 140, 255, 220), width=lw)
    legend = [((80, 255, 140), f"safe area{(' · ' + label) if label else ''}"), ((255, 60, 60), "outside it: platform UI"), ((255, 210, 60), "action-safe 90%"), ((120, 220, 255), "title-safe 80%"), ((255, 255, 255), "thirds")]
    if caption_h:
        legend.append(((80, 140, 255), "caption band"))
    for n, (name, m) in enumerate((bands or {}).items()):
        col = BAND_COLORS[n % len(BAND_COLORS)]
        d.rectangle([m["left"], m["top"], W - m["right"], H - m["bottom"]], outline=(*col, 255), width=lw)
        legend.append((col, f"{name} safe area"))
    out = Image.alpha_composite(base, ov)
    d = ImageDraw.Draw(out)
    lh = round(f.size * 1.5)
    bw = max(text_w(d, t, f) for _, t in legend) + round(56 * u)
    # the legend goes bottom-left, where a frame is least likely to carry its message
    bh = lh * len(legend) + round(14 * u)
    x, y = round(14 * u), H - bh - round(14 * u)
    d.rectangle([x, y, x + bw, y + bh], fill=(12, 12, 14))
    for i, (col, t) in enumerate(legend):
        yy = y + round(8 * u) + i * lh
        d.rectangle([x + round(12 * u), yy + f.size * 0.25, x + round(34 * u), yy + f.size * 0.95], fill=col)
        d.text((x + round(44 * u), yy), t, font=f, fill=(245, 245, 245))
    return out.convert("RGB")


def guides(project: Path, scene: str, platform: str | None = None, bands: list[str] | None = None) -> Path:
    from PIL import Image
    project = ensure_project(project)
    cfg = project_config(project)
    platform = first_platform(project, platform)
    tl = ensure_timeline(project, platform)
    pr = probe(project, platform, scenes=[scene], mode="render", out=project / "build" / platform / "design" / "guides")
    fr = pr["frames"][0]
    W, H = tl["W"], tl["H"]
    safe = tl.get("safe") or {"top": 60, "right": 60, "bottom": 60, "left": 60}
    other = {}
    for name in bands or []:
        prof = cfg["platforms"].get(name)
        if not prof:
            raise FishError(f"unknown platform {name!r} for --bands (known: {', '.join(sorted(cfg['platforms']))})")
        if abs(prof["W"] / prof["H"] - W / H) > 0.02:
            warn(f"{name} is {prof['W']}x{prof['H']}: a different shape from {platform}, skipped")
            continue
        s = prof["W"] / W
        other[name] = {k: round(v / s) for k, v in prof["safe"].items()}
    cap = tl.get("captions") or {}
    style = cap.get("style") if isinstance(cap.get("style"), str) else "karaoke"
    cap_h = (cap.get("reserve") or round(H * (0.1 if style == "pop" else 0.12 if style == "minimal" else 0.17))) if cap.get("burn") and style != "none" else 0
    with Image.open(fr["file"]) as im:
        out = draw_guides(im, safe, bands=other, caption_h=cap_h, label=platform)
    dest = project / "build" / platform / "design" / f"guides-{re.sub(r'[^\w.-]+', '_', scene)}.png"
    out.save(dest)
    return dest


# ------------------------------------------------------------------ frame variants
TYPE_FACES = {"grotesk": "Inter", "editorial": "Fraunces", "hand": "Caveat", "mono": "JetBrains Mono"}
TEXTURES = ["clean", "grain", "paper", "grid", "blueprint"]


def variant_specs(vary: str, tl: dict, brief: dict) -> list[dict]:
    """The variants of one kind: [{name, patch}] where patch is applied to a timeline copy."""
    styles = load_yaml(SKILL / "config" / "styles.yaml")
    out = [{"name": "current", "patch": {}}]
    if vary == "palette":
        for name, p in styles["palettes"].items():
            if p.get("colors"):
                out.append({"name": name, "patch": {"theme": {"colors": dict(p["colors"]), "mode": p.get("mode", "light")}}, "brief": {"palette": name, "brand": {"colors": dict(p["colors"]), "mode": p.get("mode", "light")}}})
    elif vary == "texture":
        for name in TEXTURES:
            if name != tl.get("texture"):
                out.append({"name": name, "patch": {"texture": name}, "brief": {"texture": name}})
    elif vary == "type":
        cur = ((tl.get("theme") or {}).get("fonts") or {}).get("display") or "Inter"
        for feel, face in TYPE_FACES.items():
            if face != cur:
                out.append({"name": f"{feel} ({face})", "patch": {"theme": {"fonts": {"display": face}}}, "brief": {"type_feel": feel, "brand": {"fonts": {"display": face}}}})
    else:
        raise FishError("--vary must be palette, texture or type")
    return out


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = copy.deepcopy(v)
    return base


def variants(project: Path, scene: str, vary: str, platform: str | None = None, apply: int | None = None) -> dict:
    """Render one scene in several palettes, textures or type faces, side by side and numbered.
    With apply=N the chosen variant is written to brief.yaml and the timelines are rebuilt."""
    from PIL import Image, ImageDraw
    project = ensure_project(project)
    cfg = project_config(project)
    platform = first_platform(project, platform)
    tl = ensure_timeline(project, platform)
    sc = next((s for s in tl["scenes"] if s["id"] == scene), None)
    if not sc:
        raise FishError(f"no scene {scene!r} (scenes: {', '.join(s['id'] for s in tl['scenes'])})")
    specs = variant_specs(vary, tl, cfg["brief"])
    if apply is not None:
        if not 1 <= apply <= len(specs):
            raise FishError(f"--apply must be 1 to {len(specs)}")
        pick = specs[apply - 1]
        if not pick.get("brief"):
            log("variant 1 is the current look: nothing to change")
            return {"applied": pick["name"]}
        brief = load_yaml(project / "brief.yaml")
        _merge(brief, pick["brief"])
        save_yaml(project / "brief.yaml", brief)
        sb = load_yaml(project / "storyboard.yaml") if (project / "storyboard.yaml").exists() else {}
        if vary == "texture" and sb.get("texture"):
            warn(f"storyboard.yaml sets texture: {sb['texture']}, which overrides the brief; change it there too")
        import storyboard as sbmod
        sbmod.build(project, quiet=True)
        log(f"applied {vary}: {pick['name']} (brief.yaml updated, timelines rebuilt)")
        return {"applied": pick["name"]}
    t = round(sc["t0"] + (sc["t1"] - sc["t0"]) * 0.8, 3)
    W, H = tl["W"], tl["H"]
    cw = 560 if W > H * 1.05 else 300 if H > W * 1.05 else 420
    ddir = project / "build" / platform / "design" / "variants"
    ddir.mkdir(parents=True, exist_ok=True)
    cells = []
    for n, sp in enumerate(specs, 1):
        name = f"{platform}--v{n}"
        v = _merge(copy.deepcopy(tl), sp["patch"])
        save_json(project / "build" / f"timeline-{name}.json", v)
        f = ddir / f"{re.sub(r'[^\w.-]+', '_', scene)}-{vary}-{n}.png"
        try:
            r = node("stills.mjs", project, "--platform", name, "--at", t, "--out", f, "--scale", round(cw / W, 4), capture=True, check=False)
        finally:
            (project / "build" / f"timeline-{name}.json").unlink(missing_ok=True)
            shutil.rmtree(project / "build" / name, ignore_errors=True)  # the empty stills folder stills.mjs makes
        if f.exists():
            cells.append((n, sp["name"], f))
        else:
            warn(f"variant {n} ({sp['name']}) did not render: {(r.stderr or '')[-200:]}")
    if not cells:
        raise FishError("no variant rendered")
    if len(cells) > 1:
        ref = load_rgb(cells[0][2])
        moved = [diff_regions(ref, load_rgb(c[2]))["changed"] for c in cells[1:] if load_rgb(c[2]).shape == ref.shape]
        if moved and max(moved) < 0.01:
            warn(f"all {vary} variants of {scene!r} look the same: this scene draws its own backdrop or look, so {vary} changes nothing here; try another scene")
    ch, pad, lab = round(cw * H / W), 18, 46
    cols = min(len(cells), 4 if W > H * 1.05 else 6)
    rows = -(-len(cells) // cols)
    out = Image.new("RGB", (pad + cols * (cw + pad), pad + rows * (ch + lab + pad)), (20, 20, 22))
    d = ImageDraw.Draw(out)
    f2 = font(20, 800)
    for i, (n, name, f) in enumerate(cells):
        x, y = pad + (i % cols) * (cw + pad), pad + (i // cols) * (ch + lab + pad)
        with Image.open(f) as im:
            out.paste(im.convert("RGB").resize((cw, ch), Image.LANCZOS), (x, y))
        d.rectangle([x - 1, y - 1, x + cw, y + ch], outline=(70, 70, 76))
        d.text((x, y + ch + 10), fit_label(d, f"{n} · {name}", f2, cw), font=f2, fill=(245, 245, 245))
    dest = ddir / f"{re.sub(r'[^\w.-]+', '_', scene)}-{vary}.png"
    out.save(dest)
    return {"sheet": str(dest), "scene": scene, "vary": vary, "variants": [{"n": n, "name": name, "file": str(f)} for n, name, f in cells]}


# ------------------------------------------------------------------ frame palette
def video_frames(path: Path, n: int = 6, at: list[float] | None = None) -> list:
    """n frames spread through a video (or the frames at the given times), as HxWx3 arrays."""
    import numpy as np
    pr = subprocess.run([ffprobe_bin(), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
                        capture_output=True, text=True, check=True)
    info = json.loads(pr.stdout)
    W, H = info["streams"][0]["width"], info["streams"][0]["height"]
    dur = float(info["format"].get("duration") or 0)
    times = at or [dur * (i + 0.5) / n for i in range(n)]
    out = []
    for t in times:
        r = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        if len(r.stdout) >= W * H * 3:
            out.append(np.frombuffer(r.stdout[: W * H * 3], dtype=np.uint8).reshape(H, W, 3).copy())
    if not out:
        raise FishError(f"could not read frames from {path}")
    return out


def palette(src: Path, colors: int = 8, write: Path | None = None, out: Path | None = None) -> dict:
    """Extract a palette from an image or a video, propose bg / ink / accent with contrast ratios,
    draw a swatch sheet next to the source, and optionally write the colours to a project's brief."""
    import numpy as np
    from PIL import Image, ImageDraw
    src = Path(src)
    if not src.exists():
        raise FishError(f"missing file: {src}")
    if src.suffix.lower() in VIDEO_EXT:
        frames = video_frames(src)
        small = [np.asarray(Image.fromarray(f).resize((160, max(1, round(160 * f.shape[0] / f.shape[1])))), dtype=np.uint8) for f in frames]
        img = np.concatenate(small, axis=0)
    else:
        img = load_rgb(src)
    pal = extract_palette(img, colors)
    prop = propose_theme(pal)
    sw, sh, pad = 150, 110, 20
    sheet_img = Image.new("RGB", (pad * 2 + max(len(pal) * sw, 1040), pad * 3 + sh + 250), (24, 24, 26))
    d = ImageDraw.Draw(sheet_img)
    f1, f2 = font(18, 700), font(15, 500)
    for i, p in enumerate(pal):
        x = pad + i * sw
        d.rectangle([x, pad, x + sw - 8, pad + sh], fill=tuple(p["rgb"]))
        tc = (17, 17, 17) if rel_lum(p["rgb"]) > 0.4 else (245, 245, 245)
        d.text((x + 10, pad + 10), p["hex"], font=f1, fill=tc)
        d.text((x + 10, pad + 36), (f"{p['share'] * 100:.1f}% · accent" if p.get("accent") else f"{p['share'] * 100:.0f}%"), font=f2, fill=tc)
    y = pad * 2 + sh
    bg, ink, acc = (parse_color(prop[k])[:3] for k in ("bg", "ink", "accent"))
    d.rectangle([pad, y, sheet_img.width - pad, y + 230], fill=tuple(round(c) for c in bg))
    d.text((pad + 24, y + 20), "Proposed theme", font=f2, fill=tuple(round(c) for c in mix(ink, bg, 0.4)))
    d.text((pad + 24, y + 48), "Ink on background", font=font(54, 900), fill=tuple(round(c) for c in ink))
    d.rectangle([pad + 24, y + 128, pad + 330, y + 196], fill=tuple(round(c) for c in acc))
    on_acc = ink if contrast(ink, acc) >= contrast(bg, acc) else bg
    d.text((pad + 44, y + 142), "Accent", font=font(34, 900), fill=tuple(round(c) for c in on_acc))
    c = prop["contrast"]
    notes = [f"bg {prop['bg']} · ink {prop['ink']} ({c['ink_on_bg']}:1) · accent {prop['accent']} ({c['accent_on_bg']}:1) · mode {prop['mode']}"]
    if prop["bg_adjusted"]:
        notes.append("background moved so the ink clears 7:1")
    if prop["accent_adjusted"]:
        notes.append("accent adjusted to reach 3:1 on the background")
    if not prop["accent_found"]:
        notes.append("no saturated colour found: accent = ink")
    for i, line in enumerate(notes):
        d.text((pad + 360, y + 128 + i * 24), fit_label(d, line, f2, sheet_img.width - pad * 2 - 380), font=f2, fill=tuple(round(v) for v in ink))
    dest = Path(out) if out else src.with_name(src.stem + "-palette.png")
    sheet_img.save(dest)
    res = {"source": str(src), "palette": pal, "proposal": prop, "sheet": str(dest)}
    if write:
        project = ensure_project(write)
        brief = load_yaml(project / "brief.yaml")
        brand = brief.setdefault("brand", {})
        brand["colors"] = {**(brand.get("colors") or {}), **prop["colors"]}
        brand["mode"] = prop["mode"]
        brief["palette"] = "brand"
        save_yaml(project / "brief.yaml", brief)
        res["written"] = str(project / "brief.yaml")
    return res


# ------------------------------------------------------------------ frame compare
def _frames_of(src: Path, at: list[float] | None) -> list[tuple[str, object]]:
    if src.is_dir():
        files = sorted(f for f in src.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
        return [(f.name, load_rgb(f)) for f in files]
    if src.suffix.lower() in VIDEO_EXT:
        times = at or None
        fr = video_frames(src, 4, times)
        names = [f"{t:.2f}s" for t in times] if times else [f"frame {i + 1}" for i in range(len(fr))]
        return list(zip(names, fr))
    return [(src.name, load_rgb(src))]


def compare(a: Path, b: Path, at: list[float] | None = None, out: Path | None = None, tol: int = 24) -> dict:
    """A before/after sheet: A, B and a difference map per pair, with the share of changed pixels.
    a and b are two stills, two videos (sampled at --at, or at four points) or two folders of stills."""
    import numpy as np
    from PIL import Image, ImageDraw
    a, b = Path(a), Path(b)
    for f in (a, b):
        if not f.exists():
            raise FishError(f"missing: {f}")
    fa, fb = _frames_of(a, at), _frames_of(b, at)
    n = min(len(fa), len(fb))
    if not n:
        raise FishError("nothing to compare")
    cw, pad, lab = 520, 16, 40
    rows, results = [], []
    for i in range(n):
        (na, ia), (nb, ib) = fa[i], fb[i]
        resized = ia.shape != ib.shape
        if resized:
            ib = np.asarray(Image.fromarray(ib).resize((ia.shape[1], ia.shape[0]), Image.LANCZOS))
        df = diff_regions(ia, ib, tol)
        grey = np.repeat((np.asarray(Image.fromarray(ia).convert("L"), dtype=np.float32) * 0.35 + 30)[..., None], 3, axis=2).astype(np.uint8)
        grey[df["mask"]] = (255, 40, 200)
        heat = Image.fromarray(grey)
        hd = ImageDraw.Draw(heat)
        for x, y, w, h in df["boxes"][:12]:
            hd.rectangle([x, y, x + w - 1, y + h - 1], outline=(255, 235, 60), width=max(2, ia.shape[1] // 480))
        rows.append((na, nb, Image.fromarray(ia), Image.fromarray(ib), heat, df["changed"], resized))
        results.append({"a": na, "b": nb, "changed": df["changed"], "boxes": df["boxes"][:12], "resized": resized})
    ch = round(cw * rows[0][2].height / rows[0][2].width)
    sheet_img = Image.new("RGB", (pad + 3 * (cw + pad), pad + n * (ch + lab + pad)), (20, 20, 22))
    d = ImageDraw.Draw(sheet_img)
    f2 = font(17, 700)
    for i, (na, nb, ia, ib, heat, changed, resized) in enumerate(rows):
        y = pad + i * (ch + lab + pad)
        for j, (im, name) in enumerate(((ia, f"A · {na}"), (ib, f"B · {nb}" + (" (resized)" if resized else "")), (heat, f"difference · {changed * 100:.1f}% of pixels changed"))):
            x = pad + j * (cw + pad)
            sheet_img.paste(im.resize((cw, ch), Image.LANCZOS), (x, y))
            d.text((x, y + ch + 8), fit_label(d, name, f2, cw), font=f2, fill=(245, 245, 245))
    dest = Path(out) if out else a.with_name(f"{a.stem}-vs-{b.stem}.png")
    sheet_img.save(dest)
    return {"sheet": str(dest), "pairs": results}


# ------------------------------------------------------------------ CLI
def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fishvideo frame", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sheet"); p.add_argument("project"); p.add_argument("--platform", default=None); p.add_argument("--cols", type=int, default=None)
    p = sub.add_parser("lint"); p.add_argument("project"); p.add_argument("--platform", default=None); p.add_argument("--scene", default=None); p.add_argument("--strict", action="store_true")
    p = sub.add_parser("guides"); p.add_argument("project"); p.add_argument("--scene", required=True); p.add_argument("--platform", default=None); p.add_argument("--bands", default=None)
    p = sub.add_parser("variants"); p.add_argument("project"); p.add_argument("--scene", required=True); p.add_argument("--vary", required=True, choices=["palette", "texture", "type"])
    p.add_argument("--platform", default=None); p.add_argument("--apply", type=int, default=None)
    p = sub.add_parser("palette"); p.add_argument("source"); p.add_argument("--colors", type=int, default=8); p.add_argument("--write", default=None); p.add_argument("--out", default=None)
    p = sub.add_parser("compare"); p.add_argument("a"); p.add_argument("b"); p.add_argument("--at", default=None); p.add_argument("--out", default=None); p.add_argument("--tol", type=int, default=24)
    a = ap.parse_args(argv)
    if a.cmd == "sheet":
        log(f"sheet: {sheet(Path(a.project), a.platform, a.cols)}")
    elif a.cmd == "lint":
        import storyboard as sbmod
        project = ensure_project(a.project)
        plats = a.platform.split(",") if a.platform else sbmod.platforms_of(project_config(project))
        bad = 0
        for pl in plats:
            rep = lint(project, pl, a.scene.split(",") if a.scene else None)
            bad += sum(rep["warnings"].values())
            log(f"{pl}: {rep['status']}  {rep['scenes']} scenes, {sum(rep['warnings'].values())} warnings -> build/{pl}/design-lint.md")
            for f in rep["findings"]:
                log(f"  {f['severity']:<4} {f['scene']:<14} {f['kind']:<18} {(f['text'][:28] + ': ') if f['text'] else ''}{f['detail']}\n       fix: {f['fix']}")
        return 1 if bad and a.strict else 0
    elif a.cmd == "guides":
        log(f"guides: {guides(Path(a.project), a.scene, a.platform, a.bands.split(',') if a.bands else None)}")
    elif a.cmd == "variants":
        res = variants(Path(a.project), a.scene, a.vary, a.platform, a.apply)
        if res.get("sheet"):
            log(f"variants: {res['sheet']}")
            for v in res["variants"]:
                log(f"  {v['n']}  {v['name']}")
            log(f"choose one with: fishvideo frame variants <dir> --scene {a.scene} --vary {a.vary} --apply N")
    elif a.cmd == "palette":
        res = palette(Path(a.source), a.colors, Path(a.write) if a.write else None, Path(a.out) if a.out else None)
        pr = res["proposal"]
        log("palette: " + "  ".join(f"{p['hex']} {p['share'] * 100:.0f}%" for p in res["palette"]))
        log(f"proposal: bg {pr['bg']}  ink {pr['ink']} ({pr['contrast']['ink_on_bg']}:1)  accent {pr['accent']} ({pr['contrast']['accent_on_bg']}:1)  mode {pr['mode']}"
            + ("  [background moved so the ink clears 7:1]" if pr["bg_adjusted"] else "") + ("  [accent adjusted to reach 3:1]" if pr["accent_adjusted"] else ""))
        log(f"sheet: {res['sheet']}" + (f"\nwritten to {res['written']}" if res.get("written") else ""))
    elif a.cmd == "compare":
        res = compare(Path(a.a), Path(a.b), [float(x) for x in a.at.split(",")] if a.at else None, Path(a.out) if a.out else None, a.tol)
        for pr in res["pairs"]:
            log(f"  {pr['a']} vs {pr['b']}: {pr['changed'] * 100:.1f}% of pixels changed, {len(pr['boxes'])} regions")
        log(f"compare: {res['sheet']}")
    return 0


if __name__ == "__main__":
    main_guard(cli)
