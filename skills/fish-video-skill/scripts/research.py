"""Research: fetch the sources, extract what they say, cite them, and check
every number in the video against them.

    python scripts/research.py <project> [--url URL ...] [--from-json results.json]
    python scripts/research.py check <project>          fact-check the storyboard's numbers

The agent does the searching (web search / fetch tools) and hands this
script the URLs worth reading: brief.sources, brief.website.url, --url, or a
JSON list of search results ([{"url", "title", "snippet"}]). For each URL it
writes research/pages/S<n>.txt (clean text), and it builds

    research/sources.json   [{id, url, title, description, headings, numbers, fetched}]
    research/facts.md       candidate facts (sentences with numbers or key terms), each tagged [S<n>]

`check` lists every number that appears on screen or in the narration and
reports the ones found in no source and not in brief.facts. A video must
not ship with an unsupported number.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from fvcore import FishError, ensure_project, load_json, load_yaml, log, main_guard, project_config, save_json, warn

UA = "Mozilla/5.0 (compatible; FishVideoSkill/1.0; research for an explainer video)"
NUM = re.compile(r"(?<![\w.])(?:v)?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)*)(?:\s?(%|×|x\b|k\b|K\b|M\b|B\b))?")


class _Text(HTMLParser):
    """Readable text from HTML: drops script/style/nav/footer/svg, keeps headings."""
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "template", "iframe", "form"}
    BLOCK = {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "td", "th", "header", "main", "blockquote", "pre", "dd", "dt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts: list[str] = []
        self.title = ""
        self.meta: dict[str, str] = {}
        self.headings: list[str] = []
        self._h = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            k = (a.get("name") or a.get("property") or "").lower()
            if k in ("description", "og:description", "og:title", "twitter:description", "og:site_name"):
                self.meta[k] = a.get("content") or ""
        if tag in ("h1", "h2", "h3"):
            self._h = []
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in ("h1", "h2", "h3") and self._h is not None:
            h = re.sub(r"\s+", " ", "".join(self._h)).strip()
            if h:
                self.headings.append(h)
            self._h = None
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self.skip:
            return
        if self._h is not None:
            self._h.append(data)
        self.parts.append(data)

    def text(self) -> str:
        t = "".join(self.parts)
        t = re.sub(r"[ \t\r\f\v]+", " ", t)
        t = re.sub(r"\n\s*\n+", "\n\n", t)
        return "\n".join(l.strip() for l in t.splitlines()).strip()


def extract(raw_html: str) -> dict:
    p = _Text()
    p.feed(raw_html)
    return {"title": html.unescape(p.title.strip()), "description": p.meta.get("description") or p.meta.get("og:description") or "",
            "site": p.meta.get("og:site_name", ""), "headings": p.headings[:60], "text": p.text()}


def fetch(url: str, timeout: int = 30) -> tuple[str, str]:
    """(content-type, body text). Raises FishError on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,text/plain,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("content-type", "")
            body = r.read(6_000_000)
    except urllib.error.HTTPError as e:
        raise FishError(f"{url}: HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise FishError(f"{url}: {getattr(e, 'reason', e)}")
    enc = re.search(r"charset=([\w-]+)", ctype)
    return ctype, body.decode(enc.group(1) if enc else "utf-8", "replace")


def norm_number(s: str) -> str:
    """'10,631' -> '10631', '2.10' -> '2.1', 'v0.3.0' -> '0.3.0'."""
    s = s.lower().lstrip("v").replace(",", "")
    if re.fullmatch(r"\d+\.\d+", s):
        s = s.rstrip("0").rstrip(".") if "." in s else s
    return s


def numbers_in(text: str) -> list[str]:
    """Normalised numbers in text; a version a.b.c also yields a.b (v0.3.0 supports "v0.3")."""
    out = []
    for m in NUM.finditer(text or ""):
        n = norm_number(m.group(1))
        out.append(n)
        if n.count(".") >= 2:
            out.append(".".join(n.split(".")[:2]))
    return out


def sentences_with_facts(text: str, limit: int = 40) -> list[str]:
    out = []
    for s in re.split(r"(?<=[.!?])\s+|\n+", text):
        s = s.strip()
        if 25 <= len(s) <= 260 and re.search(r"\d", s) and not re.search(r"cookie|©|copyright|all rights", s, re.I):
            out.append(s)
        if len(out) >= limit:
            break
    return out


def gather(project: Path, urls: list[str] | None = None, results_json: Path | None = None) -> dict:
    project = ensure_project(project)
    brief = project_config(project)["brief"]
    want: list[str] = []
    for u in (brief.get("sources") or []) + ([(brief.get("website") or {}).get("url")] if (brief.get("website") or {}).get("url") else []) + (urls or []):
        if u and u not in want:
            want.append(u)
    snippets = {}
    if results_json:
        for r in json.loads(Path(results_json).read_text(encoding="utf-8")):
            if r.get("url") and r["url"] not in want:
                want.append(r["url"])
            snippets[r.get("url")] = r.get("snippet", "")
    rdir = project / "research"
    (rdir / "pages").mkdir(parents=True, exist_ok=True)
    old = {s["url"]: s for s in load_json(rdir / "sources.json", default={"sources": []}).get("sources", [])} if (rdir / "sources.json").exists() else {}
    sources = []
    for i, u in enumerate(want, 1):
        sid = f"S{i}"
        try:
            ctype, body = fetch(u)
            ex = extract(body) if "html" in ctype or body.lstrip().startswith("<") else {"title": u, "description": "", "site": "", "headings": [], "text": body}
            (rdir / "pages" / f"{sid}.txt").write_text(f"{ex['title']}\n{u}\n\n{ex['text']}", encoding="utf-8")
            sources.append({"id": sid, "url": u, "title": ex["title"], "description": ex["description"], "headings": ex["headings"],
                            "numbers": sorted(set(numbers_in(ex["text"] + " " + ex["description"])))[:400], "snippet": snippets.get(u, ""),
                            "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "chars": len(ex["text"])})
            log(f"  {sid} {u}  ({len(ex['text'])} chars, {len(ex['headings'])} headings)")
        except FishError as e:
            warn(str(e))
            if u in old:
                sources.append({**old[u], "id": sid, "stale": True})
    res = {"sources": sources}
    save_json(rdir / "sources.json", res)
    md = [f"# Research: {brief.get('title', '')}", "", "Every fact below is quoted from a fetched source. Use only these (or brief.facts) on screen.", ""]
    for s in sources:
        md += [f"## [{s['id']}] {s['title'] or s['url']}", "", s["url"], ""]
        if s.get("description"):
            md += [f"> {s['description']}", ""]
        if s.get("headings"):
            md += ["Headings: " + " · ".join(s["headings"][:15]), ""]
        page = rdir / "pages" / f"{s['id']}.txt"
        if page.exists():
            md += [f"- {x} [{s['id']}]" for x in sentences_with_facts(page.read_text(encoding="utf-8"))]
        md.append("")
    (rdir / "facts.md").write_text("\n".join(md), encoding="utf-8")
    log(f"research: {len(sources)} sources -> {rdir / 'sources.json'}, {rdir / 'facts.md'}")
    return res


# ------------------------------------------------------------------ fact check
GEOM_KEYS = {"path", "rect", "circle", "line", "arrow", "cells", "x", "y", "w", "h", "size", "at", "dur", "seed", "speed", "from", "z", "d", "m", "f", "len", "t0", "page", "cam", "decimals", "cps", "gap"}
TEXT_KEYS = {"title", "subtitle", "kicker", "text", "lines", "items", "label", "caption", "take", "tagline", "note", "t", "d",
             "eyebrow", "bullets", "value", "data", "left", "right", "nodes", "sub", "flow", "notes", "chips", "badge", "html"}


DECORATIVE_KEYS = {"glyph"}     # drawn symbols (a "0.12" standing for an embedding), not claims; any dict with `decorative: true` is skipped too


def claims_in(sb: dict) -> list[tuple[str, str, str]]:
    """(scene id, field, number) for every number on screen or in narration."""
    out = []

    def walk(sid, key, v):
        if isinstance(v, dict):
            if v.get("decorative") is True:
                return
            for k, x in v.items():
                if k in DECORATIVE_KEYS:
                    continue
                if k in TEXT_KEYS or (key in ("data", "items", "nodes", "left", "right", "lines") and k not in GEOM_KEYS):
                    walk(sid, k, x)
        elif isinstance(v, list):
            for x in v:
                walk(sid, key, x)
        elif isinstance(v, (int, float)) and key == "value":
            out.append((sid, key, norm_number(repr(float(v)) if isinstance(v, float) else str(v))))
        elif isinstance(v, str):
            for m in NUM.finditer(v):
                n, unit = norm_number(m.group(1)), m.group(2)
                if re.fullmatch(r"\d", n) and not unit:
                    continue  # single digits are structure ("3 steps", "step 2"), not claims
                out.append((sid, key, n))

    from storyboard import parse_say
    for s in sb.get("scenes") or []:
        if s.get("type") == "terminal":
            continue
        walk(s["id"], "params", s.get("params") or {})
        say = s.get("say") or []
        for ln in [say] if isinstance(say, str) else say:
            txt = ln.get("text", "") if isinstance(ln, dict) else str(ln)
            walk(s["id"], "say", parse_say(txt)[0])
    return out


def check_claims(project: Path) -> dict:
    project = Path(project)
    sbf = project / "storyboard.yaml"
    if not sbf.exists():
        raise FishError("no storyboard.yaml to check")
    sb = load_yaml(sbf)
    brief = load_yaml(project / "brief.yaml")
    known: set[str] = set()
    for f in brief.get("facts") or []:
        known.update(numbers_in(f"{f.get('text', '')} {f.get('value', '')}"))
    known.update(numbers_in(brief.get("prompt", "")))
    for page in (project / "research" / "pages").glob("*.txt") if (project / "research" / "pages").exists() else []:
        known.update(numbers_in(page.read_text(encoding="utf-8")))
    for f in (sb.get("facts_ok") or []):
        known.add(norm_number(str(f)))
    cl = claims_in(sb)
    bad = sorted({f"{sid}: {n}" for sid, _, n in cl if n not in known and n.rstrip(".0") not in known})
    return {"checked": len(cl), "unsupported": bad}


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("project", nargs="?")
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--from-json", default=None)
    a = ap.parse_args(argv)
    if a.target == "check":
        r = check_claims(Path(a.project))
        log(f"{r['checked']} numbers checked; {len(r['unsupported'])} unsupported")
        for x in r["unsupported"]:
            log(f"  UNSUPPORTED  {x}")
        return 1 if r["unsupported"] else 0
    gather(Path(a.target), a.url, Path(a.from_json) if a.from_json else None)
    return 0


if __name__ == "__main__":
    main_guard(cli)
