"""Asset search, download, licensing and processing.

    python scripts/assets.py search <project> "brain" --kind photo|video|audio|sfx|music [--providers pexels,openverse] [-n 12]
    python scripts/assets.py get <project> <candidate-id> [<candidate-id> ...]
    python scripts/assets.py cutout <src.png> <dst.png> [--model isnet-general-use]
    python scripts/assets.py clip <project> <src.mp4> <clip_id> [--start 0] [--dur 6] [--fps 30] [--width 1080]
    python scripts/assets.py sfx-pack [dest]
    python scripts/assets.py credits <project>

Providers: pexels (photo/video, PEXELS_API_KEY), pixabay (photo/video,
PIXABAY_API_KEY), openverse (photo/audio, key-less, cc0/pdm/by/by-sa only),
wikimedia (photo, key-less, CC0/PD/CC-BY/CC-BY-SA only), nasa (photo/video,
key-less), freesound (sfx, FREESOUND_API_KEY, CC0 only, hq-mp3 previews).

Unified record: id, provider, kind, title, url, download_url, preview_url,
width, height, duration, author, author_url, license, license_url,
attribution_required. `search` writes assets/_candidates/<kind>-<slug>.json
plus small preview images; `get` downloads full files into
assets/<kind>/<provider>-<id>.<ext> and logs assets/credits.json.
"""
from __future__ import annotations

import argparse
import html
import io
import json
import re
import shutil
import urllib.parse
import zipfile
from pathlib import Path

from fvcore import SKILL, FishError, ensure_project, ffmpeg_bin, log, main_guard, run, save_json, secret, slugify, warn, load_json
import fvnet
from fvnet import add_credit, credits_text, norm_license

KINDS = ("photo", "video", "audio", "sfx", "music")
DEFAULT_PROVIDERS = {
    "photo": ["pexels", "pixabay", "openverse", "wikimedia", "nasa"],
    "video": ["pexels", "pixabay", "nasa"],
    "audio": ["openverse"],
    "music": ["openverse"],
    "sfx": ["freesound", "openverse"],
}
REMBG_MODELS = ("isnet-general-use", "birefnet-general-lite", "birefnet-general", "u2net", "u2netp", "silueta", "isnet-anime", "birefnet-portrait")
KEY_NAMES = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY", "freesound": "FREESOUND_API_KEY"}


def _rec(provider, pid, kind, title, url, download_url, preview_url, width=None, height=None, duration=None, author="", author_url="",
         lic="", lic_url="", attribution=None, **extra) -> dict:
    n = norm_license(lic, lic_url)
    r = {"id": f"{provider}-{pid}", "provider": provider, "kind": kind, "title": (title or "").strip()[:140], "url": url,
         "download_url": download_url, "preview_url": preview_url, "width": width, "height": height, "duration": duration,
         "author": author or "", "author_url": author_url or "", "license": n["label"] if n["ok"] else lic, "license_url": n["url"] or lic_url,
         "attribution_required": n["attribution"] if attribution is None else attribution, "_ok": n["ok"] or attribution is False}
    r.update(extra)
    return r


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


# ------------------------------------------------------------------ providers
def _pexels(q, kind, n):
    key = secret("PEXELS_API_KEY")
    if not key:
        raise FishError("PEXELS_API_KEY not set")
    H = {"Authorization": key}
    out = []
    if kind == "photo":
        for p in fvnet.fetch_json("https://api.pexels.com/v1/search", {"query": q, "per_page": n}, H).get("photos", []):
            s = p.get("src", {})
            out.append(_rec("pexels", p["id"], "photo", p.get("alt") or q, p["url"], s.get("original") or s.get("large2x"), s.get("medium"),
                            p.get("width"), p.get("height"), None, p.get("photographer"), p.get("photographer_url"), "Pexels License", "https://www.pexels.com/license/", attribution=False))
    else:
        for v in fvnet.fetch_json("https://api.pexels.com/v1/videos/search", {"query": q, "per_page": n}, H).get("videos", []):
            files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")]
            files.sort(key=lambda f: (abs(f["width"] - 1920) if f["width"] >= 1280 else 5000 - f["width"]))
            f = files[0] if files else {}
            out.append(_rec("pexels", v["id"], "video", q, v["url"], f.get("link"), v.get("image"), f.get("width") or v.get("width"), f.get("height") or v.get("height"),
                            v.get("duration"), (v.get("user") or {}).get("name"), (v.get("user") or {}).get("url"), "Pexels License", "https://www.pexels.com/license/", attribution=False))
    return out


