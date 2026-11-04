---
name: scroll-motion-graphics
description: Use when building or fixing a scroll-driven motion-graphics section on a web page, such as a canvas film scrubbed by scroll position, a pinned sticky "scrollytelling" stage, scroll-linked chapters with captions, or a 3D story drum or carousel rolled by scroll, drag and arrow keys. Also use when an existing scroll animation janks, hijacks the wheel, draws under its text, only plays forwards, burns CPU while idle, or ignores prefers-reduced-motion. Not for simple fade-in-on-scroll reveals, autoplaying video, or WebGL scenes.
version: 1.0.0
license: MIT
author: ImuTechz
compatibility: Any agent that loads SKILL.md (Claude Code, Cursor, OpenCode). Output is vanilla JS + Canvas 2D + CSS with zero dependencies and an optional React 18+ wrapper; evergreen Chrome, Edge, Firefox and Safari 15.4+.
---

# Scroll motion graphics

A canvas timeline driven by scroll position: a pinned stage, reels that are pure functions of progress, and captions the drawing is never allowed to touch. This method runs the story drum on the ImuTechz home page, the R&D drum and the Founder path film. It also powers the five-reel demo in [assets/demo.html](assets/demo.html).

The whole technique fits in one sentence. **Scroll position is the only clock: map it to p ∈ [0, 1], and make every pixel, caption and rotation a function of p.**

## What good looks like

- **It scrubs like a video.** Scroll forward and the film plays. Scroll back and it rewinds, frame for frame. Stopping halfway leaves a frame that makes sense.
- **The page is never hijacked.** Wheel, trackpad, touch and keys move the page exactly as they do everywhere else. The section is just tall.
- **The words are always readable.** Captions are real DOM text on a card. The drawing lays itself out in the space the captions leave, and the canvas is clipped around them as a safety net.
- **It is a control, not just a show.** A story drum's faces are links. Its rail, arrow buttons, arrow keys and mouse drag all seek *by scrolling the page*, so the scroll and the drum can never disagree.
- **An idle page costs nothing.** No requestAnimationFrame runs once p settles or after the section leaves the viewport.
- **Reduced motion is respected.** No smoothing, no in-between drum roll and no caption entrance animation. All of the content is still there.
- **It holds up from 360 to 1920 px wide**, in light and dark, at DPR 1 and 2.

## Hard rules

1. **p comes from the scroll position, never from a clock.** Do not use `performance.now()`, `Date`, CSS animations or `setInterval` inside a reel. Smoothing (a lerp toward the target p) is allowed because it converges to the same frame.
2. **A reel is a pure function** `draw(ctx, t, env)`. It keeps no state between frames and never calls `Math.random()`; use a seeded `hash(i)` instead. The same (t, env) must paint the same pixels.
3. **Pin with CSS, not JS.** Use a tall track (`position: relative; height: N×vh`) holding a `position: sticky; top: 0; height: 100svh` stage. Never set `position: fixed` on the stage, never lock the body, and never put `overflow: hidden|auto|clip` on an ancestor of the track.
4. **Never capture input.** Use no `preventDefault` on wheel or touch, no `overflow: hidden` on html or body, and no scroll snapping on the track. Only a focused drum may handle arrow keys, and it does so by scrolling the page.
5. **Seek by scrolling.** Every button, rail item, key and anchor changes `window.scrollY`. Never set p or a rotation directly. Use `behavior: "instant"` for programmatic jumps that must not animate, because `"auto"` obeys a page's CSS `scroll-behavior: smooth`.
6. **Text lives in the DOM.** Captions, titles and links are HTML. Canvas text is limited to decorative labels such as years, axis ticks and step names.
7. **Measure captions every frame and keep the drawing off them.** Each caption and HUD element is a keep-out (`data-keep`). Reels lay out inside `env.free`, and the engine clips the keep-outs with an even-odd clip.
8. **Never show two captions at once.** Caption windows sit inside their reel with a gap at each boundary, and reels crossfade inside that gap.
9. **The loop stops when idle.** Start rAF on scroll or resize only while the section is near the viewport (IntersectionObserver), and stop it when p equals the target.
10. **Canvas is sized to the stage at `min(devicePixelRatio, 2)`.** Call `setTransform(dpr, …)` once per frame and clear it every frame.
11. **Colours come from CSS custom properties.** Do not hard-code a light-mode palette into a reel. Re-read the palette on `prefers-color-scheme` change.
12. **Honour `prefers-reduced-motion: reduce`.** Use no smoothing, have the drum snap face to face, and turn off caption entrance animations. Frames still follow the scroll, because the user drives them.

## Build order

Do it in this order. Each step is testable before the next.

1. **Content first.** Write the chapters: a kicker, a title, one or two sentences and an optional link for each. Choose the number of reels (3 to 7) and give each one roughly 80 to 100 svh of scroll.
2. **Track and stage.** Add the tall section with a sticky 100svh stage inside it, and check that it pins with no JS at all (see [layout-and-captions](references/layout-and-captions.md)).
3. **The scrub engine.** Wire `ScrollMotion.scrub` or `film` (see [engine](references/engine.md)) and log p. Check that it reads 0 at pin start and 1 at pin end, and that it moves both ways.
4. **Captions and HUD in the DOM.** Place them per breakpoint, mark them `data-keep`, and let the engine drive their opacity from p.
5. **Reels, one at a time.** Write `draw(ctx, t, env)` inside `env.free` (see [drawing](references/drawing.md)), and scrub it back and forth before writing the next one.
6. **Motion grammar.** Add enter, hold and exit envelopes, staggers, dwell and crossfades (see [motion-grammar](references/motion-grammar.md)).
7. **Interactivity, if it is a drum.** Add face links, the rail, prev and next buttons, keys and drag, all seeking by scroll.
8. **Performance and accessibility pass.** Cover the idle loop, DPR, reduced motion, focus order, screen reader text and dark mode (see [performance-and-a11y](references/performance-and-a11y.md)).
9. **Verify** at 360, 390, 414, 768, 1024, 1280, 1440 and 1920 with the headless script (see [verification](references/verification.md)). Do not call it done until every check passes.

