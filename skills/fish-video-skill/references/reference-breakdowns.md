# Reference breakdowns: what top Shorts actually do

These are forensic breakdowns of 7 reference videos (6 Shorts and one 9-minute tutorial). Each was made with `scripts/dissect.py`, which extracts frame sheets at 4 fps, a spectrogram, classified sound events and voice/music balance numbers. They set the quality bar. We copy **craft**: timing, layering, sound placement and mix. We never copy content, footage, characters or music.

To dissect a new reference:

```bash
fishvideo yt download <project> <url> --purpose reference
python scripts/dissect.py <project>/reference/src.mp4 --out <project>/reference/dissect --fps 4 [--vtt subs.vtt]
```

Then read every `sheets/*.jpg`, `spectrogram.png` and `timeline.md`, and write `reference/analysis.md` using the nine sections in [reference-video analysis](reference-video-analysis.md).

## The numbers that repeat across all of them

| Element | What the good ones do | What a generic pipeline does wrong |
|---|---|---|
| Visual change rate | Something new every **0.75–1.2 s**. Hard cuts are rare (1–7 per 15 s), and the camera or an element is moving about 80% of the time. | One static layout per 4–8 s. |
| Hook | Frame 0 already has the subject or a title slam. There is no logo and no fade-in. | A title card, then a fade-in. |
| Depth | Real cut-outs with **contact shadows** (offset 10–20 px, blur about 25 px, key light top-left), paper or grain texture, a vignette of 35–45%, and glow on dark backgrounds. | Flat vector boxes on a flat colour. |
| Type | One family (heavy grotesk, Inter 800/900), about 3× size contrast between the hero word and small words, one accent colour, and a blur-to-sharp or scale-0.8→1 word reveal staggered about 6 frames. | Uniform sizes and many colours. |
| Transitions | Object-as-portal: zoom-through with motion blur, a 2-frame white flash, then a pull-back. Also split reveals, rack-focus defocus and 3D flips. | Crossfades. |
| Swish SFX | **140–250 ms**, centroid 5–6 kHz, starting **50–120 ms before** the move, at −18 to −28 dBFS. | Long 0.6 s whooshes, late. |
| Pops and ticks | 40–140 ms, on element arrival, −20 to −30 dB (subliminal, felt rather than heard). | Loud pops on everything. |
| Risers | 0.75–1.2 s, **ending exactly on** the reveal, often cut dead into silence or an impact. | A riser that starts at the reveal. |
| Impacts | 60–120 Hz thump or boom with a 240–500 ms tail, on flash cuts and title slams, −12 to −15 dBFS. | None, or a thin click. |
| Voice | Measured at −15 to −16 LUFS (short-term while speaking), compressed, presence-lifted, short room. Pace runs 2.3–2.9 words/s; motivational and story pieces run faster. | −20 LUFS and dry. |
| Music bed | Present from **frame 0**, **8–12 dB under the voice**, sidechain duck of about **6 dB** (attack 5–20 ms, release 250 ms), 250 Hz–3 kHz carved out of the music, and a fade over the last 1–2.5 s. | Either inaudible (−5 dB bed then ratio 6 duck) or masking the voice. |
| SFX ducking | SFX are **never ducked** by the voice; they are placed in the gaps between words. | SFX on the music bus, so they get ducked. |
| Master | Integrated loudness of the references ranges from −10 to −29 LUFS. Several are badly mastered (too quiet or clipped). | Copying their loudness. |
| End | A loop back to frame 0, or a 0.3–1.3 s hold with silence. | A long logo outro. |

## The seven, one by one

### R1: Paper-craft documentary collage (14 s, male documentary voice)
- **Look.** Crumpled paper from #C8C8C8 at the centre to #707070 at the edges. B&W halftone photo cut-outs sit in chamfered (octagonal) cards with a thin outline offset. Labels are bold grotesk with hand-drawn curved arrows. Every object has a contact shadow.
- **Motion.** One continuous virtual camera. A card fades in at scale 0.9→1 over 12 frames. At 2.25 s the card **splits** down the middle (expo-out) to reveal a brain with hairline connectors. Small words rise while the hero word ("mind", about 9% of frame height, ExtraBold) resolves from blur. A **rack-focus** into an eyeball follows. A hard cut goes to near-black, where a **spotlight cone** shows text only inside the light. A disc scales down to a laser line.
- **Sound.** Airy swishes of 0.14–0.16 s at −27 dB on the split, the cut and the cone sweeps. A tick of 100 ms. A sub swell under the split. Two soft thuds as the line closes. A dark drone bed with no drums. Voice runs at 2.3 words/s.
- **Lesson.** Subliminal SFX, a monochrome palette and real assets with light and shadow make it feel expensive.

