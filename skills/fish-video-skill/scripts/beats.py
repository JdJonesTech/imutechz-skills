"""Music analysis: tempo, beat grid, first downbeat and the drop.

    python scripts/beats.py <track>          prints JSON {bpm, first_downbeat, beats[], drop, engine}

Use it to lock a video to a track:
  storyboard.yaml  bpm: <bpm>                  every bar and cut then lands on the beat grid
  brief.yaml       music: {offset: <first_downbeat>}   the track starts on its first downbeat
  or               music: {offset: <drop - t_reveal>}  the drop lands on the reveal scene
                   (t_reveal = the reveal scene's t0 in build/timeline-<platform>.json)
`render` seeks into the track by music.offset seconds; with no offset it plays from 0 as before.

Uses librosa (beat_track over an onset-strength envelope) when installed, otherwise a numpy
fallback (onset envelope + autocorrelation + phase search). The drop is the biggest rise of
smoothed RMS that follows a low-energy stretch.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from fvcore import FishError, ffmpeg_bin, main_guard

SR = 22050
HOP = 512


def load(path: Path, max_seconds: float = 240) -> np.ndarray:
    p = subprocess.run([ffmpeg_bin(), "-v", "error", "-t", str(max_seconds), "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    if p.returncode != 0 or not p.stdout:
        raise FishError(f"cannot decode audio: {path}")
    return np.frombuffer(p.stdout[: len(p.stdout) // 4 * 4], dtype=np.float32).copy()


def onset_envelope(y: np.ndarray) -> np.ndarray:
    """Spectral-flux onset strength, one value per HOP samples."""
    n_fft = 1024
    if len(y) < n_fft * 2:
        return np.zeros(1)
    n = 1 + (len(y) - n_fft) // HOP
    idx = np.arange(n_fft)[None, :] + HOP * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(y[idx] * np.hanning(n_fft), axis=1))
    logs = np.log1p(spec * 20)
    env = np.maximum(0, np.diff(logs, axis=0)).sum(1)
    return np.r_[0.0, env]


def _numpy_beats(y: np.ndarray) -> tuple[float, list[float]]:
    env = onset_envelope(y)
    fps = SR / HOP
    e = env - env.mean()
    lo, hi = int(fps * 60 / 180), int(fps * 60 / 60)
    ac = np.array([float((e[:-l] * e[l:]).sum()) if l < len(e) else 0.0 for l in range(lo, hi + 1)])
    if not len(ac) or ac.max() <= 0:
        raise FishError("no steady beat found")
    lag = lo + int(ac.argmax())
    bpm = 60 * fps / lag
    while bpm < 80:
        bpm *= 2
    while bpm > 170:
        bpm /= 2
    period = 60 * fps / bpm
    best, phase = -1.0, 0.0
    for ph in np.arange(0, period, 0.5):
        pos = np.arange(ph, len(env) - 1, period).astype(int)
        sc = float(env[pos].sum())
        if sc > best:
            best, phase = sc, float(ph)
    beats = [round(float(p) / fps, 3) for p in np.arange(phase, len(env) - 1, period)]
    return bpm, beats


def _librosa_beats(y: np.ndarray) -> tuple[float, list[float]]:
    import librosa
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    tempo, frames = librosa.beat.beat_track(onset_envelope=env, sr=SR, hop_length=HOP)
    bpm = float(np.atleast_1d(tempo)[0])
    return bpm, [round(float(t), 3) for t in librosa.frames_to_time(frames, sr=SR, hop_length=HOP)]


def downbeat(beats: list[float], y: np.ndarray) -> float | None:
    """First downbeat: of the 4 possible bar phases, the one whose beats carry the most low-band energy
    (the kick / bass lands on the one). Falls back to the first beat."""
    if len(beats) < 8:
        return beats[0] if beats else None
    n_fft = 2048
    scores = []
    for ph in range(4):
        tot = 0.0
        for t in beats[ph::4][:24]:
            s = int(t * SR)
            seg = y[s:s + n_fft]
            if len(seg) < n_fft:
                continue
            sp = np.abs(np.fft.rfft(seg * np.hanning(n_fft)))
            tot += float(sp[1:int(150 * n_fft / SR)].sum())
        scores.append(tot)
    return beats[int(np.argmax(scores))]


def find_drop(y: np.ndarray, win_s: float = 1.0) -> float | None:
    """Largest jump of smoothed RMS that follows a low-energy stretch (>= ~3 s quieter than the median)."""
    hop = SR // 10
    n = len(y) // hop
    if n < 60:
        return None
    rms = np.sqrt((y[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    k = max(1, int(win_s * 10))
    sm = np.convolve(rms, np.ones(k) / k, mode="same")
    quiet = sm < np.median(sm) * 0.75
    best, at = 0.0, None
    span = 30  # 3 s look-back / look-ahead
    for i in range(span, n - span):
        before, after = sm[i - span:i], sm[i:i + span]
        if quiet[i - span:i].mean() < 0.6:
            continue
        jump = float(after.mean() - before.mean())
        if jump > best:
            best, at = jump, i
    if at is None:
        return None
    # refine to the steepest single step inside +-1.5 s
    seg = np.diff(sm[max(0, at - 15):at + 15])
    return round((max(0, at - 15) + int(np.argmax(seg)) + 1) / 10, 2)


def analyse(path) -> dict:
    path = Path(path)
    y = load(path)
    engine = "numpy"
    try:
        import librosa  # noqa: F401
        bpm, beats = _librosa_beats(y)
        engine = "librosa"
    except ImportError:
        bpm, beats = _numpy_beats(y)
    return {"bpm": round(bpm, 1), "first_downbeat": downbeat(beats, y), "beats": beats, "drop": find_drop(y), "engine": engine}


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("track")
    ns = ap.parse_args(argv)
    print(json.dumps(analyse(ns.track)))
    return 0


if __name__ == "__main__":
    main_guard(cli)
