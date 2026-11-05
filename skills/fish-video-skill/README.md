# Fish Video Skill

The Fish Video Skill makes an animated explainer or promo video from one prompt, end to end, for any topic. It covers research, script, storyboard, motion graphics, live website capture, an original score, a neural voiceover, word-timed captions, per-platform encodes, QA and packaging.

It is an agent skill: `SKILL.md` is what an AI agent reads. It also works as a plain command-line tool for humans.

Videos are rendered from code. Every frame is a pure function of time, drawn in headless Chromium and encoded with ffmpeg, so renders are deterministic and parallel. Real assets can be mixed in: licensed photos, b-roll, music and SFX, plus your own screen recordings, each one logged with its licence. No number appears on screen without a source.

## What's new in 2.2

- Fixed: `custom_scenes` were rejected by the validator, and explicit scene `cues:` never reached the render.
- New scenes `roadmap` and `pile` for long-format explainers.
- Custom SFX cue types with their own level (`brief.mix.sfx_levels`).
- New QA checks: `explicit cues` and `bare frame`.
- Chatterbox documented as a free local voice route, with a pacing recipe (`references/voice-direction.md`).
- `references/long-roadmap-videos.md`: what popular roadmap videos do, and memes without copyright claims.

## What's new in 2.0

- **One strict interview first.** There are 8 rounds and about 30 questions (`config/interview.yaml`) covering topic, platforms, style, colours, type, texture, voice and delivery (with audio auditions), music, SFX density, real assets, screen recording, facts, CTA, captions, thumbnail, approvals and API keys. Each key comes with how to get it and a free fallback. Nothing is asked after creation starts, except the final review and permission to clean up.
- **A gate.** No script without a confirmed interview, and no render while the storyboard has TODO, stock or example-copied text.
- **Style recipes** built from forensic analysis of top Shorts (`references/reference-breakdowns.md`): paper collage, studio kinetic, neon diagram, glow metaphor, screen explainer, whiteboard and minimal fable.
- **New tools:**
  - `yt` (search, info, subs, CC-only downloads and clips, suggest)
  - `trends` (what is ranking now: titles, tags, hooks, length)
  - `assets` (Pexels, Pixabay, Openverse, Wikimedia, NASA, Freesound, a credits ledger, cut-outs, b-roll frames, the Kenney CC0 SFX pack)
  - `screenrec` (desktop recording with cursor and click log, F8 marks, F9 stop)
  - `dissect` (frame sheets, spectrogram, classified sound events, voice/music balance)
  - `voices --audition`
  - `clean` (dry run first; deletes only with `--yes`)
  - `doctor --keys`
- **A three-stem mix:**
  - The voice sits at −16 LUFS.
  - The music sits 10 dB under it, ducked about 6 dB, and is always audible.
  - The SFX stem is never ducked and uses real samples plus synth. Swishes lead the move, and risers end on the reveal.
  - QA measures the balance.
- **A tidy package:** `out/<date>_<slug>/` with `video/`, `captions/`, `thumbnails/`, `metadata/` (titles, post text, tags, credits, transcript) and `qa/`, plus a README and an upload checklist.

The skill grew out of the pipeline that produced the ImuTechz explainer (see `examples/imutechz-explainer/`). That example shows structure only; its lines are blocked from reuse.

## Setup

You need:
- **Node 18+**
- **Python 3.10+**
- a **Chromium** browser (Brave, Chrome, Edge or Chromium)
- internet, for the voice and research

ffmpeg and ffprobe are installed by npm.

### Windows (PowerShell or Git Bash)

```bash
cd "fish-video-skill"
npm install                               # puppeteer-core, rough.js, fonts, ffmpeg-static, ffprobe
node node_modules/ffmpeg-static/install.js   # only if npm skipped install scripts
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python scripts/fishvideo.py doctor
```

