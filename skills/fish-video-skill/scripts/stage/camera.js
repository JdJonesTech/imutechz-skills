/* The 3D virtual camera rig.

   main.js wraps every scene in  .layer (perspective P)  >  .fv-world  and
   moves the world opposite to the camera, so one physical camera looks at
   every scene. Scenes put elements on depth planes with L.layer(el, z):
   background ~ -800, subject 0, labels / arrows +120..+250. Each plane is
   pre-scaled by (P - z) / P so at the rest pose the layout is exactly what
   the scene laid out (and what the lint checks); any camera move then gives
   real parallax.

   Camera spec (storyboard scene field `camera:`, or params.camera):
     a preset name     static | drift | dolly-in | dolly-out | push-in | orbit-left | orbit-right |
                       crane-up | crane-down | push-through | whip-left | whip-right   ("a+b" sums them)
     a style name      paper | studio | glow | neon | screen  (the scene type's default)
     keyframes         [{t | beat | m, x, y, z, rx, ry, rz, fov, focus_z, ease}]
     an object         {preset, amount, keys, follow}
   camera_from: prev      start from the previous scene's end pose and blend into this one
   camera_shake: 0..1     handheld micro-motion (seeded sum of sines, +-4 px, +-0.3 deg at 1)
   camera_shake_on: impact   a decaying kick on impact / boom / thump / hit cues
   focus_z (in keys)      depth of field: layered planes blur by |z - focus_z|

   Everything is a pure function of (scene, t). */
