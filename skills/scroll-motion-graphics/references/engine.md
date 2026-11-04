# Engine: from scroll position to p

Everything in this skill hangs off one number: **p ∈ [0, 1]**, how far the reader has scrolled through a section. The engine measures it, optionally smooths it, and calls your frame function only while it changes. It never touches input.

The full source is [assets/scroll-motion.js](../assets/scroll-motion.js). This document explains the parts you must get right if you write your own.

## The two modes

```text
mode "pin"                                  mode "view"

 ┌──────────── track (tall) ───┐            viewport
 │ ┌── stage (sticky, 100svh) ┐│   p = 0     ┌──────────┐
 │ │                          ││  ← track    │          │  ← el's top enters
 │ │   canvas + captions      ││    top at   │          │     at the bottom: p = 0
 │ │                          ││    viewport └──────────┘
 │ └──────────────────────────┘│    top          ...
 │            ...              │              el's bottom leaves
 │                             │   p = 1      at the top: p = 1
 └─────────────────────────────┘  ← track bottom at viewport bottom
```

```js
function progressOf(el, mode, stage) {
  const r = el.getBoundingClientRect();
  const vh = window.innerHeight || 1;
  if (mode === "pin") {
    // the scrollable run is the track minus the stage it pins
    const span = el.offsetHeight - (stage ? stage.offsetHeight : vh);
    return span > 4 ? clamp01(-r.top / span) : clamp01(-r.top / vh);
  }
  return clamp01((vh - r.top) / (vh + r.height));
}
```

Use the **stage's own height** (not `innerHeight`) as the pinned part when the stage is `100svh`. On mobile, `innerHeight` grows when the URL bar hides, but `svh` does not, and mixing the two makes p overshoot.

## The scrub loop

```js
function scrub(el, onFrame, { mode = "pin", smooth = 0.18, stage = null } = {}) {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let target = 0, cur = -1, raf = 0, on = false;

  const measure = () => { target = progressOf(el, mode, stage); };
  function tick() {
    raf = 0;
    if (!on) return;
    measure();
    const d = target - cur;
    // snap when close (so the loop can end), when reduced, or on the first frame
    cur = cur < 0 || reduce || Math.abs(d) < 0.0005 ? target : cur + d * smooth;
    onFrame(cur);
    if (cur !== target) raf = requestAnimationFrame(tick);   // settled → loop ends
  }
  const kick = () => { if (on && !raf) raf = requestAnimationFrame(tick); };

  // only run near the viewport
  const io = new IntersectionObserver((es) => {
    const vis = es[es.length - 1].isIntersecting;
    if (vis && !on) { on = true; kick(); }
    else if (!vis && on) { on = false; cancelAnimationFrame(raf); raf = 0; }
  }, { rootMargin: "25% 0px" });
  io.observe(el);

  addEventListener("scroll", kick, { passive: true });   // passive: never blocks scrolling
  addEventListener("resize", kick);
  measure(); cur = target; onFrame(cur);                 // paint the right frame on load

  return { stop() { on = false; cancelAnimationFrame(raf); io.disconnect();
                    removeEventListener("scroll", kick); removeEventListener("resize", kick); } };
}
```

Why it is shaped like this:

- **Scroll events only kick the loop.** They never draw. The rAF tick reads layout once and writes once.
- **The snap threshold** (`0.0005`) is what lets `cur === target` become true, so the loop ends. Without it, a lerp approaches forever and the page never idles.
- **Smoothing is a lerp toward the scroll target**, not a timeline. Because it converges to the same p, the frame you land on is the same frame you would get without smoothing. That is why "pure function of p" survives it. Use `smooth` 0.12 to 0.2. Higher is snappier, and 1 means none.
- **On the first frame `cur = target`**, so a page reloaded mid-section shows the correct frame instead of animating from 0.
- **IntersectionObserver with a margin** means a page with five scroll sections runs, at most, the loop of the one on screen.

## The film: reels on a shared timeline

`ScrollMotion.film()` is the scrub loop plus a canvas, a timeline split into equal reel slices, captions and keep-outs.

```js
const player = ScrollMotion.film({
  track: document.querySelector(".smf"),           // tall section
  stage: document.querySelector(".smf-stage"),     // sticky child
  canvas: document.querySelector(".smf-canvas"),
  reels: ScrollReels.all,                          // [{ name, draw(ctx, t, env) }]
  captions: [...document.querySelectorAll(".smf-cap")], // one per reel, in order
  smooth: 0.14,      // lerp factor
  cross: 0.12,       // reel crossfade half-width, in reel units
  capFade: 0.1,      // caption fade length, in reel units
  onChange(i, reel) { /* the dominant reel changed: analytics, aria-live, etc. */ },
});
```

### The timeline math

With `n` reels, reel `i` owns `p ∈ [i/n, (i+1)/n]`. Inside it, the local coordinate is `u = p·n − i` (unclamped) and the reel receives `t = clamp01(u)`.

```js
const local = (p, i) => p * n - i;

function reelAlpha(p, i) {                      // reels crossfade across each boundary
  const u = local(p, i);
  const fin  = i === 0     ? 1 : smoothstep((u + cross) / (2 * cross));
  const fout = i === n - 1 ? 1 : smoothstep((1 + cross - u) / (2 * cross));
  return Math.min(fin, fout);
}

function capAlpha(p, i) {                       // captions fade inside their reel, leaving a gap
  const u = local(p, i);
  const fin  = i === 0     ? 1 : seg(u, cross, cross + capFade);
  const fout = i === n - 1 ? 1 : 1 - seg(u, 1 - cross - capFade, 1 - cross);
  return Math.min(fin, fout);
}
```

