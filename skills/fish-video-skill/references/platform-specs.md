# Platform specs

These are the profiles in `config/defaults.yaml`. Override fields per project with `brief.platform_profiles.<name>`. Platforms change their limits. **Check the platform's current help page before relying on a hard limit for a client delivery**, and update `max_seconds` if it has changed.

| key | Frame | fps | Captions | Safe margins (top/right/bottom/left px) | Length limit used | Video | Audio |
|---|---|---|---|---|---|---|---|
| `youtube` | 1920×1080 (16:9) | 30 | SRT upload (not burned) | 70/110/80/110 | none | H.264 High, CRF 18, maxrate 16M | AAC 192k 48 kHz stereo |
| `linkedin` | 1080×1350 (4:5) | 30 | burned + SRT | 70/64/80/64 | 600 s | CRF 19, maxrate 10M | AAC 192k |
| `linkedin-square` | 1080×1080 (1:1) | 30 | burned + SRT | 60/64/64/64 | 600 s | CRF 19, 10M | AAC 192k |
| `shorts` | 1080×1920 (9:16) | 30 | burned | 240/140/420/64 | 180 s | CRF 19, 12M | AAC 192k |
| `reels` | 1080×1920 (9:16) | 30 | burned | 250/140/480/64 | 90 s | CRF 19, 10M | AAC 192k |
| `tiktok` | 1080×1920 (9:16) | 30 | burned | 220/160/460/64 | 600 s | CRF 19, 10M | AAC 192k |
| `x` | 1920×1080 (16:9) | 30 | burned + SRT | 70/110/90/110 | 140 s | CRF 20, 12M | AAC 128k |
| `thumbnail` | 1280×720 PNG | n/a | n/a | 40/56/40/56 | n/a | n/a | n/a |

Common to every cut:
- H.264 High profile, `yuv420p`
- constant 30 fps, GOP 2 s (`-g 60`)
- AAC-LC 48 kHz stereo
- `-movflags +faststart` (the moov atom first, for progressive playback)
- integrated loudness **-14 LUFS**, true peak **≤ -1.5 dBTP**, two-pass `loudnorm`, linear mode

## Why these numbers

- **-14 LUFS:** YouTube, Spotify and most social apps normalise playback to roughly -14 LUFS. Mastering there means the platform neither turns you down (wasting dynamics) nor up (raising noise). -1.5 dBTP leaves headroom for AAC encoding overshoot.
- **4:5 for LinkedIn:** in a desktop or mobile feed it takes about 25% more screen than 16:9. Square is the safe alternative.
- **Burned captions on social:** most feed video autoplays muted. YouTube viewers expect selectable subtitles, so YouTube gets an SRT instead.
- **9:16 safe zones:**
  - The top band holds the account and search UI.
  - The right column holds like, comment and share.
  - The bottom band holds the caption, music ticker and CTA.
  - Keep text and faces inside the safe rectangle. Burned captions sit *above* the bottom band.
- **CRF + maxrate:** quality-targeted encoding with a ceiling. The platform re-encodes anyway, so feed it a clean, high-quality master and keep files uploadable.

## Delivery checklist per platform

- **YouTube:**
  - the MP4
  - SRT uploaded as subtitles (language set)
  - a 1280×720 thumbnail (< 2 MB)
  - a title of ≤ 70 characters with the keyword first
  - chapters in the description: the first is `0:00`, there are at least 3, and each is ≥ 10 s
  - sources and credits
- **LinkedIn:**
  - the 4:5 MP4 with burned captions, plus the SRT for the caption upload
  - post text in which the first 2 lines carry the hook (they show before "…see more")
  - ≤ 3 hashtags
- **Shorts, Reels, TikTok:**
  - the 9:16 cut, with the hook in the first second
  - burned captions
  - nothing important inside the UI bands
  - a loopable ending helps
- **X:**
  - ≤ 140 s (2:20) for standard accounts
  - 16:9 or 1:1
  - burned captions

## QA thresholds (`qa.py`)

| Check | Pass |
|---|---|
| codec / profile / pix_fmt | h264 / High / yuv420p |
| resolution | profile W×H × render scale (±2 px) |
| fps | profile fps ± 0.01 |
| audio | AAC, 48000 Hz, 2 ch |
| faststart | moov before mdat |
| duration | timeline ± 0.15 s; ≤ `max_seconds` |
| loudness | target ± 1.0 LU |
| true peak | ≤ target + 0.5 dB |
| dropouts | no silence > 1.5 s (−50 dB) overlapping narration |
| black frames | none outside the first and last 0.5 s (WARN) |
| captions, text lint, facts | zero issues |
