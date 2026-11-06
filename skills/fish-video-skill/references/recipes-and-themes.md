# Recipes, themes, gates and the thumbnail

Everything a weaker model needs to reach the quality of the benchmark videos: start from a recipe, pick a theme, pass the gates, and make the house thumbnail.

## Recipes (`fishvideo recipes`, `fishvideo new <dir> --recipe <id>`)

| Recipe | From | Use for | Recommended themes | Imagery gate |
|---|---|---|---|---|
| `roadmap-explainer` | the long GenAI roadmap video (555 s) | learning paths, tool landscapes, "how to become X", 5-10 min | tech-dark, minimal-light, editorial-serif, news-broadcast | images 40%+ of the time, 10+ new images/min, no stretch over 45 s without one, text cards under 40% |
| `story-short` | the two Onoda Shorts (26 s) | history, true stories, people; series with part 2 | archive-doc, noir-crime, news-broadcast, luxury-finance, nature-calm | images 85%+, 10+ new images/min, no gap over 6 s, text cards under 10% |
| `bold-short` | the bold typographic Short | facts, rules, deadlines when no licensed photo exists | bold-shorts, comic-pop, news-broadcast, kids-playful, retro-arcade | drawn or photo visuals 85%+, text cards under 15% (it has no photographs by design: add some whenever the topic has them) |

A recipe fills the brief (theme, pacing, `max_word_gap 0.9`, `line_gap 0.05`, `music_under_voice_db -12`, the Chatterbox soft voice), a storyboard skeleton (scene types, order, timing; every word a TODO), and `assets/PLAN.md` (what to collect, with the command). The skeleton never contains copy, so nothing can leak into a video.

## Imagery gate (`fishvideo gates <dir>`)

Measured from the storyboard and the timeline, never judged: each scene is `image` (a jpg/png/webp/mp4 anywhere in its params, or a footage/meme/tour scene), `graphic` (diagram, roadmap map, flow, bold shapes) or `text` (title, kinetic, quote, bullets, stat, statement, cards, end). Reported: `image_share`, `image_changes_pm` (new images per minute; a photo swapping inside a scene via `srcs:` counts), `longest_no_image`, `text_share`. A project with `recipe:` in its brief is blocked at `gate`/render when a threshold is missed. Without a recipe the generic thresholds only warn.

Measured on the benchmarks: roadmap video 44% image, 13.0 new images/min, longest gap 39.5 s, 36% text; Onoda Part 1 and 2 100% image, 14.1 and 13.3 per minute; the bold Short 100% drawn, 0% text. A video made only of title, kinetic, quote, bullets, stat and end cards scores 100% text and fails every recipe.

## Frame-sheet sign-off (`fishvideo signoff <dir>`)

Writes `build/<p>/review/SIGNOFF.md`: a checklist and one row per scene. For each scene write what you see (4+ words, name every object) and a verdict `ok` or `fix`. `package` refuses while a row is TODO or `fix`, a box is unticked, or the file is older than the last render. QA cannot see an empty half-frame or a title card; this step makes a person (or model) look.

## Themes (`fishvideo themes`, `themes preview`, `brief.theme`)

14 themes in `config/themes.yaml`: archive-doc (documentary), editorial-serif, tech-dark, bold-shorts, retro-arcade, retro-70s, minimal-light, kids-playful, news-broadcast, noir-crime, notebook-class, luxury-finance, comic-pop, nature-calm. Each differs from every other in at least two of: display font, texture (12 exist: paper, grain, clean, grid, blueprint, halftone, scanlines, notebook, dots, sunburst, stripes, film), layout (kicker style, card style, radius, caps, shadow) and motion (speed, travel, camera push). Tests check contrast (ink/bg 7:1, muted/bg 4.5:1, accent/bg 3:1). Fonts are OFL or Apache-2.0 and fetched by `npm install`; nothing is committed. `theme_overrides:` changes single values. A brief without `theme:` renders exactly as before. `themes preview` draws one gallery image per theme with generated placeholders (no photos are bundled).

## The thumbnail (`fishvideo thumbnail <dir>`, required)

The house design: a short tag above, a huge two-tone headline on the left (the first words in the theme accent, the rest white), an audience line below, and on the right a smooth glowing road (uniform Catmull-Rom through the tile centres) passing through tiles on a dark glow ground. Shorts and Reels get a 9:16 cover of the same design.

```yaml
# storyboard.yaml
thumbnail: {title: "GenAI Engineer Roadmap", accent: "GenAI", tag: "7 STEPS, IN ORDER", sub: "FOR *COMPLETE* BEGINNERS", logos: [huggingface, langchain, meta, googlegemini, claude]}
```

- **Tiles** are brand logos from the `simple-icons` npm package (`fishvideo thumb logos --find <name>`; icon files are CC0, but the marks are trademarks of their owners). Use only brands the video is about: a logo the brief and storyboard never mention is refused. A topic with no brands uses licensed pictures from `assets/credits.json` or `thumbnail.tiles: [assets/photo/a.jpg]`. Some brands are not in simple-icons; the error lists close matches.
- **Never a website screenshot.** Screenshot scenes (`site`, `tour`, `pile`) are skipped when frames are chosen, and the check fails any picture with a browser window or a screenshot path.
- **Checks** (all FAIL when missed): 1280x720 (9:16 for covers), under 2 MB, no screenshot, at least 2 tiles, every tile inside the frame, no word box within 12 px of a tile (measured from layout boxes), headline readable at 246 px wide (main text 12 px or more there and 3:1 contrast), plus the older WARN checks for brightness, saturation and the time-stamp corner.
- **Enforced:** `package` (and `all`) stop and name `fishvideo thumbnail <dir>` when there is no thumbnail, the check fails, or the storyboard changed after it was made. `--no-thumbnail` exists only for a user who asks for no thumbnail.

## Voice

`chatterbox-soft` is the recommended default everywhere a voice is chosen (interview, brief template, recipes, voice studio, README). It needs Chatterbox once: `fishvideo voice setup --engine chatterbox`. If it is missing, `voice`, `audition` and `render` stop and print that command; there is no silent fallback. Another voice is always a choice the user can make, and you say what changes (less natural pacing, no per-sentence emotion). English only.
