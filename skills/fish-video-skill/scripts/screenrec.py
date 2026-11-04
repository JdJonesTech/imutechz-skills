"""Desktop screen recorder that produces a `tour`-compatible capture folder.

    python scripts/screenrec.py record <project> <shot> [--seconds 20] [--region x,y,w,h] [--window "Title"] [--fps 30] [--scale 2]
    python scripts/screenrec.py import <project> <shot> <file.mp4> [--cursor cursor.json] [--fps 30] [--scale 1]
    python scripts/screenrec.py tighten <project> <shot> [--idle-speed 6] [--threshold 0.6] [--min-idle 1.5] [--keep 0.3]

Records the real desktop with ffmpeg (gdigrab on Windows, avfoundation on
macOS, x11grab on Linux) WITHOUT the OS cursor: the stage redraws it. In
parallel the cursor position, mouse buttons and modifier key-combos are
logged at 60 Hz (ctypes on Windows; pynput elsewhere when installed, else
cursor-less). Typed text is never logged: only key names while Ctrl / Alt /
Win is held (e.g. "ctrl+c") become badges.

Stop with --seconds, F9, or Ctrl+C. F8 drops a mark (m1, m2, ...).

Output (identical to scripts/recorder.mjs):
  <project>/build/cap/<shot>/NNNNN.jpg   (5 digits, 0-based)
  <project>/build/cap/<shot>/meta.json   {id, fps, w, h, dpr, count, marks, frames:[{x,y,d,c,k,s}], errors}
w,h are the region size in logical px (= recorded pixels / scale), dpr = scale,
and x,y are in that logical space, so frame size == w*dpr x h*dpr.
Raw video is kept at <project>/build/rec/<shot>.mp4.

cursor.json for `import`: {"cursor": [{"t": sec, "x": px, "y": px, "d": 0|1, "c": 0|1, "k": "ctrl+c"}], "marks": {"m1": sec}}
(x,y in video pixels), or a ready recorder meta ({"frames": [...]}).
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from fvcore import IS_WIN, FishError, ensure_project, ffmpeg_bin, ffprobe_bin, log, main_guard, run, save_json, warn

STOP_KEY, MARK_KEY = 0x78, 0x77  # F9, F8
MODS = {0x11: "ctrl", 0x12: "alt", 0x5B: "win", 0x5C: "win", 0x10: "shift"}
_NAMES = {0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x1B: "esc", 0x20: "space", 0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
          0x2E: "delete", 0x24: "home", 0x23: "end", 0x21: "pageup", 0x22: "pagedown", 0xBB: "+", 0xBD: "-", 0xBC: ",", 0xBE: ".", 0xBF: "/",
          0xDB: "[", 0xDD: "]", 0xBA: ";", 0xDE: "'", 0xC0: "`", 0xDC: "\\"}


def key_name(vk: int) -> str | None:
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk).lower()
    if 0x70 <= vk <= 0x87:
        return f"f{vk - 0x6F}"
    return _NAMES.get(vk)


# ------------------------------------------------------------------ pure conversion (testable, no OS)
def build_frames(samples: list[dict], n: int, fps: float, region: tuple[int, int, int, int], scale: float, w: int, h: int) -> list[dict]:
    """Per-frame cursor/click/key records from time-stamped samples.

    samples: [{t, x, y, d, c, k}] with x,y in SCREEN pixels, t seconds since video start.
    Frame i is at i/fps. x,y are mapped into the region and divided by scale (logical px).
    Clicks (c) fire on the frame whose interval (prev, now] holds a button-down edge; k likewise.
    """
    rx, ry = region[0], region[1]
    samples = sorted(samples, key=lambda s: s["t"])
    ts = [s["t"] for s in samples]
    frames = []
    prev_t = -1.0 / fps
    cx, cy = w * 0.5, h * 0.5
    for i in range(n):
        t = i / fps
        j = bisect.bisect_right(ts, t)
        if samples:
            a = samples[max(j - 1, 0)]
            b = samples[min(j, len(samples) - 1)]
            if b["t"] > a["t"] and a["t"] <= t:
                u = (t - a["t"]) / (b["t"] - a["t"])
                px, py = a["x"] + (b["x"] - a["x"]) * u, a["y"] + (b["y"] - a["y"]) * u
            else:
                px, py = a["x"], a["y"]
            cx = min(max((px - rx) / scale, 0), w)
            cy = min(max((py - ry) / scale, 0), h)
        lo, hi = bisect.bisect_right(ts, prev_t), bisect.bisect_right(ts, t)
        window = samples[lo:hi]
        click = 1 if any(s.get("c") for s in window) else 0
        key = next((s["k"] for s in window if s.get("k")), None)
        held = samples[max(hi - 1, 0)].get("d", 0) if samples and hi > 0 else 0
        frames.append({"x": round(cx, 1), "y": round(cy, 1), "d": 1 if held else 0, "c": click, "k": key, "s": 0})
        prev_t = t
    return frames


def marks_to_frames(marks_t: dict, fps: float, n: int) -> dict:
    return {k: min(max(int(round(v * fps)), 0), max(n - 1, 0)) for k, v in marks_t.items()}


def extract_frames(video: Path, outdir: Path, fps: int, quality: int = 3) -> int:
    shutil.rmtree(outdir, ignore_errors=True)
    outdir.mkdir(parents=True, exist_ok=True)
    run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-an", "-vf", f"fps={fps}", "-start_number", "0",
         "-q:v", str(quality), str(outdir / "%05d.jpg")])
    return len(list(outdir.glob("[0-9][0-9][0-9][0-9][0-9].jpg")))


def probe_size(video: Path) -> tuple[int, int]:
    r = run([ffprobe_bin(), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(video)], capture=True)
    s = json.loads(r.stdout)["streams"][0]
    return int(s["width"]), int(s["height"])


def write_capture(project: Path, shot: str, video: Path, samples: list[dict], marks_t: dict, fps: int, region: tuple[int, int, int, int], scale: float) -> dict:
    """Video + samples -> build/cap/<shot>/ (frames + meta.json in the recorder.mjs schema)."""
    outdir = project / "build" / "cap" / shot
    n = extract_frames(video, outdir, fps)
    if n == 0:
        raise FishError("no frames were extracted (the recording is empty)")
    vw, vh = probe_size(video)
    w, h = round(vw / scale), round(vh / scale)
    frames = build_frames(samples, n, fps, region, scale, w, h)
    meta = {"id": shot, "fps": fps, "w": w, "h": h, "dpr": scale, "count": n, "marks": marks_to_frames(marks_t, fps, n), "frames": frames, "errors": [],
            "source": "screenrec"}
    outdir.joinpath("meta.json").write_text(json.dumps(meta), encoding="utf-8")
    log(f"{n} frames ({vw}x{vh} px -> {w}x{h} @ dpr {scale}) -> {outdir}")
    return meta


# ------------------------------------------------------------------ cursor / key tracking
class Tracker:
    """Samples cursor + buttons + modifier combos at ~60 Hz on a thread."""

    def __init__(self, hz: int = 60):
        self.hz = hz
        self.samples: list[dict] = []
        self.marks: dict[str, float] = {}
        self.t0 = 0.0
        self.stop_requested = False
        self._stop = threading.Event()
        self._th: threading.Thread | None = None
        self.available = True

    def start(self, t0: float | None = None):
        self.t0 = t0 if t0 is not None else time.perf_counter()
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._th.start()

    def stop(self):
        self._stop.set()
        if self._th:
            self._th.join(timeout=2)

    def _loop(self):
        raise NotImplementedError


class WinTracker(Tracker):
    def _loop(self):
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        pt = wintypes.POINT()
        gks = u.GetAsyncKeyState
        prev_l = prev_r = False
        prev_keys: set[int] = set()
        f8 = f9 = False
        period = 1.0 / self.hz
        nxt = time.perf_counter()
        scan = [v for v in range(0x08, 0xFF) if v not in MODS and v not in (0x01, 0x02, 0x04, STOP_KEY, MARK_KEY) and key_name(v)]
        while not self._stop.is_set():
            now = time.perf_counter()
            t = now - self.t0
            u.GetCursorPos(ctypes.byref(pt))
            l, r = bool(gks(0x01) & 0x8000), bool(gks(0x02) & 0x8000)
            c = 1 if ((l and not prev_l) or (r and not prev_r)) else 0
            prev_l, prev_r = l, r
            mods = [name for vk, name in MODS.items() if gks(vk) & 0x8000]
            combo_mods = sorted({m for m in mods if m in ("ctrl", "alt", "win")}, key=["ctrl", "alt", "win"].index)
            k = None
            if combo_mods:  # privacy: key names are only read while a command modifier is held
                cur = {vk for vk in scan if gks(vk) & 0x8000}
                new = cur - prev_keys
                prev_keys = cur
                if new:
                    nm = key_name(sorted(new)[0])
                    k = "+".join((["shift"] if "shift" in mods else []) + combo_mods + [nm]) if nm else None
            else:
                prev_keys = set()
            d9, d8 = bool(gks(STOP_KEY) & 0x8000), bool(gks(MARK_KEY) & 0x8000)
            if d9 and not f9:
                self.stop_requested = True
            if d8 and not f8:
                self.marks[f"m{len(self.marks) + 1}"] = round(t, 3)
            f9, f8 = d9, d8
            self.samples.append({"t": round(t, 4), "x": pt.x, "y": pt.y, "d": 1 if (l or r) else 0, "c": c, "k": k})
            nxt += period
            dly = nxt - time.perf_counter()
            if dly > 0:
                time.sleep(dly)
            else:
                nxt = time.perf_counter()


class PynputTracker(Tracker):
    def _loop(self):
        try:
            from pynput import keyboard, mouse  # type: ignore
        except ImportError:
            self.available = False
            warn("pynput is not installed: recording without cursor data (pip install pynput)")
            return
        ms = mouse.Controller()
        state = {"d": 0, "c": 0, "k": None}
        mods: set[str] = set()
        modmap = {"ctrl": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl", "alt": "alt", "alt_l": "alt", "alt_r": "alt", "cmd": "win", "cmd_l": "win", "cmd_r": "win"}

        def on_click(x, y, button, pressed):
            state["d"] = 1 if pressed else 0
            if pressed:
                state["c"] = 1

        def nm(key):
            n = getattr(key, "name", None)
            return modmap.get(n) if n else None

        def on_press(key):
            if key == keyboard.Key.f9:
                self.stop_requested = True
                return
            if key == keyboard.Key.f8:
                self.marks[f"m{len(self.marks) + 1}"] = round(time.perf_counter() - self.t0, 3)
                return
            m = nm(key)
            if m:
                mods.add(m)
            elif mods:  # only while a command modifier is held
                ch = getattr(key, "char", None) or getattr(key, "name", None)
                if ch:
                    state["k"] = "+".join(sorted(mods, key=["ctrl", "alt", "win"].index) + [str(ch).lower()])

        def on_release(key):
            m = nm(key)
            if m:
                mods.discard(m)

        ml = mouse.Listener(on_click=on_click)
        kl = keyboard.Listener(on_press=on_press, on_release=on_release)
        ml.start(); kl.start()
        period = 1.0 / self.hz
        while not self._stop.is_set():
            t = time.perf_counter() - self.t0
            x, y = ms.position
            self.samples.append({"t": round(t, 4), "x": x, "y": y, "d": state["d"], "c": state["c"], "k": state["k"]})
            state["c"], state["k"] = 0, None
            time.sleep(period)
        ml.stop(); kl.stop()


def make_tracker() -> Tracker:
    return WinTracker() if IS_WIN else PynputTracker()


# ------------------------------------------------------------------ screen geometry
def set_dpi_aware() -> None:
    if not IS_WIN:
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def screen_size() -> tuple[int, int]:
    if IS_WIN:
        import ctypes
        u = ctypes.windll.user32
        return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    try:
        import tkinter
        r = tkinter.Tk(); r.withdraw()
        w, h = r.winfo_screenwidth(), r.winfo_screenheight(); r.destroy()
        return w, h
    except Exception:
        return 1920, 1080


def window_rect(title: str) -> tuple[int, int, int, int]:
    if not IS_WIN:
        raise FishError("--window is only supported on Windows; use --region x,y,w,h")
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    hwnd = u.FindWindowW(None, title)
    if not hwnd:
        raise FishError(f"no window with the exact title '{title}'")
    rc = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(rc))
    return rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top


def parse_region(s: str | tuple | list | None) -> tuple[int, int, int, int] | None:
    if not s:
        return None
    parts = [int(float(x)) for x in (s.split(",") if isinstance(s, str) else s)]
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
        raise FishError("region must be x,y,w,h with positive size")
    return tuple(parts)  # type: ignore


def ffmpeg_capture_args(region: tuple[int, int, int, int], fps: int, window: str | None, out: Path) -> list[str]:
    x, y, w, h = region
    w, h = w - w % 2, h - h % 2
    enc = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p", str(out)]
    if IS_WIN:
        if window:
            src = ["-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "0", "-i", f"title={window}"]
        else:
            src = ["-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "0", "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}", "-i", "desktop"]
        return src + (["-vf", f"crop={w}:{h}:0:0"] if window else []) + enc
    if sys.platform == "darwin":
        sw, sh = screen_size()
        return ["-f", "avfoundation", "-framerate", str(fps), "-capture_cursor", "0", "-i", "1:none", "-vf", f"crop={w}:{h}:{x}:{y}"] + enc
    return ["-f", "x11grab", "-framerate", str(fps), "-draw_mouse", "0", "-video_size", f"{w}x{h}", "-i", f"{os.environ.get('DISPLAY', ':0.0')}+{x},{y}"] + enc


# ------------------------------------------------------------------ record
def record(project, shot_id: str, seconds: float | None = None, region=None, fps: int = 30, scale: float = 2, window: str | None = None,
           countdown: int = 3) -> dict:
    """Record the desktop + cursor, then convert into build/cap/<shot_id>/. Returns the meta dict."""
    project = ensure_project(project)
    set_dpi_aware()
    reg = parse_region(region)
    if window:
        reg = window_rect(window)
    if not reg:
        sw, sh = screen_size()
        reg = (0, 0, sw, sh)
    reg = (reg[0], reg[1], reg[2] - reg[2] % 2, reg[3] - reg[3] % 2)
    raw = project / "build" / "rec" / f"{shot_id}.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.unlink(missing_ok=True)
    tr = make_tracker()
    print(f"\nScreen recording '{shot_id}': region {reg[2]}x{reg[3]} at ({reg[0]},{reg[1]}), {fps} fps, dpr {scale}", flush=True)
    print("  Press F9 to stop, F8 to drop a mark (m1, m2, ...)." + (f" Auto-stop after {seconds:g} s." if seconds else " Ctrl+C also stops."), flush=True)
    print("  The OS cursor is not recorded: it is redrawn in the video. Typed text is never logged.", flush=True)
    for i in range(countdown, 0, -1):
        print(f"  recording in {i}...", flush=True)
        time.sleep(1)
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y"] + ffmpeg_capture_args(reg, fps, window, raw)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    t_spawn = time.perf_counter()
    for _ in range(400):  # wait until the first frames hit the disk -> that is t = 0
        if proc.poll() is not None:
            raise FishError("ffmpeg stopped immediately: " + (proc.stderr.read().decode("utf-8", "replace")[-400:] if proc.stderr else ""))
        if raw.exists() and raw.stat().st_size > 0:
            break
        time.sleep(0.01)
    t0 = time.perf_counter()
    tr.start(t0)
    print("  RECORDING", flush=True)
    try:
        while True:
            if proc.poll() is not None:
                break
            if tr.stop_requested or (seconds and time.perf_counter() - t0 >= seconds):
                break
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("  stopping (Ctrl+C)", flush=True)
    tr.stop()
    try:
        if proc.poll() is None:
            proc.stdin.write(b"q"); proc.stdin.flush()
    except Exception:
        pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    if not raw.exists() or raw.stat().st_size == 0:
        err = proc.stderr.read().decode("utf-8", "replace")[-400:] if proc.stderr else ""
        raise FishError(f"recording failed: {err}")
    if not tr.available:
        warn("no cursor data was captured; the tour will use a static pointer")
    log(f"recorded {time.perf_counter() - t0:.1f} s; converting to frames ...")
    return write_capture(project, shot_id, raw, tr.samples, tr.marks, fps, reg, scale)


# ------------------------------------------------------------------ import
def import_video(project, shot_id: str, mp4, cursor_json=None, fps: int = 30, scale: float = 1) -> dict:
    """An existing screen recording -> build/cap/<shot_id>/ (no cursor data unless cursor_json is given)."""
    project = ensure_project(project)
    mp4 = Path(mp4)
    if not mp4.exists():
        raise FishError(f"missing file: {mp4}")
    cur = None
    if cursor_json:
        cur = json.loads(Path(cursor_json).read_text(encoding="utf-8"))
    if isinstance(cur, dict) and "frames" in cur:  # a ready per-frame track: use as is
        meta = write_capture(project, shot_id, mp4, [], {}, fps, (0, 0, 0, 0), scale)
        outdir = project / "build" / "cap" / shot_id
        fr = cur["frames"]
        n = meta["count"]
        meta["frames"] = [dict({"x": meta["w"] / 2, "y": meta["h"] / 2, "d": 0, "c": 0, "k": None, "s": 0}, **fr[min(i, len(fr) - 1)]) for i in range(n)]
        meta["marks"] = cur.get("marks", {})
        outdir.joinpath("meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return meta
    samples = (cur or {}).get("cursor", []) if isinstance(cur, dict) else (cur or [])
    marks_t = (cur or {}).get("marks", {}) if isinstance(cur, dict) else {}
    meta = write_capture(project, shot_id, mp4, samples, marks_t, fps, (0, 0, 0, 0), scale)
    return meta


# ------------------------------------------------------------------ tighten idle stretches
def frame_changes(frames_dir: Path, n: int) -> list[float]:
    """Mean absolute grey change of each frame against the previous one (0-255 scale, 96 px wide). [0] is 0."""
    import numpy as np
    from PIL import Image
    out, prev = [0.0], None
    for i in range(n):
        with Image.open(frames_dir / f"{i:05d}.jpg") as im:
            g = np.asarray(im.convert("L").resize((96, max(1, round(96 * im.height / im.width)))), dtype=np.float32)
        if prev is not None:
            out.append(float(np.abs(g - prev).mean()))
        prev = g
    return out[:n]


def plan_tighten(diffs: list[float], frames: list[dict], marks: dict, fps: float, idle_speed: int = 6, threshold: float = 0.6,
                 min_idle: float = 1.5, keep: float = 0.3, cursor_px: float = 6.0) -> list[int]:
    """Indices of the frames to KEEP. Idle = picture change below `threshold`, no click, no key badge, and the
    cursor moving less than `cursor_px` per frame. Idle runs longer than `min_idle` s are thinned to every
    `idle_speed`-th frame, except `keep` s around every click / key badge / mark, which stays real-time."""
    n = len(diffs)
    active = [False] * n
    for i in range(n):
        f = frames[i] if i < len(frames) else {}
        step = 0.0
        if i and i < len(frames):
            step = max(abs(f.get("x", 0) - frames[i - 1].get("x", 0)), abs(f.get("y", 0) - frames[i - 1].get("y", 0)))
        active[i] = diffs[i] >= threshold or bool(f.get("c")) or bool(f.get("k")) or step > cursor_px
    guard = int(round(keep * fps))
    pinned = [i for i in range(n) if frames[i].get("c") or frames[i].get("k")] + [int(v) for v in marks.values()]
    protect = [False] * n
    for i in pinned:
        for j in range(max(0, i - guard), min(n, i + guard + 1)):
            protect[j] = True
    idle = [not active[i] and not protect[i] for i in range(n)]
    drop = [False] * n
    i, need = 0, int(round(min_idle * fps))
    while i < n:
        if not idle[i]:
            i += 1
            continue
        j = i
        while j < n and idle[j]:
            j += 1
        if j - i > need and j - i >= 2 * idle_speed:
            for q in range(i, j):
                drop[q] = (q - i) % idle_speed != 0
        i = j
    return [i for i in range(n) if not drop[i]]


def tighten_idle(project, shot_id: str, idle_speed: int = 6, threshold: float = 0.6, min_idle: float = 1.5, keep: float = 0.3) -> dict:
    """Play dead stretches of a capture fast: drops frames, renumbers them and remaps cursor, click and mark
    data in meta.json. The untouched capture is kept at build/cap/<shot>.orig, so re-running starts from it."""
    project = ensure_project(project)
    cap = project / "build" / "cap" / shot_id
    orig = project / "build" / "cap" / f"{shot_id}.orig"
    if not orig.exists():
        if not (cap / "meta.json").exists():
            raise FishError(f"no capture {shot_id} in {cap.parent}")
        cap.rename(orig)
    meta = json.loads((orig / "meta.json").read_text(encoding="utf-8"))
    n, fps = int(meta["count"]), float(meta["fps"])
    frames = meta.get("frames") or [{}] * n
    diffs = frame_changes(orig, n)
    kept = plan_tighten(diffs, frames, meta.get("marks") or {}, fps, idle_speed, threshold, min_idle, keep)
    shutil.rmtree(cap, ignore_errors=True)
    cap.mkdir(parents=True)
    for new, old in enumerate(kept):
        shutil.copyfile(orig / f"{old:05d}.jpg", cap / f"{new:05d}.jpg")
    new_index = {old: new for new, old in enumerate(kept)}
    marks = {}
    for k, v in (meta.get("marks") or {}).items():
        v = int(v)
        marks[k] = new_index.get(v, bisect.bisect_right(kept, v) - 1 if bisect.bisect_right(kept, v) else 0)
    out = {**meta, "count": len(kept), "frames": [frames[i] for i in kept], "marks": marks,
           "tightened": {"from_frames": n, "to_frames": len(kept), "idle_speed": idle_speed, "threshold": threshold,
                         "saved_s": round((n - len(kept)) / fps, 2)}}
    (cap / "meta.json").write_text(json.dumps(out), encoding="utf-8")
    log(f"tighten {shot_id}: {n} -> {len(kept)} frames ({(n - len(kept)) / fps:.1f} s of dead time sped up x{idle_speed})")
    return out


# ------------------------------------------------------------------ CLI
def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="screenrec.py", description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("record"); a.add_argument("project"); a.add_argument("shot"); a.add_argument("--seconds", type=float)
    a.add_argument("--region"); a.add_argument("--window"); a.add_argument("--fps", type=int, default=30); a.add_argument("--scale", type=float, default=2)
    a.add_argument("--countdown", type=int, default=3)
    a = sp.add_parser("import"); a.add_argument("project"); a.add_argument("shot"); a.add_argument("file"); a.add_argument("--cursor")
    a.add_argument("--fps", type=int, default=30); a.add_argument("--scale", type=float, default=1)
    a = sp.add_parser("tighten"); a.add_argument("project"); a.add_argument("shot"); a.add_argument("--idle-speed", type=int, default=6)
    a.add_argument("--threshold", type=float, default=0.6); a.add_argument("--min-idle", type=float, default=1.5); a.add_argument("--keep", type=float, default=0.3)
    ns = ap.parse_args(argv)
    if ns.cmd == "tighten":
        tighten_idle(ns.project, ns.shot, ns.idle_speed, ns.threshold, ns.min_idle, ns.keep)
    elif ns.cmd == "record":
        record(ns.project, ns.shot, ns.seconds, ns.region, ns.fps, ns.scale, ns.window, ns.countdown)
    else:
        import_video(ns.project, ns.shot, ns.file, ns.cursor, ns.fps, ns.scale)
    return 0


if __name__ == "__main__":
    main_guard(cli)
