"""Comedy and meme sounds: synthesise them, find licensed ones, install your own as cue types, and audition them.

    python scripts/sounds.py list     <project>                         every cue type a storyboard can name, where it comes from, its level
    python scripts/sounds.py synth    <project> [--only airhorn,boing] [--all] [--out DIR]
    python scripts/sounds.py search   <project> "sad trombone" [-n 12] [--unverified]     Freesound, Openverse, Wikimedia Commons
    python scripts/sounds.py add      <project> <file> <cue> [--start S] [--dur D] [--level -14] [--title T] [--author A]
                                      [--source myinstants|own|...] [--source-url U] [--license "CC BY 4.0"] [--accept-risk]
    python scripts/sounds.py audition <project> [--out build/auditions/sfx.wav]

A cue type is a folder name: a storyboard plays it with `cues: [{lt: 1.2, type: trombone}]` or a `meme` scene's
`sound:`. Sounds come from three places, later ones winning: the skill's library (Kenney CC0 plus the meme pack in
sfx/library/meme), the project's assets/sfx/<type>/, and levels from brief.mix.sfx_levels.

`synth` writes original sounds made by this code (no samples, so nothing to license): generic comedy types, not copies
of any famous recording. `add` takes a file you have, any audio or video: it keeps the hit, fades the ends, normalises
it and logs its licence. A viral sound from a sound-button site has no licence, so `add` refuses it unless the brief
says `memes.policy: viral` or you pass --accept-risk. Nobody has listened to the synthesised sounds: audition them.
"""
from __future__ import annotations

import argparse
import struct
import subprocess
import wave
from pathlib import Path

from fvcore import FishError, ensure_project, ffmpeg_bin, load_json, log, main_guard, save_json, slugify, warn
import fvnet
from fvnet import add_credit
import sfx

SR = 48000
TAU = 6.283185307179586


# ------------------------------------------------------------------ audio in, audio out
def decode(path: Path | str, start: float | None = None, dur: float | None = None):
    """Any audio or video file -> float32 stereo at 48 kHz."""
    import numpy as np
    cmd = [ffmpeg_bin(), "-v", "error"] + (["-ss", str(start)] if start else []) + (["-t", str(dur)] if dur else [])
    cmd += ["-protocol_whitelist", "file,pipe", "-i", str(path), "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode or not r.stdout:
        raise FishError(f"could not read sound from {Path(path).name}: {r.stderr.decode('utf-8', 'replace')[-160:].strip() or 'no audio stream'}")
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).copy()


