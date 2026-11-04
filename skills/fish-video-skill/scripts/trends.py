"""Trending + niche research for a video topic.

    python scripts/trends.py <project> --topic "AI agents" [--region IN] [--days 30] [-n 40]

Combines (all optional, each fails soft): yt-dlp / Data API search for the
topic (recent and all-time), YouTube autocomplete, and the Data API
`chart=mostPopular` when YOUTUBE_API_KEY exists. Ranks by views_per_day, then
extracts title patterns, keywords, tags, typical durations and the top-10
hooks (first sentence of the auto-subs for the top 5, best effort).

Writes <project>/research/trends.json and trends.md with recommendations:
title formulas, <= 15 tags, 3-5 hashtags and an ideal length.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import statistics
from collections import Counter
from pathlib import Path

from fvcore import ensure_project, log, main_guard, save_json, warn
import youtube

STOP = set("""a an the and or but of to in on for with at by from is are was were be been it its this that these those you your
i we they he she as not no yes do does did can will just so if than then how what why when who which about into out up down
over under more most very new vs via per my our their me us them have has had get got""".split())
POWER = ["secret", "ultimate", "best", "free", "easy", "fast", "insane", "stop", "never", "mistake", "mistakes", "worst", "truth", "proven",
         "simple", "instantly", "amazing", "shocking", "hidden", "powerful", "beginner", "beginners", "complete", "guide", "tutorial",
         "tips", "tricks", "hack", "hacks", "why", "how", "now", "finally", "real", "actually", "wrong", "must", "only", "essential"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF⭐⬆⏩-⏳]")
FORMULAS = [
    ("number-list", r"^\s*\d+\b|\b\d+\s+(ways|things|tips|tricks|reasons|mistakes|ideas|steps|tools)\b", "N things/ways/tips to ... (e.g. '7 mistakes that ...')"),
    ("how-to", r"^\s*how\s+to\b|\bhow\s+i\b", "How to <result> (in <time>) / How I <result>"),
    ("question", r"\?|^\s*(why|what|is|are|can|do|does|should)\b", "Why/What/Can ...? (curiosity question)"),
    ("mistakes-warning", r"\b(mistake|mistakes|stop|never|don't|dont|worst|wrong|avoid)\b", "Stop/Never/Avoid ... (warning or mistake framing)"),
    ("versus", r"\bvs\.?\b|\bversus\b|\bor\b.*\?", "A vs B (comparison)"),
    ("ultimate-guide", r"\b(ultimate|complete|full|beginner'?s?|masterclass|crash course|guide|tutorial)\b", "The complete/ultimate guide to ..."),
    ("time-box", r"\bin\s+\d+\s*(minutes?|mins?|seconds?|secs?|days?|hours?)\b|\b\d+\s*(minute|min|second|day|hour)s?\b", "... in N minutes/days (time-boxed promise)"),
    ("secret-reveal", r"\b(secret|truth|hidden|nobody|no one|they don't|exposed|revealed)\b", "The secret/truth about ... (reveal)"),
]


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9][a-z0-9'+#.-]*", text.lower()) if w not in STOP and len(w) > 2 and not w.isdigit()]


def title_patterns(titles: list[str]) -> dict:
    n = max(len(titles), 1)
    lens = [len(t) for t in titles] or [0]
    wc = [len(t.split()) for t in titles] or [0]
    caps = sum(1 for t in titles if any(w.isupper() and len(w) >= 3 and w.isalpha() for w in t.split()))
    low = [t.lower() for t in titles]
    power = Counter(w for t in low for w in set(re.findall(r"[a-z']+", t)) if w in POWER)
    return {
        "count": len(titles), "avg_chars": round(sum(lens) / n, 1), "median_chars": statistics.median(lens), "avg_words": round(sum(wc) / n, 1),
        "pct_number": round(100 * sum(1 for t in titles if re.search(r"\d", t)) / n),
        "pct_question": round(100 * sum(1 for t in titles if "?" in t or re.match(r"\s*(why|what|how|is|are|can|do|does|should)\b", t, re.I)) / n),
        "pct_statement": round(100 * sum(1 for t in titles if "?" not in t and not re.match(r"\s*(why|what|how|is|are|can|do|does|should)\b", t, re.I)) / n),
        "pct_caps_word": round(100 * caps / n), "pct_emoji": round(100 * sum(1 for t in titles if EMOJI.search(t)) / n),
        "pct_brackets": round(100 * sum(1 for t in titles if re.search(r"[\(\[].+[\)\]]", t)) / n),
        "power_words": power.most_common(10),
    }


def detect_formulas(ranked: list[dict]) -> list[dict]:
    """Which title formulas the top videos use, weighted by views_per_day."""
    res = []
    total = sum(v["views_per_day"] for v in ranked) or 1
    for name, rx, tmpl in FORMULAS:
        hit = [v for v in ranked if re.search(rx, v["title"], re.I)]
        if not hit:
            continue
        res.append({"formula": name, "template": tmpl, "videos": len(hit), "share_of_views_per_day": round(100 * sum(v["views_per_day"] for v in hit) / total),
                    "example": hit[0]["title"]})
    return sorted(res, key=lambda r: r["share_of_views_per_day"], reverse=True)


def keywords_and_tags(ranked: list[dict], topic: str, limit_tags: int = 15) -> tuple[list[tuple[str, int]], list[str]]:
    kw = Counter()
    tagc = Counter()
    for v in ranked:
        for w in set(_words(v["title"])):
            kw[w] += 1
        for t in v.get("tags") or []:
            t = t.strip().lower()
            if 1 < len(t) <= 30:
                tagc[t] += 1
    tags = [t for t, _ in tagc.most_common(limit_tags * 2)]
    topic_l = topic.strip().lower()
    out = [topic_l] if topic_l else []
    for t in tags + [w for w, _ in kw.most_common(30)]:
        if t not in out:
            out.append(t)
        if len(out) >= limit_tags:
            break
    return kw.most_common(25), out[:limit_tags]


def make_hashtags(topic: str, keywords: list[tuple[str, int]], k: int = 4) -> list[str]:
    out: list[str] = []
    for cand in ["".join(_words(topic)[:3])] + [w for w, _ in keywords]:
        h = "#" + re.sub(r"[^a-z0-9]", "", cand.lower())
        if len(h) > 2 and h not in out:
            out.append(h)
        if len(out) >= k:
            break
    return out[:5] if len(out) >= 3 else out


def duration_stats(ranked: list[dict]) -> dict:
    ds = [v["duration"] for v in ranked if v.get("duration")]
    top = [v["duration"] for v in ranked[:10] if v.get("duration")]
    shorts = [v for v in ranked if v.get("duration")]
    if not ds:
        return {"typical_s": None}
    qs = statistics.quantiles(top, n=4) if len(top) >= 4 else [min(top or ds), statistics.median(top or ds), max(top or ds)]
    return {"typical_s": round(statistics.median(ds)), "top10_median_s": round(statistics.median(top or ds)), "top10_p25_p75_s": [round(qs[0]), round(qs[-1])],
            "pct_shorts": round(100 * sum(1 for v in shorts if v["is_short"]) / max(len(shorts), 1))}


def dedupe(vids: list[dict]) -> list[dict]:
    seen, out = set(), []
    for v in vids:
        if v.get("id") and v["id"] not in seen:
            seen.add(v["id"])
            out.append(v)
    return out


def recommend(topic: str, ranked: list[dict], formulas: list[dict], tags: list[str], hashtags: list[str], dur: dict, pat: dict) -> dict:
    ideal = None
    if dur.get("top10_p25_p75_s"):
        lo, hi = dur["top10_p25_p75_s"]
        ideal = {"seconds": [lo, hi], "note": "shorts-length (<= 60 s vertical)" if (dur["top10_median_s"] or 999) <= 60 else "long-form" if hi > 240 else "mid-length"}
    tl = int(pat["median_chars"]) if pat["count"] else 55
    return {
        "title_formulas": [{"formula": f["formula"], "template": f["template"], "example": f["example"]} for f in formulas[:3]],
        "title_rules": [f"aim for about {tl} characters (top titles average {pat['avg_chars']})",
                        "put a number in the title" if pat["pct_number"] >= 40 else "numbers are optional here",
                        "phrase it as a question" if pat["pct_question"] >= 40 else "statement titles dominate; lead with the payoff",
                        "use one ALL-CAPS word at most" if pat["pct_caps_word"] >= 25 else "avoid shouting caps",
                        "emoji are common" if pat["pct_emoji"] >= 30 else "skip emoji"],
        "tags": tags[:15], "hashtags": hashtags[:5], "ideal_length": ideal,
    }


def _hooks(top: list[dict], n_subs: int = 5) -> None:
    for i, v in enumerate(top):
        v["hook"] = ""
        if i < n_subs:
            try:
                v["hook"] = youtube.subs(v["url"])["hook"]
            except Exception as e:
                warn(f"hook skipped for {v['id']}: {str(e)[:90]}")


def trends(project, topic: str, region: str = "US", days: int = 30, n: int = 40, hooks: bool = True) -> dict:
    project = ensure_project(project)
    log(f"researching '{topic}' (region {region}, last {days} days) ...")
    recent = youtube.search(topic, n, recent_days=days)
    alltime = youtube.search(topic, n)
    sugg = youtube.suggest(topic)
    for extra in ("how to " + topic, topic + " tutorial"):
        sugg += [s for s in youtube.suggest(extra) if s not in sugg]
    popular = youtube.most_popular(region, 25)
    ranked = sorted(dedupe(recent + alltime), key=lambda v: v["views_per_day"], reverse=True)[:n]
    if not ranked:
        warn("no videos found: results will be empty (offline, rate limited, or yt-dlp needs updating)")
    top = [dict(v) for v in ranked[:10]]
    if hooks and top:
        _hooks(top)
    titles = [v["title"] for v in ranked]
    pat = title_patterns(titles)
    formulas = detect_formulas(ranked)
    kws, tags = keywords_and_tags(ranked, topic)
    hashtags = make_hashtags(topic, kws)
    dur = duration_stats(ranked)
    rec = recommend(topic, ranked, formulas, tags, hashtags, dur, pat)
    data = {"topic": topic, "region": region, "days": days, "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "source": "youtube-data-api" if youtube.secret("YOUTUBE_API_KEY") else "yt-dlp",
            "ranked": [{k: v[k] for k in ("id", "title", "channel", "views", "upload_date", "duration", "views_per_day", "is_short", "url")} for v in ranked],
            "top10": [{k: v.get(k) for k in ("id", "title", "channel", "views", "views_per_day", "duration", "url", "hook")} for v in top],
            "patterns": pat, "formulas": formulas, "keywords": kws, "durations": dur, "suggestions": sugg,
            "most_popular": [{k: v[k] for k in ("id", "title", "channel", "views", "views_per_day", "url")} for v in popular[:15]],
            "recommendations": rec}
    out = project / "research"
    save_json(out / "trends.json", data)
    (out / "trends.md").write_text(render_md(data), encoding="utf-8")
    log(f"wrote {out / 'trends.json'} and trends.md ({len(ranked)} videos)")
    return data


def render_md(d: dict) -> str:
    r, p = d["recommendations"], d["patterns"]
    L = [f"# Trends: {d['topic']}", f"_{d['generated']} | region {d['region']} | last {d['days']} days | source {d['source']}_", "", "## Recommendations", "",
         "**Title formulas**"]
    L += [f"- `{f['formula']}`: {f['template']}  \n  e.g. \"{f['example']}\"" for f in r["title_formulas"]] or ["- (no data)"]
    L += ["", "**Title rules**"] + [f"- {x}" for x in r["title_rules"]]
    il = r["ideal_length"]
    L += ["", f"**Ideal length**: {il['seconds'][0]}-{il['seconds'][1]} s ({il['note']})" if il else "**Ideal length**: unknown",
          "", f"**Tags ({len(r['tags'])})**: " + ", ".join(r["tags"]), "", "**Hashtags**: " + " ".join(r["hashtags"]), "",
          "## Title patterns", "",
          f"- {p['count']} titles, median {p['median_chars']} chars, {p['avg_words']} words",
          f"- numbers {p['pct_number']}%, questions {p['pct_question']}%, ALL-CAPS word {p['pct_caps_word']}%, emoji {p['pct_emoji']}%, brackets {p['pct_brackets']}%",
          "- power words: " + (", ".join(f"{w} ({c})" for w, c in p["power_words"]) or "none"), "", "## Top 10 by views per day", ""]
    for i, v in enumerate(d["top10"], 1):
        L.append(f"{i}. **{v['title']}** ({v['channel']}) - {v['views']:,} views, {v['views_per_day']:,.0f}/day, {int(v['duration'] or 0)} s  \n   {v['url']}")
        if v.get("hook"):
            L.append(f"   - hook: \"{v['hook']}\"")
    L += ["", "## Keywords", "", ", ".join(f"{w} ({c})" for w, c in d["keywords"]), "", "## Autocomplete", ""] + [f"- {s}" for s in d["suggestions"][:25]]
    if d["most_popular"]:
        L += ["", f"## Most popular now ({d['region']})", ""] + [f"- {v['title']} ({v['channel']})" for v in d["most_popular"]]
    return "\n".join(L) + "\n"


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="trends.py", description=__doc__.split("\n")[0])
    ap.add_argument("project")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--region", default="US")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("-n", type=int, default=40)
    ap.add_argument("--no-hooks", action="store_true")
    ns = ap.parse_args(argv)
    trends(Path(ns.project), ns.topic, ns.region, ns.days, ns.n, hooks=not ns.no_hooks)
    return 0


if __name__ == "__main__":
    main_guard(cli)
