/* Studio / neon / geometric scenes: coinflip, orbit, neonline, glowshape,
   tunnel, ringbloom.

   coinflip   kinetic studio: radial #F4F4F4 -> #D9D9D9, title words slide in
              with a motion-blur trail, 3D coins (rotateY, perspective 1000px,
              shadow ellipse) land one by one with labels on an arc
   orbit      a ring of glowing spheres orbiting a centre word / icon
   neonline   #111 + 24px grid: a glowing line draws segment by segment, glow
              icons pop at each vertex, an electric arc trails the draw head
   glowshape  a glowing #F5F5F5 sphere on a starfield that morphs into a box
   tunnel     ~25 nested squares (x0.86, +6deg per layer) with an expo-out zoom-through
   ringbloom  N circles blooming round a ring, staggered 30 ms, round a centre value */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const H = L.H;
  const { el, seg, eo, ei, clamp, C } = L;
  const B_ = (c, v, d) => (v != null ? v : d) * c.beat;

  /* a centred title block at the top of the safe area */
  function titleBlock(parent, c, p, o = {}) {
    const u = c.u;
    const tb = el("div", "abs", parent);
    L.pos(tb, c.safe.x, c.safe.y + (o.top || 0), c.safe.w);
    tb.style.cssText += `;display:flex;flex-direction:column;align-items:center;text-align:center;gap:${16 * u}px`;
    const out = { tb };
    if (p.kicker) { out.k = el("div", "fv-step", tb, L.esc(p.kicker)); out.k.style.cssText += `;font-size:${30 * u}px;color:${o.dark ? "#bbb" : "#555"}`; }
    if (p.title) {
      out.h = L.slideWords(tb, p.title, o.dark ? "fv-neon" : "fv-label", { dist: 420 * u });
      const px = (p.size || (c.P ? (o.hero ? 170 : 112) : 116)) * u;
      out.h.node.style.lineHeight = "0.98";
      if (o.hero) L.fitHero(out.h.node, { w: c.safe.w, lines: o.lines || 2, max: px, min: px * 0.4 });
      else L.fit(out.h.node, px, px * 0.4, c.safe.w, px * (o.lines || 2) * 1.02);
      if (o.dark) out.h.spans.forEach((s) => (s.style.textShadow = `0 0 8px ${L.hexA(o.glow || "#ffffff", 0.7)}, 0 0 26px ${L.hexA(o.glow || "#ffffff", 0.35)}`));
    }
    if (p.sub) {
      out.sub = L.subWords(tb, p.sub, "fv-tag");
      out.sub.node.style.cssText += `;white-space:normal;font-size:${(c.P ? 42 : 38) * u}px;line-height:1.2;color:${o.dark ? "#d8d8d8" : "#333"};font-weight:700;max-width:${c.safe.w}px`;
    }
    out.at = (t, t0, fps) => {
      if (out.k) L.enter(out.k, t, Math.max(0, t0 - 0.2), 0.4, "fade");
      if (out.h) out.h.at(t, t0);
      if (out.sub) out.sub.at(t, t0 + 0.45, fps);
    };
    out.height = () => tb.offsetHeight;
    return out;
  }
  const titleCues = (c, t0) => (c.p.title ? [L.cue(t0 - L.SWISH_LEAD, "swish", 2)] : []).concat(c.p.sub ? [L.cue(t0 + 0.45, "tick", 1)] : []);

  /* neonline vertex times: each node lands on its own label word when the narration says it */
  function neonTimes(c) {
    const p = c.p, sp = p.points || p.steps || [1, 2, 3, 4], n = sp.length;
    const segd = p.seg || 0.6, t0 = B_(c, p.at, 1.5);
    const T = sp.map((s, i) => (i === 0 ? t0 : t0 + 0.2 + (i - 1) * (segd + 0.08) + segd));
    if (!c.styled || p.sync === false) return T;
    const said = sp.map((s) => (s && s.label ? L.wordTime(c, s.label) : null));
    if (said.filter((v) => v != null).length < 2) return T;
    const out = said.slice();
    for (let i = 0; i < n; i++) if (out[i] == null) {
      let a = i - 1; while (a >= 0 && out[a] == null) a--;
      let b = i + 1; while (b < n && out[b] == null) b++;
      const A = a >= 0 ? out[a] : null, Bb = b < n ? out[b] : null;
      out[i] = A != null && Bb != null ? A + ((Bb - A) * (i - a)) / (b - a) : A != null ? A + (segd + 0.08) * (i - a) : Bb - (segd + 0.08) * (b - i);
    }
    for (let i = 0; i < n; i++) { out[i] = Math.max(i ? out[i - 1] + 0.25 : 0.1, out[i]); }
    /* the closing pull-back needs the whole diagram up for at least 0.8 s */
    const lim = c.dur - 1.2;
    if (c.P && p.follow !== false && out[n - 1] > lim) { out[n - 1] = lim; for (let i = n - 2; i >= 0; i--) out[i] = Math.min(out[i], out[i + 1] - 0.25); }
    return out;
  }

  /* a 3D coin: edge discs + front face (icon/image/text) + back face (accent) */
  function coin(parent, size, it, c) {
    const rig = el("div", "abs", parent);
    rig.style.width = rig.style.height = size + "px";
    rig.style.perspective = "1000px";
    const k = el("div", "fv-coin", rig);
    k.style.width = k.style.height = size + "px";
    const th = size * 0.09;
    for (let i = 0; i < 7; i++) {
      const d = el("i", "", k);
      d.style.background = `linear-gradient(90deg, #6f6f6f, #b9b9b9 45%, #8a8a8a)`;
      d.style.transform = `translateZ(${(-th / 2 + (th * i) / 6).toFixed(2)}px)`;
    }
    const f = el("i", "cf", k);
    f.style.background = it.face || "radial-gradient(circle at 34% 26%, #4a4a4a 0%, #1d1d1d 42%, #0b0b0b 100%)";
    f.style.boxShadow = `inset 0 0 0 ${size * 0.035}px #d9d9d9, inset 0 0 0 ${size * 0.05}px ${C.accent}, inset 0 0 0 ${size * 0.062}px rgba(0,0,0,.6), inset ${size * 0.03}px ${size * 0.05}px ${size * 0.1}px rgba(255,255,255,.18)`;
    f.style.transform = `translateZ(${th / 2}px)`;
    if (it.src) { const img = el("img", "", f); img.style.cssText = `width:${size * 0.58}px;height:${size * 0.58}px;object-fit:contain`; L.setImg(img, L.projUrl(it.src)); }
    else if (it.icon && L.ICONS[it.icon]) f.innerHTML = `<span style="display:grid;filter:drop-shadow(0 0 ${size * 0.04}px rgba(255,255,255,.5))">${L.icon(it.icon, size * 0.46, it.color || "#fff", 2.1)}</span>`;
    else { const tx = el("div", "fv-label", f, L.esc(it.text || it.icon || "")); tx.style.fontSize = size * (String(it.text || "").length > 3 ? 0.24 : 0.36) + "px"; tx.style.color = it.color || "#fff"; }
    const b = el("i", "cb", k);
    b.style.background = `radial-gradient(circle at 34% 28%, ${L.hexA(C.accent, 1)} 0%, ${C.accent} 50%, #000 140%)`;
    b.style.transform = `rotateY(180deg) translateZ(${th / 2}px)`;
    b.innerHTML = `<b style="font:900 ${size * 0.3}px var(--display);color:#fff;letter-spacing:-.04em">${L.esc(((c.brand && c.brand.name) || "•").slice(0, 1))}</b>`;
    const sh = el("div", "abs", parent);
    sh.style.cssText += `;width:${size * 0.9}px;height:${size * 0.16}px;border-radius:50%;background:radial-gradient(ellipse at 50% 50%, rgba(0,0,0,.42) 0%, rgba(0,0,0,.18) 50%, transparent 72%)`;
    return { rig, k, sh, size };
  }

  /* ================================================================ coinflip
     params: title, sub, kicker, items: [{icon | src | text, label}], at (beat of the first coin, 2),
             gap (beats between coins, 1), subject (cut-out image rising from the bottom), bg (studio|dark), arc (0..1 sag) */
  S.coinflip = {
    cam: "studio",
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      const dark = p.bg === "dark";
      st.bg = dark ? L.darkBg(root, c) : L.studioBg(root, c);
      L.layer(st.bg.node || st.bg, -800);
      const cam = (st.cam = el("div", "abs", root));
      L.pos(cam, 0, 0, c.W, c.H);
      st.T = titleBlock(root, c, p, { dark });
      L.layer(st.T.tb, 200);
      const items = p.items || [];
      const n = Math.max(1, items.length);
      const size = Math.min((c.safe.w * 0.96) / (n + 0.35), 290 * u, c.safe.h * 0.28);
      const top = c.safe.y + st.T.height() + 40 * u;
      const bottom = c.safe.y + c.safe.h - (p.subject ? c.safe.h * 0.3 : 0);
      const midY = top + (bottom - top) * 0.5;
      const sag = (p.arc != null ? p.arc : 0.35) * size * 1.4;
      if (p.subject) {
        st.subj = el("div", "fv-cut", cam);
        const sw = c.safe.w * 0.62, sh = c.safe.h * 0.42;
        L.pos(st.subj, c.W / 2 - sw / 2, c.safe.y + c.safe.h - sh + 20 * u, sw, sh);
        const img = el("img", "", st.subj);
        L.setImgFx(img, L.projUrl(p.subject), p.halftone ? { bw: true, halftone: true } : null);
        st.subj.style.filter = L.cutFilter({ outline: 0, shadow: { x: 0, y: 24 * u, blur: 30 * u, a: 0.35 } });
        L.layer(st.subj, -140);
      }
      st.coins = items.map((it, i) => {
        const fx = n === 1 ? 0 : (i / (n - 1)) * 2 - 1;
        const x = c.W / 2 + fx * (c.safe.w / 2 - size * 0.62);
        const y = midY - sag * (1 - fx * fx) + sag * 0.5;
        const k = coin(cam, size, it, c);
        L.pos(k.rig, x - size / 2, y - size / 2);
        L.pos(k.sh, x - size * 0.45, y + size * 0.52);
        let lab = null;
        if (it.label) {
          lab = el("div", "fv-tag", cam, L.md(it.label));
          lab.style.cssText += `;position:absolute;font-size:${(c.P ? 34 : 30) * u}px;color:${dark ? "#fff" : "#111"};text-align:center`;
          const lw = lab.offsetWidth;
          L.pos(lab, clamp(x - lw / 2, c.safe.x, c.safe.x + c.safe.w - lw), y + size * 0.7);
          lab.dataset.rot = (fx * 9).toFixed(2);
        }
        if (lab) L.layer(lab, 110);
        return { ...k, lab, x, y, at: B_(c, p.at, 2) + i * B_(c, p.gap, 1) };
      });
      L.layer(cam, 0);
      return st;
    },
    update(st, t, c) {
      if (st.bg.at) st.bg.at(t);
      st.T.at(t, 0.25, c.fps);
      if (st.subj) { const q = L.expo(seg(t, 0.1, 0.9)); st.subj.style.transform = `translateY(${((1 - q) * c.H * 0.35).toFixed(1)}px)`; st.subj.style.opacity = clamp(q * 3); }
      st.coins.forEach((k) => {
        const p = seg(t, k.at, k.at + 1.0);
        const ang = (1 - L.expo(p)) * 1080;
        const drop = (1 - L.back(seg(t, k.at, k.at + 0.6), 1.3)) * -320 * c.u;
        const sc = 0.55 + 0.45 * L.expo(p);
        k.k.style.transform = `translateY(${drop.toFixed(1)}px) rotateY(${ang.toFixed(2)}deg) scale(${sc.toFixed(4)})`;
        k.rig.style.opacity = t >= k.at ? clamp((t - k.at) * 10) : 0;
        const cs = Math.abs(Math.cos((ang * Math.PI) / 180));
        k.sh.style.opacity = t >= k.at ? clamp(0.35 + 0.65 * L.expo(p)) : 0;
        k.sh.style.transform = `scaleX(${(0.35 + 0.65 * Math.max(cs, L.expo(p))).toFixed(3)}) scale(${(0.6 + 0.4 * eo(seg(t, k.at, k.at + 0.6))).toFixed(3)})`;
        if (k.lab) { const q = eo(seg(t, k.at + 0.55, k.at + 0.75)); k.lab.style.opacity = q; k.lab.style.transform = `rotate(${k.lab.dataset.rot}deg) scale(${(0.8 + 0.2 * q).toFixed(3)})`; k.lab.style.filter = q < 1 ? `blur(${((1 - q) * 4).toFixed(2)}px)` : ""; }
      });
      H.outAll([st.cam, st.T.tb], t, c, 0.25);
    },
    cues(c) {
      const p = c.p, out = titleCues(c, 0.25);
      if (p.subject) out.push(L.cue(0.1, "whoosh", 2));
      (p.items || []).forEach((_, i) => {
        const at = B_(c, p.at, 2) + i * B_(c, p.gap, 1);
        out.push(L.cue(at - L.SWISH_LEAD, "swish", 1), L.cue(at + 0.55, "coin", 2));
      });
      return out;
    },
  };

  /* ================================================================ orbit
     params: title, sub, kicker, center: {text | icon | src}, n (spheres, 7), items: [{label}],
             radius (0..1 of the safe width, .4), tilt (.32), speed (turns/s, .07), bg (dark|studio) */
  S.orbit = {
    cam: "studio",
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      const dark = p.bg !== "studio";
      st.dark = dark;
      st.bg = dark ? L.darkBg(root, c) : L.studioBg(root, c);
      L.layer(st.bg.node || st.bg, -800);
      st.T = titleBlock(root, c, p, { dark });
      L.layer(st.T.tb, 200);
      const top = c.safe.y + st.T.height();
      st.cx = c.W / 2; st.cy = top + (c.safe.y + c.safe.h - top) * 0.52;
      st.R = Math.min(c.safe.w * (p.radius || 0.42), (c.safe.y + c.safe.h - top) * 0.9);
      st.tilt = p.tilt != null ? p.tilt : 0.32;
      const ring = L.svg("svg", { width: c.W, height: c.H }, root);
      ring.style.cssText = "position:absolute;left:0;top:0;overflow:visible";
      st.ring = L.svg("ellipse", { cx: st.cx, cy: st.cy, rx: st.R, ry: st.R * st.tilt, fill: "none", stroke: dark ? "rgba(255,255,255,.35)" : "rgba(0,0,0,.25)", "stroke-width": 2 * u, pathLength: 1, "stroke-dasharray": "1 1", filter: dark ? "url(#fv-bloom-s)" : "" }, ring);
      st.core = el("div", "abs", root);
      const cs = 220 * u;
      L.pos(st.core, st.cx - cs / 2, st.cy - cs / 2, cs, cs);
      st.core.style.cssText += `;border-radius:50%;display:grid;place-items:center;z-index:50;background:${dark ? "radial-gradient(circle at 36% 30%, #ffffff, #f5f5f5 35%, #bdbdbd 80%, #8a8a8a)" : "radial-gradient(circle at 36% 30%, #2a2a2a, #111 70%)"};box-shadow:${dark ? "0 0 60px 12px rgba(255,255,255,.28), 0 0 140px 40px rgba(255,255,255,.12)" : "0 30px 50px -20px rgba(0,0,0,.5)"}`;
      const ce = p.center || {};
      if (ce.icon && L.ICONS[ce.icon]) st.core.innerHTML = L.icon(ce.icon, cs * 0.46, dark ? "#111" : "#fff", 2.2);
      else if (ce.src) { const img = el("img", "", st.core); img.style.cssText = `width:${cs * 0.6}px;height:${cs * 0.6}px;object-fit:contain`; L.setImg(img, L.projUrl(ce.src)); }
      else { const tx = el("div", "fv-label", st.core, L.esc(ce.text || "")); tx.style.color = dark ? "#111" : "#fff"; L.fit(tx, 70 * u, 20 * u, cs * 0.8, cs * 0.6); }
      const items = p.items || [];
      const n = Math.max(items.length, p.n || 7);
      st.balls = Array.from({ length: n }, (_, i) => {
        const b = el("div", "fv-ball", root);
        const s = (p.ball || (c.P ? 84 : 64)) * u;
        b.style.width = b.style.height = s + "px";
        b.style.background = dark ? "radial-gradient(circle at 34% 30%, #fff 0%, #f0f0f0 30%, #9a9a9a 85%)" : "radial-gradient(circle at 34% 30%, #fff 0%, #ececec 40%, #a8a8a8 100%)";
        b.style.boxShadow = dark ? `0 0 ${24 * u}px ${6 * u}px rgba(255,255,255,.35)` : `0 ${18 * u}px ${26 * u}px -${8 * u}px rgba(0,0,0,.45)`;
        let lab = null;
        if (items[i] && items[i].label) { lab = el("div", "fv-tag", root, L.md(items[i].label)); lab.style.cssText += `;position:absolute;font-size:${(c.P ? 38 : 30) * u}px;color:${dark ? "#fff" : "#111"};${dark ? "text-shadow:0 0 10px rgba(255,255,255,.5)" : ""}`; }
        return { b, s, lab, a0: (i / n) * Math.PI * 2 };
      });
      return st;
    },
    update(st, t, c) {
      const p = c.p, u = c.u;
      if (st.bg.at) st.bg.at(t);
      st.T.at(t, 0.2, c.fps);
      const t0 = 0.5;
      st.ring.setAttribute("stroke-dashoffset", (1 - eo(seg(t, t0, t0 + 0.9))).toFixed(4));
      const cq = L.back(seg(t, t0 - 0.1, t0 + 0.5), 1.6);
      st.core.style.transform = `scale(${cq.toFixed(4)})`;
      st.core.style.opacity = clamp(cq * 2);
      const spin = t * (p.speed || 0.07) * Math.PI * 2 + L.expo(seg(t, t0, t0 + 1.4)) * 1.2;
      st.balls.forEach((q, i) => {
        const a = q.a0 + spin;
        const x = st.cx + Math.cos(a) * st.R, y = st.cy + Math.sin(a) * st.R * st.tilt;
        const depth = (Math.sin(a) + 1) / 2;
        const born = t0 + 0.3 + i * 0.12;
        const sc = L.pop3(seg(t, born, born + 0.2)) * (0.72 + 0.38 * depth);
        q.b.style.left = x - q.s / 2 + "px"; q.b.style.top = y - q.s / 2 + "px";
        q.b.style.transform = `scale(${sc.toFixed(4)})`;
        q.b.style.zIndex = depth > 0.5 ? 60 : 10;
        q.b.style.opacity = t >= born ? 0.55 + 0.45 * depth : 0;
        if (q.lab) {
          const w = q.lab.offsetWidth;
          const lx = clamp(x - w / 2, c.safe.x, c.safe.x + c.safe.w - w), ly = y + q.s * 0.6 * sc + 6 * u;
          q.lab.style.left = lx + "px"; q.lab.style.top = Math.min(ly, c.safe.y + c.safe.h - q.lab.offsetHeight) + "px";
          q.lab.style.opacity = t >= born + 0.15 ? clamp((t - born - 0.15) * 5) * (0.45 + 0.55 * depth) : 0;
          q.lab.style.zIndex = depth > 0.5 ? 61 : 11;
        }
      });
      H.outAll([...st.balls.map((q) => q.b), st.core], t, c, 0.25);
    },
    cues(c) {
      const n = Math.max((c.p.items || []).length, c.p.n || 7);
      return [...titleCues(c, 0.2), L.cue(0.4, "pop", 2), L.cue(0.5, "swell", 2), ...Array.from({ length: n }, (_, i) => L.cue(0.8 + i * 0.12, "pop", 1)), L.cue(1.9, "chime", 3)];
    },
  };

  /* ================================================================ neonline
     params: title, sub, kicker, steps: [{label, icon}] (auto zigzag rising left to right)
             or points: [{x, y, label, icon}] (0..1 of the chart box, y = 0 bottom),
             kind (zigzag|path), seg (s per segment, .6), at (beat of the first segment, 1.5),
             color (line, #fff), glow (icon ring, accent), zap (true), baseline (true) */
  S.neonline = {
    cam: "neon",
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      st.bg = L.darkBg(root, c, { seed: 21 });
      L.layer(st.bg.node, -800);
      const glow = (st.glow = p.glow || C.accent);
      st.T = titleBlock(root, c, { size: 136, ...p }, { dark: true, glow, hero: c.P });
      L.layer(st.T.tb, 200);
      /* vertices + labels: in portrait the chart spans the safe width and every pixel of height below the title */
      const r = (p.node || (c.P ? 92 : 58)) * u, lfs = Math.max(c.P ? 58 : 40, p.label_size || 0) * u;
      const top = c.safe.y + st.T.height();
      const bx = c.P ? c.safe.x + r + 4 * u : c.safe.x + 60 * u, bw = c.P ? c.safe.w - 2 * r - 8 * u : c.safe.w - 120 * u;
      const by = c.P ? top + r + lfs * 1.25 : top + 100 * u;
      const bh = c.P ? Math.max(120 * u, c.safe.y + c.safe.h - by - r - lfs * 1.15 - 18 * u) : c.safe.y + c.safe.h - top - 190 * u;
      st.box = { bx, bw, by, bh };
      let pts = p.points;
      if (!pts) {
        const sp = p.steps || [{ label: "A" }, { label: "B" }, { label: "C" }, { label: "D" }];
        const n = sp.length;
        /* a rising zigzag: alternate up / down around an upward trend */
        /* portrait: a tall zigzag, side to side while it climbs, so the chart uses the whole area */
        if (c.P && p.kind !== "path" && n > 1) pts = sp.map((s, i) => ({ ...s, x: i % 2 ? 1 : 0, y: i / (n - 1) }));
        else pts = sp.map((s, i) => ({ ...s, x: n === 1 ? 0.5 : i / (n - 1), y: p.kind === "path" ? 0.5 + 0.35 * Math.sin(i * 1.3) : clamp(0.08 + (0.84 * i) / Math.max(1, n - 1) + (i === 0 || i === n - 1 ? 0 : i % 2 ? 0.24 : -0.24)) }));
      }
      st.P = pts.map((q) => ({ ...q, X: bx + clamp(q.x) * bw, Y: by + (1 - clamp(q.y)) * bh }));
      const svg = (st.svg = L.svg("svg", { width: c.W, height: c.H }, root));
      svg.style.cssText = "position:absolute;left:0;top:0;overflow:visible";
      if (p.baseline !== false && !c.P) st.base = L.svg("line", { x1: bx - 30 * u, y1: by + bh + 40 * u, x2: bx + bw + 30 * u, y2: by + bh + 40 * u, stroke: "rgba(255,255,255,.22)", "stroke-width": 2 * u, "stroke-dasharray": `${6 * u} ${8 * u}` }, svg);
      /* the path to come, faint from the first frame, so the chart area is never empty */
      if (c.P && p.follow !== false) {
        L.svg("polyline", { points: st.P.map((q) => `${q.X.toFixed(1)},${q.Y.toFixed(1)}`).join(" "), fill: "none", stroke: "rgba(255,255,255,.3)", "stroke-width": 3 * u, "stroke-dasharray": `${5 * u} ${12 * u}`, "stroke-linecap": "round" }, svg);
        st.P.forEach((q) => L.svg("circle", { cx: q.X, cy: q.Y, r: (p.node || 92) * u * 0.7, fill: "none", stroke: "rgba(255,255,255,.14)", "stroke-width": 2.5 * u }, svg));
      }
      const lineG = L.svg("g", { filter: "url(#fv-bloom)" }, svg);
      /* follow (tall default): one dot rides the whole path, the camera goes with it */
      st.fol = c.P && p.follow !== false;
      const segd = st.fol ? 1.6 : p.seg || 0.6, T = neonTimes(c);
      st.T_ = T;
      st.segs = [];
      for (let i = 0; i < st.P.length - 1; i++) {
        const A = st.P[i], Bp = st.P[i + 1], dd = Math.min(segd, Math.max(0.15, T[i + 1] - T[i] - 0.03));
        const e = L.svg("path", { d: `M${A.X.toFixed(1)} ${A.Y.toFixed(1)} L${Bp.X.toFixed(1)} ${Bp.Y.toFixed(1)}`, stroke: p.color || "#fff", "stroke-width": 7 * u, "stroke-linecap": "round", fill: "none", pathLength: 1, "stroke-dasharray": "1 1", "stroke-dashoffset": 1 }, lineG);
        st.segs.push({ e, A, B: Bp, a: T[i + 1] - dd, d: dd });
      }
      st.zap = L.svg("path", { d: "", stroke: "#fff", "stroke-width": 2.6 * u, fill: "none", "stroke-linejoin": "round", filter: "url(#fv-zap)", opacity: 0 }, svg);
      st.head = L.svg("circle", { r: 9 * u, fill: "#fff", filter: "url(#fv-bloom)", opacity: 0 }, svg);
      /* vertex icons + labels */
      /* a soft accent haze behind the chart */
      const hz = el("div", "abs", root);
      L.pos(hz, bx - bw * 0.2, by - bh * 0.2, bw * 1.4, bh * 1.4);
      hz.style.background = `radial-gradient(ellipse at 50% 50%, ${L.hexA(glow, 0.16)} 0%, ${L.hexA(glow, 0.05)} 40%, transparent 70%)`;
      L.layer(hz, -380);
      st.nodes = st.P.map((q, i) => {
        const g = L.svg("g", { filter: "url(#fv-bloom-s)" }, svg);
        L.svg("circle", { cx: 0, cy: 0, r, fill: "#141414", stroke: glow, "stroke-width": 4 * u }, g);
        if (q.icon && L.ICONS[q.icon]) {
          const ic = L.svg("g", { transform: `translate(${-r * 0.55} ${-r * 0.55}) scale(${(r * 1.1) / 24})` }, g);
          L.svg("path", { d: L.ICONS[q.icon], fill: "none", stroke: "#fff", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" }, ic);
        } else L.svg("circle", { cx: 0, cy: 0, r: r * 0.28, fill: "#fff" }, g);
        let lab = null;
        if (q.label) {
          lab = el("div", "fv-neon", root, L.md(q.label));
          lab.style.cssText += `;position:absolute;white-space:nowrap;font-size:${lfs}px;letter-spacing:-0.01em;font-weight:900`;
          lab.dataset.lb = "1";
          L.neon(lab, glow);
          const w = lab.offsetWidth, h = lab.offsetHeight;
          const nxt = st.P[i + 1], prv = st.P[i - 1];
          /* keep the label off the line: below when the line climbs away from this vertex */
          let below = q.side ? q.side === "below" : nxt ? nxt.Y < q.Y : !!(prv && prv.Y < q.Y);
          /* flip off a neighbouring vertex that sits right under (or over) the label */
          const blocked = (dn) => st.P.some((o) => o !== q && Math.abs(o.X - q.X) < r + w / 2 && (dn ? o.Y > q.Y && o.Y - q.Y < 2 * r + h + 30 * u : o.Y < q.Y && q.Y - o.Y < 2 * r + h + 30 * u));
          if (!q.side && blocked(below) && !blocked(!below)) below = !below;
          const ly = below ? q.Y + r + 12 * u : q.Y - r - 12 * u - h;
          L.pos(lab, clamp(q.X - w / 2, c.safe.x, c.safe.x + c.safe.w - w), clamp(ly, c.safe.y, c.safe.y + c.safe.h - h));
        }
        const at = T[i];
        if (lab) L.layer(lab, 120);
        return { g, q, lab, at };
      });
      L.layer(svg, 0);
      return st;
    },
    update(st, t, c) {
      const u = c.u;
      st.bg.at(t);
      st.T.at(t, 0.2, c.fps);
      if (st.base) st.base.setAttribute("opacity", eo(seg(t, 0.4, 0.9)));
      let head = null, dir = null;
      st.segs.forEach((s) => {
        const q = (st.fol ? L.EASE.camera : eo)(seg(t, s.a, s.a + s.d));
        s.e.setAttribute("stroke-dashoffset", (1 - q).toFixed(4));
        if (q > 0 && q < 1) { head = { x: L.lerp(s.A.X, s.B.X, q), y: L.lerp(s.A.Y, s.B.Y, q) }; dir = { x: s.B.X - s.A.X, y: s.B.Y - s.A.Y }; }
      });
      if (head && c.p.zap !== false) {
        const f = Math.round(t * c.fps), r = L.rng(1000 + f * 13);
        const dl = Math.hypot(dir.x, dir.y) || 1, ux = dir.x / dl, uy = dir.y / dl;
        let d = `M${head.x.toFixed(1)} ${head.y.toFixed(1)}`;
        for (let k = 1; k <= 7; k++) { const back = k * 16 * u, off = (r() - 0.5) * 34 * u; d += ` L${(head.x - ux * back - uy * off).toFixed(1)} ${(head.y - uy * back + ux * off).toFixed(1)}`; }
        let d2 = `M${head.x.toFixed(1)} ${head.y.toFixed(1)}`;
        for (let k = 1; k <= 4; k++) { const fw = k * 10 * u, off = (r() - 0.5) * 40 * u; d2 += ` L${(head.x + ux * fw * 0.4 - uy * off).toFixed(1)} ${(head.y + uy * fw * 0.4 + ux * off).toFixed(1)}`; }
        st.zap.setAttribute("d", d + " " + d2);
        st.zap.setAttribute("opacity", 0.95);
        st.head.setAttribute("cx", head.x.toFixed(1)); st.head.setAttribute("cy", head.y.toFixed(1)); st.head.setAttribute("opacity", 1);
      } else { st.zap.setAttribute("opacity", 0); st.head.setAttribute("opacity", 0); }
      /* the camera follows the draw head (or the last vertex reached) */
      { let tgt = st.P[0]; for (const n of st.nodes) if (t >= n.at) tgt = n.q; st.camHint = head ? { x: head.x, y: head.y } : { x: tgt.X, y: tgt.Y }; }
      /* follow: push towards the active node, then pull back so the whole diagram reads */
      const lastAt = st.nodes[st.nodes.length - 1].at;
      let active = 0;
      st.nodes.forEach((n, i) => { if (t >= n.at) active = i; });
      const back = st.fol ? L.EASE.camera(seg(t, lastAt + 0.05, lastAt + 0.4)) : 1;
      if (st.fol) {
        const pin = L.EASE.camera(seg(t, st.T_[0] - 0.4, st.T_[0] + 0.3));
        st.camZ = 110 * u * pin * (1 - back);
        st.camFollow = 0.3 * pin * (1 - back);
      }
      /* once drawn, a pulse keeps running the loop and each vertex answers it */
      const loopT = c.p.pulse === false || !c.lively ? -1 : t - lastAt - 0.45;
      const N = st.P.length - 1;
      let px = -1;
      if (loopT > 0 && N > 0) {
        px = ((loopT / (N * 0.42)) % 1) * N;
        const i = Math.min(N - 1, Math.floor(px)), q = L.EASE.camera(px - i);
        const A = st.P[i], Bp = st.P[i + 1];
        st.head.setAttribute("cx", L.lerp(A.X, Bp.X, q).toFixed(1)); st.head.setAttribute("cy", L.lerp(A.Y, Bp.Y, q).toFixed(1)); st.head.setAttribute("opacity", 1);
      }
      st.nodes.forEach((n, i) => {
        let s = L.spring(t - n.at, L.SPRING.playful);
        if (px >= 0) { const near = Math.abs(px - i); s *= 1 + 0.12 * Math.max(0, 1 - near * 2.4); }
        n.g.setAttribute("transform", `translate(${n.q.X.toFixed(1)} ${n.q.Y.toFixed(1)}) scale(${s.toFixed(4)})`);
        /* passed nodes dim to ink until the pull-back brings them all up */
        const dim = st.fol && i < active ? (1 - back) * 0.5 : 0;
        n.g.setAttribute("opacity", t >= n.at ? (1 - dim).toFixed(3) : 0);
        if (n.lab) { const q = eo(seg(t, n.at + 0.08, n.at + 0.3)); n.lab.style.opacity = q; n.lab.style.transform = `translateY(${((1 - q) * 14 * u).toFixed(1)}px) scale(${(0.85 + 0.15 * q).toFixed(3)})`; n.lab.style.filter = q < 1 ? `blur(${((1 - q) * 6).toFixed(2)}px)` : ""; if (st.fol && q >= 1 && i < active) n.lab.style.opacity = (1 - (1 - back) * 0.5).toFixed(3); }
      });
      H.outAll([st.svg, ...st.nodes.map((n) => n.lab)], t, c, 0.25);
    },
    cues(c) {
      const p = c.p, out = titleCues(c, 0.2);
      const n = (p.points || p.steps || [1, 2, 3, 4]).length;
      const segd = p.seg || 0.6, T = neonTimes(c);
      out.push(L.cue(T[0], "pop", 2));
      for (let i = 0; i < n - 1; i++) {
        const a = T[i + 1] - Math.min(c.P && p.follow !== false ? 1.6 : segd, Math.max(0.15, T[i + 1] - T[i] - 0.03));
        out.push(L.cue(a, "zap", 2, { len: segd }), L.cue(a + segd, i === n - 2 ? "chime" : "pop", i === n - 2 ? 3 : 1));
      }
      return out;
    },
  };

  /* ================================================================ glowshape
     params: title, sub, kicker, label, morph (box|none), morph_at (beat, 3), stars (true), size (px at u=1, 300) */
  S.glowshape = {
    cam: "glow",
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      const bg = el("div", "abs", root); L.pos(bg, 0, 0, c.W, c.H);
      bg.style.background = "radial-gradient(ellipse 80% 60% at 50% 50%, #101014 0%, #060608 60%, #020203 100%)";
      L.layer(bg, -800);
      if (p.stars !== false) { st.stars = L.stars(root, c, 150, 9); L.layer(st.stars.node, -500); }
      st.T = titleBlock(root, c, p, { dark: true });
      L.layer(st.T.tb, 200);
      const top = c.safe.y + st.T.height();
      st.cx = c.W / 2; st.cy = top + (c.safe.y + c.safe.h - top) * 0.48;
      const s = (st.s = Math.min((p.size || 300) * u, (c.safe.y + c.safe.h - top) * 0.6));
      st.halo = el("div", "abs", root);
      L.pos(st.halo, st.cx - s * 1.3, st.cy - s * 1.3, s * 2.6, s * 2.6);
      st.halo.style.background = "radial-gradient(circle, rgba(245,245,245,.32) 0%, rgba(245,245,245,.1) 35%, transparent 62%)";
      st.sh = el("div", "abs", root);
      L.pos(st.sh, st.cx - s * 0.6, st.cy + s * 0.62, s * 1.2, s * 0.22);
      st.sh.style.cssText += ";border-radius:50%;background:radial-gradient(ellipse, rgba(255,255,255,.18), transparent 70%)";
      st.o = el("div", "abs", root);
      L.pos(st.o, st.cx - s / 2, st.cy - s / 2, s, s);
      st.o.style.background = "radial-gradient(circle at 36% 30%, #ffffff 0%, #F5F5F5 28%, #c9c9c9 68%, #7d7d7d 100%)";
      st.o.style.boxShadow = `0 0 ${50 * u}px ${12 * u}px rgba(245,245,245,.35), 0 0 ${140 * u}px ${30 * u}px rgba(245,245,245,.12), inset -${18 * u}px -${22 * u}px ${40 * u}px rgba(0,0,0,.25)`;
      if (p.label) {
        st.lab = el("div", "fv-neon", root, L.md(p.label));
        st.lab.style.cssText += `;position:absolute;text-align:center;font-size:${54 * u}px;white-space:nowrap`;
        L.neon(st.lab, C.accent);
        const w = st.lab.offsetWidth;
        L.pos(st.lab, clamp(st.cx - w / 2, c.safe.x, c.safe.x + c.safe.w - w), Math.min(st.cy + s * 0.85, c.safe.y + c.safe.h - st.lab.offsetHeight));
        L.layer(st.lab, 130);
      }
      L.layer(st.halo, -60);
      return st;
    },
    update(st, t, c) {
      const p = c.p;
      if (st.stars) st.stars.at(t, t * 0.03);
      st.T.at(t, 0.2, c.fps);
      const q = L.back(seg(t, 0.3, 1.0), 1.5);
      const m = p.morph === "none" ? 0 : L.eio(seg(t, B_(c, p.morph_at, 3), B_(c, p.morph_at, 3) + 0.7));
      const bob = Math.sin(t * 1.6) * 10 * c.u * (1 - m * 0.6);
      const squash = 1 + Math.sin(m * Math.PI) * 0.08;
      st.o.style.borderRadius = `${(50 - 36 * m).toFixed(2)}%`;
      st.o.style.transform = `translateY(${bob.toFixed(2)}px) rotate(${(m * 45 + Math.sin(t * 0.8) * 3 * m).toFixed(2)}deg) scale(${(q * squash).toFixed(4)}, ${(q / squash).toFixed(4)})`;
      st.o.style.filter = q < 1 ? `blur(${((1 - clamp(q)) * 12).toFixed(2)}px)` : "";
      st.o.style.opacity = clamp(q * 2);
      st.halo.style.opacity = clamp(q) * (0.85 + 0.15 * Math.sin(t * 2.1));
      st.sh.style.opacity = clamp(q);
      if (st.lab) L.resolveIn(st.lab, t, B_(c, p.morph_at, 3) + 0.5, 0.45, { from: 0.85, blur: 8 });
      H.outAll([st.o, st.halo, st.lab], t, c, 0.25);
    },
    cues(c) {
      const p = c.p, out = [...titleCues(c, 0.2), L.cue(0.3, "swell", 2), L.cue(0.6, "pop", 1)];
      if (p.morph !== "none") out.push(L.cue(B_(c, p.morph_at, 3) - L.SWISH_LEAD, "swish", 1), L.cue(B_(c, p.morph_at, 3) + 0.6, "thump", 2));
      if (p.label) out.push(L.cue(B_(c, p.morph_at, 3) + 0.5, "pop", 1));
      return out;
    },
  };

  /* ================================================================ tunnel
     params: title, sub, kicker, layers (25), shrink (.86), twist (deg per layer, 6), fly (layers flown through, 7),
             zoom (s, 1.8), color (#fff), accent_every (5), reveal (s, title reveal, 1.5) */
  S.tunnel = {
    cam: "glow",
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      const bg = el("div", "abs", root); L.pos(bg, 0, 0, c.W, c.H);
      bg.style.background = "radial-gradient(ellipse at 50% 50%, #0d0d10 0%, #040405 70%)";
      L.layer(bg, -800);
      st.stars = L.stars(root, c, 110, 13);
      L.layer(st.stars.node, -500);
      const svg = (st.svg = L.svg("svg", { width: c.W, height: c.H }, root));
      svg.style.cssText = "position:absolute;left:0;top:0";
      st.g = L.svg("g", { filter: "url(#fv-bloom-s)" }, svg);
      st.cx = c.W / 2; st.cy = c.safe.y + c.safe.h * 0.5;
      st.S0 = Math.min(c.W, c.H) * 0.95;
      const n = p.layers || 25, every = p.accent_every || 5;
      st.rects = Array.from({ length: n + 8 }, (_, i) => L.svg("rect", { fill: "none", stroke: i % every === 0 ? C.accent : p.color || "#fff", "stroke-linejoin": "round" }, st.g));
      st.core = el("div", "abs", root);
      const cr = Math.min(c.W, c.H) * 0.62;
      L.pos(st.core, st.cx - cr, st.cy - cr, cr * 2, cr * 2);
      st.core.style.background = "radial-gradient(circle, rgba(0,0,0,.92) 0%, rgba(0,0,0,.75) 38%, transparent 68%)";
      const box = el("div", "safe", root);
      L.pos(box, c.safe.x, c.safe.y, c.safe.w, c.safe.h);
      box.style.alignItems = "center"; box.style.justifyContent = "center"; box.style.textAlign = "center"; box.style.gap = 18 * u + "px";
      if (p.kicker) { st.k = el("div", "fv-step", box, L.esc(p.kicker)); st.k.style.cssText += `;font-size:${30 * u}px;color:#ddd`; }
      if (p.title) { st.t = el("div", "fv-neon", box, L.md(p.title)); st.t.style.lineHeight = "0.95"; st.t.style.maxWidth = c.safe.w * 0.9 + "px"; L.fit(st.t, (p.size || 130) * u, 40 * u, c.safe.w * 0.9, c.safe.h * 0.42); st.t.style.textShadow = `0 0 10px rgba(255,255,255,.6), 0 0 34px ${L.hexA(C.accent, 0.55)}`; }
      if (p.sub) { st.sub = L.subWords(box, p.sub, "fv-tag"); st.sub.node.style.cssText += `;white-space:normal;color:#e6e6e6;font-size:${40 * u}px;max-width:${c.safe.w * 0.62}px;line-height:1.2`; }
      L.layer(st.core, 120); L.layer(box, 160);
      return st;
    },
    update(st, t, c) {
      const p = c.p, u = c.u;
      const n = p.layers || 25, k0 = p.shrink || 0.86, tw = p.twist != null ? p.twist : 6;
      const fly = (p.fly != null ? p.fly : 7) * L.expo(seg(t, 0, p.zoom || 1.8)) + t * 0.35;
      st.stars.at(t, fly * 0.04);
      const base = Math.floor(fly);
      st.rects.forEach((r, j) => {
        const i = base + j - 1;
        const e = i - fly;
        if (e < -1.2 || e > n) { r.setAttribute("opacity", 0); return; }
        const s = st.S0 * Math.pow(k0, e);
        const a = clamp((n - e) / 5) * clamp((e + 1.2) / 1.2);
        r.setAttribute("x", (st.cx - s / 2).toFixed(1)); r.setAttribute("y", (st.cy - s / 2).toFixed(1));
        r.setAttribute("width", s.toFixed(1)); r.setAttribute("height", s.toFixed(1));
        r.setAttribute("rx", (s * 0.04).toFixed(1));
        r.setAttribute("stroke-width", Math.max(0.8, 5 * Math.pow(k0, e)) * u);
        r.setAttribute("stroke", ((i % (p.accent_every || 5)) + (p.accent_every || 5)) % (p.accent_every || 5) === 0 ? C.accent : p.color || "#fff");
        r.setAttribute("transform", `rotate(${(e * tw + t * 4).toFixed(2)} ${st.cx} ${st.cy})`);
        r.setAttribute("opacity", a.toFixed(3));
      });
      const rv = p.reveal != null ? p.reveal : 1.5;
      st.core.style.opacity = eo(seg(t, rv - 0.4, rv + 0.4));
      if (st.k) L.enter(st.k, t, rv - 0.2, 0.4, "fade");
      if (st.t) L.resolveIn(st.t, t, rv, 0.6, { from: 0.7, blur: 16, expo: true });
      if (st.sub) st.sub.at(t, rv + 0.5, c.fps);
    },
    cues(c) {
      const rv = c.p.reveal != null ? c.p.reveal : 1.5;
      return [L.cue(-L.SWISH_LEAD, "whoosh", 2), L.cue(rv, "riser", 2, { len: Math.min(1.2, rv) }), L.cue(rv, "boom", 3), ...(c.p.sub ? [L.cue(rv + 0.5, "tick", 1)] : [])];
    },
  };

  /* ================================================================ ringbloom
     params: title, sub, kicker, value (the centre word / number), label, n (14), radius (.36), stagger (s, .03), at (beat, 1) */
  S.ringbloom = {
    cam: "neon",
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      st.bg = L.darkBg(root, c, { seed: 33, dust: 40 });
      L.layer(st.bg.node, -800);
      st.T = titleBlock(root, c, p, { dark: true });
      L.layer(st.T.tb, 200);
      const top = c.safe.y + st.T.height();
      st.cx = c.W / 2; st.cy = top + (c.safe.y + c.safe.h - top) * 0.5;
      st.R = Math.min(c.safe.w * (p.radius || 0.36), (c.safe.y + c.safe.h - top) * 0.42);
      const svg = (st.svg = L.svg("svg", { width: c.W, height: c.H }, root));
      svg.style.cssText = "position:absolute;left:0;top:0;overflow:visible";
      const g = L.svg("g", { filter: "url(#fv-bloom)" }, svg);
      st.wave = L.svg("circle", { cx: st.cx, cy: st.cy, r: st.R, fill: "none", stroke: C.accent, "stroke-width": 3 * u, opacity: 0 }, g);
      st.ring = L.svg("circle", { cx: st.cx, cy: st.cy, r: st.R, fill: "none", stroke: "rgba(255,255,255,.4)", "stroke-width": 2 * u, pathLength: 1, "stroke-dasharray": "1 1", "stroke-dashoffset": 1, transform: `rotate(-90 ${st.cx} ${st.cy})` }, g);
      const n = p.n || 14;
      st.dots = Array.from({ length: n }, (_, i) => {
        const a = -Math.PI / 2 + (i / n) * Math.PI * 2;
        return L.svg("circle", { cx: (st.cx + Math.cos(a) * st.R).toFixed(1), cy: (st.cy + Math.sin(a) * st.R).toFixed(1), r: (p.dot || 18) * u, fill: i % 4 === 0 ? C.accent : "#fff" }, g);
      });
      const box = el("div", "abs", root);
      const bw = st.R * 1.5;
      L.pos(box, st.cx - bw / 2, st.cy - st.R * 0.7, bw, st.R * 1.4);
      box.style.cssText += `;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:${8 * u}px`;
      st.v = el("div", "fv-neon", box, L.md(String(p.value != null ? p.value : "")));
      L.fit(st.v, 180 * u, 40 * u, bw, st.R * 0.9);
      L.neon(st.v, C.accent);
      if (p.label) { st.lab = el("div", "fv-tag", box, L.md(p.label)); st.lab.style.cssText += `;white-space:normal;color:#ddd;font-size:${34 * u}px;max-width:${bw}px`; }
      L.layer(box, 110);
      return st;
    },
    update(st, t, c) {
      const p = c.p, at = B_(c, p.at, 1), sg = p.stagger || 0.03;
      st.bg.at(t);
      st.T.at(t, 0.2, c.fps);
      st.ring.setAttribute("stroke-dashoffset", (1 - eo(seg(t, at, at + 0.6))).toFixed(4));
      st.dots.forEach((d, i) => { const b = at + i * sg; const s = L.pop3(seg(t, b, b + 0.2)); d.setAttribute("opacity", t >= b ? 1 : 0); d.setAttribute("transform", `translate(${d.getAttribute("cx")} ${d.getAttribute("cy")}) scale(${s.toFixed(4)}) translate(${-d.getAttribute("cx")} ${-d.getAttribute("cy")})`); });
      const done = at + st.dots.length * sg + 0.1;
      const w = seg(t, done, done + 0.8);
      st.wave.setAttribute("r", (st.R * (1 + 0.5 * eo(w))).toFixed(1));
      st.wave.setAttribute("opacity", w > 0 && w < 1 ? (1 - w).toFixed(3) : 0);
      L.resolveIn(st.v, t, done, 0.5, { from: 0.7, blur: 10 });
      if (st.lab) L.enter(st.lab, t, done + 0.3, 0.4, "fade");
      H.outAll([st.svg, st.v, st.lab], t, c, 0.25);
    },
    cues(c) {
      const p = c.p, at = B_(c, p.at, 1), n = p.n || 14, done = at + n * (p.stagger || 0.03) + 0.1;
      return [...titleCues(c, 0.2), L.cue(at, "swell", 2), L.cue(at, "tick", 1), L.cue(done, "chime", 3), L.cue(done, "ripple", 1), ...(p.label ? [L.cue(done + 0.3, "tick", 1)] : [])];
    },
  };
})();
