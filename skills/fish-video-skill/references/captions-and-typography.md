# Captions and typography

## Type system

| Role | Face (bundled) | Weight | 16:9 size (u = 1) | 9:16 size |
|---|---|---|---|---|
| Display / headline | Inter (`--display`) | 700, tracking -0.035em | 128 (fitted) | 100 (fitted) |
| Serif accent (contrast word, quotes, tagline) | Fraunces italic | 400 | 0.8–1.2 × display | same |
| Section title (h2) | Inter / Fraunces | 600–700 | 72 | 60 |
| Body / bullets | Inter | 550 | 34–40 | 36–42 |
| Eyebrow / kicker / step tag | JetBrains Mono, uppercase, +0.2em | 400–600 | 22 | 28 |
| Whiteboard | Caveat | 600–700 | 84–96 title, 38–64 notes | scaled board |
| Code / terminal | JetBrains Mono, ligatures off | 400–700 | 32 | 32 |
| Hindi / Devanagari | Noto Sans Devanagari (fallback in every stack) | 400–700 | as above | |

Rules:
1. **Use two families plus mono.** Contrast comes from size, weight and the one serif-italic word, not from more fonts.
2. **Use one accent colour per scene**, on the single most important word or shape.
3. **Headline ≤ 8 words. Bullet ≤ 7 words. Kinetic line ≤ 6 words.** If the text does not fit at the size above, *cut words*. Do not shrink the text below the minimum.
4. **Minimum on-screen size:** 22 px on a 1080-tall 16:9 frame, 24 px on 4:5 and 1:1, and 28 px on 9:16. The QA lint enforces this.
5. **Contrast** ≥ 4.5:1 for body text and ≥ 3:1 for display text. Check `ink` on `bg` and `muted` on `bg` when you choose brand colours.
6. **Safe areas:** every text element lies inside the platform's safe margins (see [platform-specs](platform-specs.md)). The lint fails any text outside them.
7. **Numbers** use tabular figures in counters (`font-variant-numeric: tabular-nums`). Use the thousands separator for the locale (10,631 / 10 631 / 10.631). Put units next to the number.
8. **Line length:** use about 45 characters maximum for body text on 16:9 and about 28 on 9:16.
9. **Text never moves while it is meant to be read.** Animate it in, hold it, then animate it out. Read time is at least 0.3 s + 0.06 s per character.

## Captions

### Cue building (`captions.chunk_words`)

Input: word timings `[{w, t0, t1}]` from the TTS, mapped back to *displayed* words through `{shown|spoken}`.

| Rule | 16:9 | 4:5 / 1:1 | 9:16 |
|---|---|---|---|
| max characters per line | 42 | 32 | 26 |
| max lines | 2 | 2 | 2 |
| min cue duration | 0.9 s | 0.9 s | 0.9 s |
| max cue duration | 6 s | 6 s | 6 s |
| max reading speed | 20 chars/s | 20 | 20 |

Further rules:
- Break after `. ! ? : ;`, or after a comma once the cue is about 45% full.
- Never span a pause longer than 0.6 s.
- A cue holds up to 0.45 s after its last word, but never overlaps the next cue.
- Line wrap is balanced: two lines of similar length beat one long line and one short one, with a bonus for breaking at punctuation.

### Outputs

- **SRT** (`HH:MM:SS,mmm`) and **VTT** (`WEBVTT`, `HH:MM:SS.mmm`) ship for every platform. Upload the SRT to YouTube as subtitles; it is also good for LinkedIn's caption upload.
- **Burned-in** captions are drawn by the stage on `linkedin`, `linkedin-square`, `shorts`, `reels`, `tiktok` and `x`. Override with `captions: {burn: true|false}` in the brief. How the burned-in captions look and sit:
  - Inter 700 at 44 px × u, on a surface-coloured rounded box.
  - Each word lights (opacity 0.38 → 1) as it is spoken, and the current word takes the accent colour.
  - The caption band is reserved: scenes lay out *above* it (`c.safe` excludes it), so captions never cover content.
  - Position: above the platform's bottom safe margin, so app UI never covers them.
- **Fallback burn-in** for footage the stage did not render: `python scripts/captions.py burn in.mp4 subs.srt out.mp4` (libass `subtitles` filter, styled box).

### Checks (`qa.py`)

- The SRT parses, and no cue overlaps the next.
- No line is longer than the platform's maximum, and no cue has more than 2 lines.
- Reading speed is ≤ 25 characters/s (20 × 1.25 tolerance).
- No cue ends after the video.
- **Sync:** every spoken word's midpoint falls inside a cue (±0.25 s).

## Accessibility

- Captions are on by default. They should always be available, even where they are not burned in.
- Never put essential information only in sound, or only in colour.
- Avoid flashing above 3 Hz. Keep wipes ≥ 0.6 s.
- Spell brand words in captions the way the brand spells them: the `shown` side of `{shown|spoken}`.
