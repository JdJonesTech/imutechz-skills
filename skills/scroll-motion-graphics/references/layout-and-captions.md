# Layout and captions

The drawing and the words share one screen. The rule is simple: **the words win.** Captions are DOM, measured every frame, and the canvas lays out in whatever space they leave. Anything that would still touch them is clipped away.

## The track and the stage

```html
<section class="smf" style="--smf-n: 5" aria-label="A film in five reels">
  <div class="smf-stage">
    <canvas class="smf-canvas" aria-hidden="true"></canvas>
    <div class="smf-frame">
      <div class="smf-hud" data-keep>…counter, progress bar…</div>
      <article class="smf-cap" data-place="left">…</article>   <!-- one per reel -->
      …
      <p class="smf-hint" data-keep>Scroll back: it rewinds</p>
    </div>
  </div>
</section>
```

```css
.smf       { position: relative; height: calc(var(--smf-n) * 90svh + 100svh); }
.smf-stage { position: sticky; top: 0; height: 100svh; overflow: hidden; }
.smf-canvas{ position: absolute; inset: 0; display: block; pointer-events: none; }
.smf-frame { position: absolute; inset: calc(var(--sm-nav-h) + 16px) clamp(16px, 4vw, 48px) 20px; pointer-events: none; }
.smf-frame > * { pointer-events: auto; }
```

- The **track** is the timeline. Its height sets the pace (see [motion-grammar](motion-grammar.md)).
- The **stage** is sticky, so it pins with zero JS. `overflow: hidden` goes on the stage, never on an ancestor of the track.
- The **frame** is the safe area: side gutters (16 px minimum on phones) and a top inset for a fixed site header (`--sm-nav-h`).
- The canvas has `pointer-events: none`, so links in captions stay clickable and text stays selectable.

Sticky checklist when "it doesn't pin":

1. Is any ancestor `overflow: hidden | auto | scroll | clip`? Remove it, or use `overflow-x: clip` only on `body` (clip does not create a scroll container in modern engines, but test it).
2. Does the stage have `top: 0`?
3. Is the track taller than the stage? Sticky needs room to travel.
4. Is the stage a flex or grid child stretched to the track's height? Give it an explicit `height: 100svh`.

## Keep-outs: measured every frame

Every element the drawing must avoid carries `data-keep`. Captions are keep-outs too, and the engine adds them per reel.

```js
function boxIn(el, stage) {          // layout box relative to the stage, transform-free
  let x = 0, y = 0, n = el;
  while (n && n !== stage) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; }
  return { x, y, w: el.offsetWidth, h: el.offsetHeight };
}
```

Why `offset*` rather than `getBoundingClientRect`:

- A caption mid-entrance has `translateY(14px)`. Its *resting* box is what should be reserved, otherwise the free rect wobbles while it slides.
- `offset*` returns layout values that the browser has already computed. After the frame's style writes, reading them costs one layout at most, and nothing when nothing changed.
- The stage is `position: sticky`, which makes it an `offsetParent`, so the walk stops there.

Elements with `display: none` (for example a hint hidden on phones) have `offsetParent === null` and are skipped.

Each rect is padded (default 14 px) before use.

## The free rect

`freeRect(W, H, keeps, margin)` returns the largest rectangle of the stage that misses every keep-out. It is greedy: for each keep-out (largest first) that intersects the current free area, take the best of the four sides of it.

```js
function freeRect(W, H, keeps, margin = 0) {
  let F = { x: 0, y: 0, w: W, h: H };
  // area, with thin slivers penalised: a 1400×60 strip is not a good canvas
  const score = (r) => r.w <= 0 || r.h <= 0 ? -1
    : r.w * r.h * Math.pow(Math.min(r.w, r.h) / Math.max(r.w, r.h), 0.35);
  for (const k of [...keeps].sort((a, b) => b.w * b.h - a.w * a.h)) {
    if (!hits(F, k)) continue;
    const cands = [
      { x: F.x,       y: F.y,       w: k.x - F.x,             h: F.h },             // left
      { x: k.x + k.w, y: F.y,       w: F.x + F.w - k.x - k.w, h: F.h },             // right
      { x: F.x,       y: F.y,       w: F.w,                   h: k.y - F.y },       // above
      { x: F.x,       y: k.y + k.h, w: F.w,                   h: F.y + F.h - k.y - k.h }, // below
    ];
    F = cands.reduce((best, c) => (score(c) > score(best) ? c : best));
  }
  return { x: F.x + margin, y: F.y + margin, w: F.w - 2 * margin, h: F.h - 2 * margin };
}
```

What it gives you in practice:

| Layout | Free rect |
| --- | --- |
| HUD strip on top, caption card at the left middle | right of the card, below the HUD |
| Wide caption at the bottom (desktop) | above the caption, full width |
| Caption at the right | left of it |
| Phone: HUD on top, caption as a bottom sheet | the band between them |

Reels receive this as `env.free` and lay out inside it. The engine passes each reel a keep list of **its own caption** (visible or not), the fixed keep-outs and any caption currently visible. A reel therefore lays out around the caption it will share the screen with, and does so from its first faded-in frame, so nothing jumps when its caption arrives.

## The clip: a safety net

Layout in `free` is the design. The clip is the guarantee:

