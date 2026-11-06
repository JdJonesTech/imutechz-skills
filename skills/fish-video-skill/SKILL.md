---
name: fish-video-skill
description: Make a premium, upload-ready Short, Reel, TikTok, YouTube or LinkedIn video on any topic, with any model on any device. Use it when someone asks for a video, explainer, roadmap video, story Short, promo, product or app tour, screen-recorded tutorial, or "a video like this one". It starts from a recipe (roadmap-explainer, story-short, bold-short) and one of 14 themes, runs one strict interview, collects licensed real images and footage, narrates with the recommended Chatterbox soft voice, renders deterministic motion graphics, then enforces measured gates: image coverage, a frame-sheet sign-off, and a required designed thumbnail (headline plus logo or picture tiles on a glowing road). It packages videos, thumbnails, titles, descriptions and credits, and cleans up only with permission.
version: 2.5.0
license: MIT
author: ImuTechz
compatibility: Python 3.10+ (3.12 recommended), Node 18+, a Chromium browser (Brave/Chrome/Edge/Chromium), ffmpeg (bundled via npm). Windows, macOS, Linux. Optional Chatterbox voice (one command), and keys ELEVENLABS_API_KEY, PEXELS_API_KEY, PIXABAY_API_KEY, FREESOUND_API_KEY, YOUTUBE_API_KEY; every key has a key-less fallback.
---

# Fish Video Skill

You make one video from one conversation. Quality comes from the tools, not from your taste: follow the numbered path, run each command, and stop where it says STOP. Every frame needs a real image, footage or drawn graphic, never only words.

Run commands with the skill's venv: `.venv/bin/python scripts/fishvideo.py <cmd>` (Windows: `.venv/Scripts/python`). Below, `fv` means that.

## The path (do not skip, do not reorder)

1. **Setup.** `fv doctor --keys`. Install what it lists as missing (`npm install` also fetches the theme fonts; render stops if they are missing). If `chatterbox` is missing, tell the user and run `fv voice setup --engine chatterbox` (one command, the recommended voice). STOP if `doctor` shows no browser or no ffmpeg.
2. **Pick a recipe and a theme.** `fv recipes`, then `fv themes`. Roadmap, guide or "how to become" = `roadmap-explainer`. True story, history, people = `story-short`. Facts, rules, deadlines with no photos = `bold-short`. Show the user the recipe's recommended themes (`fv themes preview` renders a gallery) and let them choose.
3. **Create.** `fv new projects/<slug> --recipe <id> --prompt "<the user's words>"`. You get a brief, a storyboard skeleton full of TODOs and `assets/PLAN.md`.
4. **Interview, once.** `fv interview projects/<slug>`, ask every open question (every question has a Recommended option; with no question tool such as AskUserQuestion, ask in one plain message listing the options with the recommended one first, wait for the reply, then record it with `--set`; never answer for the user) (theme and voice included; the voice option "Chatterbox soft (Recommended)" comes first), record answers with `--set`, read `--summary` back, then `--confirm`. After this, ask nothing until the final review. STOP until confirmed.
5. **Collect real assets, beat by beat.** `fv assets source <dir> "<what the beat shows>" --beat <id>` searches Wikimedia Commons, NASA, the Library of Congress (plus Pexels/Pixabay when keyed), keeps only licences the API confirms, downloads, records source, licence and author in `assets/credits.json` (they flow into every post text) and points the beat at the file, labelled `illustrative`; add `--depicts "<who or what>"` only when the picture truly shows it (label `archive photo`). `fv assets plan <dir>` lists beats still without an image. Also `fv capture`, `fv thumb logos --find <brand>`. Open the previews and look. STOP if most beats have no real image; text-only beats are a small minority.
6. **Write the storyboard.** Replace every TODO: narration, on-screen words (6 words or fewer, one `*accent*`), params. Use `story`, `site`, `cards`, `flow`, `roadmap`, `bold` scenes ([scene catalogue](references/scene-catalogue.md)). Facts need `brief.facts` with a source. Write `brief.publish` (5 titles, description, tags) and the `thumbnail:` block (below).
7. **Gate the script.** `fv gate projects/<slug>` must say `ready`, and `fv gates projects/<slug>` must PASS (it also runs inside `gate`/render for every video): most beats have a real image or footage that exists and is credited (source, licence, author), photos of people or events carry `label: archive photo|illustrative`, a site screenshot is never the main visual, and images keep arriving. The only opt-out is `visuals: {mode: abstract, user_asked: true, reason: "<the user's words>"}` when the user asked for an abstract or text-led video. STOP and fix on any BLOCKED or FAIL: add real images to text scenes, split long scenes, use `srcs:` to swap photos inside a scene.
8. **Voice.** First `fv budget <dir>` (words per beat slot, before any minutes-long voice run). Then `fv voice projects/<slug>` (Chatterbox soft by default; only changed lines are re-voiced). If the words check flags a homophone ("emus" heard as "emos"), `fv voice words <dir> --add emos=emus`; no re-voicing needed. Then `fv storyboard projects/<slug>`. If Chatterbox is not installed the command stops and prints the setup command; it never switches voice silently. If the user picks another voice, say what changes.
9. **Look before rendering.** `fv stills projects/<slug> --scenes`, open every still. Fix empty frames, text under the platform UI, unreadable captions.
10. **Render.** Preview the hardest 10 s: `fv render <dir> --scale 0.5 --fast --from 8 --to 18`. Then `fv render <dir>`.
11. **QA and the frame sheet (required).** `fv qa <dir>`, then `fv review <dir> --platform <p>` and `fv signoff <dir> --platform <p>`. Open every sheet and `build/<p>/contact.png`. Fill `build/<p>/review/SIGNOFF.md`: for every scene one sentence naming every object you see (4+ words) and a verdict `ok` or `fix`; tick the checklist. Fix every `fix`, re-render, sign again. Check with `fv signoff <dir> --check`. STOP until it passes. Never score a video out of 10; list the changes instead.
12. **Thumbnail (required).** Put the brands the video is about in `storyboard.yaml -> thumbnail: {title, accent, tag, sub, logos: [slug, ...]}` (find slugs with `fv thumb logos --find <name>`; a topic with no brands uses its licensed pictures automatically). Run `fv thumbnail <dir>` (`fishvideo thumbnail`): it draws the headline-and-road design (plus a 9:16 cover for Shorts), runs the checks and picks it. Open the PNG. `package` refuses without it. `--no-thumbnail` only if the user asks for none. A website screenshot is never a thumbnail or cover.
13. **Package.** `fv package <dir>`. It refuses, naming the failing checks, if QA has any FAIL, or if the thumbnail or sign-off is missing. Fix and re-run `fv qa`. Only if the user explicitly accepts a failure: `--accept-qa-fail "<their words>"` (recorded in the package).
14. **Final review.** Send the user: the folder path, the video, the thumbnail, 5 titles, measured loudness, anything still open (a WARN, an estimated voice). Ask for approval or changes.
15. **Clean up, only with a yes.** `fv clean <dir>` (dry run), tell the user the size, ask, then `fv clean <dir> --yes`.