def _pixabay(q, kind, n):
    key = secret("PIXABAY_API_KEY")
    if not key:
        raise FishError("PIXABAY_API_KEY not set")
    out = []
    lic, lurl = "Pixabay Content License", "https://pixabay.com/service/license-summary/"
    if kind == "photo":
        for h in fvnet.fetch_json("https://pixabay.com/api/", {"key": key, "q": q, "per_page": max(n, 3), "safesearch": "true"}).get("hits", [])[:n]:
            out.append(_rec("pixabay", h["id"], "photo", h.get("tags") or q, h.get("pageURL"), h.get("largeImageURL") or h.get("webformatURL"), h.get("webformatURL") or h.get("previewURL"),
                            h.get("imageWidth"), h.get("imageHeight"), None, h.get("user"), f"https://pixabay.com/users/{h.get('user')}-{h.get('user_id')}/", lic, lurl, attribution=False))
    else:
        for h in fvnet.fetch_json("https://pixabay.com/api/videos/", {"key": key, "q": q, "per_page": max(n, 3), "safesearch": "true"}).get("hits", [])[:n]:
            vs = h.get("videos", {})
            v = vs.get("large") if vs.get("large", {}).get("url") else vs.get("medium", {})
            prev = f"https://i.vimeocdn.com/video/{h['picture_id']}_640x360.jpg" if h.get("picture_id") else None
            out.append(_rec("pixabay", h["id"], "video", h.get("tags") or q, h.get("pageURL"), v.get("url"), prev, v.get("width"), v.get("height"), h.get("duration"),
                            h.get("user"), f"https://pixabay.com/users/{h.get('user')}-{h.get('user_id')}/", lic, lurl, attribution=False))
    return out


def _openverse(q, kind, n):
    audio = kind in ("audio", "music", "sfx")
    ep = "audio" if audio else "images"
    d = fvnet.fetch_json(f"https://api.openverse.org/v1/{ep}/", {"q": q, "page_size": min(n * 2, 40), "license": "cc0,pdm,by,by-sa",
                                                                  "category": "sound_effect" if kind == "sfx" else None})
    out = []
    for r in d.get("results", []):
        lic = (r.get("license") or "").lower()
        if lic not in ("cc0", "pdm", "by", "by-sa"):
            continue
        label = {"cc0": "CC0", "pdm": "Public Domain", "by": f"CC BY {r.get('license_version') or '4.0'}", "by-sa": f"CC BY-SA {r.get('license_version') or '4.0'}"}[lic]
        dur = (r.get("duration") or 0) / 1000 if audio else None
        out.append(_rec("openverse", r["id"], kind, r.get("title") or q, r.get("foreign_landing_url") or r.get("url"), r.get("url"), r.get("thumbnail") or (r.get("url") if not audio else None),
                        r.get("width"), r.get("height"), dur, r.get("creator"), r.get("creator_url"), label, r.get("license_url") or "", filetype=r.get("filetype")))
        if len(out) >= n:
            break
    return out


