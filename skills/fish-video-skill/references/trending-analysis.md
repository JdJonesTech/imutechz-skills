# What trending videos do that generated ones don't

Analysis of successful YouTube videos, sampled with `scripts/dissect.py` (frame sheets, spectrogram, loudness). Long videos were sampled only every 4 seconds, so their cut counts mean little, but the visual system and loudness numbers are reliable. Audio was measured, not heard.

Re-run this for each new genre; trends shift:

```bash
fishvideo yt search "<genre>" -n 15 --recent-days 90 --json     # rank by views_per_day; prefer distinct channels
fishvideo yt download <url> --purpose reference --project <dir>
fishvideo dissect <file> --out <dir>/reference/dissect --fps 4
```

Search results include off-format videos (full short films, tutorials about the format). Check the format before learning from one.

## The patterns

**1. One recurring character carries the film.** 3Blue1Brown's nameless box, a white dot in "Emotions", the red V in the V for Vendetta typography piece, the face and eye in Bright Side. The viewer follows *something*, and everything happens to it. A generated video that introduces a new object each scene feels like a slideshow. Use `anchor` or `carry` and the `match` transition, and choose the character when you write the beats.

**2. Diagrams evolve; they aren't assembled.** 3Blue1Brown keeps one persistent box and re-labels it, zooms into it and fills it in, instead of adding unrelated nodes. Bright Side pushes the camera from the face into the eye, and each part gets one thin label. Prefer `neonline` with `follow`, `diagram` with `morph`, and camera push-throughs between levels.

**3. No dead frames at a transition.** Top videos keep a subject on screen across the cut (match cuts, flips, type-to-type). Blurring to an empty background for several frames breaks attention.

**4. The first seconds have motion and a hit.** Examples are a set-piece gag, a word slam on a beat, or "open your eyes" on a closed-eye face. Hooks are not always claims: 3Blue1Brown opens on a story prompt, and Bright Side opens on an instruction to the viewer. Choose the hook from the idea, not from a template.

**5. One type system, while colour can move.** "Emotions" changes the background colour per emotion while the system stays recognisable. Many others keep one accent. Decide deliberately: per-beat `accent` when each beat is a different *state*, one accent when the video is a single argument.

**6. A word can just sit there.** Fast kinetic pieces still let a single centred word hold for 0.5–1 s, on the beat. Reading speed and impact beat constant motion.

**7. Level is a style choice, ducking is not.** Integrated loudness across these six runs from −9 to −22.5 LUFS, with loudness range from about 2 to 20 LU. Explainers carry a quiet bed with a deep duck (3Blue1Brown: about 13 dB on the bass) or a steady low bed (Bright Side: about 2 dB). Music-driven type pieces put bass well over the voice. Nothing here justifies copying a reference's master level: platforms normalise, and phones decide what is audible.

## Per video

| Video | Format | Hook | Visual system | Sound |
|---|---|---|---|---|
| 3Blue1Brown, "Large Language Models explained briefly" (8.4M) | Long explainer | Story prompt over a curling 3D scroll | Black, cream serif, one cyan accent; one box re-labelled and zoomed | −19.8 LUFS, LRA 4.3, ~13 dB bass duck, quiet bed |
| Bright Side, "What Happens Inside Your Eyes" (4.2M) | Long 3D explainer | "Open your eyes", push into the eye by 8 s | 3D renders, one upper-third label per beat, glowing accent on near-black | −15.1 LUFS, LRA 2.3, constant bed |
| "Story behind youtube shorts" (7.8M) | Animated storytime | Gag set-piece | New location or angle about every 4 s; flat colour; outlines; reacting eyes | −13.1 LUFS, LRA 7.6, voice 7.8 dB over bass |
| "Don't Blink" (1.2M) | Rhythmic kinetic type, 43 s | Riser into the first beat at 7.2 s (after a logo) | Centred type at one size; background flips black/white on the beat; cuts every 0.5–1 s | −8.9 LUFS, bass 8.9 dB over voice |
| "V" typography (2.6M) | Kinetic type, 80 s | Dramatic line | Words stack into blocks; red V anchor; old lines blur and scroll away | −21 LUFS, LRA 19.5, drama-led |
| "Emotions" (0.9M) | Kinetic type, 44 s | A dot moving on kicks | Dot as camera; each emotion changes colour, font and micro-animation; cuts about every 2.5 s | −22.5 LUFS, deep duck |

## Screen tutorials, app demos and business/science explainers

Sampled at 4 s per frame from about 11 videos, so pace is approximate. Two of the how-to videos are in Hindi, with no transcript; their workflow notes come from on-screen text only.

**What they look like.** The screen sits in an inset or a phone mock-up, often with a face bubble. Word-highlight captions run in the lower third (current word in yellow). They push in on the cursor, return to full view, and cut away to something else every 8–60 s. Short app demos change visuals every 2–4 s and leave the raw screen within 8–12 s. None of the ones sampled showed a glow cursor, click ripples or click sounds, so ours is a real upgrade if it is used well.

**Rules for `screen-explainer`:**

1. **Hook:** by 3 s show the finished result or a before/after split ("NORMAL vs WITH X"), and say the promise in under 12 words. No logo-only intro over 1.5 s.
2. **Cut-aways:** never stay on the raw screen for more than 12 s. Every 8–12 s, insert a 1.5–3 s shot: a zoom-punch, a detail, or a keyword card for the noun being named.
3. **Zoom:** 1.6–2× on each click and typing burst, ease in over about 0.35 s, hold 2–4 s, return to 1×. At most 8 zooms per minute, or it gets tiring.
4. **Captions and progress:** burned-in groups of 3–5 words with the active word highlighted, plus a corner step counter.
5. **Sound:** a whoosh at each cut and a click per ripple, music ducked 6–10 dB under the voice.

**Rules for business and science explainers:** one idea per shot, a new visual every 3–4 s, and a year, number or label as an anchor at the start of each new scene. Use a flat palette that shifts per section, and open on a quote or a story beat.

**The common workflow** in how-to videos: LLM script, then TTS, then generated visuals, then auto-edit, then layered riser and whoosh SFX with music pushed under the voice. AI-clip makers reuse **one style reference** across all beats, with one camera move per beat (push-in, tilt, dolly, tracking, pull-back). That is the same idea as our style bible and camera presets.

These numbers are one sampling run, not a law. Look at the current top videos in the user's own genre before deciding.