## Decision checklists

**Canvas film or DOM/CSS transforms?**
- Many small moving parts, lines that draw, particles, or charts → **canvas film** (`ScrollMotion.film`).
- A handful of cards, images or text panels → **DOM transforms** driven by `scrub` (the drum is one).
- Real 3D meshes or shaders → this skill is not enough. Use WebGL, but keep rules 1 to 5 and 9 to 12.

**Pin or view mode?**
- The section should hold the screen while its story plays → `mode: "pin"` (tall track and sticky stage).
- The effect rides along as content passes, as with marquees or parallax → `mode: "view"`, with no pinning.

**How tall is the track?**
- Use `n × 80–100svh + 100svh` for a film and `n × 70vh + 100vh` for a drum. If a test reader says it goes "too fast", add height. Never slow it down by capturing the wheel.

**Where do captions go?**
- Desktop (≥ 760 px): beside the drawing (left or right card) or as a wide bottom card. Phones: always a bottom sheet, with the drawing above it.
- With a fixed site header, set `--sm-nav-h` so the HUD and drum clear it.

**Does it need the drum?**
- Use the drum when the chapters are things a user may want to *go to* (pages, products, sections). Otherwise use the film alone.

## Failure modes and fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Stage scrolls away instead of pinning | An ancestor has `overflow: hidden/auto/clip`, or the stage has no `top` | Remove the overflow (use `overflow-x: clip` on body if needed) and set `top: 0` |
| Animation only plays forwards, or jumps on scroll-up | State accumulated across frames, or a clock or `Math.random` in a reel | Make the reel a pure function of t; use `hash(i)` for randomness |
| Drawing runs under the caption | Reel laid out on the full stage | Lay out in `env.free`; keep `data-keep` on the caption; let the engine clip |
| Caption box measured in the wrong place mid-fade | Used `getBoundingClientRect` (includes the transform) | Measure layout boxes (`offsetLeft/Top/Width/Height`, see `boxIn`) |
| Two captions overlap at a boundary | Caption windows touch | Fade captions out at `1 − cross` and in at `cross`; reels crossfade in the gap |
| Fans spin on an idle page | rAF loop never stops | Stop when `cur === target`; gate on IntersectionObserver |
| Blurry canvas on phones / slow on 4K | Canvas at CSS size, or uncapped DPR | Use `width = W × min(dpr, 2)` and `setTransform(dpr, 0, 0, dpr, 0, 0)` |
| Drum and page disagree after clicking the rail | The control set the rotation directly | Every control calls `scrollToProgress`; rotation only ever comes from p |
| Drag jitters, then snaps back | Page has `scroll-behavior: smooth`, so `scrollTo(x, y)` animates | Use `scrollTo({ top, behavior: "instant" })` while dragging |
| Clicking a face after a drag opens its link | The click that ends a drag fires | Swallow one capture-phase click after a drag that moved > 4 px |
| Mobile 100vh jump when the URL bar hides | `vh` on the stage | Use `100svh` for the stage; compute p with the stage's own height |
| Dark mode shows a light-mode drawing | Hard-coded colours | Read `--sm-*` tokens via `readPalette`; re-read on scheme change |
| Back faces of the drum show through | Missing `backface-visibility: hidden` | Set it, with the `-webkit-` prefix, on every face |
| Drum face thumbnails drawn at the wrong size | Used the projected rect of a 3D-transformed face | Size by `clientWidth/clientHeight` |

## Files

- [references/engine.md](references/engine.md): p, the scrub loop, `film()`, seeking, the React hook.
- [references/drawing.md](references/drawing.md): the reel contract, canvas setup, routes, pop-ins, particles and palettes.
- [references/layout-and-captions.md](references/layout-and-captions.md): track and stage CSS, keep-outs, the free rect, the clip, the drum layout.
- [references/motion-grammar.md](references/motion-grammar.md): envelopes, staggers, dwell, crossfades, pacing and easing.
- [references/performance-and-a11y.md](references/performance-and-a11y.md): the idle loop, layout cost, reduced motion, keyboard, focus and screen readers.
- [references/verification.md](references/verification.md): the eight widths, the headless Brave/Chrome script and the manual pass.
- [assets/demo.html](assets/demo.html): standalone, zero dependencies, double-click to run. Five reels and the story drum.
- [assets/scroll-motion.js](assets/scroll-motion.js): the engine (`scrub`, `film`, `drum`, `scrollToProgress` and helpers), UMD.
- [assets/reels.js](assets/reels.js): five example reels (orbit, path, stack, wave, close) and `still()` for thumbnails.
- [assets/scroll-motion.css](assets/scroll-motion.css): film and drum styles, light and dark tokens.
- [assets/ScrollFilm.jsx](assets/ScrollFilm.jsx): the React wrapper for the film, plus the `useScrub` hook.
- [assets/StoryDrum.jsx](assets/StoryDrum.jsx): the React story drum, plus a self-rolling `DrumPreview`.
- `assets/preview-orbit.jpg`, `assets/preview-path.jpg`, `assets/preview-close.jpg`: stills of the demo at 1440 × 900.

Start from the demo: open it, view source and replace the content. The wiring at the bottom of the file is about 60 lines.