def _wikimedia(q, kind, n):
    d = fvnet.fetch_json("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrsearch": q, "gsrlimit": min(n * 2, 30),
        "prop": "imageinfo", "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 640})
    out = []
    for pg in sorted((d.get("query", {}).get("pages") or {}).values(), key=lambda p: p.get("index", 0)):
        ii = (pg.get("imageinfo") or [{}])[0]
        mime = ii.get("mime", "")
        if not (mime.startswith("image/") and mime not in ("image/svg+xml", "image/tiff")):
            continue
        md = ii.get("extmetadata", {})
        short = (md.get("LicenseShortName") or {}).get("value", "")
        lurl = (md.get("LicenseUrl") or {}).get("value", "")
        if not short:
            continue
        nl = norm_license(short, lurl)
        if not nl["ok"]:
            continue
        out.append(_rec("wikimedia", pg["pageid"], "photo", _strip((md.get("ObjectName") or {}).get("value", "")) or pg["title"].replace("File:", ""),
                        ii.get("descriptionurl"), ii.get("url"), ii.get("thumburl"), ii.get("width"), ii.get("height"), None,
                        _strip((md.get("Artist") or {}).get("value", "")), "", short, lurl))
        if len(out) >= n:
            break
    return out


def _nasa(q, kind, n):
    d = fvnet.fetch_json("https://images-api.nasa.gov/search", {"q": q, "media_type": "video" if kind == "video" else "image", "page_size": n})
    out = []
    for it in d.get("collection", {}).get("items", [])[:n]:
        dd = (it.get("data") or [{}])[0]
        prev = next((l["href"] for l in it.get("links", []) if l.get("rel") == "preview"), None)
        out.append(_rec("nasa", dd.get("nasa_id", "").replace("/", "_"), kind, dd.get("title") or q, f"https://images.nasa.gov/details/{urllib.parse.quote(dd.get('nasa_id', ''))}",
                        None, prev, None, None, None, dd.get("photographer") or dd.get("secondary_creator") or dd.get("center") or "NASA", "",
                        "NASA media (public domain; no endorsement implied)", "https://www.nasa.gov/nasa-brand-center/images-and-media/", attribution=False,
                        collection_url=it.get("href")))
    return out


def _freesound(q, kind, n):
    key = secret("FREESOUND_API_KEY")
    if not key:
        raise FishError("FREESOUND_API_KEY not set")
    d = fvnet.fetch_json("https://freesound.org/apiv2/search/text/", {"query": q, "filter": 'license:"Creative Commons 0"', "page_size": n, "token": key,
                                                                    "fields": "id,name,previews,license,username,duration,url"})
    out = []
    for s in d.get("results", []):
        pv = s.get("previews") or {}
        out.append(_rec("freesound", s["id"], "sfx", s.get("name") or q, s.get("url") or f"https://freesound.org/s/{s['id']}/", pv.get("preview-hq-mp3"), pv.get("preview-lq-mp3"),
                        None, None, s.get("duration"), s.get("username"), f"https://freesound.org/people/{s.get('username')}/", "CC0", "https://creativecommons.org/publicdomain/zero/1.0/"))
    return out


PROVIDERS = {"pexels": (_pexels, ("photo", "video")), "pixabay": (_pixabay, ("photo", "video")), "openverse": (_openverse, ("photo", "audio", "music", "sfx")),
             "wikimedia": (_wikimedia, ("photo",)), "nasa": (_nasa, ("photo", "video")), "freesound": (_freesound, ("sfx",))}


# ------------------------------------------------------------------ search / get
def search_providers(q: str, kind: str, providers=None, n: int = 12) -> list[dict]:
    """Query providers (no disk writes). Drops NC/ND/unknown licences. Soft-fails per provider."""
    if kind not in KINDS:
        raise FishError(f"kind must be one of {', '.join(KINDS)}")
    res: list[dict] = []
    for name in providers or DEFAULT_PROVIDERS[kind]:
        if name not in PROVIDERS:
            warn(f"unknown provider '{name}'")
            continue
        fn, kinds = PROVIDERS[name]
        if kind not in kinds:
            continue
        try:
            got = fn(q, kind, n)
        except fvnet.NetError as e:
            warn(f"{name}: {e}")
            continue
        except FishError as e:
            warn(f"{name} skipped: {e}" + (f" (key-less alternatives: {', '.join(p for p in DEFAULT_PROVIDERS[kind] if p not in KEY_NAMES)})" if name in KEY_NAMES else ""))
            continue
        except (KeyError, TypeError, ValueError) as e:
            warn(f"{name}: unexpected response ({e})")
            continue
        res += [r for r in got if r.get("_ok")]
    for r in res:
        r.pop("_ok", None)
    return res


def _ext(url: str, default: str) -> str:
    e = Path(urllib.parse.urlsplit(url or "").path).suffix.lower()
    return e if re.fullmatch(r"\.[a-z0-9]{2,4}", e or "") else default


def search(project, q: str, kind: str = "photo", providers=None, n: int = 12) -> list[dict]:
    """Search, write assets/_candidates/<kind>-<slug>.json and download small previews next to it."""
    project = ensure_project(project)
    res = search_providers(q, kind, providers, n)
    cdir = project / "assets" / "_candidates"
    cdir.mkdir(parents=True, exist_ok=True)
    for r in res:
        pu = r.get("preview_url")
        if not pu:
            continue
        dflt = ".mp3" if kind in ("audio", "sfx", "music") else ".jpg"
        dest = cdir / f"{r['id']}{_ext(pu, dflt)}"
        if kind in ("audio", "music") and r["provider"] == "openverse":
            continue  # audio previews are full tracks; skip bulky pre-download
        try:
            if not dest.exists():
                fvnet.download_file(pu, dest, timeout=20)
            r["preview_file"] = dest.name
        except fvnet.NetError as e:
            warn(f"preview skipped for {r['id']}: {e}")
    out = cdir / f"{kind}-{slugify(q)}.json"
    save_json(out, {"query": q, "kind": kind, "results": res})
    log(f"{len(res)} candidates -> {out}")
    for r in res:
        log(f"  {r['id']:<28} {r['license']:<14} {(r['title'] or '')[:50]}  by {r['author'][:24]}")
    return res


def _find_candidates(project: Path, ids: list[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for f in sorted((project / "assets" / "_candidates").glob("*.json")):
        try:
            for r in json.loads(f.read_text(encoding="utf-8")).get("results", []):
                if r["id"] in ids:
                    found[r["id"]] = r
        except (ValueError, OSError):
            continue
    return found


def _nasa_resolve(r: dict) -> str | None:
    items = fvnet.fetch_json(r["collection_url"]) if r.get("collection_url") else []
    if r["kind"] == "video":
        order = ["~medium.mp4", "~small.mp4", "~large.mp4", "~orig.mp4", ".mp4"]
    else:
        order = ["~large.jpg", "~medium.jpg", "~orig.jpg", ".jpg", ".png"]
    for suffix in order:
        for u in items:
            if u.lower().endswith(suffix):
                return u.replace("http://", "https://")
    return None


def get(project, candidate_ids) -> list[Path]:
    """Download candidates fully into assets/<kind>/<provider>-<id>.<ext> and log credits (deduped)."""
    project = ensure_project(project)
    ids = [candidate_ids] if isinstance(candidate_ids, str) else list(candidate_ids)
    cands = _find_candidates(project, ids)
    out: list[Path] = []
    for cid in ids:
        r = cands.get(cid)
        if not r:
            warn(f"{cid}: not in assets/_candidates (run `assets.py search` first)")
            continue
        try:
            url = r.get("download_url")
            if not url and r["provider"] == "nasa":
                url = _nasa_resolve(r)
            if not url:
                raise FishError("no download URL")
            dflt = {"photo": ".jpg", "video": ".mp4"}.get(r["kind"], ".mp3")
            if r["provider"] == "openverse" and r.get("filetype"):
                dflt = "." + str(r["filetype"]).lower()
            dest = project / "assets" / r["kind"] / f"{r['id']}{_ext(url, dflt)}"
            if not dest.exists():
                fvnet.download_file(url, dest, timeout=120)
        except FishError as e:
            warn(f"{cid}: {e}")
            continue
        rec = {k: v for k, v in r.items() if k not in ("preview_file", "collection_url", "filetype")}
        rec["file"] = str(dest.relative_to(project)).replace("\\", "/")
        rec["credit"] = fvnet.credit_line(rec)
        added = add_credit(project, rec)
        log(f"{'got' if added else 'have'} {cid} -> {rec['file']}  [{r['license']}]")
        out.append(dest)
    return out


# ------------------------------------------------------------------ processing
def cutout(src, dst, model: str = "isnet-general-use") -> Path | None:
    """Background removal via rembg with an explicit permissive model (never the default bria model)."""
    if "bria" in model.lower():
        raise FishError("the bria model is non-commercial: use isnet-general-use or birefnet-general-lite")
    if model not in REMBG_MODELS:
        warn(f"model '{model}' not in the vetted list {REMBG_MODELS}; use at your own licence risk")
    try:
        from rembg import new_session, remove  # type: ignore
        from PIL import Image
    except ImportError:
        warn('rembg is not installed: pip install "rembg[cpu]"  (cutout skipped)')
        return None
    try:
        sess = new_session(model)
        img = Image.open(src).convert("RGBA")
        res = remove(img, session=sess)
        # trim to the visible object, so `w` in a scene means the object and not transparent padding
        box = res.getchannel("A").point(lambda a: 255 if a > 12 else 0).getbbox()
        if box:
            pad = int(max(res.size) * 0.01)
            res = res.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(res.width, box[2] + pad), min(res.height, box[3] + pad)))
        res.thumbnail((1600, 1600))
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        res.save(dst, optimize=True)
    except Exception as e:
        warn(f"cutout failed: {str(e)[:200]}")
        return None
    log(f"cutout ({model}) -> {dst}")
    return Path(dst)


GRADES = {
    "warm": "eq=saturation=1.08:contrast=1.04,colorbalance=rs=0.06:gs=0.01:bs=-0.07:rm=0.05:bm=-0.05:rh=0.04:bh=-0.05",
    "cool": "eq=saturation=1.03:contrast=1.04,colorbalance=rs=-0.05:bs=0.07:rm=-0.04:bm=0.05:rh=-0.03:bh=0.05",
    "teal-orange": "eq=saturation=1.12:contrast=1.08,colorbalance=rs=-0.08:gs=0.0:bs=0.10:rm=0.0:bm=0.0:rh=0.12:gh=0.03:bh=-0.10",
    "bw": "hue=s=0,curves=all='0/0 0.25/0.20 0.75/0.82 1/1'",
}


def clip_filters(fps: int, width: int, grade: str | None = None, sharpen: bool = False, lut: str | Path | None = None) -> str:
    """The ffmpeg -vf chain of prep_clip: [light denoise] -> fps -> scale -> [sharpen] -> [grade] -> [.cube LUT]."""
    if grade and grade not in GRADES:
        raise FishError(f"unknown grade '{grade}': one of {sorted(GRADES)}")
    parts = []
    if sharpen:
        parts.append("hqdn3d=1.5:1.5:3:3")
    parts += [f"fps={fps}", f"scale='min({width},iw)':-2:flags=lanczos"]
    if sharpen:
        parts.append("unsharp=5:5:0.8")
    if grade:
        parts.append(GRADES[grade])
    if lut:
        lp = Path(lut)
        if not lp.exists() or lp.suffix.lower() != ".cube":
            raise FishError(f"LUT must be an existing .cube file: {lut}")
        # filter-graph escaping: forward slashes, escape the drive colon and quotes
        esc = lp.resolve().as_posix().replace(":", chr(92) + ":").replace("'", chr(92) + "'")
        parts.append(f"lut3d=file='{esc}'")
    return ",".join(parts)


def prep_clip(project, src, clip_id: str, start: float = 0, dur: float | None = None, fps: int = 30, width: int = 1080,
              grade: str | None = None, sharpen: bool = False, lut: str | Path | None = None) -> dict:
    """Extract frames to build/clips/<clip_id>/f_%05d.jpg + meta.json {frames,fps,W,H,src}.

    grade   warm | cool | teal-orange | bw  (ffmpeg eq/colorbalance/curves, no LUT files)
    sharpen light hqdn3d first, then lanczos scale + unsharp=5:5:0.8 (soft stock footage)
    lut     path to a .cube file, applied last with lut3d
    """
    project = ensure_project(project)
    src = Path(src)
    if not src.exists():
        raise FishError(f"missing file: {src}")
    out = project / "build" / "clips" / clip_id
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start)]
    if dur:
        cmd += ["-t", str(dur)]
    cmd += ["-i", str(src), "-an", "-vf", clip_filters(fps, width, grade, sharpen, lut), "-q:v", "3", str(out / "f_%05d.jpg")]
    run(cmd)
    frames = sorted(out.glob("f_*.jpg"))
    if not frames:
        raise FishError("ffmpeg produced no frames (check start/dur)")
    from PIL import Image
    with Image.open(frames[0]) as im:
        W, H = im.size
    meta = {"frames": len(frames), "fps": fps, "W": W, "H": H, "src": str(src)}
    if grade or sharpen or lut:
        meta["look"] = {k: v for k, v in {"grade": grade, "sharpen": sharpen or None, "lut": str(lut) if lut else None}.items() if v}
    save_json(out / "meta.json", meta)
    log(f"{len(frames)} frames ({W}x{H} @ {fps}) -> {out}")
    return meta


