/* Typographic scenes: title, kinetic, bullets, quote, stat, compare, steps.
   All layouts are flex boxes inside the platform safe area, so one scene
   definition works at 16:9, 1:1, 4:5 and 9:16. Headlines are fitted to
   their box with L.fit, so nothing can overflow. Entrances land on beats
   (c.beat = 0.5 s at 120 BPM). */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const H = (L.H = L.H || {}); // shared layout helpers (not scenes)
  const { el, seg, eo, ei, back, clamp, C } = L;

  /* a flex column filling the safe area */
  H.box = (root, c, o = {}) => {
    const b = el("div", "safe", root);
    L.pos(b, c.safe.x, c.safe.y, c.safe.w, c.safe.h);
    b.style.justifyContent = o.justify || "center";
    b.style.alignItems = o.align || (c.P ? "flex-start" : "flex-start");
    b.style.gap = (o.gap || 28) * c.u + "px";
    if (o.center) { b.style.alignItems = "center"; b.style.textAlign = "center"; }
    return b;
  };
  /* type scale per aspect: [display, h2, body, small] at u = 1 */
  H.scale = (c) => ({ land: [128, 72, 34, 22], square: [108, 64, 32, 24], port: [104, 62, 32, 24], tall: [100, 60, 36, 28] }[c.mode]);
  H.kicker = (parent, text, c) => { const k = el("div", "eyebrow", parent, L.esc(text)); k.style.fontSize = H.scale(c)[3] * c.u + "px"; return k; };
  /* a headline sized to fit width w and at most `lines` lines */
  H.headline = (parent, text, c, { size, lines = 3, cls = "display", w } = {}) => {
    const h = L.words(parent, text, cls, { stagger: 0.07 });
    const px = (size || H.scale(c)[0]) * c.u;
    h.node.style.lineHeight = "1.04";
    const width = w || c.safe.w;
    h.node.style.maxWidth = width + "px";
    /* tall: headlines fill the width */
    if (c.P) L.fitHero(h.node, { w: width, lines, max: Math.max(px, 118 * c.u), min: 44 * c.u });
    else L.fit(h.node, px, px * 0.45, width, px * 1.08 * lines);
    return h;
  };
  /* one line, fitted to width w */
  H.fitLine = (node, w, max, min) => { node.style.whiteSpace = "nowrap"; node.style.width = w + "px"; return L.fit(node, max, min, w, 1e6); };
  /* the ground of this scene */
  H.dark = (c) => (c.p.bg ? c.p.bg === "dark" : c.texture === "paper" ? false : L.isDark(L.C.bg));
  /* a slow accent glow behind type: it breathes and answers each pulse */
  H.ambient = (root, c) => {
    const g = el("div", "abs", root);
    L.pos(g, 0, 0, c.W, c.H);
    g.dataset.nolint = "";
    g.style.background = `radial-gradient(ellipse 62% 40% at 50% 44%, ${L.hexA(C.accent, H.dark(c) ? 0.2 : 0.13)} 0%, transparent 72%)`;
    L.layer(g, -420);
    return (t, kick = 0) => { g.style.opacity = (0.72 + 0.2 * Math.sin((t * Math.PI * 2) / 3.1) + 0.5 * kick).toFixed(3); };
  };
  /* tall: a flex child that takes all the height left */
  H.fill = (e) => { e.style.flex = "1"; e.style.minHeight = "0"; return e; };
  /* c.holdOut: the scene stays up through its cut (no blank frames before a held transition) */
  H.outAll = (nodes, t, c, d = 0.3) => { if (c.holdOut) return; const o = ei(seg(t, c.dur - d, c.dur)); if (o > 0) nodes.forEach((n) => n && (n.style.opacity = 1 - o)); };

  /* ================================================================ title
     params: kicker, title, subtitle, chips[], logo (bool, default true) */
  S.title = {
    build(root, c) {
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { center: true, gap: 30 }));
      /* a badge needs a logo file or a name the brief really gave (brand.name falls back to the video title) */
      if (p.logo !== false && (p.logo === true || !c.brand || c.brand.logo || c.brand.explicit_name !== false)) { st.logo = L.logo(b, c.brand, 170 * c.u); st.logo.node.style.position = "relative"; }
      if (p.kicker) st.k = H.kicker(b, p.kicker, c);
      if (c.P) st.amb = H.ambient(root, c);
      st.h = H.headline(b, p.title || c.brand.name || "", c, { lines: c.P ? 3 : 2, size: c.P ? 190 : undefined });
      if (p.subtitle) { st.sub = L.words(b, p.subtitle, "serif-it", { stagger: 0.05 }); st.sub.node.style.fontSize = H.scale(c)[1] * 0.78 * c.u + "px"; st.sub.node.style.color = C.ink; st.sub.node.style.maxWidth = c.safe.w * 0.92 + "px"; L.fit(st.sub.node, H.scale(c)[1] * 0.78 * c.u, 24 * c.u, c.safe.w * 0.92, H.scale(c)[1] * 0.78 * c.u * 2.6); }
      if (p.chips && p.chips.length) {
        st.row = el("div", "row", b); st.row.style.justifyContent = "center";
        st.chips = p.chips.map((t, i) => { const e = el("span", "chip" + (i === p.chips.length - 1 ? " ink" : ""), st.row, (i === p.chips.length - 1 ? '<i class="d"></i>' : "") + L.esc(t)); e.style.fontSize = 24 * c.u + "px"; return e; });
      }
      return st;
    },
    update(st, t, c) {
      const B = c.beat;
      if (st.amb) st.amb(t);
      if (st.logo) st.logo.at(t, 0);
      if (st.k) L.enter(st.k, t, B, 0.5);
      st.h.at(t, B * 1);
      if (st.sub) st.sub.at(t, B * 3);
      (st.chips || []).forEach((e, i) => L.enter(e, t, B * (5 + i * 0.5), 0.45, "pop"));
    },
    cues: (c) => [{ lt: 0, type: "swell" }, { lt: c.beat, type: "hit" }, { lt: c.beat * 3, type: "tick" }, ...(c.p.chips || []).map((_, i) => ({ lt: c.beat * (5 + i * 0.5), type: "pop" }))],
  };

  /* ================================================================ kinetic
     Big words that rise in, line by line. params: lines[] (use ~serif~ and
     *accent*), kicker, align (center|left), sub */
  S.kinetic = {
    build(root, c) {
      const p = c.p, st = {};
      const center = p.align !== "left";
      const b = (st.b = H.box(root, c, { center, gap: 6 }));
      if (p.kicker) { st.k = H.kicker(b, p.kicker, c); st.k.style.marginBottom = 18 * c.u + "px"; }
      const lines = (Array.isArray(p.lines) ? p.lines : String(p.lines != null ? p.lines : p.text || "").split("\n")).map(String);
      const px = (p.size || H.scale(c)[0] * 1.2) * c.u;
      /* the poster form: every line fills the width, one accent word, words slam in */
      if (c.P || c.styled) {
        st.slam = true;
        st.amb = H.ambient(root, c);
        /* no accent asked for: the last word carries it (p.accent: false for none) */
        if (p.accent !== false && !lines.some((l) => l.includes("*")) && lines.length) {
          const ws = lines[lines.length - 1].split(/\s+/), k = ws.length - 1;
          ws[k] = "*" + ws[k].replace(/~/g, "") + "*" + (ws[k].includes("~") ? "~" : "");
          lines[lines.length - 1] = ws.join(" ");
        }
        b.style.gap = 14 * c.u + "px";
        const wide = c.safe.w, cap = Math.max(p.size ? p.size * c.u : 0, (c.P ? 300 : 190) * c.u);
        st.lines = lines.map((ln) => {
          const w = L.words(b, ln, /^~/.test(ln) ? "serif-it" : "display", { stagger: 0.09 });
          w.node.style.color = L.inkOn(H.dark(c));
          w.node.style.fontWeight = "800";
          w.node.style.lineHeight = "1.02";
          H.fitLine(w.node, wide, cap, 40 * c.u);
          w.node.dataset.free = ""; /* fitted; a word mid-slam may overshoot for a frame or two */
          w.node.querySelectorAll(".kt-m").forEach((m) => (m.style.overflow = "visible"));
          return w;
        });
        /* very long stacks give way together */
        const room = c.safe.h * (p.sub ? 0.78 : 0.94), sum = st.lines.reduce((a, w) => a + w.node.offsetHeight, 0);
        if (sum > room) st.lines.forEach((w) => { w.node.style.fontSize = Math.floor((parseFloat(w.node.style.fontSize) * room) / sum) + "px"; });
        if (p.sub) { st.sub = el("div", "lede", b, L.md(p.sub)); st.sub.style.cssText += `;margin-top:${28 * c.u}px;font-size:${(c.P ? 66 : 44) * c.u}px;line-height:1.1;font-weight:600;max-width:${c.safe.w}px;color:${L.inkOn(H.dark(c))}`; }
        /* each line lands on its first word if it is spoken */
        let prev = -1;
        st.at = st.lines.map((w, i) => {
          const said = c.styled ? L.wordTime(c, lines[i]) : null;
          const a = Math.max(prev + 0.25, said != null ? said - 0.05 : c.beat * (0.5 + i * 2));
          prev = a + (w.spans.length - 1) * 0.09;
          return a;
        });
        return st;
      }
      st.lines = lines.map((ln) => {
        const w = L.words(b, ln, /^~/.test(ln) ? "serif-it" : "display", { stagger: 0.07 });
        w.node.style.color = C.ink;
        L.fit(w.node, px, px * 0.35, c.safe.w, px * 1.1 * (c.P ? 2 : 1));
        return w;
      });
      if (p.sub) { st.sub = el("div", "lede", b, L.md(p.sub)); st.sub.style.marginTop = 24 * c.u + "px"; st.sub.style.fontSize = H.scale(c)[2] * c.u + "px"; st.sub.style.maxWidth = c.safe.w + "px"; }
      return st;
    },
    update(st, t, c) {
      const B = c.beat;
      if (st.k) L.enter(st.k, t, 0, 0.4);
      if (st.slam) {
        let kick = 0;
        st.lines.forEach((w, i) => w.spans.forEach((s, k) => {
          const a = st.at[i] + k * 0.09, d = t - a;
          const q = L.spring(d, { stiffness: 340, mass: 1, damping: 24 });
          s.style.opacity = d >= 0 ? 1 : 0;
          s.style.transform = `scale(${(1.55 - 0.55 * q).toFixed(4)})`;
          s.style.filter = d >= 0 && d < 0.1 ? `blur(${((1 - d / 0.1) * 6).toFixed(2)}px)` : "";
          if (d > 0 && d < 0.7) kick += Math.exp(-7 * d);
        }));
        /* every word kicks the camera */
        st.camKick = 26 * c.u * L.punch(kick > 0 ? 0.05 + (kick > 1 ? 0.03 : 0) : 0) + 34 * c.u * Math.min(1.2, kick);
        st.amb(t, Math.min(1, kick));
        if (st.sub) L.resolveIn(st.sub, t, st.at[st.at.length - 1] + 0.3, 0.3, { from: 0.94, blur: 6, spring: L.SPRING.premium });
        return;
      }
      st.lines.forEach((w, i) => { w.at(t, B * (0.5 + i * 2)); if (!c.holdOut) w.outAt(t, c.dur - 0.32 - (st.lines.length - 1 - i) * 0.04, 0.3); });
      if (st.sub) L.enter(st.sub, t, B * (1 + st.lines.length * 2), 0.5);
    },
    cues: (c) => [{ lt: 0, type: "rise" }, ...(c.p.lines || [1]).map((_, i) => ({ lt: c.beat * (0.5 + i * 2), type: i ? "pop" : "hit" }))],
  };

  /* ================================================================ bullets
     params: kicker, title, items[] (strings, *accent* allowed), source */
  S.bullets = {
    build(root, c) {
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { gap: 26 }));
      if (p.kicker) st.k = H.kicker(b, p.kicker, c);
      if (p.title) st.h = H.headline(b, p.title, c, { size: H.scale(c)[1], lines: 2 });
      const list = el("div", "", b);
      list.style.display = "flex"; list.style.flexDirection = "column"; list.style.gap = 22 * c.u + "px"; list.style.marginTop = 10 * c.u + "px";
      if (c.P) { b.style.justifyContent = "flex-start"; H.fill(list); list.style.justifyContent = "space-evenly"; list.style.width = "100%"; }
      const fs = c.P ? Math.min(74, 300 / Math.max(3, (p.items || []).length) + 12) * c.u : H.scale(c)[2] * 1.18 * c.u;
      st.items = (p.items || []).map((tx, i) => {
        const nf = Math.max(fs * 0.6, H.scale(c)[3] * c.u), bd = Math.max(fs * 1.05, nf * 1.75);
        const e = el("div", "", list, `<i style="flex:none;width:${bd}px;height:${bd}px;border-radius:50%;background:${i === 0 ? C.accent : C.ink};color:${C.bg};display:grid;place-items:center;font:600 ${nf}px var(--mono);font-style:normal">${i + 1}</i><span>${L.md(tx)}</span>`);
        e.style.cssText += `;display:flex;gap:${20 * c.u}px;align-items:center;font-size:${fs}px;line-height:1.25;font-weight:550;color:${C.fg};max-width:${c.safe.w}px`;
        return e;
      });
      if (p.source) { st.src = el("div", "foot", b, "Source: " + L.esc(p.source)); st.src.style.fontSize = H.scale(c)[3] * c.u + "px"; }
      return st;
    },
    update(st, t, c) {
      const B = c.beat;
      if (st.k) L.enter(st.k, t, 0, 0.4);
      if (st.h) st.h.at(t, B * 0.5);
      /* tall: the items spread over the whole scene */
      const per = c.P ? Math.max(B, (c.dur - B * 2 - 0.8) / Math.max(1, st.items.length)) : Math.max(B, Math.min(B * 4, (c.dur - B * 4) / Math.max(1, st.items.length)));
      st.items.forEach((e, i) => L.enter(e, t, B * 2 + i * per, 0.45, "left", 60));
      if (st.src) L.enter(st.src, t, B * 3, 0.5, "fade");
      H.outAll([st.b], t, c);
    },
    cues: (c) => {
      const n = (c.p.items || []).length, B = c.beat;
      const per = c.P ? Math.max(B, (c.dur - B * 2 - 0.8) / Math.max(1, n)) : Math.max(B, Math.min(B * 4, (c.dur - B * 4) / Math.max(1, n)));
      return [{ lt: 0, type: "tick" }, ...Array.from({ length: n }, (_, i) => ({ lt: B * 2 + i * per, type: "pop" }))];
    },
  };

  /* The hero stat. The number fits the safe width (the block is at least 25% of the frame
     height), counts up on a spring, and sits on a supporting visual, params.visual:
       grid   a pictogram: of 100 for a percentage, or one tile per unit up to 200
       ring   a ring filled to the percentage (or value / of)
       bar    a bar filled to value / of; without `of` it only sweeps (no claim about scale)
       none   no visual; the number and label grow to take the room
     Default: grid for %, a grid for whole numbers up to 200, else bar. */
  function statFmt(p, x) { const s = x.toFixed(p.decimals || 0); return (p.prefix || "") + (p.grouping === false ? s : s.replace(/\B(?=(\d{3})+(?!\d))/g, ",")) + (p.suffix || ""); }
  function statVisual(p) {
    if (p.visual) return p.visual;
    const v = Number(p.value) || 0, pct = /%/.test(p.suffix || "");
    if (pct) return "grid";
    return Number.isInteger(v) && v >= 1 && v <= 200 && !p.of ? "grid" : "bar";
  }
  function tallStat(root, c) {
    const p = c.p, u = c.u, st = { hero: true }, dark = H.dark(c), ink = L.inkOn(dark);
    st.amb = H.ambient(root, c);
    const b = (st.b = H.box(root, c, { center: true, gap: 26, justify: "flex-start" }));
    if (p.kicker) st.k = H.kicker(b, p.kicker, c);
    const nw = el("div", "", b);
    nw.style.cssText += `;width:100%;display:flex;align-items:center;justify-content:center;min-height:${c.P ? c.H * 0.2 : c.H * 0.3}px`;
    st.n = el("div", "display", nw);
    st.n.style.cssText += `;line-height:1;color:${C.accent};font-weight:800;font-variant-numeric:tabular-nums;text-align:center;transform-origin:50% 55%`;
    st.n.textContent = statFmt(p, Number(p.value || 0));
    /* a little under the full width: it pulses */
    H.fitLine(st.n, c.safe.w * 0.93, (c.P ? 430 : 300) * u, 90 * u);
    st.n.dataset.free = "";
    st.n.dataset.lb = "1";
    const kind = (st.kind = statVisual(p));
    const vis = (st.vis = el("div", "abs", b));
    vis.style.cssText = `position:relative;flex:1;width:100%;min-height:0;${kind === "none" ? "flex:0" : ""}`;
    if (p.label) { st.l = el("div", "", b, L.md(p.label)); st.l.style.cssText += `;font-family:var(--display);font-weight:700;letter-spacing:-.02em;font-size:${(c.P ? 62 : 44) * u}px;line-height:1.1;color:${ink};max-width:${c.safe.w}px`; L.fitHero(st.l, { w: c.safe.w, lines: 3, max: (kind === "none" ? 96 : c.P ? 62 : 44) * u, min: 34 * u }); }
    if (p.source) { st.s = el("div", "foot", b, "Source: " + L.esc(p.source)); st.s.style.cssText += `;font-size:${Math.max(24, H.scale(c)[3]) * u}px;max-width:${c.safe.w}px;line-height:1.2`; }
    return st;
  }
  function statBuildVisual(st, c) {
    const p = c.p, u = c.u, W = st.vis.clientWidth, Hh = st.vis.clientHeight, v = Number(p.value) || 0, dark = H.dark(c);
    const off = dark ? "rgba(255,255,255,.13)" : "rgba(0,0,0,.14)";
    st.built = true;
    const pct = /%/.test(p.suffix || "");
    st.frac = p.of ? clamp(v / +p.of) : pct ? clamp(v / 100) : null;
    if (st.kind === "grid") {
      const n = pct || p.of ? 100 : Math.max(1, Math.round(v));
      const on = pct || p.of ? Math.round((st.frac || 0) * 100) : n;
      /* the largest tiles that fit n cells */
      let cols = 1, best = 0;
      for (let k = 1; k <= n; k++) { const rows = Math.ceil(n / k), sz = Math.min(W / k, Hh / rows); if (sz > best) { best = sz; cols = k; } }
      const rows = Math.ceil(n / cols), s = best, g = s * 0.14, x0 = (W - cols * s) / 2, y0 = (Hh - rows * s) / 2;
      st.tiles = Array.from({ length: n }, (_, i) => {
        const e = el("i", "abs", st.vis);
        L.pos(e, x0 + (i % cols) * s + g / 2, y0 + Math.floor(i / cols) * s + g / 2, s - g, s - g);
        e.style.borderRadius = (s - g) * 0.24 + "px";
        e.style.background = i < on ? C.accent : off;
        return { e, on: i < on, i };
      });
      st.nOn = on;
    } else if (st.kind === "ring") {
      const R = Math.min(W, Hh) * 0.44, cx = W / 2, cy = Hh / 2, sw = R * 0.26;
      const svg = L.svg("svg", { width: W, height: Hh }, st.vis);
      svg.style.cssText = "position:absolute;left:0;top:0;overflow:visible";
      L.svg("circle", { cx, cy, r: R, fill: "none", stroke: off, "stroke-width": sw }, svg);
      st.arc = L.svg("circle", { cx, cy, r: R, fill: "none", stroke: C.accent, "stroke-width": sw, "stroke-linecap": "round", pathLength: 1, "stroke-dasharray": "1 1", "stroke-dashoffset": 1, transform: `rotate(-90 ${cx} ${cy})` }, svg);
    } else if (st.kind === "bar") {
      const bh = Math.min(Hh * 0.5, 150 * u), y = (Hh - bh) / 2;
      const tr = el("div", "abs", st.vis); L.pos(tr, 0, y, W, bh); tr.style.background = off; tr.style.borderRadius = bh * 0.22 + "px"; tr.style.overflow = "hidden";
      st.fill = el("div", "abs", tr); L.pos(st.fill, 0, 0, 0, bh); st.fill.style.background = C.accent;
      st.sheen = el("div", "abs", st.fill); L.pos(st.sheen, 0, 0, W * 0.2, bh); st.sheen.style.background = "linear-gradient(90deg, transparent, rgba(255,255,255,.4), transparent)";
      st.vW = W;
    }
  }
  function tallStatAt(st, t, c) {
    const p = c.p, B = c.beat, a0 = B * 0.6;
    if (!st.built) statBuildVisual(st, c);
    if (st.k) L.enter(st.k, t, 0, 0.4);
    /* the count: a damped spring, clamped so a figure is never overstated */
    const q = Math.min(1, L.spring(t - a0, { stiffness: 26, mass: 1, damping: 9.2 }));
    const done = q > 0.998 ? 1 : q;
    st.n.textContent = statFmt(p, Number(p.value || 0) * done);
    const settle = a0 + 1.5;
    /* lands, then beats: a new pulse every 1.1 s */
    let pulse = 0;
    for (let k = settle; k < t; k += 1.1) pulse += L.punch(t - k, 13, 5);
    L.resolveIn(st.n, t, a0 - 0.05, 0.2, { from: 0.72, blur: 8, spring: L.SPRING.playful, post: ` scale(${(1 + 0.05 * pulse).toFixed(4)})` });
    st.amb(t, Math.max(0, pulse));
    if (st.tiles) {
      const lit = st.nOn * done;
      st.tiles.forEach((q2) => {
        const k = q2.on ? seg(lit, q2.i, q2.i + 1) : seg(t, a0, a0 + 0.3);
        /* a soft wave keeps running through the grid */
        const wave = 0.07 * Math.sin(t * 3.2 - q2.i * 0.33);
        q2.e.style.opacity = (q2.on ? (k > 0 ? 1 : 0.14) : k).toFixed(3);
        q2.e.style.transform = `scale(${((q2.on ? 0.55 + 0.45 * L.spring(k * 0.35, L.SPRING.playful) : 0.9) + (k >= 1 ? wave : 0)).toFixed(4)})`;
      });
    }
    if (st.arc) st.arc.setAttribute("stroke-dashoffset", (1 - (st.frac != null ? st.frac : 1) * done).toFixed(4));
    if (st.fill) {
      const f = (st.frac != null ? st.frac : 1) * done;
      st.fill.style.width = (st.vW * f).toFixed(1) + "px";
      st.sheen.style.transform = `translateX(${(((t * 0.55) % 1.3) * st.vW - st.vW * 0.2).toFixed(1)}px)`;
    }
    if (st.l) L.resolveIn(st.l, t, a0 + 0.35, 0.3, { from: 0.94, blur: 6, spring: L.SPRING.premium });
    if (st.s) L.enter(st.s, t, a0 + 1.1, 0.4, "fade");
    H.outAll([st.b], t, c);
  }

  /* ================================================================ stat
     A number that counts up. params: value (number, from a source!), prefix,
     suffix, decimals, label, source, kicker. Never invent the number. */
  S.stat = {
    build(root, c) {
      if (c.P || c.styled) return tallStat(root, c);
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { center: true, gap: 18 }));
      if (p.kicker) st.k = H.kicker(b, p.kicker, c);
      st.n = el("div", "display", b);
      const px = H.scale(c)[0] * 2.1 * c.u;
      st.n.style.fontSize = px + "px"; st.n.style.lineHeight = "1"; st.n.style.color = C.accent; st.n.style.fontVariantNumeric = "tabular-nums";
      st.n.textContent = (p.prefix || "") + Number(p.value || 0).toFixed(p.decimals || 0) + (p.suffix || "");
      L.fit(st.n, px, px * 0.3, c.safe.w, px * 1.1);
      st.n.dataset.free = "";
      if (p.label) { st.l = el("div", "serif", b, L.md(p.label)); st.l.style.fontSize = H.scale(c)[1] * 0.85 * c.u + "px"; st.l.style.color = C.ink; st.l.style.maxWidth = c.safe.w + "px"; st.l.style.lineHeight = "1.1"; }
      if (p.source) { st.s = el("div", "foot", b, "Source: " + L.esc(p.source)); st.s.style.fontSize = H.scale(c)[3] * c.u + "px"; st.s.style.marginTop = 18 * c.u + "px"; }
      return st;
    },
    update(st, t, c) {
      if (st.hero) return tallStatAt(st, t, c);
      const p = c.p, B = c.beat;
      if (st.k) L.enter(st.k, t, 0, 0.4);
      const q = L.expo(seg(t, B, B * 5));
      const v = Number(p.value || 0) * q;
      const fmt = (x) => { const s = x.toFixed(p.decimals || 0); return p.grouping === false ? s : s.replace(/\B(?=(\d{3})+(?!\d))/g, ","); };
      st.n.textContent = (p.prefix || "") + fmt(v) + (p.suffix || "");
      L.enter(st.n, t, B, 0.4, "pop");
      if (st.l) L.enter(st.l, t, B * 3, 0.5);
      if (st.s) L.enter(st.s, t, B * 5, 0.5, "fade");
      H.outAll([st.b], t, c);
    },
    cues: (c) => (c.P || c.styled ? [{ lt: c.beat * 0.6, type: "hit" }, { lt: c.beat * 0.6, type: "blips", len: 1.2 }, { lt: c.beat * 0.6 + 1.5, type: "tick" }] : [{ lt: c.beat, type: "hit" }, { lt: c.beat, type: "blips", len: c.beat * 4 }, { lt: c.beat * 5, type: "tick" }]),
  };

  /* ================================================================ quote
     params: text, by, role */
  S.quote = {
    build(root, c) {
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { gap: 30 }));
      st.mark = el("div", "serif", b, "“"); st.mark.style.cssText += `;font-size:${220 * c.u}px;line-height:.6;color:${C.accent};height:${110 * c.u}px`;
      st.q = L.words(b, p.text || "", "serif", { stagger: 0.04 });
      const px = H.scale(c)[1] * 1.05 * c.u;
      st.q.node.style.color = C.ink; st.q.node.style.lineHeight = "1.12";
      if (c.P) { st.amb = H.ambient(root, c); L.fit(st.q.node, 128 * c.u, px * 0.45, c.safe.w, c.safe.h * 0.68); }
      else L.fit(st.q.node, px, px * 0.45, c.safe.w, c.safe.h * 0.62);
      if (p.by) { st.by = el("div", "", b, `<b style="font-weight:650;color:${C.ink}">${L.esc(p.by)}</b>${p.role ? ` <span style="color:${C.muted}">· ${L.esc(p.role)}</span>` : ""}`); st.by.style.fontSize = H.scale(c)[2] * c.u + "px"; }
      return st;
    },
    update(st, t, c) {
      if (st.amb) st.amb(t);
      L.enter(st.mark, t, 0, 0.5, "pop");
      st.q.at(t, c.beat);
      if (st.by) L.enter(st.by, t, c.beat * 6, 0.5);
      H.outAll([st.b], t, c);
    },
    cues: (c) => [{ lt: 0, type: "pop" }, { lt: c.beat * 6, type: "tick" }],
  };

  /* ================================================================ compare
     params: title, left:{label, items[]}, right:{label, items[]} (right is "ours") */
  S.compare = {
    build(root, c) {
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { gap: 30 }));
      if (p.title) st.h = H.headline(b, p.title, c, { size: H.scale(c)[1], lines: 2 });
      const grid = el("div", "", b);
      grid.style.cssText = `display:flex;flex-direction:${c.mode === "land" ? "row" : "column"};gap:${26 * c.u}px;width:100%`;
      if (c.P) { b.style.justifyContent = "flex-start"; H.fill(grid); }
      const rowFs = (c.P ? 68 : H.scale(c)[2]) * c.u;
      const col = (side, hi) => {
        const e = el("div", "card", grid);
        e.style.cssText += `;flex:1;padding:${30 * c.u}px ${34 * c.u}px;${hi ? `border:2px solid ${C.accent};box-shadow:0 0 0 6px ${L.C.accentSoft}` : "opacity:.92"}`;
        el("div", "eyebrow", e, L.esc(side.label || "")).style.fontSize = (c.P ? 34 : H.scale(c)[3]) * c.u + "px";
        if (c.P) { e.style.display = "flex"; e.style.flexDirection = "column"; e.style.justifyContent = "center"; e.style.minHeight = "0"; }
        const ul = el("div", "", e); ul.style.marginTop = 18 * c.u + "px";
        const rows = (side.items || []).map((tx) => { const r = el("div", "", ul, `<span style="color:${hi ? C.accent : C.dim};font-weight:700;margin-right:14px">${hi ? "✓" : "–"}</span>${L.md(tx)}`); r.style.cssText = `font-size:${rowFs}px;line-height:1.2;margin:${(c.P ? 18 : 10) * c.u}px 0;color:${C.fg}`; return r; });
        return { e, rows };
      };
      st.L = col(p.left || {}, false);
      st.R = col(p.right || {}, true);
      return st;
    },
    update(st, t, c) {
      const B = c.beat;
      if (st.h) st.h.at(t, 0);
      L.enter(st.L.e, t, B * 2, 0.5);
      st.L.rows.forEach((r, i) => L.enter(r, t, B * (2.5 + i * 0.5), 0.4, "left"));
      const r0 = B * (3 + st.L.rows.length * 0.5);
      L.enter(st.R.e, t, r0, 0.5);
      st.R.rows.forEach((r, i) => L.enter(r, t, r0 + B * (0.5 + i), 0.4, "left"));
      H.outAll([st.b], t, c);
    },
    cues: (c) => { const B = c.beat, n = ((c.p.left || {}).items || []).length; return [{ lt: B * 2, type: "swoosh" }, { lt: B * (3 + n * 0.5), type: "hit" }]; },
  };

  /* ================================================================ steps
     Numbered cards in a row (landscape) or a column. params: kicker, title, items:[{t, d}] */
  S.steps = {
    build(root, c) {
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { gap: 30 }));
      if (p.kicker) st.k = H.kicker(b, p.kicker, c);
      if (p.title) st.h = H.headline(b, p.title, c, { size: H.scale(c)[1], lines: 2 });
      const row = el("div", "", b);
      const land = c.mode === "land";
      row.style.cssText = `display:flex;flex-direction:${land ? "row" : "column"};gap:${22 * c.u}px;width:100%`;
      if (c.P) { b.style.justifyContent = "flex-start"; H.fill(row); }
      const tf = (c.P ? 78 : H.scale(c)[2] * 1.1) * c.u, df = (c.P ? 46 : H.scale(c)[3] * 1.1) * c.u;
      st.cards = (p.items || []).map((it, i) => {
        const e = el("div", "card", row);
        e.style.cssText += `;flex:1;padding:${26 * c.u}px ${28 * c.u}px;display:flex;flex-direction:${land ? "column" : "row"};gap:${16 * c.u}px;align-items:${land ? "flex-start" : "center"}`;
        e.innerHTML = `<span class="mono" style="font-size:${(c.P ? 84 : 30) * c.u}px;font-weight:700;color:${C.accent}">${String(i + 1).padStart(2, "0")}</span><div><div style="font-size:${tf}px;font-weight:700;color:${C.ink};letter-spacing:-.01em;line-height:1.1">${L.md(it.t || it)}</div>${it.d ? `<div style="font-size:${df}px;color:${C.muted};margin-top:6px;line-height:1.3">${L.md(it.d)}</div>` : ""}</div>`;
        return e;
      });
      return st;
    },
    update(st, t, c) {
      const B = c.beat;
      if (st.k) L.enter(st.k, t, 0, 0.4);
      if (st.h) st.h.at(t, B * 0.5);
      /* tall: the cards spread over the whole scene */
      const gap = c.P ? Math.max(B, (c.dur - B * 2 - 0.8) / Math.max(1, st.cards.length)) : B * 2;
      st.cards.forEach((e, i) => L.enter(e, t, B * 2 + i * gap, 0.45, "rise", 40));
      H.outAll([st.b], t, c);
    },
    cues: (c) => { const n = (c.p.items || []).length, gap = c.P ? Math.max(c.beat, (c.dur - c.beat * 2 - 0.8) / Math.max(1, n)) : c.beat * 2; return (c.p.items || []).map((_, i) => ({ lt: c.beat * 2 + i * gap, type: "pop" })); },
  };
})();