(function () {
  "use strict";
  const L = window.L;
  const { clamp, seg } = L;
  const R = (L.rig = {});

  R.P = (c) => Math.round(1100 * c.u);
  R.persp = (c, fov) => (fov ? c.H / 2 / Math.tan((fov * Math.PI) / 360) : R.P(c));
  const EASE = {
    power2: L.EASE.camera, "power4-out": L.EASE.arrive2, linear: (x) => clamp(x), "expo-out": L.expo, expo: L.expo, cubic: L.eio, "in-out": L.eio, "cubic-in-out": L.eio,
    "cubic-in": L.ei, "cubic-out": L.eo, "back-out": (x) => L.back(x, 1.4), portal: (x) => L.portal(x),
  };
  const AX = ["x", "y", "z", "rx", "ry", "rz"];
  /* the subtle default of the older scene types once a video has a style (legacy briefs stay static) */
  R.STYLED = { title: "drift+push-in", kinetic: "drift+push-in", bullets: "drift+dolly-in", stat: "drift+push-in", chart: "drift+dolly-in", diagram: "drift+dolly-in", whiteboard: "drift+dolly-in", end: "drift", quote: "drift+push-in", compare: "drift+dolly-in", steps: "drift+dolly-in", terminal: "drift", image: "drift+dolly-in", stepcard: "drift" };
  const STYLE = { paper: "drift+dolly-in", studio: "push-in", glow: "push-through", neon: "crane-up+follow", screen: "static" };
  const TAU = Math.PI * 2;

  /* camera moves ease power2.inOut */
  const MOVE = L.EASE.camera;
  /* presets: (t, dur, amount, c) -> partial pose */
  const PRESETS = {
    static: () => ({}),
    drift: (t, d, a) => ({ x: 14 * a * Math.sin((TAU * t) / 7.3), y: 8 * a * Math.sin((TAU * t) / 5.1 + 1), rz: 0.35 * a * Math.sin((TAU * t) / 9.4 + 0.5) }),
    "dolly-in": (t, d, a) => ({ z: 110 * a * MOVE(t / d) }),
    "dolly-out": (t, d, a) => ({ z: 140 * a * (1 - MOVE(t / d)) }),
    "push-in": (t, d, a, c) => ({ z: R.P(c) * (1 - 1 / (1 + 0.08 * a)) * MOVE(t / d), y: 5 * a * Math.sin((TAU * t) / 3.4) }),
    "orbit-left": (t, d, a) => ({ ry: 7 * a - 14 * a * MOVE(t / d), x: -40 * a + 80 * a * MOVE(t / d) }),
    "orbit-right": (t, d, a) => ({ ry: -7 * a + 14 * a * MOVE(t / d), x: 40 * a - 80 * a * MOVE(t / d) }),
    "crane-up": (t, d, a) => ({ y: 50 * a - 100 * a * MOVE(t / d), rx: -2.5 * a + 5 * a * MOVE(t / d) }),
    "crane-down": (t, d, a) => ({ y: -50 * a + 100 * a * MOVE(t / d), rx: 2.5 * a - 5 * a * MOVE(t / d) }),
    /* a slow push, then the camera flies through the subject in the last 0.45 s */
    "push-through": (t, d, a, c) => ({ z: R.P(c) * (0.05 * a * L.eio(t / Math.max(0.1, d - 0.45)) + 0.82 * L.ei(seg(t, d - 0.45, d))) }),
    "whip-left": (t, d, a) => ({ x: 700 * a * (1 - L.expo(seg(t, 0, 0.3))), ry: -6 * a * (1 - L.expo(seg(t, 0, 0.3))) }),
    "whip-right": (t, d, a) => ({ x: -700 * a * (1 - L.expo(seg(t, 0, 0.3))), ry: 6 * a * (1 - L.expo(seg(t, 0, 0.3))) }),
  };
  R.PRESETS = Object.keys(PRESETS);

  const keyTime = (k, c) => {
    if (k.t != null) return +k.t;
    if (k.beat != null) return k.beat * c.beat;
    if (k.at === "end") return c.dur;
    if (k.m != null && c.p.shot && L.META[c.p.shot]) {
      const from = c.p.from, f0 = typeof from === "string" ? L.mark$(c.p.shot, from) : from || 0;
      return (L.mark$(c.p.shot, k.m) + (k.d || 0) - f0) / (L.FPS * (c.p.speed || 1));
    }
    return 0;
  };
  /* keyframes: values carry forward; the ease of a key shapes the segment arriving at it */
  function keyed(keys, t, c) {
    const ks = keys.map((k) => ({ k, t: keyTime(k, c) })).sort((a, b) => a.t - b.t);
    const full = [];
    let prev = { x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0, fov: null, focus_z: null };
    for (const { k, t: kt } of ks) { const v = { ...prev }; for (const a of [...AX, "fov", "focus_z"]) if (k[a] != null) v[a] = +k[a]; full.push({ t: kt, v, ease: EASE[k.ease] || L.eio }); prev = v; }
    if (!full.length) return {};
    if (t <= full[0].t) return { ...full[0].v };
    for (let i = 0; i < full.length - 1; i++) {
      const A = full[i], B = full[i + 1];
      if (t <= B.t) {
        const q = B.ease(seg(t, A.t, B.t)), o = {};
        for (const a of AX) o[a] = L.lerp(A.v[a], B.v[a], q);
        for (const a of ["fov", "focus_z"]) o[a] = A.v[a] == null ? B.v[a] : B.v[a] == null ? A.v[a] : L.lerp(A.v[a], B.v[a], q);
        return o;
      }
    }
    return { ...full[full.length - 1].v };
  }

  /* the normalised spec of a scene: {presets:[names], amount, keys, follow} */
  R.spec = (c) => {
    if (c._camSpec) return c._camSpec;
    let s = c.cam.camera != null ? c.cam.camera : c.defCam || "static";
    let o = {};
    if (Array.isArray(s)) o = { keys: s };
    else if (typeof s === "object") o = { ...s, keys: s.keys };
    else o = { preset: String(s) };
    let names = String(o.preset || (o.keys ? "static" : "static"));
    names = names.split("+").map((n) => n.trim()).flatMap((n) => (STYLE[n] ? STYLE[n].split("+") : [n]));
    o.follow = o.follow != null ? o.follow : names.includes("follow") ? 0.08 : 0;
    o.presets = names.filter((n) => PRESETS[n]);
    o.amount = o.amount != null ? +o.amount : 1;
    return (c._camSpec = o);
  };
  R.active = (c) => { const s = R.spec(c); return !!(s.keys || s.presets.some((n) => n !== "static") || c.cam.camera_shake || c.cam.camera_from); };

  /* the scene's own move, no blend / shake */
  R.local = (c, t) => {
    const s = R.spec(c), o = { x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0, fov: null, focus_z: null };
    for (const n of s.presets) { const q = PRESETS[n](t, c.dur, s.amount, c); for (const a in q) o[a] += q[a]; }
    if (s.keys) { const q = keyed(s.keys, t, c); for (const a of AX) o[a] += q[a] || 0; o.fov = q.fov; o.focus_z = q.focus_z; }
    return o;
  };
  /* the full pose: camera_from: prev blend + handheld shake + impact kicks */
  R.pose = (c, t, depth = 0, still = false) => {
    let o = R.local(c, t);
    if (c.cam.camera_from === "prev" && c.prev && depth < 8) {
      const e = R.pose(c.prev, c.prev.dur - 1e-4, depth + 1, true);
      const bd = c.cam.camera_blend != null ? +c.cam.camera_blend : 0.9;
      const q = MOVE(seg(t, 0, bd));
      const m = {};
      for (const a of AX) m[a] = L.lerp(e[a], o[a], q);
      m.fov = o.fov != null ? o.fov : e.fov; m.focus_z = o.focus_z != null ? o.focus_z : q < 1 ? e.focus_z : null;
      o = m;
    }
    if (still) return o;
    /* a new visual event at least every 1.2 s: spring micro-pushes on the spoken phrases, alternating so they stay bounded */
    if (c.lively) {
      const ev = R.events(c), K = 24 * c.u;
      for (let i = 0; i < ev.length; i++) {
        if (ev[i] > t) break;
        const s = (i % 2 ? -1 : 1) * L.spring(t - ev[i], KICK_SPRING);
        o.z += K * s; o.x += 4 * c.u * s; o.rz += 0.12 * s;
      }
    }
    const A = +c.cam.camera_shake || 0;
    if (A > 0) {
      const r = L.rng(L.hash(c.id || "cam") || 7), w = Array.from({ length: 9 }, () => [0.4 + r() * 1.4, r() * TAU]);
      const n = (i) => (Math.sin(t * w[i][0] * TAU + w[i][1]) + 0.6 * Math.sin(t * w[i + 1][0] * TAU * 2.3 + w[i + 1][1]) + 0.3 * Math.sin(t * w[i + 2][0] * TAU * 4.1 + w[i + 2][1])) / 1.9;
      o.x += 4 * A * n(0); o.y += 4 * A * n(3); o.rz += 0.3 * A * n(6);
    }
    if (String(c.cam.camera_shake_on || "").includes("impact")) {
      for (const k of R.kicks(c)) {
        const d = t - k;
        if (d < 0 || d > 0.6) continue;
        const e = Math.exp(-d * 9);
        o.x += 11 * e * Math.sin(d * 55); o.y += 7 * e * Math.cos(d * 47); o.rz += 0.45 * e * Math.sin(d * 39);
      }
    }
    return o;
  };
  const KICK_SPRING = { stiffness: 150, mass: 1, damping: 18 };
  /* the times of a scene's visual events: phrase starts, gaps filled so none exceeds 1.1 s */
  R.events = (c) => {
    if (c._events) return c._events;
    const out = [];
    let prev = null;
    for (const w of c.words || []) {
      if (prev == null || w.lt - prev.end >= 0.15 || /[.!?…,;:]["”’)]*$/.test(prev.w)) out.push(w.lt);
      prev = { end: w.lt1, w: w.w };
    }
    const ev = [];
    let last = 0.5;
    ev.push(last);
    for (const q of [...out, c.dur]) {
      while (q - last > 1.1) { last += 1.0; ev.push(last); }
      if (q < c.dur - 0.2 && q - last >= 0.35) { ev.push(q); last = q; }
    }
    return (c._events = ev);
  };
  const KICK = new Set(["impact", "boom", "thump", "hit"]);
  R.kicks = (c) => c._kicks || (c._kicks = (c.def && c.def.cues ? c.def.cues(c) : []).filter((q) => KICK.has(q.type)).map((q) => q.lt));

  /* screen-space speed (px per frame) of the camera at t */
  R.speed = (c, t, still = false) => {
    const f = 1 / L.FPS, a = R.pose(c, t - f, 0, still), b = R.pose(c, t, 0, still);
    const P = R.P(c);
    const dx = b.x - a.x, dy = b.y - a.y, dz = ((b.z - a.z) * P) / Math.max(1, P - b.z) * 0.5, dr = (Math.abs(b.rx - a.rx) + Math.abs(b.ry - a.ry)) * 14 + Math.abs(b.rz - a.rz) * 10;
    return { v: Math.hypot(dx, dy) + Math.abs(dz) + dr, lateral: Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > Math.abs(dz) };
  };
  R.THRESH = 9;

  /* cues: fast moves get a whoosh (long) / swish (short) 0.1 s before they start; push-through lands an impact */
  R.cues = (c) => {
    if (!R.active(c)) return [];
    const out = [], step = 1 / 60;
    let run = null;
    for (let t = step; t <= c.dur + 1e-6; t += step) {
      const fast = R.speed(c, t, true).v > R.THRESH;
      if (fast && !run) run = { a: t };
      if (!fast && run) { run.b = t; out.push(run); run = null; }
    }
    if (run) { run.b = c.dur; out.push(run); }
    const cs = out.filter((r) => r.b - r.a > 0.06).map((r) => L.cue(Math.max(-0.12, r.a - 0.1), r.b - r.a > 0.3 ? "whoosh" : "swish", 2, { len: +(r.b - r.a).toFixed(3) }));
    if (R.spec(c).presets.includes("push-through")) cs.push(L.cue(c.dur - 0.04, "impact", 3));
    return cs;
  };

  /* text and its arrows stay sharp at rest: depth of field is for the non-text planes */
  const planeHasText = (pl) => {
    if (pl._hasText != null) return pl._hasText;
    if (pl.dataset.sharp === "1") return (pl._hasText = true);
    const w = document.createTreeWalker(pl, NodeFilter.SHOW_TEXT);
    let n; while ((n = w.nextNode())) if (n.textContent.trim()) return (pl._hasText = true);
    return (pl._hasText = false);
  };
  /* apply a pose: world transform, perspective, depth of field */
  R.apply = (root, world, c, o, rest) => {
    const P = R.persp(c, o.fov);
    root.style.perspective = P.toFixed(1) + "px";
    world.style.transform = rest ? "" : `translate3d(${(-o.x).toFixed(2)}px, ${(-o.y).toFixed(2)}px, ${o.z.toFixed(2)}px) rotateX(${o.rx.toFixed(3)}deg) rotateY(${o.ry.toFixed(3)}deg) rotateZ(${o.rz.toFixed(3)}deg)`;
    if (world._planes) for (const k in world._planes) {
      const pl = world._planes[k], z = +pl.dataset.z;
      const b = o.focus_z == null || (planeHasText(pl) && !c.cam.dof_text) ? 0 : Math.min(c.cam.dof_max != null ? +c.cam.dof_max : 6, Math.abs(z - o.focus_z) * (c.cam.dof != null ? +c.cam.dof : 0.03));
      pl.style.filter = b > 0.15 ? `blur(${b.toFixed(2)}px)` : "";
    }
    return P / Math.max(1, P - o.z);
  };

  /* put an element on a depth plane of its scene's world */
  L.layer = (el, z = 0, o = {}) => {
    const world = el && el.closest ? el.closest(".fv-world") : null;
    if (!world) return el;
    world.style.transformStyle = "preserve-3d";
    const P = +world.dataset.p || 1100;
    const cover = o.cover != null ? o.cover : z <= -300;
    const key = z + (cover ? "c" : "");
    world._planes = world._planes || {};
    let pl = world._planes[key];
    if (!pl) {
      pl = document.createElement("div");
      pl.className = "fv-plane";
      pl.style.cssText = `position:absolute;left:0;top:0;width:${world.style.width};height:${world.style.height};transform-origin:50% 50%`;
      const s = ((P - z) / P) * (cover ? o.overscan || 1.22 : 1);
      pl.style.transform = `translateZ(${z}px) scale(${s.toFixed(5)})`;
      pl.dataset.z = z;
      if (o.sharp) pl.dataset.sharp = "1";
      world.appendChild(pl);
      world._planes[key] = pl;
    }
    pl.appendChild(el);
    return pl;
  };
})();
