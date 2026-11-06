"""Quality gates a weaker model cannot skip: measured, not judged.

    fishvideo gates <dir> [--platform p] [--recipe r]   imagery coverage of the storyboard against the recipe's thresholds
    fishvideo signoff <dir> [--platform p]              write the frame-sheet checklist (build/<p>/review/SIGNOFF.md) to fill in
    fishvideo signoff <dir> --check                     verify the checklist is complete and newer than the last render

Imagery gate. Every scene is classified from the storyboard (never from its text):
  image    a real raster picture or footage is on screen (a jpg/png/webp/mp4 path anywhere in its params, or a footage/meme/tour scene)
  graphic  drawn visuals with no photograph (diagram, collage shapes, roadmap map, flow ...)
  text     words on a card (title, kinetic, quote, bullets, stat, statement, cards, end ...)
Measured over the timeline (or bars / dur / spoken words when no timeline exists yet):
  image_share        share of running time with an image scene on screen
  image_changes_pm   distinct images brought on screen per minute (a photo that swaps inside a scene counts each time)
  longest_no_image   longest stretch in seconds without an image
  text_share         share of running time on text cards
Thresholds live in config/recipes.yaml per recipe (tuned on the benchmark videos; see references/recipes.md).
A video with `recipe:` in its brief fails `fishvideo gate` (and so render) when a threshold is missed; without a recipe the
generic thresholds only warn. Sign-off: the frame sheet must be opened and every beat described and judged.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from fvcore import FishError, load_json, load_yaml, log, main_guard, project_config, SKILL

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".mp4", ".webm", ".mov")
IMAGE_TYPES = {"footage", "meme", "tour", "image"}
GRAPHIC_TYPES = {"collage", "diagram", "whiteboard", "neonline", "split", "chart", "glowshape", "tunnel", "ringbloom", "orbit", "cone", "coinflip", "compare", "flow", "roadmap", "terminal", "bold"}
TEXT_TYPES = {"title", "kinetic", "quote", "bullets", "stat", "end", "steps", "stepcard", "statement", "cards", "thumbnail"}
GENERIC = {"image_share_min": 0.35, "image_changes_pm_min": 4, "longest_no_image_max": 45, "text_share_max": 0.5}


def _paths(obj, out: list) -> None:
    if isinstance(obj, str):
        if obj.lower().split("?")[0].endswith(IMG_EXT):
            out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("clip",) and isinstance(v, str):
                out.append("clip:" + v)
            else:
                _paths(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _paths(v, out)


def classify(scene: dict) -> tuple[str, list[str]]:
    """(kind, distinct image sources) for one scene."""
    params = scene.get("params") or {}
    srcs: list[str] = []
    _paths(params, srcs)
    srcs = list(dict.fromkeys(srcs))
    t = scene.get("type")
    if t in IMAGE_TYPES and not srcs:
        srcs = [f"{t}:{scene.get('id')}"]
    if srcs:
        return "image", srcs
    if t in TEXT_TYPES:
        return "text", []
    return "graphic", []


def scene_times(project: Path, platform: str | None) -> tuple[list[dict], str]:
    """[{id, type, params, t0, t1}] from the built timeline, else from the storyboard (bars, dur or spoken words)."""
    bt = project / "build"
    tls = sorted(bt.glob("timeline-*.json")) if bt.exists() else []
    tls = [f for f in tls if "thumbnail" not in f.name]
    if platform:
        tls = [f for f in tls if f.name == f"timeline-{platform}.json"] or tls
    if tls:
        tl = load_json(tls[0])
        return [{"id": s["id"], "type": s["type"], "params": s.get("params") or {}, "t0": s["t0"], "t1": s["t1"]} for s in tl["scenes"]], tls[0].stem.replace("timeline-", "")
    sb = load_yaml(project / "storyboard.yaml")
    bpm = float(sb.get("bpm") or 120)
    bar = 4 * 60 / bpm
    out, t = [], 0.0
    for s in sb["scenes"]:
        say = s.get("say") or ""
        words = len(" ".join(say if isinstance(say, list) else [say]).split())
        d = float(s["dur"]) if s.get("dur") else float(s["bars"]) * bar if s.get("bars") else max(2.0, words / 2.8)
        out.append({"id": s["id"], "type": s["type"], "params": s.get("params") or {}, "t0": t, "t1": t + d})
        t += d
    return out, "storyboard"


def measure(project: Path, platform: str | None = None) -> dict:
    scenes, src = scene_times(Path(project), platform)
    total = scenes[-1]["t1"] - scenes[0]["t0"] if scenes else 0.0
    if total <= 0:
        raise FishError("the storyboard has no running time to measure")
    share = {"image": 0.0, "graphic": 0.0, "text": 0.0}
    changes, gap, longest, last_img_end = 0, 0.0, 0.0, 0.0
    rows = []
    t_prev = scenes[0]["t0"]
    for s in scenes:
        kind, srcs = classify(s)
        d = s["t1"] - s["t0"]
        share[kind] += d
        if kind == "image":
            longest = max(longest, s["t0"] - last_img_end)
            last_img_end = s["t1"]
            changes += len(srcs)
        rows.append({"id": s["id"], "type": s["type"], "kind": kind, "seconds": round(d, 2), "images": len(srcs)})
    longest = max(longest, scenes[-1]["t1"] - last_img_end)
    return {"source": src, "seconds": round(total, 1), "scenes": len(scenes), "image_share": round(share["image"] / total, 3),
            "graphic_share": round(share["graphic"] / total, 3), "text_share": round(share["text"] / total, 3),
            "image_changes_pm": round(changes / (total / 60), 1), "longest_no_image": round(longest, 1), "rows": rows}


def recipe_gate(name: str | None) -> dict:
    if not name:
        return dict(GENERIC)
    import recipes
    return {**GENERIC, **(recipes.get(name).get("gate") or {})}


def check(project: Path, platform: str | None = None, recipe: str | None = None) -> tuple[dict, list[str]]:
    """(metrics, failures). A failure line says what to change."""
    project = Path(project)
    brief = project_config(project)["brief"]
    name = recipe or brief.get("recipe")
    m = measure(project, platform)
    g = recipe_gate(name)
    f = []
    if m["image_share"] < g["image_share_min"]:
        f.append(f"images are on screen {m['image_share']:.0%} of the time; this recipe needs {g['image_share_min']:.0%}+. Put a real photo or footage (assets search/get) behind the text scenes")
    if m["image_changes_pm"] < g["image_changes_pm_min"]:
        f.append(f"a new image arrives {m['image_changes_pm']}/min; needs {g['image_changes_pm_min']}+. Use `srcs:` to swap photos inside a scene, or split long scenes")
    if m["longest_no_image"] > g["longest_no_image_max"]:
        f.append(f"{m['longest_no_image']} s pass with no image; the limit is {g['longest_no_image_max']} s. Add a photo or footage scene in that stretch")
    if m["text_share"] > g["text_share_max"]:
        f.append(f"{m['text_share']:.0%} of the time is text cards; the limit is {g['text_share_max']:.0%}. Replace text cards with `story` scenes or add imagery")
    if "graphic_share_min" in g and m["graphic_share"] + m["image_share"] < g["graphic_share_min"]:
        f.append(f"only {(m['graphic_share'] + m['image_share']):.0%} of the time shows drawn or photographic visuals; needs {g['graphic_share_min']:.0%}+")
    m["recipe"] = name or "generic"
    m["thresholds"] = g
    return m, f


# ------------------------------------------------------------------ frame-sheet sign-off
def _review_dir(project: Path, platform: str) -> Path:
    return project / "build" / platform / "review"


def signoff_template(project: Path, platform: str | None = None) -> Path:
    project = Path(project)
    scenes, src = scene_times(project, platform)
    plat = platform or (src if src != "storyboard" else "youtube")
    d = _review_dir(project, plat)
    d.mkdir(parents=True, exist_ok=True)
    lines = ["# Frame-sheet sign-off", "",
             f"Platform `{plat}`. Open the sheet(s) in `build/{plat}/review/` (run `fishvideo review {project.name} --platform {plat}` first) and the contact sheet.",
             "Fill every row. `see` = one sentence naming every object on screen (an object that needs explaining is a problem). `verdict` = ok or fix. Do not ship while any row says fix.", "",
             "Checklist (answer each with yes or the fix you made):",
             "- [ ] Every frame has a picture, footage or drawn graphic, not only words",
             "- [ ] Nothing is empty: no bare colour or blank half-frame",
             "- [ ] Hero word is 3x the small text; text is inside the safe area and not under the platform UI",
             "- [ ] Captions are legible on the busiest frame",
             "- [ ] No website screenshot is used as thumbnail or cover",
             "- [ ] Logos or photos shown relate to what the narration says at that moment", "",
             "| scene | t | kind | see | verdict |", "|---|---|---|---|---|"]
    for s in scenes:
        kind, _ = classify(s)
        lines.append(f"| {s['id']} | {s['t0']:.1f} | {kind} | TODO | TODO |")
    f = d / "SIGNOFF.md"
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f


def signoff_errors(project: Path, platform: str | None = None) -> list[str]:
    project = Path(project)
    plats = [platform] if platform else [p.parent.parent.name for p in (project / "build").glob("*/review/SIGNOFF.md")]
    if not plats:
        return ["no frame-sheet sign-off: run `fishvideo signoff <dir>`, open the frame sheet and fill build/<platform>/review/SIGNOFF.md"]
    errs = []
    for plat in plats:
        f = _review_dir(project, plat) / "SIGNOFF.md"
        if not f.exists():
            errs.append(f"{plat}: no SIGNOFF.md: run `fishvideo signoff {project.name} --platform {plat}`")
            continue
        text = f.read_text(encoding="utf-8")
        if re.search(r"- \[ \]", text):
            errs.append(f"{plat}: SIGNOFF.md still has unchecked checklist items")
        for row in [r for r in text.splitlines() if r.startswith("|") and not r.startswith("|---") and not r.startswith("| scene")]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) < 5:
                continue
            see, verdict = cells[3], cells[4].lower()
            if "todo" in see.lower() or len(see.split()) < 4:
                errs.append(f"{plat}: scene {cells[0]}: describe what you see (4+ words, name each object)")
            if verdict != "ok":
                errs.append(f"{plat}: scene {cells[0]}: verdict is '{cells[4]}', not ok")
        finals = list((project / "build" / plat).glob("final*.mp4"))
        if finals and f.stat().st_mtime < max(x.stat().st_mtime for x in finals) - 1:
            errs.append(f"{plat}: SIGNOFF.md is older than the last render: look at the new frames and sign again")
    return errs[:12]


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fishvideo gates", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("--platform", default=None); ap.add_argument("--recipe", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    m, f = check(Path(a.project), a.platform, a.recipe)
    if a.json:
        print(json.dumps({k: v for k, v in m.items() if k != "rows"}, indent=1))
    else:
        log(f"imagery ({m['recipe']}, {m['seconds']} s from {m['source']}): images {m['image_share']:.0%}, drawn {m['graphic_share']:.0%}, text {m['text_share']:.0%}; "
            f"{m['image_changes_pm']} new images/min; longest stretch without one {m['longest_no_image']} s")
        for x in f:
            log("FAIL " + x)
        if not f:
            log("PASS imagery gate")
    return 1 if f else 0


def signoff_cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fishvideo signoff")
    ap.add_argument("project"); ap.add_argument("--platform", default=None); ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        e = signoff_errors(Path(a.project), a.platform)
        for x in e:
            log("FAIL " + x)
        if not e:
            log("PASS sign-off complete")
        return 1 if e else 0
    f = signoff_template(Path(a.project), a.platform)
    log(f"checklist written: {f}\nOpen the review sheets, fill every row (see + verdict) and tick the boxes. Then: fishvideo signoff {a.project} --check")
    return 0


if __name__ == "__main__":
    main_guard(cli)
