"""Small shared network + credits helpers for the research / asset tools.

stdlib only (urllib). Every request sends a descriptive User-Agent, times out
at 20 s and raises NetError (a FishError) with a clear message, so callers can
fail soft. Also hosts the assets/credits.json ledger used by youtube.py and
assets.py (one record per (provider, id), deduped).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fvcore import FishError, load_json, save_json

UA = "FishVideoSkill/2.0 (+https://imutechz.com)"
TIMEOUT = 20


class NetError(FishError):
    """A network call failed (soft: callers warn and carry on)."""


def _redact(url: str) -> str:
    """Strip key/token query params so errors never leak a secret."""
    try:
        p = urllib.parse.urlsplit(url)
        q = [(k, "***" if k.lower() in ("key", "token", "api_key", "client_id") else v) for k, v in urllib.parse.parse_qsl(p.query)]
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), ""))
    except Exception:
        return url.split("?")[0]


def build_url(url: str, params: dict | None = None) -> str:
    if not params:
        return url
    clean = {k: v for k, v in params.items() if v is not None}
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(clean, doseq=True)


def fetch(url: str, params: dict | None = None, headers: dict | None = None, timeout: float = TIMEOUT, retries: int = 1) -> bytes:
    full = build_url(url, params)
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(full, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429 and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            break
        except Exception as e:  # URLError, timeout, ssl...
            last = e
            break
    why = f"HTTP {last.code}" if isinstance(last, urllib.error.HTTPError) else str(getattr(last, "reason", last))
    raise NetError(f"request failed ({why}): {_redact(full)}")


def fetch_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: float = TIMEOUT) -> Any:
    raw = fetch(url, params, headers, timeout)
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        raise NetError(f"not JSON from {_redact(build_url(url, params))}")


def download_file(url: str, dest: Path | str, headers: dict | None = None, timeout: float = 60) -> Path:
    """Stream url to dest (atomic via .part)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    h = {"User-Agent": UA}
    h.update(headers or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r, tmp.open("wb") as fh:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        raise NetError(f"download failed ({getattr(e, 'reason', e)}): {_redact(url)}")
    tmp.replace(dest)
    return dest


# ------------------------------------------------------------------ licences
def norm_license(raw: str | None, url: str | None = None) -> dict:
    """Normalise a licence string/url -> {label, url, ok, attribution}.

    ok=False for NC / ND / unknown restrictive licences (we drop those).
    """
    s = f"{raw or ''} {url or ''}".lower()
    if not s.strip():
        return {"label": "unknown", "url": "", "ok": False, "attribution": True}
    if "-nc" in s or " nc" in s or "noncommercial" in s or "non-commercial" in s or "-nd" in s or "noderiv" in s or "no deriv" in s or "sampling" in s:
        return {"label": str(raw or url), "url": url or "", "ok": False, "attribution": True}
    if "publicdomain/zero" in s or "cc0" in s or "creative commons 0" in s or "cc zero" in s or "zero" in s.split():
        return {"label": "CC0", "url": "https://creativecommons.org/publicdomain/zero/1.0/", "ok": True, "attribution": False}
    if "pdm" in s or "public domain" in s or "publicdomain/mark" in s or s.strip().startswith("pd"):
        return {"label": "Public Domain", "url": "https://creativecommons.org/publicdomain/mark/1.0/", "ok": True, "attribution": False}
    import re
    ver = re.search(r"(\d\.\d)", s)
    v = ver.group(1) if ver else "4.0"
    if "by-sa" in s or "by sa" in s or "attribution-sharealike" in s or "attribution share" in s:
        return {"label": f"CC BY-SA {v}", "url": f"https://creativecommons.org/licenses/by-sa/{v}/", "ok": True, "attribution": True}
    if "licenses/by/" in s or "cc by" in s or "cc-by" in s or s.strip().startswith("by ") or s.strip() == "by" or "attribution" in s:
        return {"label": f"CC BY {v}", "url": f"https://creativecommons.org/licenses/by/{v}/", "ok": True, "attribution": True}
    return {"label": str(raw or url), "url": url or "", "ok": False, "attribution": True}


# ------------------------------------------------------------------ credits
def credits_path(project: Path | str) -> Path:
    return Path(project) / "assets" / "credits.json"


def load_credits(project: Path | str) -> list[dict]:
    d = load_json(credits_path(project), default=[])
    return d if isinstance(d, list) else d.get("items", [])


def add_credit(project: Path | str, rec: dict) -> bool:
    """Append rec to assets/credits.json unless (provider, id) is already there. True if added."""
    items = load_credits(project)
    key = (rec.get("provider"), str(rec.get("id")))
    for it in items:
        if (it.get("provider"), str(it.get("id"))) == key:
            if rec.get("file") and it.get("file") != rec["file"]:
                it["file"] = rec["file"]
                save_json(credits_path(project), items)
            return False
    items.append(rec)
    save_json(credits_path(project), items)
    return True


def project_of(path: Path | str) -> Path | None:
    """Walk up from path to the folder holding brief.yaml."""
    p = Path(path).resolve()
    for q in [p] + list(p.parents):
        if (q / "brief.yaml").exists():
            return q
    return None


PROVIDER_NAMES = {"pexels": "Pexels", "pixabay": "Pixabay", "openverse": "Openverse", "wikimedia": "Wikimedia Commons",
                  "nasa": "NASA Image and Video Library", "freesound": "Freesound", "kenney": "Kenney", "youtube": "YouTube"}


def credit_line(rec: dict) -> str:
    title = rec.get("title") or "Untitled"
    author = rec.get("author") or "unknown"
    prov = PROVIDER_NAMES.get(rec.get("provider"), rec.get("provider") or "")
    src = rec.get("url") or ""
    lic = rec.get("license") or ""
    if rec.get("attribution_required"):
        lurl = rec.get("license_url") or ""
        return f'"{title}" by {author} ({src}) is licensed under {lic}{f" ({lurl})" if lurl else ""}. Source: {prov}.'.replace(" ()", "")
    return f'{title} by {author} via {prov} ({src}), {lic}.'.replace(" ()", "")


def credits_text(project: Path | str) -> str:
    """Description-ready credits block built from assets/credits.json."""
    items = load_credits(project)
    must = [credit_line(i) for i in items if i.get("attribution_required")]
    nice = [credit_line(i) for i in items if not i.get("attribution_required")]
    out: list[str] = []
    if must:
        out += ["Credits:"] + [f"- {x}" for x in must]
    if nice:
        out += ([""] if out else []) + ["Also thanks to:"] + [f"- {x}" for x in nice]
    return "\n".join(out)