### R2: Clean studio infographic (10 s, punchy US male TTS)
- **Look.** A radial grey studio gradient. A B&W cut-out subject with **neon-lime** (#B6FF7A) accent spheres orbiting. Then a **3D coin flip** carousel landing five logos one by one, each labelled on an arc.
- **Motion.** Title words slide in with a blur trail. Subtitle words scale 0.8→1 with a 4 px blur over 5 frames, staggered 6 frames. The cut-out rises from the bottom. A slow push-in from 1.0 to 1.08 with a bob. Each logo lands within about 3 frames of the word that names it.
- **Sound.** A title slam at 0.02 s (−10 dB). A rising whoosh plus a thud for the figure. A swish (150 ms) and a click per coin flip. A bass-heavy groove that is too loud: voice sits 3 dB *below* the bass. **Do not copy that balance.**

### R3: 3D camera promo (29 s, Spanish-accented human male voice, 2.9 words/s)
- **Look.** Light vignette from #F2F2F2 to #808080. A clock rolls into a coin through a 3D Y-flip **match cut**. A chalkboard with struck-through words and a yellow "NOW" sticky note. A squircle card with corner brackets. Icon tiles **zoom through** (300% with motion blur) into a road scene.
- **Sound.** Sparse swishes (140–200 ms, −27 to −33 dB) on moves. The biggest impact (−15 dBFS) lands exactly on a white-flash cut. The music carries most transitions and stops dead at the end.
- **Lesson.** Each scene hands off through an object; there is no "cut, then new layout".

### R4: Neon "expectation vs reality" chart (8 s, no voice)
- **Look.** #111 with a 24 px grid, dust and a vignette. A glowing white line draws straight, then **zigzags** through glow pictograms that pop at each vertex (scale 0→1.1→1 over 6 frames). A yellow lightning arc trails the draw head. Neon amber labels have a 20 px glow.
- **Sound.** A drone that builds sub energy over the clip. A swish on each line start. A glassy **zap** (40 ms, >5 kHz) on each vertex. A thump on the slide-up. A 0.75 s **riser into an impact**, then hard silence.
- **Lesson.** Sync every SFX to a vertex or arrival, and end with silence after the impact.

### R5: Stick-figure fable (14 s, music only)
- **Look.** Three stacked lanes, white round-cap stick figures, tiny red accents. Animation is **stepped at about 12 fps**. A one-line punchline ("Hell nah.") appears near the end. A fade to black that reads as a loop.
- **Sound.** A dense trap/phonk loop. One bass impact on the story beat. No voice and no SFX.
- **Lesson.** Some formats want **no** SFX. Silence is part of the style, so `sfx: minimal` exists for this.

### R6: Geometric glow metaphor (12 s, calm cinematic male TTS, about 150 wpm)
- **Look.** Black, with a glowing #F5F5F5 sphere as the protagonist. It drops into a box ("trapped"), then an **expo-out zoom-through** into a rotating tunnel of about 25 nested squares, then a gradient cone with an infinity glyph, a starfield, a tree growing with trails, and a **ring bloom** of 10 circles. Captions are word by word at the top. They lack a backing plate on busy frames, which is a flaw to fix.
- **Sound.** A **sub riser cut dead** into the zoom-through. An air whoosh with a sub swell on the zoom. A pop on each new shape. A sub bloom as the cone sinks. A boom and a pop as the tree vanishes. Ring spawn is ticks at about 16 per second with rising pitch. No drums: drones and swells sit in the word gaps, and the bass ducks about 7 dB under the voice.
- **Lesson.** Morphs instead of cuts, and sound that swells into the gaps between words.

### R7: Tutorial, "AI motion graphics with a master prompt" (9 min, screen recording)
- **Method taught.** A **locked style bible** (palette hex, one type family, one recurring motif, format) kept separate from per-beat content. The script is split into 4–8 *meaning beats* (hook, claim, human moment, abstract concept, escalation, turning point, payoff). Each beat gets a block: stage, hero subject, motif, camera/transition, timed lines on a 2 s grid, **sound design**, and a **final-frame spec** that bridges into the next beat. Intensity must keep rising to the finale. We implement this as `style` + `beats` in the storyboard and the `lint` checks.
- **Production.** The recording sits in a white-bordered inset on a solid brand background. It uses 1.5–2× punch-ins (soft, because it was recorded at 1×, so **record at 2× scale**), a glow cursor, "STEP N" cards and pops on zooms and clicks. Voice sits about 3 dB over the bass, with a 6 dB duck. About 40 whooshes in the first 2 minutes. Screen segments run 20–60 s with only zoom changes.
- **Weaknesses to beat.** Blurry zooms, no click ripples, no spotlight and no captions in screen segments.

## Mapping to Fish Video features

| Reference trait | Feature |
|---|---|
| Paper, halftone cut-outs, arrows, split reveal, cone | `style: paper-collage`; scenes `collage`, `split`, `cone`; `texture: paper`; `assets cutout` |
| Studio kinetic plus coin carousel | `style: studio-kinetic`; scenes `kinetic`, `coinflip`, `orbit` |
| Object-as-portal transitions | transitions `zoom`, `flash`, `flip`, `defocus` |
| Neon chart | `style: neon-diagram`; scene `neonline`; cues `zap`, `riser` → `impact` |
| Geometric glow metaphor | `style: glow-metaphor`; scenes `glowshapes`, `tunnel`, `ringbloom` |
| Screen tutorial | `style: screen-explainer`; scene `tour` with `frame: inset`, spotlight, glow cursor, click ripple, STEP cards; `fishvideo screenrec` |
| Real b-roll | scene `footage` with `assets search/get/clip` and `yt clip` (CC-BY only) |
| Word-pop captions | `captions.style: pop` |
| Mix balance | `config/defaults.yaml` `mix:` (stems, see [sound design](sound-design.md)) |
