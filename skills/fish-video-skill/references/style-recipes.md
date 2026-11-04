# Style recipes

A style is a **locked style bible** plus a **beat pattern**. It defines the look, type, motif, sound and pacing. The machine-readable version is in [config/styles.yaml](../config/styles.yaml). The interview offers these styles; the chosen one sets defaults the user can override (palette, texture, captions, SFX density, music mood). The scaffold builds the beat skeleton. **You write all the words.**

| Style | Looks like | Sounds like | Change every | Best for | From reference |
|---|---|---|---|---|---|
| **paper-collage** | Crumpled grey paper; B&W halftone photo cut-outs with contact shadows; chamfered cards; bold grotesk labels and hand-drawn arrows; split reveals; rack-focus; a spotlight cone on black | A dark drone with no drums; subliminal swishes (−27 dB, 150 ms); a sub swell under reveals; soft thuds at the end; documentary narrator | 1.1 s | facts, psychology, history, "how X really works" | R1 |
| **studio-kinetic** | Light studio gradient; words slam in with a blur trail; cut-out subject rises; glow orbit; 3D coin carousel; slow push-in and bob | Title impact at 0.0 s; swish and click per coin flip; a groove bed **10 dB under the voice** (not the reference's muddy balance) | 0.9 s | people, companies, products | R2 |
| **neon-diagram** | #111 grid; glowing line draws; glow icons pop at vertices; electric arc; neon labels | A building drone; a zap on every vertex; a riser into an impact, then silence | 0.75 s | expectation vs reality, growth, processes, data | R4 |
| **glow-metaphor** | Black; one glowing sphere as the hero; morphs, a nested-square tunnel zoom-through, a starfield, a ring bloom | Sub risers cut dead into zooms; air whooshes; pops on shapes; swells in the word gaps; calm cinematic voice | 1.2 s | motivation, habits, mindset | R6 |
| **screen-explainer** | A real recording in an inset frame on a brand background; glow cursor; click ripple; 1.6–2× focus zoom; spotlight; STEP cards | A click SFX per click; a swish per zoom; lo-fi bed; clear narrator | 2.0 s | app and web tutorials, demos | R7 (minus its weaknesses) |
| **whiteboard-explainer** | Grid paper; marker-drawn diagrams built live; Caveat hand lettering | Marker scribbles; pops; calm pulse | 1.5 s | mechanisms, architecture | v1 ImuTechz |
| **stick-fable** | Black lanes; simple figures performing the same action and diverging; one punchline | Music only (phonk/trap loop); one impact on the story beat; no voice | 1.8 s | A vs B vs C comparisons, loops | R5 |

## The bible lock (enforced while you write)

- **One palette.** Use the interview palette or the brand hex values. The accent appears in every scene, on exactly the word or shape that matters.
- **One type family**, with about a 3× size contrast between the hero word and small words.
- **One motif**, the style's `motif`, which recurs in every beat.
- **Intensity rises** until the payoff. Raise `energy` scene by scene, then drop to 0 on the end card (or hard silence after the final impact).
- **Final-frame hand-off.** The last frame of each beat sets up the next one: the object that becomes the portal, or the word that becomes the next title.

## Screen-explainer rules

Never stay on the raw screen for more than 12 s. Zoom 1.6–2× on clicks and typing, at most 8 zooms a minute. Show the finished result by 3 s. Details and numbers are in [trending analysis](trending-analysis.md).

## Mixing styles

A style can borrow a scene from another style for one beat. For example, a `paper-collage` explainer can use a `neonline` chart for its proof beat if it keeps the palette and type. Never mix more than two styles in one video.