def tidy(a, trim: bool = True, fade_in: float = 0.003, fade_out: float = 0.03, peak_db: float = -1.0, floor_db: float = -40.0):
    """Keep the sound, lose the silence around it, fade both ends and set the peak.

    trim cuts everything before the first and after the last sample above floor_db (relative to the peak), keeping
    5 ms before the hit so its attack survives. A cue plays from sample 0, so the hit has to start there."""
    import numpy as np
    a = np.asarray(a, dtype=np.float32)
    if a.ndim == 1:
        a = np.stack([a, a], axis=1)
    pk = float(np.abs(a).max()) if len(a) else 0.0
    if pk < 1e-6:
        raise FishError("the sound is silent")
    if trim:
        loud = np.flatnonzero(np.abs(a).max(axis=1) >= pk * 10 ** (floor_db / 20))
        a = a[max(0, int(loud[0]) - int(0.005 * SR)): int(loud[-1]) + 1 + int(0.02 * SR)]
    a = a / pk * 10 ** (peak_db / 20)
    fi, fo = min(len(a) // 2, int(fade_in * SR)), min(len(a) // 2, int(fade_out * SR))
    if fi:
        a[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    if fo:
        a[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    return a


def write_wav(path: Path | str, a) -> Path:
    """16-bit PCM WAV (every tool reads it)."""
    import numpy as np
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(a, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    return path


def project_pack(project: Path) -> dict:
    return load_json(project / "assets" / "sfx" / "pack.json", default={"levels": {}})


def set_level(project: Path, cue: str, db: float) -> None:
    """Remember a cue type's level for this project (assets/sfx/pack.json; brief.mix.sfx_levels still wins)."""
    data = project_pack(project)
    data.setdefault("levels", {})[cue] = float(db)
    save_json(project / "assets" / "sfx" / "pack.json", data)


# ------------------------------------------------------------------ synthesis
def _t(sec: float):
    import numpy as np
    return np.arange(int(sec * SR)) / SR


def _env(n: int, attack: float, decay: float):
    """Linear attack, exponential decay (seconds to fall to 1/e)."""
    import numpy as np
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(attack, 1e-4)) * np.exp(-np.maximum(0.0, t - attack) / max(decay, 1e-4))


def _noise(n: int, seed: int):
    import numpy as np
    return np.random.default_rng(seed).uniform(-1.0, 1.0, n)


def _band(x, lo: float, hi: float):
    """Keep lo..hi Hz (FFT brick wall with soft 12% edges: no filter state to manage)."""
    import numpy as np
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.clip((f - lo * 0.88) / max(lo * 0.12, 1.0), 0, 1) * np.clip((hi * 1.12 - f) / max(hi * 0.12, 1.0), 0, 1)
    return np.fft.irfft(X * g, len(x))


def _tone(freq, harmonics=(1.0,), phase: float = 0.0):
    """A tone whose pitch follows `freq` (Hz per sample); harmonics are amplitudes of partials 1, 2, 3..."""
    import numpy as np
    ph = TAU * np.cumsum(freq) / SR + phase
    return sum(a * np.sin(k * ph) for k, a in enumerate(harmonics, 1) if a)


def _room(x, seconds: float = 1.2, mix: float = 0.3, seed: int = 7):
    """A plain reverb: convolve with decaying noise."""
    import numpy as np
    n = int(seconds * SR)
    ir = _noise(n, seed) * np.exp(-np.arange(n) / (seconds * SR / 5))
    ir = _band(ir, 150, 7000)
    m = len(x) + n
    wet = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)
    wet /= max(1e-9, np.abs(wet).max())
    out = np.zeros(m)
    out[: len(x)] = x
    return out * (1 - mix) + wet * mix * max(1e-9, np.abs(x).max())


def _place(parts: list[tuple[float, object]], total: float):
    import numpy as np
    out = np.zeros(int(total * SR))
    for at, x in parts:
        i = int(at * SR)
        x = x[: max(0, len(out) - i)]
        out[i:i + len(x)] += x
    return out


SAW = tuple(1 / k for k in range(1, 15))
BRASS = tuple((1 / k) * (1.0 if k < 6 else 0.5) for k in range(1, 13))


def _bassboom():
    import numpy as np
    t = _t(1.1)
    body = np.sin(TAU * np.cumsum(38 + 85 * np.exp(-t / 0.07)) / SR) * _env(len(t), 0.004, 0.42)
    thud = _band(_noise(len(t), 1), 40, 900) * _env(len(t), 0.001, 0.05) * 0.5
    return _room(body + thud, 1.6, 0.35)


def _airhorn():
    import numpy as np
    def blast(sec):
        t = _t(sec)
        bend = 1 - 0.06 * np.exp(-t / 0.03)
        x = sum(_tone(np.full(len(t), f) * bend * (1 + 0.004 * np.sin(TAU * 5.5 * t)), SAW) for f in (349.0, 440.0, 523.0))
        return np.tanh(1.6 * x / 3) * np.minimum(1, t / 0.012) * np.minimum(1, (sec - t) / 0.03)
    return _place([(0.0, blast(0.13)), (0.2, blast(0.13)), (0.4, blast(0.85))], 1.3)


def _sadtrombone():
    import numpy as np
    parts, at = [], 0.0
    for f0, sec, fall in ((233.1, 0.42, 0.0), (220.0, 0.42, 0.0), (207.7, 0.42, 0.0), (196.0, 1.25, 0.16)):
        t = _t(sec)
        f = f0 * (1 - fall * (t / sec) ** 2) * (1 + 0.012 * np.sin(TAU * 5.2 * t) * np.minimum(1, t / 0.3))
        mute = 0.25 + 0.75 * np.sin(np.pi * np.minimum(1, t / sec)) ** 0.6          # the "wah": the bell opens and closes
        ph = TAU * np.cumsum(f) / SR
        x = sum((1 / k) * np.exp(-k / (1.5 + 9 * mute)) * np.sin(k * ph) for k in range(1, 13))
        parts.append((at, x * np.minimum(1, t / 0.03) * np.minimum(1, (sec - t) / 0.08)))
        at += sec + 0.03
    return _room(_place(parts, at + 0.1), 0.8, 0.15)


def _drum(seed: int, f0: float, f1: float, tone_decay: float, noise_decay: float, lo: float, hi: float, noise_amt: float):
    import numpy as np
    t = _t(max(tone_decay, noise_decay) * 6)
    tone = np.sin(TAU * np.cumsum(f1 + (f0 - f1) * np.exp(-t / 0.02)) / SR) * _env(len(t), 0.001, tone_decay)
    return tone + _band(_noise(len(t), seed), lo, hi) * _env(len(t), 0.001, noise_decay) * noise_amt


def _cymbal(seed: int, decay: float):
    import numpy as np
    t = _t(decay * 5)
    metal = sum(np.sign(np.sin(TAU * f * t)) for f in (3120.0, 4270.0, 5410.0, 6830.0, 8170.0)) / 5
    return _band(metal * 0.5 + _noise(len(t), seed), 4500, 15000) * _env(len(t), 0.002, decay)


def _rimshot():
    return _place([(0.0, _drum(2, 260, 190, 0.07, 0.09, 180, 7000, 0.9)), (0.17, _drum(3, 190, 120, 0.12, 0.05, 90, 3000, 0.4)),
                   (0.38, _drum(4, 150, 60, 0.12, 0.03, 40, 800, 0.3) * 0.8), (0.38, _cymbal(5, 0.32) * 0.9)], 2.0)


def _boing():
    import numpy as np
    t = _t(0.95)
    f = 150 + 330 * np.exp(-t / 0.3) * (0.55 + 0.45 * np.sin(TAU * 11 * t))
    return _tone(f, (1.0, 0.45, 0.2)) * _env(len(t), 0.003, 0.3)


def _whistle(up: bool):
    import numpy as np
    t = _t(0.75)
    sweep = (t / 0.75) ** 1.5 if up else 1 - (t / 0.75) ** 0.7
    f = (520 + 1500 * sweep) * (1 + 0.006 * np.sin(TAU * 6 * t))
    breath = _band(_noise(len(t), 6), 2000, 9000) * 0.05
    return (_tone(f, (1.0, 0.12, 0.05)) + breath) * np.minimum(1, t / 0.03) * np.minimum(1, (0.75 - t) / 0.06)


def _scratch():
    import numpy as np
    t = _t(0.5)
    pos = np.where(t < 0.16, t / 0.16, np.where(t < 0.42, 1 - (t - 0.16) / 0.26 * 1.4, -0.4 + (t - 0.42) / 0.08 * 0.3))   # the record's position
    speed = np.abs(np.gradient(pos) * SR)
    grain = _band(_noise(len(t), 8), 300, 6500)
    tone = np.sin(TAU * np.cumsum(180 + 420 * speed) / SR)
    return (0.6 * grain + 0.5 * tone) * np.clip(speed / 5, 0, 1) * np.minimum(1, (0.5 - t) / 0.03)


def _crickets():
    import numpy as np
    t = _t(2.6)
    def bug(freq, period, offset, pan_seed):
        gate = ((t + offset) % period < 0.105) & (((t + offset) % 0.035) < 0.02)
        soft = np.convolve(gate.astype(float), np.hanning(int(0.004 * SR)), "same")
        return np.sin(TAU * freq * t) * soft / max(1e-9, soft.max())
    return (bug(4300, 0.42, 0.0, 1) + 0.6 * bug(3850, 0.57, 0.21, 2) + _band(_noise(len(t), 9), 2000, 9000) * 0.015) * np.minimum(1, t / 0.2) * np.minimum(1, (2.6 - t) / 0.3)


def _bleep():
    import numpy as np
    t = _t(0.5)
    return np.sin(TAU * 1000 * t) * np.minimum(1, t / 0.005) * np.minimum(1, (0.5 - t) / 0.005)


def _sting():
    import numpy as np
    def hit(f0, sec):
        t = _t(sec)
        x = _tone(np.full(len(t), f0), BRASS) + 0.6 * _tone(np.full(len(t), f0 / 2), BRASS) + 0.5 * _tone(np.full(len(t), f0 * 1.498), BRASS)
        return _band(x, 40, 2600) * np.minimum(1, t / 0.02) * np.exp(-t / (sec * 0.9)) + np.pad(_drum(11, 110, 55, 0.25, 0.04, 40, 600, 0.3), (0, len(t)))[: len(t)] * 1.2
    return _room(_place([(0.0, hit(196.0, 0.3)), (0.36, hit(196.0, 0.3)), (0.72, hit(155.6, 1.6))], 2.5), 1.4, 0.3)


def _ding():
    import numpy as np
    t = _t(1.3)
    return sum(a * np.sin(TAU * 1318.5 * r * t) * np.exp(-t / d) for r, a, d in ((1.0, 1.0, 0.45), (2.76, 0.45, 0.2), (5.4, 0.25, 0.1), (8.93, 0.12, 0.06))) * np.minimum(1, t / 0.002)


def _buzzer():
    import numpy as np
    t = _t(0.6)
    x = np.sign(np.sin(TAU * 110 * t)) + np.sign(np.sin(TAU * 116.5 * t))
    return _band(x, 60, 4200) * np.minimum(1, t / 0.008) * np.minimum(1, (0.6 - t) / 0.02)


def _fanfare():
    import numpy as np
    def chord(freqs, sec, decay):
        t = _t(sec)
        x = sum(_tone(np.full(len(t), f) * (1 + 0.004 * np.sin(TAU * 5 * t)), BRASS) for f in freqs)
        return _band(x, 120, 6000) * np.minimum(1, t / 0.015) * np.exp(-np.maximum(0, t - 0.1) / decay) * np.minimum(1, (sec - t) / 0.05)
    return _room(_place([(0.0, chord((392.0, 493.9, 587.3), 0.14, 0.3)), (0.19, chord((523.3, 659.3, 784.0, 1046.5), 1.1, 0.7))], 1.5), 0.9, 0.2)


def _heartbeat():
    def thump(amp):
        return _drum(12, 95, 48, 0.09, 0.03, 30, 300, 0.25) * amp
    return _place([(k * 0.86 + d, thump(a)) for k in range(3) for d, a in ((0.0, 1.0), (0.27, 0.7))], 2.8)


def _drumroll():
    import numpy as np
    parts, at, k = [], 0.0, 0
    while at < 1.55:
        gap = 0.055 - 0.028 * (at / 1.55)
        parts.append((at, _drum(20 + k % 5, 240, 185, 0.03, 0.05, 200, 7500, 1.0) * (0.35 + 0.65 * at / 1.55)))
        at += gap
        k += 1
    return _place(parts + [(1.6, _cymbal(26, 0.5) * 1.3), (1.6, _drum(27, 140, 50, 0.16, 0.04, 35, 700, 0.3) * 1.3)], 3.4)


def _clock():
    def tick(f):
        return _drum(30, f, f, 0.004, 0.006, 1800, 9000, 0.8)
    return _place([(k * 0.5, tick(2400 if k % 2 == 0 else 1900)) for k in range(8)], 4.1)


# name -> (generator, default level in dBFS before the master, what it is)
SYNTH = {
    "bassboom": (_bassboom, -12, "a deep boom with a long room tail: the punchline lands"),
    "airhorn": (_airhorn, -15, "three brassy horn blasts: hype, a win"),
    "sadtrombone": (_sadtrombone, -14, "four falling notes: a failure"),
    "rimshot": (_rimshot, -14, "two drums and a cymbal: a joke's button"),
    "boing": (_boing, -16, "a spring: something bounces or pops up"),
    "whistleup": (_whistle, -18, "a slide whistle rising"),
    "whistledown": (_whistle, -18, "a slide whistle falling: something drops"),
    "scratch": (_scratch, -15, "a record scratch: stop, wait, what"),
    "crickets": (_crickets, -20, "night insects: an awkward silence"),
    "bleep": (_bleep, -18, "a 1 kHz tone: a censored word"),
    "sting": (_sting, -13, "three low brass hits: a dramatic reveal"),
    "ding": (_ding, -18, "a small bell: correct, an idea"),
    "buzzer": (_buzzer, -16, "a harsh buzz: wrong"),
    "fanfare": (_fanfare, -14, "a short two-chord fanfare: ta-da"),
    "heartbeat": (_heartbeat, -14, "three slow double thumps: suspense"),
    "drumroll": (_drumroll, -16, "a snare roll into a crash: the reveal is coming"),
    "clock": (_clock, -22, "eight ticks: waiting, thinking"),
}


def render(name: str):
    """One synthesised sound, tidied: float32 stereo at 48 kHz."""
    if name not in SYNTH:
        raise FishError(f"unknown synth sound '{name}': one of {', '.join(sorted(SYNTH))}")
    fn = SYNTH[name][0]
    x = fn(name == "whistleup") if fn is _whistle else fn()
    return tidy(x, peak_db=-1.0, fade_out=0.04)


def synth(project=None, only: list[str] | None = None, every: bool = False, out=None) -> list[Path]:
    """Write synthesised comedy sounds as cue types. A type the library already has a real recording of is skipped
    (a recording beats a synthesiser) unless it is named in `only` or every=True."""
    project = ensure_project(project) if project else None
    if not project and not out:
        raise FishError("give a project, or --out DIR")
    names = only or sorted(SYNTH)
    have = set(sfx.library(project)) if project else set(sfx.library(Path(out)))
    dest = Path(out) if out else project / "assets" / "sfx"
    files = []
    for n in names:
        if n not in SYNTH:
            raise FishError(f"unknown synth sound '{n}': one of {', '.join(sorted(SYNTH))}")
        if n in have and not only and not every:
            log(f"  skipped {n}: there is already a sound for this cue type")
            continue
        f = write_wav(dest / n / "synth.wav", render(n))
        files.append(f)
        if project and not out:
            set_level(project, n, SYNTH[n][1])
        log(f"  {n:<12} {f}")
    if project and files and not out:
        add_credit(project, {"id": "synth-comedy-pack", "provider": "synth", "kind": "sfx", "title": "Synthesised comedy sounds", "author": "Fish Video Skill",
                             "url": "", "license": "CC0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "attribution_required": False,
                             "risk": "safe", "file": "assets/sfx"})
    log(f"synthesised {len(files)} sound(s). Nobody has heard them: run `sounds audition` and listen before you rely on one.")
    return files


# ------------------------------------------------------------------ add a sound you have
def add(project, src, cue: str, start: float | None = None, dur: float | None = None, level: float | None = None, title: str | None = None,
        author: str | None = None, source: str | None = None, source_url: str | None = None, license: str | None = None,
        accept_risk: bool = False, trim: bool = True) -> Path:
    """Install an audio or video file's sound as cue type `cue`: the hit trimmed to sample 0, ends faded, peak at -1 dBFS."""
    project = ensure_project(project)
    src = Path(src)
    if not src.is_file():
        raise FishError(f"missing file: {src}")
    if fvnet.safe_name(cue) != cue or not cue.replace("_", "").replace("-", "").isalnum():
        raise FishError(f"cue type '{cue}' must be letters, digits, dash or underscore (it becomes a folder name)")
    risk, lic, lurl, att = fvnet.claim_license(source, license)
    name = fvnet.safe_name(slugify(title or src.stem) or "sound")
    rec = {"id": f"{fvnet.safe_name(source or 'own')}-sfx-{cue}-{name}", "provider": source or "own", "kind": "sfx", "title": (title or src.stem)[:140],
           "url": source_url or "", "author": author or "unknown", "license": lic, "license_url": lurl, "attribution_required": att, "risk": risk}
    fvnet.check_risk(project, rec, accept_risk)
    a = tidy(decode(src, start, dur), trim=trim)
    dest = write_wav(project / "assets" / "sfx" / cue / f"{name}.wav", a)
    rec["file"] = str(dest.relative_to(project)).replace("\\", "/")
    add_credit(project, rec)
    known = sfx.levels(project)
    if level is not None or cue not in known:
        set_level(project, cue, level if level is not None else -16.0)
    log(f"cue '{cue}': {len(a) / SR:.2f} s -> {rec['file']}  [{lic}; risk: {risk}]  level {sfx.levels(project).get(cue)} dBFS")
    return dest


# ------------------------------------------------------------------ list and audition
def catalogue(project) -> list[dict]:
    """Every cue type with a sample: [{cue, files, level, where}]."""
    project = ensure_project(project)
    lv = sfx.levels(project)
    out = []
    for cue, files in sorted(sfx.library(project).items()):
        f = files[0]
        where = "project" if project.resolve() in f.resolve().parents else "meme pack" if f.parent.name == "meme" else "library"
        out.append({"cue": cue, "files": len(files), "file": f, "level": lv.get(cue, -22), "where": where, "note": SYNTH.get(cue, (None, None, ""))[2] if f.name == "synth.wav" else ""})
    return out


def audition(project, out=None, max_each: float = 4.0) -> Path:
    """One montage of every cue type, with a text index of what plays when: the agent cannot hear, the user can."""
    import numpy as np
    project = ensure_project(project)
    items = catalogue(project)
    if not items:
        raise FishError("no sounds yet: run `sounds synth`, `sounds add` or `assets sfx-pack`")
    out = Path(out) if out else project / "build" / "auditions" / "sfx.wav"
    parts, lines, at = [], ["time   cue           level   source      file"], 0.0
    for it in items:
        a = decode(it["file"])[: int(max_each * SR)]
        a = tidy(a, trim=False, fade_out=0.08, peak_db=-3.0)
        lines.append(f"{int(at // 60)}:{at % 60:04.1f}  {it['cue']:<13} {it['level']:>5} dB  {it['where']:<10}  {it['file'].name}" + (f"   ({it['note']})" if it["note"] else ""))
        parts.append((at, a))
        at += len(a) / SR + 0.6
    mix = np.zeros((int(at * SR), 2), dtype=np.float32)
    for t0, a in parts:
        i = int(t0 * SR)
        mix[i:i + len(a)] += a
    write_wav(out, mix)
    out.with_suffix(".txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"{len(items)} cue types, {at:.0f} s -> {out}  (index: {out.with_suffix('.txt').name})")
    return out


# ------------------------------------------------------------------ CLI
def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sounds.py", description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("list"); a.add_argument("project")
    a = sp.add_parser("synth"); a.add_argument("project", nargs="?"); a.add_argument("--only"); a.add_argument("--all", action="store_true"); a.add_argument("--out")
    a = sp.add_parser("search"); a.add_argument("project"); a.add_argument("q"); a.add_argument("-n", type=int, default=12); a.add_argument("--providers")
    a.add_argument("--unverified", action="store_true")
    a = sp.add_parser("add"); a.add_argument("project"); a.add_argument("src"); a.add_argument("cue"); a.add_argument("--start", type=float); a.add_argument("--dur", type=float)
    a.add_argument("--level", type=float); a.add_argument("--title"); a.add_argument("--author"); a.add_argument("--source"); a.add_argument("--source-url"); a.add_argument("--license")
    a.add_argument("--accept-risk", action="store_true"); a.add_argument("--no-trim", action="store_true")
    a = sp.add_parser("audition"); a.add_argument("project"); a.add_argument("--out")
    ns = ap.parse_args(argv)
    if ns.cmd == "list":
        for it in catalogue(ns.project):
            log(f"  {it['cue']:<13} {it['files']:>3} file(s)  {it['level']:>5} dB  {it['where']:<10} {it['note']}")
        log("synthesised types (`sounds synth`): " + ", ".join(sorted(SYNTH)))
    elif ns.cmd == "synth":
        synth(ns.project, ns.only.split(",") if ns.only else None, ns.all, ns.out)
    elif ns.cmd == "search":
        import assets
        assets.search(ns.project, ns.q, "sfx", ns.providers.split(",") if ns.providers else None, ns.n, True if ns.unverified else None)
    elif ns.cmd == "add":
        add(ns.project, ns.src, ns.cue, ns.start, ns.dur, ns.level, ns.title, ns.author, ns.source, ns.source_url, ns.license, ns.accept_risk, not ns.no_trim)
    elif ns.cmd == "audition":
        audition(ns.project, ns.out)
    return 0


if __name__ == "__main__":
    main_guard(cli)