```js
ctx.save();
ctx.beginPath();
ctx.rect(0, 0, W, H);                          // the whole stage…
for (const k of visibleKeeps) ctx.rect(k.x, k.y, k.w, k.h);  // …minus every visible keep-out
ctx.clip("evenodd");
/* draw reels */
ctx.restore();
```

Even-odd fill makes each inner rect a hole. A glow radius or label that spills past `free` is cut at the caption's padded edge instead of running under the text. If you ever see a visibly cut drawing, the reel's layout is wrong. Fix the layout, not the clip.

The verification script reads the canvas pixels inside every visible keep-out and requires an alpha of exactly 0.

## Captions

```html
<article class="smf-cap" data-place="left" data-keep>
  <p class="smf-cap-k"><span>01 · Orbit</span><span>Pin a stage</span></p>
  <h3 class="smf-cap-h">One timeline, many moving parts.</h3>
  <p class="smf-cap-d">One or two sentences. No more.</p>
</article>
```

```css
.smf-cap { position: absolute; width: min(400px, 100%); padding: 22px 24px 24px; border-radius: 20px;
  background: var(--sm-card); border: 1px solid var(--sm-card-line);
  backdrop-filter: blur(14px) saturate(1.4); box-shadow: 0 18px 50px -26px var(--sm-shadow);
  opacity: 0; visibility: hidden; }
.smf-cap[data-place="left"]   { left: 0;  top: 50%; margin-top: -110px; }
.smf-cap[data-place="right"]  { right: 0; top: 50%; margin-top: -110px; }
.smf-cap[data-place="bottom"] { left: 0;  bottom: 0; width: min(560px, 100%); }
.smf-cap[data-place="top"]    { left: 0;  top: 44px; }
@media (max-width: 759px) {    /* phones: always a bottom sheet */
  .smf-cap, .smf-cap[data-place] { left: 0; right: 0; top: auto; bottom: 0; width: auto; margin: 0; }
}
```

- The engine writes `opacity`, `transform` and `visibility` from p every frame. CSS never animates them, so they scrub backwards too.
- Vary `data-place` between reels on desktop. It keeps the composition moving, and the free rect follows automatically.
- Use a frosted card rather than bare text over a drawing. Contrast must hold even if a glow sits near the edge.
- Keep the copy short, because phone bottom sheets must not eat more than about 40% of the stage. At 360 × 740 a kicker, a two-line title and three lines of body is the limit.
- **No two captions at once** (see the timeline math in [engine](engine.md)).

## The HUD

A thin strip across the top: a title, a counter (`[data-sm-count]`) and a progress bar (`[data-sm-bar]`, `scaleX(p)`). It tells the reader that this is a sequence and how far through it they are. It is a keep-out.

## The story drum layout

```html
<section class="sd" style="height: calc(5 * 70vh + 100vh)">
  <div class="sd-stage">                       <!-- sticky grid: copy | drum | rail -->
    <div class="sd-copy">kicker, title, one .sd-cap per chapter (hidden), ‹ › buttons</div>
    <div class="sd-viewport" tabindex="0">     <!-- perspective, mask, focus target -->
      <div class="sd-ring">                    <!-- preserve-3d, rotated by p -->
        <a class="sd-face" href="…">art + meta</a> × n
      </div>
    </div>
    <ol class="sd-rail"><i><i data-sd-bar></i></i><li><button data-sd-go="0">…</button></li>…</ol>
  </div>
</section>
```

```css
.sd-stage    { position: sticky; top: 0; height: 100svh; display: grid;
               grid-template-columns: minmax(0, 1fr) minmax(320px, 1.1fr) 180px; align-items: center; }
.sd-viewport { --r: clamp(180px, 19vw, 260px); height: min(74vh, 600px); perspective: 1300px;
               display: grid; place-items: center; touch-action: pan-y;
               mask-image: linear-gradient(to bottom, transparent, #000 20%, #000 80%, transparent); }
.sd-ring     { position: relative; width: 100%; height: calc(var(--r) * 1.12); transform-style: preserve-3d; }
.sd-face     { position: absolute; inset: 0; backface-visibility: hidden; }
/* each face: rotateX(-i·360/n deg) translateZ(var(--r)); ring: translateZ(-r) rotateX(turn·360/n deg) */
@media (max-width: 1000px) {
  .sd-stage { grid-template-columns: minmax(0, 1fr); }
  .sd-rail, .sd-title, .sd-tip, .sd-d { display: none; }
  .sd-viewport { --r: clamp(150px, 40vw, 220px); height: min(52vh, 440px); }
  .sd-copy { order: 2; }
  .sd-nav button { width: 44px; height: 44px; }
}
```

- `--r` is the cylinder radius. The ring's `translateZ(-r)` pulls the front face back to the screen plane, so it renders at 1:1.
- The vertical mask fades the neighbour faces at the top and bottom edges. You see that it is a drum without the neighbours competing.
- `minmax(0, 1fr)` (not `1fr`) on phones stops long words from forcing horizontal overflow.
- Give `.sd-cap` a `min-height`, so the buttons below do not jump between chapters of different lengths.

## Breakpoints that matter

| Width | What changes |
| --- | --- |
| < 760 | film captions become bottom sheets; `env.mobile` true; HUD extras and hint hidden |
| < 1000 | drum stacks (drum on top, copy below); rail, title and body copy hidden; 44 px buttons |
| ≥ 1000 | drum three-column grid |
| ≥ 1440 | nothing new: let `clamp()` carry it, cap the drum stage at 1320 px |
