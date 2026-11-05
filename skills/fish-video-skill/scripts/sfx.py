"""Sample-based sound effects: place real SFX files at the scene cue times.

    python scripts/sfx.py <project> --platform shorts

Sample sources, first match wins per cue type:
  <project>/assets/sfx/<type>/*.wav|mp3|ogg   (the user's or downloaded files; licences in assets/credits.json)
  <skill>/sfx/library/index.json              ({type: [files]}; Kenney CC0 packs via `fishvideo assets sfx-pack`)
Types without samples are synthesised by music.mjs (it skips the types listed in
build/<platform>/sfx-covered.json, which this script writes).

Placement rules (see references/sound-design.md):
  swish/whoosh/wipe/paper start 0.10 s BEFORE the cue; riser ENDS on the cue;
  everything else starts on the cue. No two SFX within 80 ms. Density filters as music.mjs.
Each sample is peak-normalised to its type's level (dBFS), chosen deterministically.
Output: build/<platform>/sfx-samples.wav (48 kHz stereo float).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from fvcore import SKILL, ensure_project, ffmpeg_bin, load_json, log, main_guard, save_json

SR = 48000
LEVEL_DB = {"swish": -24, "whoosh": -20, "wipe": -18, "riser": -16, "swell": -18, "impact": -13, "hit": -13, "boom": -15,
            "thump": -16, "pop": -26, "tick": -30, "click": -20, "ripple": -28, "zap": -22, "coin": -22, "paper": -24,
            "flash": -16, "typing": -26, "key": -28, "scribble": -24, "chime": -22, "enter": -24}
PRE = {"swish": 0.10, "whoosh": 0.10, "wipe": 0.12, "paper": 0.05}
SMALL = {"pop", "tick", "tok", "blips", "key", "ripple", "paper"}
BIG = {"impact", "hit", "boom", "riser", "swell", "flash", "wipe", "thump"}
EXT = (".wav", ".mp3", ".ogg", ".flac")


def library(project: Path) -> dict[str, list[Path]]:
    lib: dict[str, list[Path]] = {}
    idx = SKILL / "sfx" / "library" / "index.json"
    if idx.exists():
        data = load_json(idx) or {}
        for t, files in (data.get("cues", data) if isinstance(data, dict) else {}).items():
            if not isinstance(files, list):
                continue
            files = [x.get("file") or x.get("path") if isinstance(x, dict) else x for x in files]
            fs = [Path(f) if Path(f).is_absolute() else idx.parent / f for f in files]
            lib[t] = [f for f in fs if f.exists()]
    for pj in sorted((SKILL / "sfx" / "library").glob("*/pack.json")):  # committed packs (cue type -> files)
        for t, files in ((load_json(pj) or {}).get("cues") or {}).items():
            fs = [pj.parent / f for f in files if (pj.parent / f).is_file()]
            if fs:
                lib[t] = fs
    own = project / "assets" / "sfx"
    if own.exists():
        for d in own.iterdir():
            if d.is_dir():
                fs = sorted(f for f in d.iterdir() if f.suffix.lower() in EXT)
                if fs:
                    lib[d.name] = fs  # the project's own files override the library
    return {k: v for k, v in lib.items() if v}


def levels(project: Path) -> dict[str, float]:
    """Cue levels in dBFS. Lowest to highest precedence: built-in table, sfx/library/*/pack.json,
    <project>/assets/sfx/pack.json (written by `sounds add`), brief.mix.sfx_levels."""
    lv: dict[str, float] = dict(LEVEL_DB)
    for pj in sorted((SKILL / "sfx" / "library").glob("*/pack.json")):
        lv.update({k: float(v) for k, v in ((load_json(pj) or {}).get("levels") or {}).items()})
    pj = Path(project) / "assets" / "sfx" / "pack.json"
    if pj.exists():
        lv.update({k: float(v) for k, v in ((load_json(pj) or {}).get("levels") or {}).items()})
    if (Path(project) / "brief.yaml").exists():
        lv.update({k: float(v) for k, v in (load_brief_mix(Path(project)).get("sfx_levels") or {}).items()})
    return lv


def load_brief_mix(project: Path) -> dict:
    """brief.yaml -> mix (empty when the project has no brief)."""
    import yaml
    f = project / "brief.yaml"
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("mix") or {} if f.exists() else {}


def decode(f: Path):
    import numpy as np
    r = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(f), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True)
    a = np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).copy()
    pk = float(np.abs(a).max()) or 1.0
    return a / pk


def build(project: Path, platform: str) -> dict:
    import numpy as np
    project = ensure_project(project)
    b = project / "build" / platform
    info = load_json(b / "info.json")
    tl = load_json(project / "build" / f"timeline-{platform}.json", default={})
    density = (tl.get("sfx") or {}).get("density") or "rich"
    lib = library(project)
    # per-project levels for any cue type, including custom ones: brief.mix.sfx_levels: {trombone: -14}
    lv = levels(project)
    covered = sorted(lib)
    save_json(b / "sfx-covered.json", covered)
    if not lib:
        log(f"[{platform}] sfx: no sample library (synth SFX only). Add files to assets/sfx/<type>/ or run `fishvideo assets sfx-pack`")
        return {"covered": [], "placed": 0}
    n = int((info["duration"] + 2) * SR)
    out = np.zeros((n, 2), dtype=np.float32)
    cache: dict[Path, object] = {}
    placed, last = 0, -1.0
    cues = sorted((q for q in info.get("cues", []) if q.get("type") in lib), key=lambda q: q["t"])
    for k, q in enumerate(cues):
        typ, t = q["type"], float(q["t"])
        if density == "standard" and typ in SMALL or density == "minimal" and typ not in BIG:
            continue
        if typ != "typing" and t - last < 0.08:
            continue
        last = t
        files = lib[typ]
        f = files[int(hashlib.md5(f"{typ}{k}".encode()).hexdigest(), 16) % len(files)]
        if f not in cache:
            cache[f] = decode(f)
        a = cache[f]
        if typ == "typing" and q.get("len"):
            a = a[: int(q["len"] * SR)]
        g = 10 ** (float(lv.get(typ, -22)) / 20)
        start = t - len(a) / SR if typ == "riser" else t - PRE.get(typ, 0.0)
        i0 = max(0, int(start * SR))
        seg = a[: max(0, min(len(a), n - i0))]
        out[i0:i0 + len(seg)] += seg * g
        placed += 1
    wav = b / "sfx-samples.wav"
    pcm = np.clip(out, -1, 1).astype("<f4").tobytes()
    import struct
    hdr = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 3, 2, SR, SR * 8, 8, 32) + b"data" + struct.pack("<I", len(pcm))
    wav.write_bytes(hdr + pcm)
    log(f"[{platform}] sfx: placed {placed} sample cues ({', '.join(covered)})")
    return {"covered": covered, "placed": placed, "wav": str(wav)}


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--platform", default="youtube")
    a = ap.parse_args(argv)
    print(json.dumps(build(Path(a.project), a.platform)))
    return 0


if __name__ == "__main__":
    main_guard(cli)
