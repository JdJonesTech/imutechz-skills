# Reference-video analysis

Users often say "make it like this one". This method extracts the *rhythm* of a reference so you can match its feel with entirely original material.

## Copyright and ethics (non-negotiable)

- The reference is downloaded **for analysis only**, into `<project>/reference/`. Never cut its footage, music, voice or graphics into the new video, and never trace its layouts or characters.
- The download stays local. It is listed in the project's `.gitignore` (`reference/src.*`). Delete it when the project ends.
- Respect the platform's terms. If the user can't legally access the video, don't download it. Ask for a local file the user has rights to, or analyse it by watching only, using its public metadata.
- What you take away are **numbers and observations**:
  - shot lengths and the energy curve
  - how long type holds
  - colour temperature
  - loudness

## Command

```bash
fishvideo reference <project> --src https://youtu.be/VIDEO_ID     # yt-dlp, ≤ 720p, analysis only
fishvideo reference <project> --src path/to/reference.mp4
python scripts/reference.py analyse clip.mp4 --out some/dir --threshold 0.3
```

## What it does

1. **Download** (YouTube or other URLs): `yt-dlp -f "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]"`. It writes `reference/src.mp4` and `src.info.json` (title, uploader, duration, URL, licence).
2. **Probe**: duration, resolution, fps, and whether there is audio.
3. **Scene detection**: `ffmpeg -vf "scale=320:-2,select='gt(scene,0.3)',showinfo"`. The `pts_time` values of the selected frames are the cuts.
   - A threshold of 0.3 suits hard cuts.
   - Use 0.2 for soft motion graphics, and 0.4 for footage with flashes.
   - Cuts closer than 0.25 s merge (flashes, dissolves).
4. **Shot list**: `shots.csv` (n, start, end, duration, palette).
5. **Pacing**:
   - shots per minute
   - mean, median and 90th-percentile shot length
   - the three longest holds
   - the **median shot length in 120-BPM bars**, and a suggested bars-per-scene
6. **Palette**: 5 dominant colours for each shot's middle frame (k-means on a 48×27 thumbnail), plus an overall palette of 6.
7. **Type-card share**: the share of shots whose frame is mostly one flat colour. This is a proxy for how much of the video is motion-graphics or type, against footage.
8. **Loudness**: `ebur128` integrated LUFS, true peak and LRA.
9. **Tempo**: the onset-strength envelope at 100 Hz, autocorrelated over 60–180 BPM and folded into 80–170.
10. **Contact sheet**: one thumbnail per shot (the first 48), as `reference/contact.png`.
11. **Report**: `reference/report.md`.

## Turning the analysis into decisions

| Reference says | Do |
|---|---|
| median shot ≈ 1 bar (2 s) | high energy: kinetic and tour scenes of 1–2 bars, cut on every bar, energy 2–3 |
| median shot ≈ 2–3 bars | explainer pace: the default templates |
| p90 shot ≫ median | it has "breather" holds; use 1–2 long whiteboards at those moments |
| type-card share > 50% | it is a motion-graphics piece; use kinetic, bullets and stat rather than tours |
| tempo ≈ 100–110 | set `bpm: 105` in the storyboard (one bar is then 2.29 s) and keep everything on the grid |
| palette warm/cream vs cold/dark | choose `brand.mode` and `bg`/`ink` tokens with the same temperature, but **your own** brand accent |
| loudness well below -14 | it was mastered quietly; still deliver at -14 LUFS |

Write a short paragraph in the project notes that names the reference, states the numbers you are matching, and confirms that nothing was reused.

## Watching it yourself

The numbers don't tell you *why* a cut works. Open the contact sheet and the video at the points the analysis flags (the longest holds, the energy lifts), and note:
- what the hook does in the first 3 s
- where the first number appears
- how the end card resolves