## The defaults you must not change without the user asking

- **Voice:** `chatterbox-soft`: Chatterbox default voice, one sentence at a time, exaggeration 0.32-0.55 by sentence, cfg_weight 0.25, temperature 0.75, seed 11, pauses 0.35-0.55 s, then the post chain and `loudnorm=I=-18:TP=-2:LRA=9`, 48 kHz. Brief: `pacing.max_word_gap: 0.9`, `line_gap: 0.05`, `mix.music_under_voice_db: -12`. Details: [local voices](references/local-voices.md).
- **Looks:** a theme (`theme:` in the brief). 14 exist; `theme_overrides:` changes single values. [Recipes and themes](references/recipes-and-themes.md).
- **Imagery:** the recipe's gate thresholds (`fv gates`). A text-card video fails.
- **Thumbnail:** `fv thumbnail`. Logos must relate to the video's content; they are trademarks of their owners.

## Hard rules

- One interview at the start; never write a script before it is confirmed. Never ship template text: the gate blocks TODOs and lines copied from `examples/`.
- Explainers need a diagram (`diagram`, `whiteboard`, `neonline`, `flow`, `roadmap` or a `split` reveal).
- Never invent facts, numbers, quotes or logos; every number is in `brief.facts` with a source.
- Licences: never NC or ND, never a non-CC YouTube video, never a reference video's footage. Memes and viral sounds only with the user's opt-in (`memes.policy`). Every asset is in `assets/credits.json`.
- Film websites read-only. Keys live in `.env` only; never print or commit them.
- Renders run at low priority under a CPU cap; run heavy jobs one at a time. Scene code is deterministic (no `Math.random`, `Date`, CSS animation).
- Do not upload or publish. `--no-gate` and `--no-thumbnail` are for tests and explicit user requests only.

## Load only what the current step needs

- Recipes, themes, gates, thumbnail design: [recipes and themes](references/recipes-and-themes.md)
- The long form of every step above: [pipeline details](references/pipeline-details.md)
- Script ideas and trending angles: [topic to video](references/topic-to-video.md), [trending analysis](references/trending-analysis.md)
- Scenes, motion, camera: [scene catalogue](references/scene-catalogue.md), [long roadmap videos](references/long-roadmap-videos.md)
- Style, colours, type, diagrams: [style recipes](references/style-recipes.md), [diagram design](references/diagram-design.md), [captions and typography](references/captions-and-typography.md)
- Voice and sound: [local voices](references/local-voices.md), [voice direction](references/voice-direction.md), [sound design](references/sound-design.md), [pacing and music](references/pacing-and-music.md)
- Memes, logos, icons, real assets: [memes and real assets](references/memes-and-real-assets.md)
- Frames and thumbnails: [frame design](references/frame-design.md)
- A website or app on screen: [website-tour capture](references/website-tour-capture.md)
- A reference video to match: [reference breakdowns](references/reference-breakdowns.md), [reference-video analysis](references/reference-video-analysis.md)
- Platform sizes: [platform specs](references/platform-specs.md). Tools: [field guide](references/open-source-field-guide.md)

## Files

`scripts/` (CLI `fishvideo.py`, `recipes.py`, `themes.py`, `gates.py`, `thumbs.py`, `voicelab.py`, the stage in `stage/`), `config/` (`recipes.yaml`, `themes.yaml`, `voicelab.yaml`, `styles.yaml`, `interview.yaml`), `references/`, `examples/` (structure only, never reuse their lines), `tests/`.