If Node is not on PATH, set `NODE=C:\path\to\node.exe`. If the browser is not in a standard location, set `BROWSER=...`. Paths work in both forms (`C:/Users/...` and Git Bash's `/c/Users/...`).

### macOS / Linux

```bash
cd fish-video-skill
npm install
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fishvideo.py doctor
```

On Linux without a desktop browser: `sudo apt install chromium` (or set `BROWSER`).

### CPU limit

Rendering is heavy, so it is capped: below-normal priority and a hard 60% CPU limit on Windows, enforced by the OS for the render and everything it starts. On macOS and Linux it lowers priority and limits workers instead. A render takes longer, but your PC stays usable. To change it: `FISH_CPU_LIMIT=40` (or `100` for no cap, for example overnight).

### Voice

The default narrator is the ElevenLabs voice `fydPJq00SigRIaPxWgiS` (English, India). To use it, put your key in `.env`, which is gitignored:

```
ELEVENLABS_API_KEY=...
```

Without a key, or if the plan does not allow the voice, the free **edge-tts** voice `en-IN-NeerjaNeural` is used, and the run tells you so.

## Make a video from one prompt

```bash
# Windows: .venv/Scripts/python      macOS/Linux: .venv/bin/python
python scripts/fishvideo.py all projects/kettle \
  --prompt "A 45 second YouTube + LinkedIn explainer of https://example.com, Indian English voice"
```

This runs every step: new, research, script, capture, voice, re-time, factcheck, render, qa and package. The result lands in `projects/kettle/out/<title>/`.

The scaffolded script is only a starting point. The intended loop is:

```bash
python scripts/fishvideo.py new projects/kettle --prompt "..."    # 1. brief.yaml: fill points, facts, brand
python scripts/fishvideo.py research projects/kettle --url https://example.com/about
python scripts/fishvideo.py script projects/kettle                # 2. storyboard.yaml + script.md: rewrite the narration
python scripts/fishvideo.py stills projects/kettle --scenes       # 3. look at every scene
python scripts/fishvideo.py all projects/kettle                   # 4. capture → voice → render → qa → package
```

Quick previews:

```bash
python scripts/fishvideo.py render projects/kettle --platform youtube --scale 0.5 --fast --from 10 --to 20
```

## Commands

| Command | What it does |
|---|---|
| `new <dir> --prompt …` | creates a project and `brief.yaml` from the prompt (`--url`, `--ref`, `--platforms`, `--length`, `--lang`) |
| `research <dir> [--url …]` | fetches sources and writes `research/sources.json` and `facts.md` (each fact cited) |
| `reference <dir> --src file\|youtube-url` | analyses a reference video's pacing, palette, loudness and tempo (analysis only) |
| `script <dir>` | scaffolds `storyboard.yaml` if missing, and writes `script.md` |
| `storyboard <dir> [--table youtube]` | validates the storyboard and resolves the timelines on the 120 BPM bar grid |
| `factcheck <dir>` | lists every number on screen or in the narration that has no source |
| `capture <dir> [shot…]` | films website shots on virtual time (read-only) |
| `voice <dir> [--provider …]` | generates narration (ElevenLabs or edge-tts) with word timings; cached per line |
| `stills <dir> --scenes` | renders one PNG per scene for review |
| `render <dir>` | frames, score, voice, ducking mix, -14 LUFS, H.264 per platform, SRT and VTT |
| `qa <dir>` | checks the container, loudness, captions, text lint and facts; writes a contact sheet |
| `package <dir>` | builds the upload folder: videos, captions, thumbnail, post texts, tags, metadata |
| `all <dir>` | runs everything above in order |
| `doctor` | checks the toolchain |

Platforms are `youtube` (16:9), `linkedin` (4:5), `linkedin-square`, `shorts`, `reels`, `tiktok` (9:16) and `x`. Profiles live in `config/defaults.yaml`.

## Tests

```bash
.venv/Scripts/python -m pytest tests/test_units.py -q        # fast unit tests
node --test tests/                                            # node unit tests
.venv/Scripts/python -m pytest tests/test_e2e.py -m e2e -s    # renders 2 real videos at 640x360 (~6 min)
```

The end-to-end tests render two videos and verify them with `qa.py`:
- a 16-second video about a **fictional** product (YouTube and Shorts)
- a live **website tour** of the ImuTechz site (the local dev server if it is running, otherwise https://www.imutechz.in)

Their output stays in `tests/_out/`.

## Layout

```
SKILL.md            the method (what an agent reads)
references/         storyboards, scene catalogue, pacing & music, captions & type, voice, platforms, reference analysis, tour capture
scripts/            fishvideo.py (CLI) + Python modules + Node renderer/capture/synth + stage/ (scene library)
config/defaults.yaml
templates/          brief.yaml, storyboard.yaml, description.md, tags.txt
examples/           why-you-cant-put-it-down/ (full narrated sample), showcase/ (style demo), imutechz-explainer/ (structure only)
tests/              pytest + node tests, fixtures
```

## Licence

MIT © 2026 ImuTechz. The bundled fonts are under the OFL. ffmpeg-static ships ffmpeg under its own licence.
