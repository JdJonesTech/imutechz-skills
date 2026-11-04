"""Shared helpers for the Fish Video Skill Python scripts.

Tool discovery (node, ffmpeg, ffprobe, browser), YAML/JSON I/O, config
merging, subprocess wrappers and small text utilities. Every other module
imports from here, so paths and tool lookup are defined exactly once.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - surfaced by `fishvideo doctor`
    yaml = None

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
IS_WIN = os.name == "nt"


class FishError(RuntimeError):
    """A user-facing error: printed without a traceback by the CLI."""


# ------------------------------------------------------------------ logging
def log(msg: str) -> None:
    print(msg, flush=True)


def warn(msg: str) -> None:
    print(f"!! {msg}", flush=True)


# ------------------------------------------------------------------ files
def load_yaml(path: Path | str) -> Any:
    if yaml is None:
        raise FishError("PyYAML is missing: pip install -r requirements.txt")
    p = Path(path)
    if not p.exists():
        raise FishError(f"missing file: {p}")
    with p.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def save_yaml(path: Path | str, data: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, width=100)
    return p


def load_json(path: Path | str, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        if default is not None:
            return default
        raise FishError(f"missing file: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path: Path | str, data: Any, indent: int = 1) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")
    return p


def deep_merge(base: dict, over: dict | None) -> dict:
    """Recursively merge `over` into a copy of `base` (lists are replaced)."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def defaults() -> dict:
    return load_yaml(SKILL / "config" / "defaults.yaml")


def project_config(project: Path) -> dict:
    """defaults.yaml deep-merged with the project's brief.yaml (brief wins)."""
    brief = load_yaml(Path(project) / "brief.yaml")
    cfg = deep_merge(defaults(), {k: brief[k] for k in ("tempo", "pacing", "voice", "mix", "score", "captions") if isinstance(brief.get(k), dict)})
    # brief.platforms is the list of cuts; brief.platform_profiles overrides profile fields
    cfg["platforms"] = deep_merge(cfg["platforms"], brief.get("platform_profiles") or {})
    cfg["brief"] = brief
    return cfg


def read_env(project: Path | None = None) -> dict:
    """KEY=VALUE pairs from <project>/.env then <skill>/.env (never logged)."""
    out: dict[str, str] = {}
    for p in [SKILL / ".env"] + ([Path(project) / ".env"] if project else []):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
                if m and not line.lstrip().startswith("#"):
                    out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def secret(name: str, project: Path | None = None) -> str:
    """An API key from the environment or a gitignored .env. Never print it."""
    v = os.environ.get(name, "").strip()
    return v or read_env(project).get(name, "").strip()


# ------------------------------------------------------------------ tools
def _first(paths: Iterable[str | Path]) -> str | None:
    for p in paths:
        if p and Path(p).exists():
            return str(p)
    return None


def node_bin() -> str:
    found = os.environ.get("NODE") or shutil.which("node") or _first([
        Path.home() / ".local" / "node" / ("node.exe" if IS_WIN else "node"),
        "/usr/local/bin/node", "/opt/homebrew/bin/node",
    ])
    if not found:
        raise FishError("Node.js not found: install Node 18+ or set NODE=/path/to/node")
    return found


def ffmpeg_bin() -> str:
    exe = "ffmpeg.exe" if IS_WIN else "ffmpeg"
    found = os.environ.get("FFMPEG") or _first([SKILL / "node_modules" / "ffmpeg-static" / exe]) or shutil.which("ffmpeg")
    if not found:
        try:
            import imageio_ffmpeg  # type: ignore
            found = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    if not found:
        raise FishError("ffmpeg not found: run `npm install` in the skill folder or install ffmpeg")
    return found


def ffprobe_bin() -> str:
    exe = "ffprobe.exe" if IS_WIN else "ffprobe"
    plat = {"nt": "win32-x64"}.get(os.name, None)
    cands = [SKILL / "node_modules" / "@ffprobe-installer" / d / exe for d in ([plat] if plat else []) + ["darwin-arm64", "darwin-x64", "linux-x64", "linux-arm64"]]
    found = os.environ.get("FFPROBE") or _first(cands) or shutil.which("ffprobe")
    if not found:
        raise FishError("ffprobe not found: run `npm install` in the skill folder or install ffmpeg")
    return found


BROWSERS = [
    "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/brave-browser", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
]


