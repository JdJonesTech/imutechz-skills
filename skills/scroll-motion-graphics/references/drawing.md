# Drawing: reels that are pure functions of t

A reel is an object with a name and a draw function:

```js
const myReel = {
  name: "path",
  draw(ctx, t, env) {
    // t   ∈ [0, 1]  local progress through this reel
    // env = { W, H, dpr, mobile, colors, keep, free, alpha, p, index, reduce }
  },
};
```

The engine calls `draw` once per painted frame for every reel whose crossfade alpha is above zero. Before it does, it has already called `setTransform(dpr, …)`, cleared the canvas, clipped out the keep-outs and set `ctx.globalAlpha = env.alpha` inside a `save`/`restore`.

## The contract

| Do | Do not |
| --- | --- |
| Derive every position, size, colour and alpha from `t` and `env` | Keep variables that carry over between frames |
| Use `hash(i, seed)` for variety | Call `Math.random()` |
| Lay out inside `env.free` | Lay out on `0..W, 0..H` |
| Read colours from `env.colors` | Hard-code `#fff` or `#000` for content |
| Multiply alpha (`rgba(c, a)`) | Assign `ctx.globalAlpha = …` (it overwrites the crossfade) |
| Draw decorative labels (years, steps, ticks) | Draw sentences: those are DOM captions |
| Return early if `env.free` is too small | Throw, or draw outside it "just a bit" |

The test of purity is mechanical: `renderAt(0.3)`, then `renderAt(0.9)`, then `renderAt(0.3)` must produce identical pixels. [verification](verification.md) checks this at every width.

Precompute nothing that depends on `t`. It is fine to cache geometry that depends only on `env.free` and the content (for example, route samples) as long as you rebuild it when `free` changes. In practice a 7-node route takes microseconds to sample, so the reference reels simply recompute it each frame.

## env

