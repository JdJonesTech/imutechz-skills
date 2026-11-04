/*! scroll-motion.js v1.0.0 · ImuTechz · MIT
 *
 * The engine behind scroll motion graphics: scroll position becomes a
 * progress value p in [0, 1], and every frame is a pure function of p.
 *
 *   ScrollMotion.scrub(el, onFrame, opts)   p for one element (useScrub, vanilla)
 *   ScrollMotion.film(opts)                 a pinned canvas film made of reels
 *   ScrollMotion.drum(root, opts)           an interactive 3D story drum
 *   ScrollMotion.scrollToProgress(el, p)    seek by scrolling the page
 *   ScrollMotion.*                          small math + drawing helpers
 *
 * Rules the engine keeps for you:
 *   - it never captures wheel, touch or keys and never pins the body;
 *     normal scrolling always moves the page
 *   - the rAF loop runs only while p is changing and the element is near
 *     the viewport; an idle page costs nothing
 *   - prefers-reduced-motion: no smoothing, no in-between drum rotation
 *
 * Zero dependencies. Works as a classic <script> (window.ScrollMotion),
 * as CommonJS, or through a bundler's CommonJS interop (import X from).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ScrollMotion = factory();
})(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* ───────────────────────── math ───────────────────────── */

  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
  const lerp = (a, b, t) => a + (b - a) * t;
  /* local progress of p inside the window [a, b] */
  const seg = (p, a, b) => clamp01((p - a) / (b - a || 1));
  const smoothstep = (t) => { t = clamp01(t); return t * t * (3 - 2 * t); };
  const ease = {
    linear: (t) => t,
    inOut: smoothstep,
    outCubic: (t) => 1 - Math.pow(1 - clamp01(t), 3),
    inOutCubic: (t) => { t = clamp01(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; },
    outBack: (t) => { t = clamp01(t); const c = 1.70158, c3 = c + 1; return 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
    outExpo: (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * clamp01(t))),
  };
  /* staggered local progress for item i of n: item i starts at i*gap */
  const stagger = (t, i, n, span = 0.5) => {
    const gap = n > 1 ? (1 - span) / (n - 1) : 0;
    return clamp01((t - i * gap) / span);
  };
  /* a deterministic pseudo-random number in [0, 1) — never Math.random in a reel */
  const hash = (i, s = 0) => { const x = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return x - Math.floor(x); };
  const prefersReduced = () =>
    typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ─────────────────────── colours ──────────────────────── */

  /* "#f2661a" | "rgb(…)" → [r, g, b] */
  function parseColor(c, fallback = [28, 25, 20]) {
    c = String(c || "").trim();
    let m = /^#([0-9a-f]{3})$/i.exec(c);
    if (m) return m[1].split("").map((h) => parseInt(h + h, 16));
    m = /^#([0-9a-f]{6})$/i.exec(c);
    if (m) return [0, 2, 4].map((k) => parseInt(m[1].slice(k, k + 2), 16));
    m = /^rgba?\(([^)]+)\)$/i.exec(c);
    if (m) return m[1].split(/[ ,/]+/).slice(0, 3).map(Number);
    return fallback;
  }
  const rgba = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  const mix = (c1, c2, t) => [0, 1, 2].map((k) => Math.round(lerp(c1[k], c2[k], t)));

  /* the canvas palette comes from CSS custom properties on `el`, so light
     and dark mode are one stylesheet change, never a second code path */
  function readPalette(el) {
    const cs = getComputedStyle(el);
    const v = (name, fb) => parseColor(cs.getPropertyValue(name), fb);
    return {
      ink: v("--sm-ink", [28, 25, 20]),
      dim: v("--sm-dim", [138, 130, 119]),
      bg: v("--sm-bg", [243, 237, 226]),
      surface: v("--sm-surface", [251, 248, 242]),
      accent: v("--sm-accent", [242, 102, 26]),
      accent2: v("--sm-accent-2", [217, 72, 30]),
      cool: v("--sm-cool", [46, 108, 150]),
    };
  }

  /* ─────────────────────── geometry ─────────────────────── */

  /* Catmull-Rom through `pts`, sampled by arc length:
     returns { samples: [[x, y, len]], at: [len of each node], total } */
  function route(pts, perSeg = 40) {
    const n = pts.length, samples = [], at = [];
    let total = 0;
    if (!n) return { samples, at, total };
    const P = (i) => pts[clamp(i, 0, n - 1)];
    for (let i = 0; i < n - 1; i++) {
      const p0 = P(i - 1), p1 = P(i), p2 = P(i + 1), p3 = P(i + 2);
      for (let s = 0; s < perSeg; s++) {
        const t = s / perSeg, t2 = t * t, t3 = t2 * t;
        const x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3);
        const y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3);
        if (samples.length) { const q = samples[samples.length - 1]; total += Math.hypot(x - q[0], y - q[1]); }
        if (s === 0) at[i] = total;
        samples.push([x, y, total]);
      }
    }
    const last = pts[n - 1], q = samples[samples.length - 1];
    if (q) total += Math.hypot(last[0] - q[0], last[1] - q[1]);
    samples.push([last[0], last[1], total]);
    at[n - 1] = total;
    return { samples, at, total };
  }

  /* stroke the first L pixels of a sampled route; returns the head point */
  function strokeTo(ctx, samples, L) {
    let head = samples[0];
    ctx.beginPath();
    for (let k = 0; k < samples.length; k++) {
      const s = samples[k];
      if (s[2] > L) {
        const a = samples[k - 1] || s, f = (L - a[2]) / Math.max(1e-6, s[2] - a[2]);
        head = [a[0] + (s[0] - a[0]) * f, a[1] + (s[1] - a[1]) * f];
        ctx.lineTo(head[0], head[1]);
        break;
      }
      head = s;
      k ? ctx.lineTo(s[0], s[1]) : ctx.moveTo(s[0], s[1]);
    }
    ctx.stroke();
    return head;
  }

  /* ───────────── keep-outs: where the drawing may not go ───────────── */

  /* el's layout box relative to `stage`, ignoring transforms (so a caption
     that is mid-fade still reserves its resting place) */
  function boxIn(el, stage) {
    let x = 0, y = 0, n = el;
    while (n && n !== stage) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; }
    if (n !== stage) { // stage is not an offsetParent: fall back to rects
      const a = el.getBoundingClientRect(), b = stage.getBoundingClientRect();
      return { x: a.left - b.left, y: a.top - b.top, w: a.width, h: a.height };
    }
    return { x, y, w: el.offsetWidth, h: el.offsetHeight };
  }
  const pad = (r, d) => ({ x: r.x - d, y: r.y - d, w: r.w + 2 * d, h: r.h + 2 * d });
  const hits = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

  /* the largest rectangle of [0,0,W,H] that misses every keep-out:
     cut the free area around each keep-out in turn, keeping the side with
     the best area (thin slivers are penalised) */
  function freeRect(W, H, keeps, margin = 0) {
    let F = { x: 0, y: 0, w: W, h: H };
    const score = (r) => (r.w <= 0 || r.h <= 0 ? -1 : r.w * r.h * Math.pow(Math.min(r.w, r.h) / Math.max(r.w, r.h), 0.35));
    const list = keeps.filter((k) => k.w > 0 && k.h > 0).sort((a, b) => b.w * b.h - a.w * a.h);
    for (const k of list) {
      if (!hits(F, k)) continue;
      const cands = [
        { x: F.x, y: F.y, w: k.x - F.x, h: F.h },                          // left of it
        { x: k.x + k.w, y: F.y, w: F.x + F.w - (k.x + k.w), h: F.h },      // right of it
        { x: F.x, y: F.y, w: F.w, h: k.y - F.y },                          // above it
        { x: F.x, y: k.y + k.h, w: F.w, h: F.y + F.h - (k.y + k.h) },      // below it
      ];
      F = cands.reduce((best, c) => (score(c) > score(best) ? c : best), cands[0]);
    }
    return { x: F.x + margin, y: F.y + margin, w: Math.max(0, F.w - 2 * margin), h: Math.max(0, F.h - 2 * margin) };
  }

  /* true when a circle at (x, y, r) touches a keep-out */
  const blocked = (keeps, x, y, r = 0) => keeps.some((k) => x + r > k.x && x - r < k.x + k.w && y + r > k.y && y - r < k.y + k.h);

  /* ─────────────────────── scrub ─────────────────────── */

  /* p for one element.
     mode "pin":  el is a tall track whose child (opts.stage, or a 100vh
                  viewport) is position: sticky; p = 0 when the track's top
                  reaches the viewport top, 1 when its bottom does.
     mode "view": p = how far el has travelled through the viewport.
     onFrame(p) runs only while p changes; then the loop stops. */
  function progressOf(el, mode, stage) {
    const r = el.getBoundingClientRect();
    const vh = window.innerHeight || 1;
    if (mode === "pin") {
      const span = el.offsetHeight - (stage ? stage.offsetHeight : vh);
      return span > 4 ? clamp01(-r.top / span) : clamp01(-r.top / vh);
    }
    return clamp01((vh - r.top) / (vh + r.height));
  }

  function scrub(el, onFrame, opts = {}) {
    const { mode = "pin", smooth = 0.18, stage = null, rootMargin = "25% 0px" } = opts;
    const reduce = opts.reduce != null ? opts.reduce : prefersReduced();
    let target = 0, cur = -1, raf = 0, on = false, dead = false;
    const measure = () => { target = progressOf(el, mode, stage); };
    function tick() {
      raf = 0;
      if (!on || dead) return;
      measure();
      const d = target - cur;
      cur = cur < 0 || reduce || Math.abs(d) < 0.0005 ? target : cur + d * smooth;
      onFrame(cur);
      if (cur !== target) raf = requestAnimationFrame(tick);
    }
    const kick = () => { if (on && !raf && !dead) raf = requestAnimationFrame(tick); };
    const io = new IntersectionObserver((es) => {
      const vis = es[es.length - 1].isIntersecting;
      if (vis && !on) { on = true; kick(); }
      else if (!vis && on) { on = false; if (raf) cancelAnimationFrame(raf); raf = 0; }
    }, { rootMargin });
    io.observe(el);
    addEventListener("scroll", kick, { passive: true });
    addEventListener("resize", kick);
    measure(); cur = target; onFrame(cur);
    return {
      kick,
      get p() { return cur; },
      stop() {
        dead = true; on = false; if (raf) cancelAnimationFrame(raf); raf = 0;
        io.disconnect();
        removeEventListener("scroll", kick);
        removeEventListener("resize", kick);
      },
    };
  }

  /* seek: scroll the page so a pinned track sits at progress p. Seeking is
     always done by scrolling, so the scroll position stays the one truth. */
  function scrollToProgress(el, p, opts = {}) {
    const stage = opts.stage || null;
    const top = el.getBoundingClientRect().top + window.scrollY;
    const run = el.offsetHeight - (stage ? stage.offsetHeight : window.innerHeight);
    const smooth = opts.smooth != null ? opts.smooth : !prefersReduced();
    window.scrollTo({ top: Math.round(top + run * clamp01(p)) + (opts.nudge || 0), behavior: smooth ? "smooth" : "instant" });
    // "instant", not "auto": auto obeys a page's CSS scroll-behavior: smooth
  }

  /* ─────────────────────── film ─────────────────────── */

  /* A pinned canvas film. Each reel owns an equal slice of p.
       reels:    [{ name, draw(ctx, t, env) }]   t ∈ [0,1] local progress
       captions: [element | null]              one per reel (DOM, data-keep)
     env = { W, H, mobile, colors, keep, free, alpha, p, index, reduce }
     A reel must be a pure function of (t, env): no state, no clock. */
  function film(opts) {
    const { track, stage, canvas, reels, captions = [], smooth = 0.14, dprMax = 2, onChange } = opts;
    const cross = opts.cross != null ? opts.cross : 0.12; // reel crossfade half-width, in reel units
    const capFade = opts.capFade != null ? opts.capFade : 0.1; // caption fade length, in reel units
    const keepPad = opts.keepPad != null ? opts.keepPad : 14;
    const ctx = canvas.getContext("2d");
    const n = reels.length;
    const reduce = opts.reduce != null ? opts.reduce : prefersReduced();
    const fixedKeeps = Array.from(stage.querySelectorAll("[data-keep]")).filter((el) => !captions.includes(el));
    const bar = stage.querySelector("[data-sm-bar]");
    const count = stage.querySelector("[data-sm-count]");
    let W = 0, H = 0, dpr = 1, colors = readPalette(stage), active = -1, painted = -1;
    let lastKeeps = [];

    function layout() {
      const r = stage.getBoundingClientRect();
      W = r.width; H = r.height;
      dpr = Math.min(window.devicePixelRatio || 1, dprMax);
      canvas.width = Math.max(1, Math.round(W * dpr));
      canvas.height = Math.max(1, Math.round(H * dpr));
      canvas.style.width = W + "px"; canvas.style.height = H + "px";
      colors = readPalette(stage);
      painted = -1;
    }

    /* the timeline, all pure functions of p */
    const local = (p, i) => p * n - i; // unclamped reel units: 0..1 is reel i's own slice
    function reelAlpha(p, i) {
      const u = local(p, i);
      const fin = i === 0 ? 1 : smoothstep((u + cross) / (2 * cross));
      const fout = i === n - 1 ? 1 : smoothstep((1 + cross - u) / (2 * cross));
      return Math.min(fin, fout);
    }
    /* captions sit inside their reel and leave a gap of 2*cross between
       neighbours, so two captions are never on screen at once */
    function capAlpha(p, i) {
      const u = local(p, i);
      const fin = i === 0 ? 1 : seg(u, cross, cross + capFade);
      const fout = i === n - 1 ? 1 : 1 - seg(u, 1 - cross - capFade, 1 - cross);
      return Math.min(fin, fout);
    }

    function paint(p) {
      // 1. writes: captions and HUD, all derived from p
      const caps = [];
      for (let i = 0; i < n; i++) {
        const el = captions[i];
        if (!el) continue;
        const a = capAlpha(p, i);
        caps[i] = a;
        el.style.opacity = a.toFixed(3);
        el.style.transform = reduce ? "none" : `translate3d(0, ${((1 - a) * 14).toFixed(1)}px, 0)`;
        el.style.visibility = a > 0.001 ? "visible" : "hidden";
      }
      if (bar) bar.style.transform = `scaleX(${p.toFixed(4)})`;
      const now = Math.min(n - 1, Math.floor(p * n));
      if (now !== active) {
        active = now;
        if (count) count.textContent = String(now + 1).padStart(2, "0") + " / " + String(n).padStart(2, "0");
        if (onChange) onChange(now, reels[now]);
      }

      // 2. reads: measure every keep-out this frame (one layout, if any)
      const fixed = fixedKeeps.filter((el) => el.offsetParent).map((el) => pad(boxIn(el, stage), keepPad));
      const own = captions.map((el) => (el && el.offsetParent ? pad(boxIn(el, stage), keepPad) : null));
      const visibleCaps = own.filter((r, i) => r && caps[i] > 0.001);
      lastKeeps = fixed.concat(visibleCaps);

      // 3. draw: clear, clip out every visible keep-out, then the reels
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, W, H);
      for (const k of lastKeeps) ctx.rect(k.x, k.y, k.w, k.h);
      ctx.clip("evenodd"); // safety net: nothing can paint under a caption
      const mobile = W < 760;
      for (let i = 0; i < n; i++) {
        const alpha = reelAlpha(p, i);
        if (alpha <= 0.001) continue;
        const keep = fixed.concat(own[i] ? [own[i]] : [], visibleCaps);
        const env = {
          W, H, dpr, mobile, colors, keep, reduce, alpha, p, index: i,
          free: freeRect(W, H, keep, mobile ? 12 : 28),
        };
        ctx.save();
        ctx.globalAlpha = alpha;
        reels[i].draw(ctx, clamp01(local(p, i)), env);
        ctx.restore();
      }
      ctx.restore();
    }

    let target = 0, cur = 0, raf = 0, on = false;
    const measure = () => { target = progressOf(track, "pin", stage); };
    function tick() {
      raf = 0;
      if (!on) return;
      measure();
      const d = target - cur;
      cur = reduce || Math.abs(d) < 0.0005 ? target : cur + d * smooth;
      if (cur !== painted) { painted = cur; paint(cur); raf = requestAnimationFrame(tick); }
    }
    const kick = () => { if (on && !raf) raf = requestAnimationFrame(tick); };
    const io = new IntersectionObserver((es) => {
      const vis = es[es.length - 1].isIntersecting;
      if (vis && !on) { on = true; measure(); cur = target; painted = -1; kick(); }
      else if (!vis && on) { on = false; if (raf) cancelAnimationFrame(raf); raf = 0; }
    }, { rootMargin: "40% 0px" });
    io.observe(track);
    const ro = new ResizeObserver(() => { layout(); paint(cur); painted = cur; });
    ro.observe(stage);
    const mq = typeof matchMedia === "function" ? matchMedia("(prefers-color-scheme: dark)") : null;
    const retheme = () => { colors = readPalette(stage); paint(cur); };
    if (mq && mq.addEventListener) mq.addEventListener("change", retheme);
    addEventListener("scroll", kick, { passive: true });
    addEventListener("resize", kick);

    layout(); measure(); cur = target; paint(cur); painted = cur;

    return {
      get p() { return cur; },
      get keeps() { return lastKeeps.slice(); },
      /* paint an arbitrary p without scrolling (tests, posters) */
      renderAt(p) { paint(clamp01(p)); painted = -1; },
      seek(p) { scrollToProgress(track, p, { stage }); },
      seekReel(i, at = 0.5) { scrollToProgress(track, (clamp(i, 0, n - 1) + at) / n, { stage }); },
      retheme,
      destroy() {
        on = false; if (raf) cancelAnimationFrame(raf);
        io.disconnect(); ro.disconnect();
        if (mq && mq.removeEventListener) mq.removeEventListener("change", retheme);
        removeEventListener("scroll", kick);
        removeEventListener("resize", kick);
      },
    };
  }

  /* ─────────────────────── drum ─────────────────────── */

  /* An interactive story drum. Markup (see demo.html / scroll-motion.css):
       .sd (tall track)  > .sd-stage (sticky)
         [data-sd-cap] × n      captions, one per chapter
         .sd-viewport > .sd-ring > a.sd-face × n   faces are links
         [data-sd-go="i"]       rail buttons      [data-sd-prev] [data-sd-next]
         [data-sd-bar]          rail progress     [data-sd-count]
     Rotation is a pure function of scroll. Every control seeks by
     scrolling the page, so the scroll and the drum never disagree. */
  function drum(root, opts = {}) {
    const stage = root.querySelector(".sd-stage") || null;
    const vp = root.querySelector(".sd-viewport");
    const ring = root.querySelector(".sd-ring");
    const faces = Array.from(root.querySelectorAll(".sd-face"));
    const caps = Array.from(root.querySelectorAll("[data-sd-cap]"));
    const rail = Array.from(root.querySelectorAll("[data-sd-go]"));
    const prev = root.querySelector("[data-sd-prev]");
    const next = root.querySelector("[data-sd-next]");
    const bar = root.querySelector("[data-sd-bar]");
    const count = root.querySelector("[data-sd-count]");
    const n = faces.length, step = 360 / n;
    const reduce = opts.reduce != null ? opts.reduce : prefersReduced();
    let idx = -1;

    faces.forEach((f, i) => { f.style.transform = `rotateX(${-i * step}deg) translateZ(var(--r))`; f.draggable = false; });

    function show(i) {
      if (i === idx) return;
      idx = i;
      faces.forEach((f, k) => {
        const on = k === i;
        f.classList.toggle("on", on);
        f.tabIndex = on ? 0 : -1;               // only the face you see is in the tab order
        f.setAttribute("aria-hidden", on ? "false" : "true");
      });
      caps.forEach((c, k) => { c.hidden = k !== i; });
      rail.forEach((b, k) => {
        const li = b.closest("li") || b;
        li.classList.toggle("on", k === i);
        li.classList.toggle("done", k < i);
        if (k === i) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
      });
      if (prev) prev.disabled = i === 0;
      if (next) next.disabled = i === n - 1;
      if (count) count.textContent = String(i + 1).padStart(2, "0") + " / " + String(n).padStart(2, "0");
      if (opts.onChange) opts.onChange(i);
    }

    const s = scrub(root, (p) => {
      const f = clamp01(p) * (n - 1);
      const base = Math.floor(f), t = f - base;
      // dwell: a smoothstep inside every step parks the drum on a face, then rolls
      const turn = reduce ? Math.round(f) : base + t * t * (3 - 2 * t);
      ring.style.transform = `translateZ(calc(var(--r) * -1)) rotateX(${(turn * step).toFixed(3)}deg)`;
      show(Math.min(n - 1, Math.round(f)));
      if (bar) bar.style.transform = `scaleY(${clamp01(p).toFixed(4)})`;
    }, { stage, smooth: opts.smooth || 0.18, reduce });

    const go = (i) => scrollToProgress(root, clamp(i, 0, n - 1) / (n - 1), { stage, nudge: 1 });

    const onRail = (e) => { const b = e.target.closest("[data-sd-go]"); if (b) go(+b.dataset.sdGo); };
    const onPrev = () => go(idx - 1), onNext = () => go(idx + 1);
    const onKey = (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowRight") { e.preventDefault(); go(idx + 1); }
      else if (e.key === "ArrowUp" || e.key === "ArrowLeft") { e.preventDefault(); go(idx - 1); }
      else if (e.key === "Home") { e.preventDefault(); go(0); }
      else if (e.key === "End") { e.preventDefault(); go(n - 1); }
    };
    root.addEventListener("click", onRail);
    if (prev) prev.addEventListener("click", onPrev);
    if (next) next.addEventListener("click", onNext);
    vp.addEventListener("keydown", onKey);

    /* drag with a mouse or pen: a vertical drag scrolls the page (touch
       already scrolls natively, so it is left alone) */
    let drag = null;
    const swallow = (ev) => { ev.preventDefault(); ev.stopPropagation(); };
    const down = (e) => {
      if (e.button !== 0 || e.pointerType === "touch") return;
      drag = { y: e.clientY, s: window.scrollY, moved: false };
    };
    const move = (e) => {
      if (!drag) return;
      const dy = e.clientY - drag.y;
      if (Math.abs(dy) > 4) { drag.moved = true; vp.classList.add("dragging"); }
      // instant: with CSS scroll-behavior: smooth every move would start a new smooth scroll
      if (drag.moved) window.scrollTo({ top: drag.s - dy * (opts.dragGain || 3.2), behavior: "instant" });
    };
    const up = () => {
      const d = drag; drag = null;
      vp.classList.remove("dragging");
      if (d && d.moved) {
        // let go on the face nearest the scroll position now (not the last
        // painted one, which can be a frame behind)
        go(Math.round(progressOf(root, "pin", stage) * (n - 1)));
        vp.addEventListener("click", swallow, { capture: true, once: true }); // the click that ends a drag is not a click
        setTimeout(() => vp.removeEventListener("click", swallow, { capture: true }), 50);
      }
    };
    vp.addEventListener("pointerdown", down);
    addEventListener("pointermove", move, { passive: true });
    addEventListener("pointerup", up);

    return {
      go,
      get index() { return idx; },
      destroy() {
        s.stop();
        root.removeEventListener("click", onRail);
        if (prev) prev.removeEventListener("click", onPrev);
        if (next) next.removeEventListener("click", onNext);
        vp.removeEventListener("keydown", onKey);
        vp.removeEventListener("pointerdown", down);
        removeEventListener("pointermove", move);
        removeEventListener("pointerup", up);
      },
    };
  }

  return {
    version: "1.0.0",
    // math
    clamp, clamp01, lerp, seg, smoothstep, ease, stagger, hash, prefersReduced,
    // colour
    parseColor, rgba, mix, readPalette,
    // geometry + layout
    route, strokeTo, boxIn, pad, hits, freeRect, blocked,
    // engines
    progressOf, scrub, scrollToProgress, film, drum,
  };
});