def browser_bin() -> str | None:
    return os.environ.get("BROWSER") or os.environ.get("BRAVE") or _first(BROWSERS)


# ------------------------------------------------------------------ processes
def run(cmd: list[str], *, cwd: Path | None = None, capture: bool = False, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command; raise FishError with its stderr tail when it fails."""
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=e,
                       capture_output=capture, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        tail = ((r.stderr or "") + (r.stdout or ""))[-1500:] if capture else ""
        raise FishError(f"command failed ({r.returncode}): {' '.join(map(str, cmd[:4]))} ...\n{tail}")
    return r


def node(script: str, *args: Any, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    """Run scripts/<script> with Node from the skill folder."""
    return run([node_bin(), str(SCRIPTS / script), *map(str, args)], cwd=SKILL, capture=capture, check=check)


def last_json_line(text: str) -> Any:
    for line in reversed((text or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


# ------------------------------------------------------------------ text
def slugify(text: str, maxlen: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return (s[:maxlen].rstrip("-")) or "video"


def sha1(obj: Any, n: int = 10) -> str:
    raw = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:n]


def fmt_time(t: float, sep: str = ",") -> str:
    """Seconds -> HH:MM:SS,mmm (SRT) or HH:MM:SS.mmm (VTT, sep='.')."""
    ms = max(0, int(round(t * 1000)))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def mmss(t: float) -> str:
    t = int(round(t))
    return f"{t // 60}:{t % 60:02d}"


def norm_path(p: Path | str) -> Path:
    """Git Bash paths (/c/Users/...) mean C:/Users/... on Windows; otherwise they land in C:\\c\\Users."""
    s = str(p)
    if IS_WIN and re.match(r"^[/\\\\][a-zA-Z][/\\\\]", s):
        s = f"{s[1].upper()}:/{s[3:]}"
    return Path(s)


def ensure_project(project: Path | str) -> Path:
    p = norm_path(project).resolve()
    if not (p / "brief.yaml").exists():
        raise FishError(f"{p} is not a Fish Video project (no brief.yaml). Run `fishvideo new` first.")
    return p


_job = None  # keep the job handle open: closing it would lift the cap


def limit_cpu(percent: int | None = None) -> str:
    """Keep the machine usable: everything this process starts (browsers, ffmpeg, node) runs at lower
    priority and, on Windows, under a hard CPU cap the OS enforces. FISH_CPU_LIMIT=1-100 (default 60;
    100 = no cap, priority still lowered). Failures here never stop a render."""
    global _job
    try:
        pct = int(percent or os.environ.get("FISH_CPU_LIMIT") or 60)
    except ValueError:
        pct = 60
    pct = max(5, min(100, pct))
    os.environ["FISH_CPU_LIMIT"] = str(pct)   # the node side reads it to size its workers
    note = []
    try:
        if IS_WIN:
            import ctypes
            from ctypes import wintypes
            k = ctypes.WinDLL("kernel32", use_last_error=True)
            k.GetCurrentProcess.restype = wintypes.HANDLE
            me = wintypes.HANDLE(k.GetCurrentProcess())
            k.SetPriorityClass(me, 0x00004000)  # BELOW_NORMAL; children inherit it
            note.append("below-normal priority")
            if pct < 100 and _job is None:
                class Rate(ctypes.Structure):
                    _fields_ = [("ControlFlags", wintypes.DWORD), ("CpuRate", wintypes.DWORD)]
                k.CreateJobObjectW.restype = wintypes.HANDLE
                job = k.CreateJobObjectW(None, None)
                info = Rate(0x1 | 0x4, pct * 100)  # ENABLE | HARD_CAP; CpuRate is in 1/100 of a percent
                ok = job and k.SetInformationJobObject(wintypes.HANDLE(job), 15, ctypes.byref(info), ctypes.sizeof(info)) \
                    and k.AssignProcessToJobObject(wintypes.HANDLE(job), me)
                if ok:
                    _job = job
                    note.append(f"hard CPU cap {pct}%")
                else:
                    note.append("cap unavailable: worker count still limits load")
        else:
            os.nice(10)
            note.append("nice +10")
    except Exception as e:  # noqa: BLE001
        note.append(f"limits not applied ({type(e).__name__})")
    return ", ".join(note)


def main_guard(fn) -> None:
    limit_cpu()
    """Run fn(), turning FishError into a clean message and exit code 1."""
    try:
        sys.exit(fn() or 0)
    except FishError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
