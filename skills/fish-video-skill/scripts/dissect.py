"""Dissect a reference video element by element: pictures, motion, cuts, and
every sound (voice, music bed, whooshes, risers, clicks, impacts).

    python scripts/dissect.py <video> --out <dir> [--fps 4] [--vtt subs.vtt]

Outputs in <dir>:
  sheets/sheet_NN.jpg   timestamped frame grids (4 x 3) at --fps; read them with your eyes
  frames/               the individual frames (small JPEGs)
  dissect.json          everything below, machine readable
  timeline.md           a human-readable timeline: cuts, motion spikes, SFX events,
                        speech windows, levels; the brief for "how was this made"

Measurements:
  cuts      frame-difference peaks (hard cuts) and soft transitions
  motion    mean pixel change per frame (camera moves, zoom punches, shakes)
  flash     brightness jumps (white flashes, glitch frames)
  audio     5-band envelopes (sub, low, voice, presence, air) at 20 ms hops,
            spectral flux onsets, spectral flatness, centroid
  events    classified sound events: impact, boom, click/tick, pop, whoosh,
            riser, swell/reverse, typing-run (heuristics, ~80% right; listen to confirm)
  balance   voice-band vs music-bed level in speech windows (from the VTT if given,
            else from voice-band activity), integrated LUFS / true peak (ebur128)

Analysis only. The source stays where it is; nothing here copies it into a render.
Needs numpy and Pillow (pip install numpy pillow).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw
except ImportError as e:  # pragma: no cover
    raise SystemExit("dissect needs numpy and Pillow: pip install numpy pillow") from e

from fvcore import ffmpeg_bin, ffprobe_bin

SR = 22050
HOP = 441  # 20 ms
NFFT = 2048
BANDS = {"sub": (20, 120), "low": (120, 300), "voice": (300, 3400), "presence": (3400, 6000), "air": (6000, 11000)}


def probe(path: Path) -> dict:
    r = subprocess.run([ffprobe_bin(), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    js = json.loads(r.stdout)
    v = next((s for s in js["streams"] if s["codec_type"] == "video"), {})
    n, d = (v.get("r_frame_rate") or "30/1").split("/")
    return {"duration": float(js["format"]["duration"]), "W": v.get("width"), "H": v.get("height"),
            "fps": float(n) / float(d or 1), "has_audio": any(s["codec_type"] == "audio" for s in js["streams"])}


# ---------------------------------------------------------------- pictures
def extract_frames(src: Path, out: Path, fps: float, width: int = 360) -> list[Path]:
    fdir = out / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    for p in fdir.glob("f_*.jpg"):
        p.unlink()
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(src), "-vf", f"fps={fps},scale={width}:-2",
                    "-q:v", "4", str(fdir / "f_%05d.jpg")], check=True)
    return sorted(fdir.glob("f_*.jpg"))


def sheets(frames: list[Path], out: Path, fps: float, cols: int = 4, rows: int = 3) -> list[str]:
    sdir = out / "sheets"
    sdir.mkdir(parents=True, exist_ok=True)
    for p in sdir.glob("*.jpg"):
        p.unlink()
    if not frames:
        return []
    w, h = Image.open(frames[0]).size
    per = cols * rows
    names = []
    for s in range(0, len(frames), per):
        sheet = Image.new("RGB", (cols * w, rows * (h + 22)), (18, 18, 18))
        d = ImageDraw.Draw(sheet)
        for k, f in enumerate(frames[s:s + per]):
            x, y = (k % cols) * w, (k // cols) * (h + 22)
            sheet.paste(Image.open(f), (x, y + 22))
            d.text((x + 6, y + 4), f"t={(s + k) / fps:6.2f}s  #{s + k}", fill=(255, 230, 80))
        name = f"sheet_{s // per:02d}.jpg"
        sheet.save(sdir / name, quality=82)
        names.append(name)
    return names


def detect_cuts(diff, fps: float, src_fps: float = 30.0, ratio: float = 3.0, floor: float = 12.0, min_frames: int = 15, win: int = 2) -> list[int]:
    """Adaptive cut detector: a frame is a cut when its change is >= `ratio` times the mean change of its
    neighbours (+-win frames, itself excluded), is >= `floor` in absolute terms, and at least `min_frames`
    VIDEO frames (scaled to the sampling rate) have passed since the previous cut. A camera pan raises the
    neighbours too, so the ratio stays low and no cut fires. Returns indices into `diff`."""
    d = np.asarray(diff, dtype=np.float32)
    gap = max(1, int(round(min_frames * fps / max(src_fps, 1e-6))))
    cuts, last = [], -10 ** 9
    for i in range(1, len(d)):
        nb = np.r_[d[max(1, i - win):i], d[i + 1:i + 1 + win]]
        base = float(nb.mean()) if len(nb) else 0.0
        if d[i] >= floor and d[i] >= ratio * max(base, 1e-3) and i - last >= gap:
            cuts.append(i)
            last = i
    return cuts


def motion_curve(frames: list[Path], fps: float, src_fps: float = 30.0) -> dict:
    arr, bright = [], []
    prev = None
    for f in frames:
        im = np.asarray(Image.open(f).convert("L").resize((96, 170)), dtype=np.float32)
        bright.append(float(im.mean()))
        arr.append(0.0 if prev is None else float(np.abs(im - prev).mean()))
        prev = im
    m = np.array(arr)
    b = np.array(bright)
    med = float(np.median(m[1:])) if len(m) > 2 else 0.0
    cut_idx = set(detect_cuts(m, fps, src_fps))
    cuts, moves, flashes = [], [], []
    for i in range(1, len(m)):
        t = round(i / fps, 2)
        if i in cut_idx:
            cuts.append(t)
        elif m[i] > max(8.0, 2.2 * med):
            moves.append(t)
        if i and b[i] - b[i - 1] > 40:
            flashes.append(t)
    return {"diff": [round(x, 2) for x in arr], "brightness": [round(x, 1) for x in bright], "median_diff": round(med, 2),
            "cuts": cuts, "motion_spikes": moves, "flashes": flashes}


# ---------------------------------------------------------------- audio
def load_audio(src: Path) -> np.ndarray:
    r = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def stft_feats(x: np.ndarray) -> dict:
    if len(x) < NFFT:
        x = np.pad(x, (0, NFFT - len(x)))
    n = 1 + (len(x) - NFFT) // HOP
    win = np.hanning(NFFT).astype(np.float32)
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * win, axis=1)) + 1e-9
    freqs = np.fft.rfftfreq(NFFT, 1 / SR)
    power = spec ** 2
    bands = {k: 10 * np.log10(power[:, (freqs >= lo) & (freqs < hi)].sum(1) + 1e-12) for k, (lo, hi) in BANDS.items()}
    total = 10 * np.log10(power.sum(1) + 1e-12)
    rms = 20 * np.log10(np.sqrt((x[idx] ** 2).mean(1)) + 1e-9)
    logs = np.log(spec)
    flat = np.exp(logs.mean(1)) / spec.mean(1)
    cent = (spec * freqs).sum(1) / spec.sum(1)
    flux = np.r_[0, np.maximum(0, np.diff(logs, axis=0)).sum(1)]
    hfflux = np.r_[0, np.maximum(0, np.diff(logs[:, freqs > 3000], axis=0)).sum(1)]
    lfflux = np.r_[0, np.maximum(0, np.diff(logs[:, (freqs > 30) & (freqs < 200)], axis=0)).sum(1)]
    return {"t": np.arange(n) * HOP / SR, "bands": bands, "total": total, "rms": rms, "flat": flat, "cent": cent,
            "flux": flux, "hfflux": hfflux, "lfflux": lfflux}


def peaks(sig: np.ndarray, k: float, min_gap: int) -> list[int]:
    med = np.median(sig)
    mad = np.median(np.abs(sig - med)) + 1e-9
    th = med + k * mad
    out, last = [], -min_gap
    for i in range(1, len(sig) - 1):
        if sig[i] > th and sig[i] >= sig[i - 1] and sig[i] >= sig[i + 1] and i - last >= min_gap:
            out.append(i)
            last = i
    return out


def classify_events(F: dict) -> list[dict]:
    t, flat, cent, rms = F["t"], F["flat"], F["cent"], F["rms"]
    sub, air, voice = F["bands"]["sub"], F["bands"]["air"], F["bands"]["voice"]
    ev = []
    # transients
    floor = float(np.max(rms)) - 45
    for i in peaks(F["flux"], 6.0, 4):
        if rms[i] < floor:
            continue
        after = rms[i:i + 25]
        decay = float(after[0] - after.min()) if len(after) > 3 else 0.0
        lowdom = sub[i] - voice[i]
        dur = int(np.argmax(after < after[0] - 12)) if (after < after[0] - 12).any() else len(after)
        if lowdom > -3 and F["lfflux"][i] > np.percentile(F["lfflux"], 95):
            kind = "boom/impact" if dur > 10 else "kick/thump"
        elif cent[i] > 3500 and dur <= 4:
            kind = "click/tick"
        elif cent[i] > 2000 and dur <= 8:
            kind = "pop/snap"
        else:
            kind = "hit/accent"
        ev.append({"t": round(float(t[i]), 2), "kind": kind, "level_db": round(float(rms[i]), 1),
                   "centroid_hz": int(cent[i]), "decay_ms": dur * 20, "drop_db": round(decay, 1)})
    # whooshes: noisy (high flatness), 0.15-1.2 s, rise then fall in air band
    noisy = flat > max(0.25, float(np.percentile(flat, 85)))
    i = 0
    while i < len(noisy):
        if noisy[i]:
            j = i
            while j < len(noisy) and noisy[j]:
                j += 1
            L = j - i
            if 7 <= L <= 60:
                seg = air[i:j]
                pk = int(np.argmax(seg))
                if seg[pk] - min(seg[0], seg[-1]) > 6:
                    ev.append({"t": round(float(t[i]), 2), "kind": "whoosh/swish", "dur_s": round(L * HOP / SR, 2),
                               "peak_t": round(float(t[i + pk]), 2), "level_db": round(float(rms[i + pk]), 1),
                               "centroid_hz": int(cent[i + pk])})
            i = j
        else:
            i += 1
    # risers: >= 0.6 s of monotone-ish rise in total level and centroid, ending in a transient or cut
    tot = np.convolve(F["total"], np.ones(5) / 5, mode="same")
    cs = np.convolve(cent, np.ones(5) / 5, mode="same")
    i = 0
    while i < len(tot) - 30:
        j = i
        while j + 1 < len(tot) and tot[j + 1] >= tot[j] - 0.4:
            j += 1
        if j - i >= 30 and tot[j] - tot[i] > 9 and cs[j] > cs[i] * 1.3:
            ev.append({"t": round(float(t[i]), 2), "kind": "riser/swell", "dur_s": round((j - i) * HOP / SR, 2),
                       "end_t": round(float(t[j]), 2), "gain_db": round(float(tot[j] - tot[i]), 1)})
            i = j
        i += 1
    ev.sort(key=lambda e: e["t"])
    # typing runs: >= 4 clicks within 1.2 s
    clicks = [e["t"] for e in ev if e["kind"] == "click/tick"]
    runs, s = [], 0
    for k in range(1, len(clicks) + 1):
        if k == len(clicks) or clicks[k] - clicks[k - 1] > 0.3:
            if k - s >= 4:
                runs.append({"t": clicks[s], "kind": "typing/click-run", "count": k - s, "dur_s": round(clicks[k - 1] - clicks[s], 2)})
            s = k
    ev += runs
    ev.sort(key=lambda e: e["t"])
    return ev


def parse_vtt(path: Path) -> list[tuple[float, float, str]]:
    """Cue windows from a VTT (YouTube auto-subs have per-word <c> timings; we keep cue windows + words)."""
    def ts(s):
        h, m, r = s.split(":") if s.count(":") == 2 else ("0",) + tuple(s.split(":"))
        return int(h) * 3600 + int(m) * 60 + float(r)
    cues, cur = [], None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"(\d[\d:.]+)\s+-->\s+(\d[\d:.]+)", line)
        if m:
            cur = [ts(m.group(1)), ts(m.group(2)), ""]
            cues.append(cur)
        elif cur is not None and line.strip():
            cur[2] += " " + re.sub(r"<[^>]+>", "", line).strip()
    out, seen = [], set()
    for a, b, txt in cues:
        txt = " ".join(txt.split())
        if txt and (b - a) > 0.05 and txt not in seen:
            seen.add(txt)
            out.append((a, b, txt))
    return out


def balance(F: dict, speech: list[tuple[float, float, str]] | None) -> dict:
    t, voice, total, sub, low = F["t"], F["bands"]["voice"], F["total"], F["bands"]["sub"], F["bands"]["low"]
    if speech:
        mask = np.zeros(len(t), bool)
        for a, b, _ in speech:
            mask |= (t >= a) & (t <= b)
    else:
        th = np.percentile(voice, 60)
        mask = voice > th
    alive = total > (np.max(total) - 60)  # ignore digital silence / tail
    mask &= alive
    if not mask.any() or not (alive & ~mask).any():
        gap = None
    else:
        gap = alive & ~mask
    def stat(arr, m):
        return round(float(np.median(arr[m])), 1) if m is not None and m.any() else None
    res = {
        "speech_share": round(float(mask.mean()), 2),
        "voice_band_db_in_speech": stat(voice, mask),
        "voice_band_db_in_gaps": stat(voice, gap),
        "sub_db_in_speech": stat(sub, mask),
        "sub_db_in_gaps": stat(sub, gap),
        "low_db_in_speech": stat(low, mask),
        "total_db_in_speech": stat(total, mask),
        "total_db_in_gaps": stat(total, gap),
    }
    # crude "music under voice" estimate: low+sub energy (mostly music) relative to the voice band while speaking
    if res["voice_band_db_in_speech"] is not None and res["sub_db_in_speech"] is not None:
        res["voice_minus_bass_db"] = round(res["voice_band_db_in_speech"] - max(res["sub_db_in_speech"], res["low_db_in_speech"] or -120), 1)
    if res["sub_db_in_speech"] is not None and res["sub_db_in_gaps"] is not None:
        res["duck_estimate_db"] = round(res["sub_db_in_gaps"] - res["sub_db_in_speech"], 1)
    return res


def ebur128(src: Path) -> dict:
    r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(src), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    g = lambda pat: (float(m.group(1)) if (m := re.search(pat, tail)) else None)
    return {"lufs": g(r"I:\s+(-?[\d.]+) LUFS"), "lra": g(r"LRA:\s+(-?[\d.]+) LU"), "true_peak": g(r"Peak:\s+(-?[\d.]+) dBFS")}


def per_second(F: dict, dur: float) -> list[dict]:
    rows = []
    for s in range(int(np.ceil(dur))):
        m = (F["t"] >= s) & (F["t"] < s + 1)
        if not m.any():
            continue
        rows.append({"s": s, **{k: round(float(np.median(v[m])), 1) for k, v in F["bands"].items()},
                     "rms": round(float(np.median(F["rms"][m])), 1), "centroid": int(np.median(F["cent"][m]))})
    return rows


def write_md(out: Path, name: str, info: dict, mot: dict, ev: list, bal: dict, loud: dict, rows: list, speech, sheets_: list):
    L = [f"# Dissection: {name}", "",
         f"- {info['W']}x{info['H']} @ {info['fps']:.2f} fps, {info['duration']:.2f} s, audio: {info['has_audio']}",
         f"- loudness: {loud.get('lufs')} LUFS integrated, LRA {loud.get('lra')} LU, true peak {loud.get('true_peak')} dBFS",
         f"- cuts ({len(mot['cuts'])}): {mot['cuts']}",
         f"- motion spikes (zoom punches, slides, shakes): {mot['motion_spikes']}",
         f"- flashes: {mot['flashes']}",
         f"- median frame change {mot['median_diff']} (0 = static, >10 = constant motion)", "",
         "## Voice / music balance", "", "```", json.dumps(bal, indent=1), "```", "",
         "Read: `voice_minus_bass_db` is voice-band level over the louder of sub/low bands while speaking (music bed proxy);"
         " `duck_estimate_db` is how much the bass drops when the voice is on (sidechain).", ""]
    if speech:
        L += ["## Speech (from captions)", ""] + [f"- {a:6.2f}-{b:6.2f}  {txt}" for a, b, txt in speech] + [""]
    L += ["## Sound events (heuristic; confirm by ear)", "", "| t (s) | kind | detail |", "|---|---|---|"]
    for e in ev:
        d = ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("t", "kind"))
        L.append(f"| {e['t']:.2f} | {e['kind']} | {d} |")
    L += ["", "## Per-second band levels (dB, median)", "", "| s | sub | low | voice | presence | air | rms | centroid |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['s']} | {r['sub']} | {r['low']} | {r['voice']} | {r['presence']} | {r['air']} | {r['rms']} | {r['centroid']} |")
    L += ["", "## Frame sheets", ""] + [f"- sheets/{s}" for s in sheets_]
    (out / "timeline.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def dissect(src: Path, out: Path, fps: float, vtt: Path | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    info = probe(src)
    frames = extract_frames(src, out, fps)
    sh = sheets(frames, out, fps)
    mot = motion_curve(frames, fps, info.get("fps") or 30.0)
    speech = parse_vtt(vtt) if vtt and vtt.exists() else None
    ev, bal, loud, rows = [], {}, {}, []
    if info["has_audio"]:
        F = stft_feats(load_audio(src))
        ev = classify_events(F)
        bal = balance(F, speech)
        loud = ebur128(src)
        rows = per_second(F, info["duration"])
        # pictures of the sound: a log-frequency spectrogram with a time legend, and the waveform
        w = int(min(4000, max(1600, info["duration"] * 120)))
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(src), "-lavfi",
                        f"showspectrumpic=s={w}x600:legend=1:fscale=log:color=intensity:scale=log", str(out / "spectrogram.png")])
        subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(src), "-lavfi",
                        f"aformat=channel_layouts=mono,showwavespic=s={w}x240:split_channels=0:scale=sqrt", "-frames:v", "1", str(out / "waveform.png")])
    res = {"src": str(src), "info": info, "motion": mot, "events": ev, "balance": bal, "loudness": loud,
           "per_second": rows, "speech": speech, "sheets": sh}
    (out / "dissect.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    write_md(out, src.name, info, mot, ev, bal, loud, rows, speech, sh)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--vtt")
    a = ap.parse_args()
    r = dissect(Path(a.video), Path(a.out), a.fps, Path(a.vtt) if a.vtt else None)
    print(f"dissect: {len(r['motion']['cuts'])} cuts, {len(r['events'])} sound events, {len(r['sheets'])} sheets -> {a.out}/timeline.md")


if __name__ == "__main__":
    main()