# ------------------------------------------------------------------ Kenney SFX pack
KENNEY_PACKS = ["interface-sounds", "impact-sounds", "ui-audio"]
CUE_KEYWORDS = {
    "pop": ["pluck", "drop", "bong", "pop", "open", "question"],
    "tick": ["tick", "rollover", "scroll"],
    "click": ["click", "switch", "toggle", "select"],
    "swish": ["swish", "scratch", "minimize", "maximize", "slide"],
    "whoosh": ["whoosh", "swoosh", "maximize", "minimize", "slide"],
    "riser": ["riser", "rise", "sweep", "build"],
    "impact": ["impact"],
    "boom": ["boom", "heavy", "explosion"],
    "thump": ["thump", "soft", "wood", "punch"],
    "zap": ["zap", "laser", "electric", "error"],
    "coin": ["coin", "confirmation", "glass"],
    "paper": ["paper", "book", "cloth", "page"],
    "typing": ["type", "typing", "key"],
    "chime": ["chime", "bong", "confirmation", "glass", "bell"],
}
AUDIO_EXT = (".ogg", ".wav", ".mp3")


def build_sfx_index(lib: Path) -> dict:
    """Map our cue types to candidate files (paths relative to lib) by filename keywords."""
    files = sorted(p for p in lib.rglob("*") if p.suffix.lower() in AUDIO_EXT)
    idx: dict[str, list[str]] = {}
    for cue, kws in CUE_KEYWORDS.items():
        hit = []
        for kw in kws:
            hit += [str(p.relative_to(lib)).replace("\\", "/") for p in files if kw in p.stem.lower() and str(p.relative_to(lib)).replace("\\", "/") not in hit]
        idx[cue] = hit[:24]
    save_json(lib / "index.json", {"license": "CC0 (Kenney, kenney.nl)", "cues": idx, "count": len(files)})
    return idx