| Field | Meaning |
| --- | --- |
| `W`, `H` | stage size in CSS px (the canvas is `W × dpr` by `H × dpr`) |
| `free` | `{x, y, w, h}`: the largest rectangle missing every keep-out, already inset by a margin. **Lay out here.** |
| `keep` | the keep-out rects (this reel's caption, the HUD, any visible caption), for `blocked(keep, x, y, r)` checks |
| `mobile` | `W < 760`: use thinner lines, fewer items and smaller labels |
| `colors` | `{ink, dim, bg, surface, accent, accent2, cool}` as `[r, g, b]`, read from CSS tokens |
| `alpha` | this reel's crossfade alpha (already applied to `globalAlpha`) |
| `p`, `index` | global progress and reel index, for readouts |
| `reduce` | prefers-reduced-motion. Frames still follow scroll, but drop decorative wobble |

## Canvas setup (the engine does this, and so must you if you roll your own)

```js
function layout() {
  const r = stage.getBoundingClientRect();
  W = r.width; H = r.height;
  dpr = Math.min(window.devicePixelRatio || 1, 2);    // cap: 3× phones and 4K gain nothing visible
  canvas.width = Math.round(W * dpr);
  canvas.height = Math.round(H * dpr);
  canvas.style.width = W + "px"; canvas.style.height = H + "px";
}
// per frame
ctx.setTransform(dpr, 0, 0, dpr, 0, 0);   // draw in CSS px
ctx.clearRect(0, 0, W, H);
```

Re-run `layout` from a `ResizeObserver` on the stage, not a window resize. Then repaint immediately at the current p, because resizing clears the canvas.

## Helpers ([assets/scroll-motion.js](../assets/scroll-motion.js))

```js
const { clamp01, lerp, seg, smoothstep, ease, stagger, hash, rgba, mix, route, strokeTo } = ScrollMotion;

seg(t, 0.2, 0.6)        // 0 before 0.2, 1 after 0.6, linear between: a window inside the reel
ease.outCubic(x)        // land, don't stop
ease.outBack(x)         // pop with a small overshoot (nodes, dots)
ease.inOutCubic(x)      // travel between two places
stagger(t, i, n, 0.4)   // item i's own 0..1, each item taking 40% of the reel, starts spread evenly
hash(i, seed)           // deterministic 0..1
rgba([r, g, b], a)      // canvas colour string
mix(c1, c2, 0.3)        // blend two palette colours
```

## Pattern: a route that draws with the scroll

This is the PathFilm technique. Nodes go through a Catmull-Rom spline sampled **by arc length**, so the line grows at a constant speed regardless of curvature.

```js
draw(ctx, t, env) {
  const { free: F, colors: C } = env;
  const nodes = STEPS.map((_, i, a) => {
    const u = i / (a.length - 1);
    return [F.x + F.w * (0.04 + u * 0.92), F.y + 30 + (F.h - 74) * (0.5 + Math.sin(u * Math.PI * 2.4 + 0.4) * 0.5)];
  });
  const { samples, at, total } = route(nodes);      // samples: [x, y, cumulativeLength]
  const L = seg(t, 0.04, 0.92) * total;              // lead-in and a hold at the end

  // 1. the road ahead: faint, dotted, full length
  ctx.setLineDash([2, 9]); ctx.strokeStyle = rgba(C.ink, 0.18); ctx.lineWidth = 2;
  ctx.beginPath(); samples.forEach(([x, y], k) => (k ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.stroke();
  ctx.setLineDash([]);

  // 2. the road travelled: solid, gradient, exactly L long; strokeTo returns the head
  ctx.strokeStyle = rgba(C.accent2); ctx.lineWidth = env.mobile ? 3 : 4;
  const head = L > 0 ? strokeTo(ctx, samples, L) : samples[0];

  // 3. milestones pop as the head reaches them
  nodes.forEach(([x, y], i) => {
    const reach = clamp01((L - at[i] + total * 0.012) / (total * 0.04));
    const r = 11 * ease.outBack(reach);
    /* reach === 0: hollow ring; reach > 0: halo + filled dot of radius r */
  });

  // 4. a glow at the head (no pulse: a time-based pulse would break purity)
}
```

Choose the layout from the free rect's aspect: a horizontal sine when `F.w > F.h`, and a vertical zigzag on phones.

## Pattern: staggered items that land

```js
const build = seg(t, 0, 0.72);                       // the build uses the first 72% of the reel
for (let i = 0; i < n; i++) {
  const k = ease.outCubic(stagger(build, i, n, 0.32));
  const h = maxH * value[i] * k;
  /* draw bar i with height h */
}
const line = seg(t, 0.62, 0.96);                     // the next layer waits for the build
```

Overlapping windows (`span` > `1/n`) look fluid. Disjoint windows look mechanical.

## Pattern: particles that resolve onto a mark

```js
for (let i = 0; i < M; i++) {
  const [sx, sy] = [F.x + hash(i, 1) * F.w, F.y + hash(i, 2) * F.h];   // scattered start (stable)
  const [tx, ty] = target(i);                                         // a point on the mark
  const e = ease.inOutCubic(stagger(seg(t, 0, 0.8), i % 40, 40, 0.6));
  const bend = Math.sin(e * Math.PI) * 40 * (hash(i, 5) - 0.5);       // curved, not straight, paths
  const x = lerp(sx, tx, e) + bend, y = lerp(sy, ty, e) - bend;
  /* dot at (x, y): dim while travelling, solid once e > 0.98 */
}
```

Keep the particle count modest (100 to 200) and draw plain `arc` fills. Do not use `shadowBlur` per particle.

## Pattern: rhythm without a clock

A wave's phase comes from `t` (`phase = t × 2π × 1.5`), so scrolling *is* the oscillator. Inset rows by the largest amplitude so no crest leaves `free`:

```js
const ampMax = (F.h / rows) * 1.1;
const rowY = (r) => F.y + ampMax + (F.h - 2 * ampMax) * (r / (rows - 1));
```

## Palette

```js
// CSS (scroll-motion.css): tokens on :root, redefined for dark mode
// JS: env.colors comes from readPalette(stage)
ctx.strokeStyle = rgba(C.ink, 0.18);   // structure
ctx.fillStyle   = rgba(C.accent2);     // the thing that matters
ctx.fillStyle   = rgba(C.surface);     // "holes" in dots (not #fff, which glows in dark mode)
```

Two accents and an ink at several alphas carry every reel in the demo. Glows are radial gradients from `accent` at 0.35 to 0.55 alpha down to 0.

## Cost guide

- `createLinearGradient` and `createRadialGradient` per frame are fine (a few per reel).
- `shadowBlur`, `filter` and `getImageData` in the frame loop are not.
- Thousands of path segments are fine. Thousands of `fill()` calls on a 4K canvas are not. Batch dots into one path if you need more than a few hundred.
- Text: set `ctx.font` once per batch, and use a monospace stack for labels so widths stay predictable.

## Thumbnails and posters

The same reel draws a still for a drum face or a poster: call it at a fixed `t` with an empty `keep` and a padded `free`. Size by `clientWidth/clientHeight`, not `getBoundingClientRect`, because a 3D-transformed face reports its projected box.

```js
ScrollReels.still(faceCanvas, ScrollReels.path, 0.86, ScrollMotion.readPalette(drumEl), 12);
```
