/* Data scenes: chart (bars), diagram (boxes and arrows).
   Every value on screen must come from a cited source (params.source). */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const H = L.H;
  const { el, seg, eo, eio, clamp, C } = L;

  /* ================================================================ chart
     params: kicker, title, data:[{label, value}], unit, decimals, highlight (label),
     source, kind: "bar" | "hbar" (default: bar in landscape, hbar otherwise) */
  S.chart = {
    build(root, c) {
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { gap: 22, justify: "flex-start" }));
      if (p.kicker) st.k = H.kicker(b, p.kicker, c);
      if (p.title) st.h = H.headline(b, p.title, c, { size: H.scale(c)[1], lines: 2 });
      const area = el("div", "", b);
      area.style.cssText = "position:relative;flex:1;width:100%;min-height:0";
      st.area = area;
      if (p.source) { st.src = el("div", "foot", b, "Source: " + L.esc(p.source)); st.src.style.fontSize = H.scale(c)[3] * c.u + "px"; }
      st.kind = p.kind || (c.mode === "land" ? "bar" : "hbar");
      st.data = (p.data || []).map((d) => ({ label: String(d.label), value: Number(d.value) || 0 }));
      st.max = Math.max(1e-9, ...st.data.map((d) => d.value));
      return st;
    },
    update(st, t, c) {
      const p = c.p, B = c.beat;
      if (!st.bars) {
        // lay out once the flex area has a size
        const W = st.area.clientWidth, Hh = st.area.clientHeight, n = st.data.length || 1;
        const fsL = (c.P ? 52 : H.scale(c)[3] * 1.05) * c.u, fsV = (c.P ? 92 : H.scale(c)[2]) * c.u;
        st.fsV = fsV;
        st.bars = st.data.map((d, i) => {
          const hi = p.highlight ? d.label === p.highlight : i === n - 1;
          const bar = el("div", "bar" + (hi ? " hi" : ""), st.area);
          const lab = el("div", "", st.area, L.esc(d.label));
          const val = el("div", "mono", st.area);
          lab.style.cssText = `position:absolute;font-size:${fsL}px;color:${c.P ? C.ink : C.muted};font-weight:${c.P ? 700 : 400};white-space:nowrap;overflow:hidden;text-overflow:ellipsis`;
          val.style.cssText = `position:absolute;font-size:${fsV}px;font-weight:700;color:${hi ? C.accent : C.ink}`;
          return { d, bar, lab, val, hi };
        });
        if (st.kind === "bar") {
          const gap = Math.min(48 * c.u, (W / n) * 0.3), bw = (W - gap * (n - 1)) / n;
          st.bars.forEach((q, i) => { q.x = i * (bw + gap); q.w = bw; q.base = Hh - fsL * 1.8; q.full = q.base - fsV * 1.8; L.pos(q.lab, q.x, q.base + fsL * 0.4, bw); q.lab.style.textAlign = "center"; });
        } else if (c.P) {
          /* tall: stacked rows that use the full height: label above, thick bar, big value */
          const gap = 34 * c.u, row = (Hh - gap * (n - 1)) / n, lh = fsL * 1.25, bh = Math.max(40 * c.u, Math.min(row - lh, 300 * c.u));
          const y0 = (Hh - (n * (lh + bh) + gap * (n - 1))) / 2;
          st.bars.forEach((q, i) => { q.y = y0 + i * (lh + bh + gap) + lh; q.h = bh; q.x0 = 0; q.full = W - fsV * 2.6; L.pos(q.lab, 0, q.y - lh, W); q.lab.style.textAlign = "left"; });
          st.tallH = true;
        } else {
          const labW = Math.min(W * 0.34, Math.max(...st.data.map((d) => d.label.length)) * fsL * 0.6 + 10);
          const gap = 18 * c.u, bh = Math.min(84 * c.u, (Hh - gap * (n - 1)) / n);
          st.bars.forEach((q, i) => { q.y = i * (bh + gap); q.h = bh; q.x0 = labW + 16; q.full = W - q.x0 - fsV * 5; L.pos(q.lab, 0, q.y + bh / 2 - fsL * 0.65, labW); q.lab.style.textAlign = "right"; });
        }
      }
      if (st.k) L.enter(st.k, t, 0, 0.4);
      if (st.h) st.h.at(t, B * 0.5);
      st.bars.forEach((q, i) => {
        /* tall: bars fill the scene on springs, one by one */
        const g = c.P ? clamp(L.spring(t - B * (1 + i * 2), { stiffness: 42, mass: 1, damping: 11 })) : eio(seg(t, B * (2 + i), B * (2 + i) + 0.9));
        const v = q.d.value * g, frac = q.d.value / st.max;
        const txt = (p.prefix || "") + v.toFixed(p.decimals != null ? p.decimals : Number.isInteger(q.d.value) ? 0 : 1) + (p.unit || "");
        q.val.textContent = txt;
        if (st.kind === "bar") {
          const hh = Math.max(0, frac * g * q.full);
          L.pos(q.bar, q.x, q.base - hh, q.w, hh);
          L.pos(q.val, q.x, q.base - hh - (c.P ? st.fsV * 1.2 : H.scale(c)[2] * c.u * 1.5), q.w); q.val.style.textAlign = "center";
        } else {
          const ww = Math.max(0, frac * g * q.full);
          L.pos(q.bar, q.x0, q.y, ww, q.h); q.bar.style.borderRadius = "4px 10px 10px 4px";
          const vy = st.tallH ? st.fsV * 0.6 : H.scale(c)[2] * c.u * 0.65;
          L.pos(q.val, q.x0 + ww + 14, q.y + q.h / 2 - vy);
          /* the winning bar keeps breathing: a sheen runs along it */
          if (st.tallH && q.hi) { const f = ((t * 0.5) % 1) * 100; q.bar.style.backgroundImage = `linear-gradient(100deg, transparent ${(f - 14).toFixed(1)}%, rgba(255,255,255,.34) ${f.toFixed(1)}%, transparent ${(f + 14).toFixed(1)}%)`; }
        }
        L.enter(q.lab, t, B * (2 + i), 0.4, "fade");
        q.val.style.opacity = g > 0.02 ? 1 : 0;
      });
      if (st.src) L.enter(st.src, t, B * 3, 0.5, "fade");
      H.outAll([st.b], t, c);
    },
    cues: (c) => [{ lt: 0, type: "tick" }, ...(c.p.data || []).map((_, i) => ({ lt: c.beat * (2 + i), type: "sweep" }))],
  };

  /* ================================================================ diagram
     Boxes joined by arrows, laid out as a row (landscape) or column.
     params: kicker, title, nodes:[{label, sub, hi}], caption, style: "rough"|"clean" */
  /* morph: one box re-labels and grows into each next step */
  function morphAt(st, t, c) {
    const p = c.p, B = c.beat, u = c.u, list = p.nodes || [], n = Math.max(1, list.length);
    if (!st.box) {
      const W = st.area.clientWidth, Hh = st.area.clientHeight;
      st.mW = W; st.mH = Hh;
      st.box = el("div", "node hi", st.area);
      st.box.style.cssText += `;position:absolute;left:0;top:0;border:${6 * u}px solid ${C.ink};background:${L.hexA(C.surface, 0.95)};box-shadow:${10 * u}px ${14 * u}px ${28 * u}px rgba(0,0,0,.28);display:block;overflow:visible`;
      st.lab = list.map((nd) => {
        const e = el("div", "", st.box);
        e.style.cssText = "position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:4%";
        const big = el("b", "", e, L.md(nd.label || ""));
        big.style.cssText = `font:900 ${(c.P ? 88 : 72) * u}px/1 var(--display);letter-spacing:-.03em;color:${C.ink}`;
        if (nd.sub) { const s = el("span", "", e, L.md(nd.sub)); s.style.cssText = `font-size:${H.scale(c)[2] * 1.1 * u}px;margin-top:${14 * u}px;color:${C.muted}`; }
        return e;
      });
    }
    if (st.k) L.enter(st.k, t, 0, 0.4);
    if (st.h) st.h.at(t, B * 0.5);
    const first = B * 2, per = Math.max(B * 2, (c.dur - first - 1) / n);
    /* grows a step at a time, on a spring */
    let g = 0;
    for (let i = 0; i < n; i++) g += L.spring(t - (first + i * per), L.SPRING.premium) / n;
    const bw = st.mW * (0.62 + 0.38 * g), bh = st.mH * (0.34 + 0.56 * g);
    L.pos(st.box, (st.mW - bw) / 2, (st.mH - bh) / 2, bw, bh);
    L.show(st.box, clamp((t - first + 0.1) * 8), `scale(${(0.9 + 0.1 * L.spring(t - first + 0.1, L.SPRING.playful)).toFixed(4)})`);
    st.lab.forEach((e, i) => {
      const a = first + i * per, next = i + 1 < n ? first + (i + 1) * per : Infinity;
      const ins = L.spring(t - a, L.SPRING.playful), o = L.EASE.exit(seg(t, next - 0.16, next));
      L.show(e, clamp((t - a) * 9) * (1 - o), `translateY(${((1 - ins) * 46 * u - o * 34 * u).toFixed(2)}px) scale(${(0.8 + 0.2 * ins).toFixed(4)})`);
    });
    H.outAll([st.b], t, c);
  }

  S.diagram = {
    build(root, c) {
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { gap: 24, justify: "flex-start" }));
      if (p.kicker) st.k = H.kicker(b, p.kicker, c);
      if (p.title) st.h = H.headline(b, p.title, c, { size: H.scale(c)[1], lines: 2 });
      st.area = el("div", "", b);
      st.area.style.cssText = "position:relative;flex:1;width:100%;min-height:0";
      if (p.caption) { st.cap = el("div", "lede", b, L.md(p.caption)); st.cap.style.fontSize = H.scale(c)[2] * c.u + "px"; }
      return st;
    },
    update(st, t, c) {
      const p = c.p, B = c.beat;
      if (p.morph) return morphAt(st, t, c);
      if (!st.nodes) {
        const W = st.area.clientWidth, Hh = st.area.clientHeight;
        const list = p.nodes || [];
        const n = Math.max(1, list.length), row = c.mode === "land" || c.mode === "square" && n <= 3;
        const gap = (row ? 90 : 70) * c.u;
        const nw = row ? (W - gap * (n - 1)) / n : c.P ? W : Math.min(W, 760 * c.u);
        const nh = row ? Math.min(Hh * 0.7, 260 * c.u) : c.P ? Math.min(420 * c.u, (Hh - gap * (n - 1)) / n) : Math.min(180 * c.u, (Hh - gap * (n - 1)) / n);
        st.svg = L.svg("svg", { width: W, height: Hh }, st.area);
        st.svg.style.cssText = "position:absolute;left:0;top:0;overflow:visible";
        const rough = p.style !== "clean";
        st.nodes = list.map((nd, i) => {
          const y0 = c.P && !row ? Math.max(0, (Hh - n * nh - gap * (n - 1)) / 2) : 0;
          const x = row ? i * (nw + gap) : (W - nw) / 2, y = row ? (Hh - nh) / 2 : y0 + i * (nh + gap);
          const e = el("div", "node" + (nd.hi ? " hi" : ""), st.area, `<b>${L.md(nd.label || "")}</b>${nd.sub ? `<span>${L.md(nd.sub)}</span>` : ""}`);
          L.pos(e, x, y, nw, nh);
          e.querySelector("b").style.fontSize = (c.P ? Math.min(82, nh / c.u * 0.34) : H.scale(c)[2] * 1.05) * c.u + "px";
          if (e.querySelector("b")) e.querySelector("b").style.lineHeight = "1.05";
          if (e.querySelector("span")) e.querySelector("span").style.fontSize = (c.P ? Math.min(46, nh / c.u * 0.19) : H.scale(c)[3]) * c.u + "px";
          e.style.overflow = "hidden";
          if (rough) { e.style.border = "0"; e.style.background = "transparent"; }
          const box = rough ? L.rough(st.svg, "rectangle", [x, y, nw, nh], { seed: 11 + i, strokeWidth: 3, stroke: nd.hi ? C.accent : C.ink, fill: nd.hi ? L.C.accentSoft : L.hexA(C.surface, 0.9), fillStyle: "solid" }) : null;
          return { e, x, y, box, hi: !!nd.hi };
        });
        st.arrows = [];
        for (let i = 0; i < st.nodes.length - 1; i++) {
          const a = st.nodes[i];
          const d = row ? `M${a.x + nw + 12} ${a.y + nh / 2} L${a.x + nw + gap - 14} ${a.y + nh / 2}` : `M${a.x + nw / 2} ${a.y + nh + 10} L${a.x + nw / 2} ${a.y + nh + gap - 12}`;
          const aw = c.P ? 6 : 3.4;
          const ln = L.rough(st.svg, "path", [d], { seed: 40 + i, strokeWidth: aw, stroke: C.ink, roughness: rough ? 1 : 0 });
          const hx = row ? a.x + nw + gap - 12 : a.x + nw / 2, hy = row ? a.y + nh / 2 : a.y + nh + gap - 10;
          const head = row ? [[hx - 16, hy - 12], [hx, hy], [hx - 16, hy + 12]] : [[hx - 12, hy - 16], [hx, hy], [hx + 12, hy - 16]];
          const hd = L.rough(st.svg, "linearPath", [head], { seed: 60 + i, strokeWidth: aw, stroke: C.ink, roughness: rough ? 0.8 : 0 });
          /* tall: a dot runs the arrow into the next box */
          const dot = c.P && !row ? L.svg("circle", { cx: hx, cy: a.y + nh, r: 11 * c.u, fill: C.accent, opacity: 0 }, st.svg) : null;
          st.arrows.push({ ln, hd, dot, y0: a.y + nh + 10, y1: a.y + nh + gap - 12 });
        }
      }
      if (st.k) L.enter(st.k, t, 0, 0.4);
      if (st.h) st.h.at(t, B * 0.5);
      /* tall: the boxes spread over the whole scene; the active one takes a nudge when it lands */
      const per = c.P ? Math.max(B * 1.5, (c.dur - B * 2 - 1) / Math.max(1, st.nodes.length)) : Math.max(B * 1.5, Math.min(B * 4, (c.dur - B * 6) / Math.max(1, st.nodes.length)));
      st.nodes.forEach((q, i) => {
        const a = B * 2 + i * per;
        if (q.box) q.box.draw(eio(seg(t, a, a + 0.6)));
        L.enter(q.e, t, a + (c.P ? 0.05 : 0.25), 0.4, q.box ? "fade" : "pop");
        if (c.P) { q.e.style.transform = (q.e.style.transform || "") + ` scale(${(1 + 0.03 * L.punch(t - a - 0.05, 12, 5)).toFixed(4)})`; const ar = st.arrows[i]; if (ar && ar.dot) { const tq = seg(t, a + per * 0.55, a + per * 0.95); ar.dot.setAttribute("opacity", tq > 0 && tq < 1 ? 1 : 0); ar.dot.setAttribute("cy", L.lerp(ar.y0, ar.y1, L.EASE.camera(tq)).toFixed(1)); } }
        if (st.arrows[i]) { st.arrows[i].ln.draw(eio(seg(t, a + per * 0.55, a + per * 0.85))); st.arrows[i].hd.draw(seg(t, a + per * 0.85, a + per * 0.95)); }
      });
      if (st.cap) L.enter(st.cap, t, B * 2 + st.nodes.length * per, 0.5);
      H.outAll([st.b], t, c);
    },
    cues: (c) => {
      const B = c.beat, n = (c.p.nodes || []).length;
      if (c.P && !c.p.morph) { const pr = Math.max(B * 1.5, (c.dur - B * 2 - 1) / Math.max(1, n)), o = []; for (let i = 0; i < n; i++) { o.push({ lt: B * 2 + i * pr, type: c.p.style === "clean" ? "pop" : "scribble", len: 0.6 }); if (i < n - 1) o.push({ lt: B * 2 + i * pr + pr * 0.55, type: "swoosh" }); } return o; }
      if (c.p.morph) { const f = B * 2, pr = Math.max(B * 2, (c.dur - f - 1) / Math.max(1, n)); return (c.p.nodes || []).map((_, i) => ({ lt: f + i * pr, type: i ? "swish" : "pop" })); }
      const per = Math.max(B * 1.5, Math.min(B * 4, (c.dur - B * 6) / Math.max(1, n)));
      const out = [];
      for (let i = 0; i < n; i++) { out.push({ lt: B * 2 + i * per, type: c.p.style === "clean" ? "pop" : "scribble", len: 0.6 }); if (i < n - 1) out.push({ lt: B * 2 + i * per + per * 0.55, type: "swoosh" }); }
      return out;
    },
  };
})();
