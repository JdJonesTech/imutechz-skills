# Performance and accessibility

A scroll film is a long-running piece of UI on the main thread, in the one interaction (scrolling) that users notice jank in most. It also hides its content in a canvas. Both need deliberate handling.

## Performance

### The loop runs only when something changes

```js
const kick = () => { if (on && !raf) raf = requestAnimationFrame(tick); };
addEventListener("scroll", kick, { passive: true });
addEventListener("resize", kick);
new IntersectionObserver(([e]) => { on = e.isIntersecting; if (on) kick(); else cancelAnimationFrame(raf); },
                         { rootMargin: "40% 0px" }).observe(track);

function tick() {
  raf = 0; if (!on) return;
  measure();
  cur = Math.abs(target - cur) < 0.0005 ? target : cur + (target - cur) * smooth;
  if (cur !== painted) { painted = cur; paint(cur); raf = requestAnimationFrame(tick); }
}
```

- **Settled means zero rAF.** The verification script counts `requestAnimationFrame` calls over one idle second and requires 0.
- **Off-screen means zero rAF.** The observer stops the loop when the section is more than 40% of a viewport away.
- **Passive listeners** let the compositor scroll without waiting for JS.
- Scroll handlers do nothing but schedule work. They never read layout or draw.

### One layout per frame, at most

Order every frame as **write, then read, then draw**:

1. Write caption opacity and transform, plus the HUD, from p (style writes).
2. Read keep-out boxes via `offset*` (one layout if the writes dirtied it, otherwise free).
3. Draw on the canvas (no layout).

Never interleave reads and writes across several elements. That forces a layout per element.

### Canvas budget

- DPR is capped at 2. A 1920 × 1080 stage at DPR 2 is 8.3 MP, which is fine for 2D. At DPR 3 it is 18.7 MP, which is not.
- Do not use `shadowBlur`, `filter` or `getImageData` in the frame. Glows are radial gradients.
- Reels with alpha 0 are skipped entirely.
- Resize through a `ResizeObserver` on the stage, with one `layout()` and an immediate repaint.
- Do not paint offscreen drum faces every frame. Paint their stills once, then again on resize or theme change. In React, render art only for the visible face ±1.

### CSS

- `will-change: transform` on the drum ring and `will-change: opacity, transform` on captions, and nowhere else.
- `backdrop-filter` on caption cards is the most expensive thing on the page. Keep it to the one visible card (`visibility: hidden` on the others removes them from painting).
- Do not put `overflow: hidden | auto | scroll` on an *ancestor* of the track. It becomes the scroll container sticky attaches to, and the stage stops pinning. If you add `contain` to an ancestor for performance, re-test the pin.

## Never pin input

These are hard requirements, not preferences:

- No `wheel` or `touchmove` listeners with `preventDefault`.
- No `overflow: hidden` on `html` or `body`, and no `position: fixed` on the body to "lock" it.
- No CSS `scroll-snap` on the track. Snapping fights the reader's own speed.
- The drum's arrow keys work **only when the drum has focus**, and they call `scrollTo`. Arrow keys anywhere else scroll the page as usual.
- Drag is mouse and pen only (`pointerType !== "touch"`). Touch already scrolls, and `touch-action: pan-y` on the viewport keeps it that way.
- After a drag that moved more than 4 px, swallow exactly one click (capture phase, removed after 50 ms), so releasing over a face does not follow its link.

## Reduced motion

```js
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
```

| What | With reduce |
| --- | --- |
| scroll smoothing | off: p is the scroll position |
| drum rotation | whole faces only |
| caption transform | none (opacity still follows p) |
| `.sd-cap` entrance animation | `animation: none` |
| programmatic seeks | instant |
| decorative self-running loops | stopped |

Frames still follow the scroll, because the user is driving them and nothing moves on its own. The content, the order and the controls are identical.

## Keyboard and focus

- The drum viewport is `tabindex="0"` with an `aria-label` that says the arrow keys change the chapter. `:focus-visible` outlines the front face.
- Only the visible face is tabbable (`tabIndex = 0`). The others are `-1` and `aria-hidden="true"`, so Tab does not walk around the back of a cylinder.
- Keys: ← ↑ for the previous chapter, → ↓ for the next, plus Home and End. Each one `preventDefault`s only the key it handles.
- The prev and next buttons are real `<button>`s with `aria-label`s, disabled at the ends. Rail items are buttons with `aria-current="step"` on the active one.
- Buttons are at least 44 × 44 px under 1000 px wide.
- Focus rings use the accent colour with a 3 to 4 px offset. Never remove outlines without a replacement.

## Screen readers

- The canvas is `aria-hidden="true"`. Nothing important may live only in it.
- Captions are real headings and paragraphs, present in the DOM in reading order the whole time (opacity, not removal), so a screen reader reads the full story top to bottom.
- Where the visible text is abbreviated (for example the PathFilm caption shows only the active milestone), add a `.sr-only` ordered list with every item.
- The section has an `aria-label` that names the sequence ("A film in five reels").
- Drum captions that are not current are `hidden`. The rail and buttons expose the full chapter list, and every face is a link with a visible name.

## Colour and contrast

- All colours are CSS custom properties on `:root`, redefined under `@media (prefers-color-scheme: dark)` (guarded by `:root:not([data-theme="light"])`) and under `:root[data-theme="dark"]` for a manual toggle.
- The canvas reads the same tokens (`readPalette`) and re-reads them on a scheme change.
- Caption text sits on a frosted card, not on the drawing, so contrast does not depend on what the reel is doing. Check body text at ≥ 4.5:1 against the card in both themes.
- Use `--sm-surface` (not `#fff`) for the "holes" in dots, or they glow in dark mode.

## Mobile specifics

- `100svh` for stages, so the URL bar showing or hiding does not resize the pin.
- `env.mobile` (stage < 760 px) means fewer items, thinner lines and smaller labels.
- Captions become bottom sheets, and the drawing sits in the band above.
- Test with a real phone flick: if one flick skips a reel, the track is too short.