The first reel never fades in and the last never fades out, so the film opens and ends on a full frame. Captions leave a gap of `2 × cross` around each boundary, which is exactly where the reels crossfade. Two captions are therefore never visible together, and the keep-outs never jump while a reel is drawing.

### The frame

Each painted frame does three things, in this order:

```js
function paint(p) {
  // 1. WRITE: caption opacity/transform, HUD counter and bar, all from p
  // 2. READ:  measure every keep-out (captions + [data-keep]) → rects
  // 3. DRAW:  clear, clip out the keep-outs (evenodd), draw each reel whose alpha > 0
  //           with ctx.globalAlpha = alpha and env.free = freeRect(stage − keep-outs)
}
```

Writes happen before reads, so there is at most one layout per frame. The keep-outs are measured with `offsetLeft/Top/Width/Height` walked up to the stage (`boxIn`). These ignore transforms, so a caption that is mid-slide still reserves its resting box. See [layout-and-captions](layout-and-captions.md).

### The returned handle

| Member | Use |
| --- | --- |
| `p` | the current (smoothed) progress |
| `keeps` | the keep-out rects of the last painted frame (tests use this) |
| `renderAt(p)` | paint any p without scrolling: posters, tests and purity checks |
| `seek(p)` / `seekReel(i, at)` | scroll the page to a p, or to a point inside reel i |
| `retheme()` | re-read the palette and repaint (after a manual theme toggle) |
| `destroy()` | remove every listener and observer |

## Seeking: always by scrolling

```js
function scrollToProgress(el, p, { stage = null, smooth = !prefersReduced(), nudge = 0 } = {}) {
  const top = el.getBoundingClientRect().top + window.scrollY;
  const run = el.offsetHeight - (stage ? stage.offsetHeight : window.innerHeight);
  window.scrollTo({ top: Math.round(top + run * clamp01(p)) + nudge,
                    behavior: smooth ? "smooth" : "instant" });
}
```

- Every control (drum rail, prev and next, keys, a "jump to chapter" link, drag release) calls this. The scroll position stays the single source of truth, so the scrollbar, browser history (`#anchor`), the drum and the film all agree.
- Use `"instant"`, never `"auto"`, for a non-animated jump. `"auto"` means "whatever CSS says", and many sites set `html { scroll-behavior: smooth }`.
- A `nudge` of 1 px past an exact chapter boundary avoids landing a hair before it on fractional scroll positions.
- **Plain anchors work too.** The demo puts zero-size anchors inside the track at `top = (at / n) × span` (recomputed on resize), so `<a href="#reel-path">` seeks the film with no JS on the link.

## The drum engine

`ScrollMotion.drum(root)` is `scrub` plus a rotation:

```js
const f = clamp01(p) * (n - 1);            // which face, fractional
const base = Math.floor(f), t = f - base;
const turn = reduce ? Math.round(f)        // reduced motion: snap face to face
                    : base + t * t * (3 - 2 * t);   // dwell: smoothstep inside each step
ring.style.transform = `translateZ(calc(var(--r) * -1)) rotateX(${turn * 360 / n}deg)`;
const idx = Math.min(n - 1, Math.round(f));         // the face you see
```

The smoothstep inside each step makes the drum *park* on a face for a while, then roll quickly to the next. That is what makes it readable. A linear rotation is always half-way between two faces.

## React

[assets/ScrollFilm.jsx](../assets/ScrollFilm.jsx) exports `useScrub` and `ScrollFilm`. [assets/StoryDrum.jsx](../assets/StoryDrum.jsx) is the drum.

```jsx
export function useScrub(ref, onFrame, { mode = "pin", smooth = 0.18, stageRef = null } = {}) {
  const cb = useRef(onFrame);
  cb.current = onFrame;                       // latest closure, without restarting the loop
  useEffect(() => {
    const s = ScrollMotion.scrub(ref.current, (p) => cb.current(p),
                                 { mode, smooth, stage: stageRef?.current ?? null });
    return () => s.stop();
  }, [ref, mode, smooth, stageRef]);
}
```

React rules:

- **Never `setState` per frame.** Write styles through refs inside `onFrame`, and set state only when a discrete index changes (the face or reel).
- `reels` must be referentially stable (module scope or `useMemo`), or the film is rebuilt.
- In Next.js these are client components (`"use client"`). The engine is safe to import during SSR, because nothing runs until an effect does.
- `scroll-motion.js` is UMD. Webpack and Next hand you `module.exports`. Vite serves it as ESM with no exports, so it registers `globalThis.ScrollMotion`. `ScrollFilm.jsx` resolves either. Import `ScrollFilm.jsx` before `reels.js`.

## Writing your own engine instead

If you port this to another framework, keep these invariants and you have kept the method:

1. One measured target per frame, from `getBoundingClientRect` of the track.
2. A lerp toward it with a snap threshold, so it can settle.
3. rAF scheduled only by scroll, resize or visibility, and only while not settled.
4. Passive listeners, and no `preventDefault` anywhere near scrolling.
5. Every control seeks with `scrollTo`.
