# Diagram and visual-element design

Explainers need a **real diagram**: a picture of the mechanism. A list of bullets does not count. These rules decide which diagram to use, how to order and colour it, and how to animate it so it teaches.

## Pick the diagram from the sentence

| The narration says… | Diagram | Scene |
|---|---|---|
| "A leads to B leads to C" | **flow**, 3–5 nodes, arrows in reading order | `diagram` (clean) / `whiteboard` `flow:` / `neonline` path |
| "X is made of a, b, c" | **anatomy**: the object in the centre, labels with arrows on the parts | `collage` labels + arrows |
| "It repeats / feeds itself" | **cycle**: 3–5 nodes on a circle, arrows clockwise | `diagram` with `layout: cycle` / `whiteboard` circle + arrows |
| "Before vs after" / "you think vs reality" | **split** or a **two-line chart** | `split`, `compare`, `neonline` (straight vs zigzag) |
| "It grows / falls over time" | **line or bar chart** of sourced values | `chart`, `neonline` |
| "Inside X there is Y" | **zoom-in layers**: the outer object, then a push-through to the inner one | camera push-through, `split` reveal |
| "Three options" | **lanes**: the same action in parallel rows | `compare` / stick-fable lanes |
| "Where it sits in a system" | **architecture**: boxes, one highlighted | `diagram` with `hi: true` on one node |

## Ordering

- Follow **reading order**: left→right in landscape and top→bottom in portrait. Cycles run clockwise from 12 o'clock.
- **Reveal in narration order.** Each node or label appears on the beat where its word is spoken (within 3 frames), never all at once.
- Use **3–5 elements** per diagram. More than that gets split into two scenes, or the first ones are collapsed into a single node.
- Build the **cause before the effect**. The arrow draws *after* its source node and *before* its target appears.

## Colour

- Neutral ink for structure: boxes, arrows and labels use `ink` / `muted`.
- Use the **accent on one thing only**: the node, arrow or word the beat is about. When the beat moves on, the accent moves with it and the previous element returns to ink.
- A second colour (`accent2`) only marks a contrast pair (before/after, expected/real).
- On dark styles, glow is the emphasis: bloom only the active element.
- The ink-to-background contrast ratio must be at least 4.5:1.

## Shape language per style

| Style | Nodes | Connectors | Labels |
|---|---|---|---|
| paper-collage | real cut-out objects with contact shadows | hairlines and hand-drawn curved arrows | heavy grotesk, about 3× hero size |
| neon-diagram | glow icons and rounded boxes | a glowing line drawn by a head (dashoffset) | neon caps, +8% tracking |
| whiteboard | rough.js boxes and circles | marker arrows | Caveat |
| studio-kinetic | white cards with soft shadows; coin discs | thin grey arcs | bold sans |
| glow-metaphor | spheres and rings | light trails | small caps at the top |

## Motion that teaches

- Draw, don't fade: strokes reveal by length (0.5–0.75 s per segment, ease-out).
- Each new node pops with scale 0→1.1→1 over about 6 frames and gets a `pop` cue (a `zap` on neon).
- Each arrow gets a `swish` cue as it draws. The final takeaway gets a `riser` that ends on it, and an `impact`.
- The camera follows the build. Push in slightly on the active node, then pull back to show the whole diagram at the end of the beat, so the viewer gets one *finished* frame to read for at least 0.8 s.

## Theme selection from mood and script

The interview's style and palette answers win. When the user chose "style default" or the agent must choose, map the **dominant mood of the script** to these defaults:

| Mood of the script | Style | Palette | Music mood | Delivery |
|---|---|---|---|---|
| curious, factual, "how it really works" | paper-collage | mono-paper | dark-drone | calm |
| bold, business, people, products | studio-kinetic | studio-lime | hiphop-groove | punchy |
| tension, failure vs success, data | neon-diagram | neon-amber | dark-build | punchy |
| reflective, motivational, mindset | glow-metaphor | mono-glow | cinematic-swell | cinematic |
| practical, step-by-step software | screen-explainer | brand or ocean-tech | lofi-tech | calm |
| technical teaching | whiteboard-explainer | warm-paper | calm-pulse | calm |
| funny or blunt comparison | stick-fable | mono-red | phonk-loop | none |

This map is also in `config/styles.yaml → mood_map`. Say which mood you detected and what you chose in the interview summary, so the user can override it before creation starts.