def _kenney_zip(slug: str) -> bytes:
    page = f"https://kenney.nl/assets/{slug}"
    did = ("assets/" + slug).encode().hex()
    d = fvnet.fetch_json(f"https://kenney.nl/download-link/{did}", headers={"Referer": page, "Accept": "application/json"})
    if not d.get("url"):
        raise fvnet.NetError(f"kenney gave no download link for {slug}")
    return fvnet.fetch(d["url"], headers={"Referer": page}, timeout=60)


def sfx_pack(dest=None) -> dict:
    """Download Kenney CC0 audio packs (UI + impacts) into <skill>/sfx/library/ and build index.json."""
    lib = Path(dest) if dest else SKILL / "sfx" / "library"
    lib.mkdir(parents=True, exist_ok=True)
    for slug in KENNEY_PACKS:
        if (lib / slug).exists() and any((lib / slug).rglob("*.ogg")):
            log(f"have {slug}")
            continue
        try:
            raw = _kenney_zip(slug)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                lic = next((z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.lower().endswith("license.txt")), "")
                if "cc0" not in lic.lower() and "creative commons zero" not in lic.lower():
                    warn(f"{slug}: licence is not CC0, skipped")
                    continue
                for n in z.namelist():
                    if n.lower().endswith(AUDIO_EXT) or n.lower().endswith("license.txt"):
                        tgt = lib / slug / Path(n).name
                        tgt.parent.mkdir(parents=True, exist_ok=True)
                        tgt.write_bytes(z.read(n))
            log(f"downloaded {slug}")
        except (fvnet.NetError, zipfile.BadZipFile, FishError) as e:
            warn(f"{slug}: {e} (SFX pack incomplete; try again later or download from kenney.nl manually)")
    idx = build_sfx_index(lib)
    log("sfx index: " + ", ".join(f"{k}={len(v)}" for k, v in idx.items()))
    return idx


