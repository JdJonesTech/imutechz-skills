/* Whiteboard: hand-drawn explainer boards (rough.js strokes, a marker pen
   that follows the stroke tip, Caveat handwriting), ported from the
   ImuTechz FISH explainer.

   The drawing lives in a fixed 1600×700 board space and is scaled to fit
   the safe area, so a board drawn once works in every aspect.

   params:
     tag, step       small label above the title ("How it works", 2)
     title           handwritten title
     take            the takeaway line, highlighter-marked, shown last
     items           explicit drawing, in board units, timed in beats:
       {rect:[x,y,w,h]} {circle:[cx,cy,d]} {line:[x1,y1,x2,y2]} {arrow:[x1,y1,x2,y2]}
       {path:"M.. C.."} {note:"text", x, y, size, acc} {cells:{x,y,cols,rows,w,h,gap}}
       common: at (beat), dur (beats), color ("accent"|"ink"|"muted"), fill, seed
     flow            shortcut: ["Read", "Think", "Answer"] -> boxes joined by arrows
     notes           with flow: one handwritten note under each box */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const H = L.H;
  const { el, seg, eo, eio, back, clamp, C } = L;
  const BW = 1600, BH = 700;
  const col = (k) => (k === "accent" ? C.accent : k === "muted" ? C.muted : k === "accent2" ? C.accent2 : !k || k === "ink" ? C.ink : k);

  /** Expand `flow` into explicit items (pure; exported for tests via L.wbFlow). */
  function flowItems(flow, notes, vertical) {
    const out = [];
    if (vertical) {
      /* portrait boards are 900×1300: boxes stacked, arrows pointing down */
      const n = flow.length, gap = 110, h = Math.min(230, (1300 - 60 - gap * (n - 1)) / n), w = 560, x = 170;
      const y0 = (1300 - (n * h + (n - 1) * gap)) / 2;
      flow.forEach((label, i) => {
        const y = y0 + i * (h + gap), at = 1 + i * 3;
        out.push({ rect: [x, y, w, h], at, dur: 1.2, seed: 5 + i, fill: i === n - 1 ? "accentSoft" : null, color: i === n - 1 ? "accent" : "ink" });
        out.push({ note: label, x: x + 34, y: y + h / 2 - 46, size: Math.min(80, (w - 60) / Math.max(4, label.length) * 1.9), at: at + 0.8, dur: 1 });
        if (notes && notes[i]) out.push({ note: notes[i], x: x + w + 24, y: y + h / 2 - 24, size: 40, at: at + 1.6, dur: 1, acc: true });
        if (i < n - 1) out.push({ arrow: [x + w / 2, y + h + 14, x + w / 2, y + h + gap - 14], at: at + 2, dur: 0.8, seed: 30 + i });
      });
      return out;
    }
    const n = flow.length, gap = 120, w = Math.min(380, (BW - 80 - gap * (n - 1)) / n), h = 190, y = 170;
    const x0 = (BW - (n * w + (n - 1) * gap)) / 2;
    flow.forEach((label, i) => {
      const x = x0 + i * (w + gap), at = 1 + i * 3;
      out.push({ rect: [x, y, w, h], at, dur: 1.2, seed: 5 + i, fill: i === n - 1 ? "accentSoft" : null, color: i === n - 1 ? "accent" : "ink" });
      out.push({ note: label, x: x + 26, y: y + h / 2 - 40, size: Math.min(64, (w - 40) / Math.max(4, label.length) * 1.9), at: at + 0.8, dur: 1 });
      if (notes && notes[i]) out.push({ note: notes[i], x: x + 6, y: y + h + 40, size: 38, at: at + 1.6, dur: 1, acc: true });
      if (i < n - 1) out.push({ arrow: [x + w + 14, y + h / 2, x + w + gap - 14, y + h / 2], at: at + 2, dur: 0.8, seed: 30 + i });
    });
    return out;
  }
  L.wbFlow = flowItems;

  S.whiteboard = {
    build(root, c) {
      const p = c.p, st = { tips: [] };
      const b = (st.b = el("div", "board", root));
      el("div", "grid", b);
      const box = H.box(b, c, { gap: 14, justify: "flex-start" });
      if (p.tag || p.step) { st.tag = el("div", "step-tag", box, `${p.step ? `<b>${L.esc(p.step)}</b>` : ""}${L.esc(p.tag || "")}`); st.tag.style.fontSize = H.scale(c)[3] * c.u + "px"; }
      st.title = el("div", "wb-title", box, L.esc(p.title || ""));
      const tpx = (c.mode === "land" ? 96 : 84) * c.u;
      st.title.style.maxWidth = c.safe.w + "px";
      L.fit(st.title, tpx, tpx * 0.5, c.safe.w, tpx * (c.P ? 2.1 : 1.1));
      const area = el("div", "", box);
      area.style.cssText = "position:relative;flex:1;width:100%;min-height:0";
      if (p.take) {
        st.take = el("div", "", box, `<span style="background:linear-gradient(transparent 62%, ${L.C.accentSoft.replace(".14", ".32")} 62%);padding:0 6px">${L.md(p.take)}</span>`);
        st.take.style.cssText += `;font-size:${(c.mode === "land" ? 36 : 34) * c.u}px;font-weight:600;color:${C.ink};line-height:1.3;max-width:${c.safe.w}px`;
      }
      st.area = area;
      st.vertical = !p.items && !!p.flow && c.P;
      st.BW = st.vertical ? 900 : BW; st.BH = st.vertical ? 1300 : BH;
      st.items = p.items || (p.flow ? flowItems(p.flow, p.notes, st.vertical) : []);
      return st;
    },
    update(st, t, c) {
      const B = c.beat;
      if (!st.inner) {
        const aw = st.area.clientWidth, ah = st.area.clientHeight;
        const bw = st.BW, bh = st.BH;
        const sc = Math.min(aw / bw, ah / bh);
        st.inner = el("div", "abs", st.area);
        st.inner.style.width = bw + "px"; st.inner.style.height = bh + "px";
        st.inner.style.transformOrigin = "0 0";
        st.inner.style.transform = `scale(${sc})`;
        L.pos(st.inner, (aw - bw * sc) / 2, (ah - bh * sc) / 2);
        st.inner.dataset.free = "";
        const svg = L.svg("svg", { width: bw, height: bh }, st.inner);
        const top = L.svg("svg", { width: bw, height: bh }, st.inner);
        top.style.zIndex = 5;
        st.pen = L.pen(top);
        st.draw = st.items.map((it, i) => {
          const o = { seed: it.seed || 3 + i * 7, strokeWidth: it.w || 3.4, stroke: col(it.color), roughness: it.roughness != null ? it.roughness : 1.1 };
          if (it.fill) { o.fill = it.fill === "accentSoft" ? L.C.accentSoft : it.fill === "accent" ? C.accent : it.fill; o.fillStyle = it.fillStyle || "hachure"; o.hachureGap = 9; }
          const R = (k, a) => ({ it, d: L.rough(svg, k, a, o) });
          if (it.rect) return R("rectangle", it.rect);
          if (it.circle) return R("circle", it.circle);
          if (it.line) return R("line", it.line);
          if (it.path) return R("path", [it.path]);
          if (it.arrow) {
            const [x1, y1, x2, y2] = it.arrow, a = Math.atan2(y2 - y1, x2 - x1), hl = 22;
            const d = L.rough(svg, "line", it.arrow, o);
            const hd = L.rough(svg, "linearPath", [[[x2 - hl * Math.cos(a - 0.5), y2 - hl * Math.sin(a - 0.5)], [x2, y2], [x2 - hl * Math.cos(a + 0.5), y2 - hl * Math.sin(a + 0.5)]]], o);
            return { it, d, hd };
          }
          if (it.note != null) {
            const n = el("div", "wb-note" + (it.acc ? " acc" : ""), st.inner, L.esc(it.note));
            n.style.fontSize = (it.size || 44) + "px";
            L.pos(n, it.x || 0, it.y || 0);
            return { it, note: n };
          }
          if (it.cells) {
            const q = it.cells, cells = [];
            for (let y = 0; y < (q.rows || 3); y++) for (let x = 0; x < (q.cols || 6); x++) {
              const e = el("div", "", st.inner);
              e.style.cssText = `position:absolute;border-radius:6px;border:2px solid ${C.line2}`;
              L.pos(e, q.x + x * ((q.w || 60) + (q.gap || 14)), q.y + y * ((q.h || 60) + (q.gap || 14)), q.w || 60, q.h || 60);
              cells.push({ e, k: L.rng(97 + x * 13 + y * 7)() });
            }
            return { it, cells };
          }
          return { it };
        });
      }
      let tip = null;
      if (st.tag) L.enter(st.tag, t, 0, 0.4);
      st.title.style.clipPath = `inset(-30% ${100 - 100 * eo(seg(t, 0.05, 0.9))}% -30% -2%)`;
      for (const q of st.draw) {
        const a = (q.it.at != null ? q.it.at : 1) * B, d = (q.it.dur != null ? q.it.dur : 1.2) * B;
        if (q.d) {
          const pr = seg(t, a, a + d);
          const tp = q.d.draw(eio(pr));
          if (pr > 0 && pr < 1 && tp) tip = tp;
          if (q.hd) q.hd.draw(seg(t, a + d, a + d + 0.15));
        } else if (q.note) {
          q.note.style.clipPath = `inset(-30% ${100 - 100 * eo(seg(t, a, a + d))}% -30% -2%)`;
        } else if (q.cells) {
          q.cells.forEach((cc) => { const pr = seg(t, a + cc.k * d, a + cc.k * d + 0.25); cc.e.style.background = pr > 0 ? L.hexA(C.accent, 0.15 + 0.55 * pr * (cc.k > 0.35 ? 1 : 0.45)) : "transparent"; cc.e.style.transform = `scale(${1 + 0.16 * Math.sin(Math.PI * pr)})`; });
        }
      }
      st.pen.at(tip, tip ? 1 : 0);
      if (st.take) {
        const last = Math.max(2, ...st.items.map((i) => (i.at || 1) + (i.dur || 1.2)));
        L.enter(st.take, t, Math.min(c.dur - 1.2, last * B + 0.2), 0.6);
      }
      const out = L.ei(seg(t, c.dur - 0.3, c.dur));
      st.b.style.opacity = 1 - out;
    },
    cues: (c) => {
      const p = c.p, B = c.beat;
      const items = p.items || (p.flow ? flowItems(p.flow, p.notes, c.P) : []);
      const out = [{ lt: 0.05, type: "write", len: 0.85 }];
      for (const it of items) {
        const a = (it.at != null ? it.at : 1) * B, d = (it.dur != null ? it.dur : 1.2) * B;
        if (it.note != null) out.push({ lt: a, type: "write", len: d });
        else if (it.cells) out.push({ lt: a, type: "blips", len: d });
        else if (it.arrow) out.push({ lt: a, type: "swoosh" });
        else out.push({ lt: a, type: "scribble", len: d });
      }
      return out;
    },
  };
})();
