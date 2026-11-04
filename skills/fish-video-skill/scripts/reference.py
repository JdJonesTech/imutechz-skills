"""Reference-video analysis: learn the pacing of a video you admire, without
copying any of it.

    python scripts/reference.py <project> [--src file.mp4 | --src https://youtu.be/...] [--threshold 0.30]
    python scripts/reference.py analyse <video> [--out dir]

What it measures (analysis only: the download is kept in reference/ for the
analysis and must never be cut into the new video; nothing is uploaded):
  shots      scene-cut times (ffmpeg scdet/select scene score) -> a shot list
  pacing     shots per minute, median/mean shot length, the longest holds,
             and the same in 120-BPM bars (what our edit grid would call it)
  palette    5 dominant colours per shot and overall (k-means on tiny frames)
  loudness   integrated LUFS, true peak, loudness range (ebur128)
  tempo      a BPM estimate of the soundtrack (onset autocorrelation)
  text       how often the frame is mostly flat colour (a proxy for type cards)
Outputs reference/analysis.json, reference/shots.csv, reference/contact.png,
reference/report.md.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import re
import statistics
from pathlib import Path

from fvcore import FishError, ffmpeg_bin, ffprobe_bin, load_yaml, log, main_guard, run, save_json, warn

YT = re.compile(r"^https?://(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com)/", re.I)


def download(url: str, outdir: Path) -> Path:
    """Fetch a YouTube (or other yt-dlp supported) video at <= 720p, for analysis only."""
    try:
        import yt_dlp
    except ImportError:
        raise FishError("yt-dlp is not installed: pip install yt-dlp (or pass a local file with --src)")
    outdir.mkdir(parents=True, exist_ok=True)
    opts = {"outtmpl": str(outdir / "src.%(ext)s"), "format": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/b",
            "merge_output_format": "mp4", "quiet": True, "noprogress": True, "ffmpeg_location": str(Path(ffmpeg_bin()).parent)}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
    (outdir / "src.info.json").write_text(json.dumps({k: info.get(k) for k in ("id", "title", "uploader", "duration", "webpage_url", "license")}, indent=1), encoding="utf-8")
    for p in outdir.glob("src.*"):
        if p.suffix in (".mp4", ".mkv", ".webm"):
            return p
    raise FishError("download finished but no video file was found")


def probe(path: Path) -> dict:
    r = run([ffprobe_bin(), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture=True)
    js = json.loads(r.stdout)
    v = next((s for s in js["streams"] if s["codec_type"] == "video"), {})
    fr = (v.get("r_frame_rate") or "30/1").split("/")
    return {"duration": float(js["format"]["duration"]), "W": v.get("width"), "H": v.get("height"), "fps": float(fr[0]) / float(fr[1] or 1),
            "has_audio": any(s["codec_type"] == "audio" for s in js["streams"])}


def scene_cuts(path: Path, threshold: float = 0.3) -> list[float]:
    """Times (s) where the scene-change score exceeds threshold."""
    r = run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"], capture=True)
    return [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def shots_from_cuts(cuts: list[float], duration: float, min_len: float = 0.25) -> list[dict]:
    """Cut times -> [{n, start, end, dur}]; cuts closer than min_len merge (flashes, dissolves)."""
    pts = [0.0]
    for c in sorted(cuts):
        if c - pts[-1] >= min_len and duration - c >= min_len:
            pts.append(c)
    pts.append(duration)
    return [{"n": i + 1, "start": round(a, 3), "end": round(b, 3), "dur": round(b - a, 3)} for i, (a, b) in enumerate(zip(pts, pts[1:]))]


def pacing(shots: list[dict], duration: float, bpm: float = 120) -> dict:
    d = [s["dur"] for s in shots]
    bar = 240.0 / bpm
    return {"shots": len(shots), "per_minute": round(len(shots) / max(duration, 1e-6) * 60, 1), "mean": round(statistics.mean(d), 2),
            "median": round(statistics.median(d), 2), "p90": round(sorted(d)[int(0.9 * (len(d) - 1))], 2), "longest": sorted(shots, key=lambda s: -s["dur"])[:3],
            "median_bars_at_120": round(statistics.median(d) / bar, 2), "suggest_bars_per_scene": max(1, round(statistics.median(d) / bar))}


def kmeans(px: list[tuple[int, int, int]], k: int = 5, iters: int = 12) -> list[tuple[list[int], float]]:
    """Tiny deterministic k-means on RGB pixels -> [(rgb, share)] by share."""
    if not px:
        return []
    step = max(1, len(px) // k)
    cents = [list(px[i * step % len(px)]) for i in range(k)]
    for _ in range(iters):
        groups = [[] for _ in cents]
        for p in px:
            j = min(range(len(cents)), key=lambda c: (p[0] - cents[c][0]) ** 2 + (p[1] - cents[c][1]) ** 2 + (p[2] - cents[c][2]) ** 2)
            groups[j].append(p)
        cents = [[sum(c[i] for c in g) // len(g) for i in range(3)] if g else cents[j] for j, g in enumerate(groups)]
    sizes = [len(g) for g in groups]
    tot = sum(sizes) or 1
    return sorted([(c, s / tot) for c, s in zip(cents, sizes) if s], key=lambda x: -x[1])


def frame_pixels(path: Path, t: float, w: int = 48, h: int = 27) -> list[tuple[int, int, int]]:
    r = run([ffmpeg_bin(), "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture=False, check=False) if False else None
    import subprocess
    p = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    b = p.stdout
    return [(b[i], b[i + 1], b[i + 2]) for i in range(0, len(b) - 2, 3)]


def hexc(c) -> str:
    return "#%02x%02x%02x" % tuple(int(x) for x in c)


def flatness(px: list[tuple[int, int, int]]) -> float:
    """Share of pixels within a small distance of the most common colour (type cards are flat)."""
    if not px:
        return 0
    top = kmeans(px, 3, 6)
    return round(top[0][1], 3) if top else 0


def loudness(path: Path) -> dict:
    r = run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture=True, check=False)
    s = r.stderr[r.stderr.rfind("Summary"):]
    g = lambda rx: (float(m.group(1)) if (m := re.search(rx, s)) else None)
    return {"I": g(r"I:\s+(-?[\d.]+) LUFS"), "TP": g(r"Peak:\s+(-?[\d.]+) dBFS"), "LRA": g(r"LRA:\s+([\d.]+) LU")}


def tempo(path: Path, max_seconds: float = 120) -> float | None:
    """BPM estimate: onset-strength envelope (100 Hz) autocorrelated over 60-180 BPM."""
    import subprocess
    p = subprocess.run([ffmpeg_bin(), "-v", "error", "-t", str(max_seconds), "-i", str(path), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
    a = array.array("h")
    a.frombytes(p.stdout[: len(p.stdout) // 2 * 2])
    if len(a) < 8000 * 8:
        return None
    hop = 80
    env = []
    prev = 0.0
    for i in range(0, len(a) - hop, hop):
        e = math.sqrt(sum(x * x for x in a[i:i + hop]) / hop)
        env.append(max(0.0, e - prev))
        prev = e
    m = statistics.mean(env)
    env = [x - m for x in env]
    best, best_lag = -1e18, None
    for lag in range(int(100 * 60 / 180), int(100 * 60 / 60) + 1):
        s = sum(env[i] * env[i + lag] for i in range(0, len(env) - lag, 2))
        if s > best:
            best, best_lag = s, lag
    if not best_lag:
        return None
    bpm = 6000 / best_lag
    while bpm < 80:
        bpm *= 2
    while bpm > 170:
        bpm /= 2
    return round(bpm, 1)


def contact(path: Path, shots: list[dict], out: Path, cols: int = 6) -> Path | None:
    if not shots:
        return None
    sel = "+".join(f"eq(n\\,{0})" for _ in [0])
    times = [s["start"] + min(0.4, s["dur"] / 2) for s in shots[:48]]
    expr = "+".join(f"between(t\\,{t - 0.02:.3f}\\,{t + 0.04:.3f})" for t in times)
    rows = max(1, -(-len(times) // cols))
    run([ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(path), "-vf", f"select='{expr}',scale=240:-2,tile={cols}x{rows}", "-frames:v", "1", "-vsync", "vfr", str(out)], check=False)
    return out if out.exists() else None


def analyse(path: Path, outdir: Path, threshold: float = 0.3) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    meta = probe(path)
    log(f"reference: {path.name} {meta['W']}x{meta['H']} {meta['duration']:.1f}s")
    cuts = scene_cuts(path, threshold)
    shots = shots_from_cuts(cuts, meta["duration"])
    pal_all: list[tuple[int, int, int]] = []
    for s in shots[:80]:
        px = frame_pixels(path, s["start"] + s["dur"] / 2)
        top = kmeans(px, 5)
        s["palette"] = [hexc(c) for c, _ in top]
        s["flat"] = flatness(px)
        pal_all += px[:: 3]
    overall = [{"hex": hexc(c), "share": round(sh, 3)} for c, sh in kmeans(pal_all, 6)]
    res = {"source": str(path), "meta": meta, "threshold": threshold, "pacing": pacing(shots, meta["duration"]), "palette": overall,
           "loudness": loudness(path) if meta["has_audio"] else None, "tempo_bpm": tempo(path) if meta["has_audio"] else None,
           "type_card_share": round(sum(1 for s in shots if s.get("flat", 0) > 0.6) / max(1, len(shots)), 2), "shots": shots}
    save_json(outdir / "analysis.json", res)
    (outdir / "shots.csv").write_text("n,start,end,dur,palette\n" + "\n".join(f"{s['n']},{s['start']},{s['end']},{s['dur']},{' '.join(s.get('palette', []))}" for s in shots), encoding="utf-8")
    contact(path, shots, outdir / "contact.png")
    p = res["pacing"]
    md = [f"# Reference analysis: {path.name}", "", f"- {meta['duration']:.1f} s, {meta['W']}x{meta['H']} @ {meta['fps']:.2f} fps",
          f"- {p['shots']} shots, {p['per_minute']} cuts/min; median shot {p['median']} s (= {p['median_bars_at_120']} bars at 120 BPM), p90 {p['p90']} s",
          f"- suggestion: about {p['suggest_bars_per_scene']} bar(s) per scene to match this energy",
          f"- soundtrack tempo ~ {res['tempo_bpm']} BPM; loudness {res['loudness']}" if res["loudness"] else "- no audio",
          f"- {int(res['type_card_share'] * 100)}% of shots are mostly flat colour (type cards / motion graphics)",
          "- palette: " + ", ".join(f"{c['hex']} ({int(c['share'] * 100)}%)" for c in overall), "",
          "Use: copy the *rhythm* (shot lengths, when the energy lifts, how long type holds), never the footage, music, voice, or layouts verbatim.", ""]
    (outdir / "report.md").write_text("\n".join(md), encoding="utf-8")
    log("\n".join(md[2:8]))
    return res


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("video", nargs="?")
    ap.add_argument("--src", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--threshold", type=float, default=0.3)
    a = ap.parse_args(argv)
    if a.target == "analyse":
        analyse(Path(a.video), Path(a.out or "reference"), a.threshold)
        return 0
    project = Path(a.target)
    src = a.src or ((load_yaml(project / "brief.yaml").get("reference") or {}).get("src"))
    if not src:
        raise FishError("no reference: pass --src or set brief.reference.src")
    outdir = project / "reference"
    path = download(src, outdir) if YT.match(src) or src.startswith("http") else Path(src)
    if not path.exists():
        raise FishError(f"reference not found: {path}")
    analyse(path, outdir, a.threshold)
    return 0


if __name__ == "__main__":
    main_guard(cli)