# ------------------------------------------------------------------ CLI
def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="assets.py", description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("search"); a.add_argument("project"); a.add_argument("q"); a.add_argument("--kind", default="photo", choices=KINDS)
    a.add_argument("--providers"); a.add_argument("-n", type=int, default=12)
    a = sp.add_parser("get"); a.add_argument("project"); a.add_argument("ids", nargs="+")
    a = sp.add_parser("cutout"); a.add_argument("src"); a.add_argument("dst"); a.add_argument("--model", default="isnet-general-use")
    a = sp.add_parser("clip"); a.add_argument("project"); a.add_argument("src"); a.add_argument("clip_id")
    a.add_argument("--start", type=float, default=0); a.add_argument("--dur", type=float); a.add_argument("--fps", type=int, default=30); a.add_argument("--width", type=int, default=1080)
    a.add_argument("--grade", choices=sorted(GRADES)); a.add_argument("--sharpen", action="store_true"); a.add_argument("--lut", help=".cube file")
    a = sp.add_parser("sfx-pack"); a.add_argument("dest", nargs="?")
    a = sp.add_parser("credits"); a.add_argument("project")
    ns = ap.parse_args(argv)
    if ns.cmd == "search":
        search(ns.project, ns.q, ns.kind, ns.providers.split(",") if ns.providers else None, ns.n)
    elif ns.cmd == "get":
        get(ns.project, ns.ids)
    elif ns.cmd == "cutout":
        return 0 if cutout(ns.src, ns.dst, ns.model) else 1
    elif ns.cmd == "clip":
        prep_clip(ns.project, ns.src, ns.clip_id, ns.start, ns.dur, ns.fps, ns.width, ns.grade, ns.sharpen, ns.lut)
    elif ns.cmd == "sfx-pack":
        sfx_pack(ns.dest)
    elif ns.cmd == "credits":
        print(credits_text(ensure_project(ns.project)))
    return 0


if __name__ == "__main__":
    main_guard(cli)
