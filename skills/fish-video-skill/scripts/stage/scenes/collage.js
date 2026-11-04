/* Paper-collage scenes: collage, split, cone.

   collage  crumpled paper, B&W halftone photo cut-outs with contact shadows,
            chamfered / octagonal cards with an offset outline, bold Inter 900
            labels with hand-drawn curved arrows, hairline connectors
   split    a card splits down the middle; the halves slide apart (expo-out)
            to reveal a second layer
   cone     near-black stage, a spotlight cone; text exists only inside the light

   Positions are fractions of the safe area (x, y = centre); times are beats. */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const H = L.H;
  const { el, seg, eo, ei, clamp, C } = L;

  const fxOf = (it) => (it.halftone === false && !it.bw ? null : { bw: true, halftone: it.halftone !== false, contrast: it.contrast || 1.3, cell: it.cell });
  const toStage = (c, x, y) => ({ x: c.safe.x + x * c.safe.w, y: c.safe.y + y * c.safe.h });

  /* a chamfered / octagonal / rectangular photo card, or a free cut-out.
     returns {node, cx, cy, w, h, at(t, t0)} */
  function card(root, c, it, k, geo) {
    const u = c.u;
    const kind = it.kind || (it.shape ? "card" : "card");
    const g = geo || itemGeo(c, it, k, 1, null);
    const w = g.w, h = g.h, p = { x: g.cx, y: g.cy };
    const node = el("div", "fv-card", root);
    L.pos(node, p.x - w / 2, p.y - h / 2, w, h);
    node.style.zIndex = it.z != null ? it.z : 2 + k;
    const rot = it.rot || 0;
    const st = { node, cx: p.x, cy: p.y, w, h, rot, kind };
    /* is this stage point on the object? (the opaque pixels of a cut-out, the box of a card) */
    const info0 = kind === "cutout" && it.src ? L.cutInfo(L.projUrl(it.src)) : null;
    const ca = Math.cos((-rot * Math.PI) / 180), sa = Math.sin((-rot * Math.PI) / 180);
    st.occ = node._occ = (x, y) => {
      const dx = x - p.x, dy = y - p.y, lx = (dx * ca - dy * sa) / w + 0.5, ly = (dx * sa + dy * ca) / h + 0.5;
      if (lx < 0 || lx >= 1 || ly < 0 || ly >= 1) return false;
      if (!info0) return true;
      return !!info0.mask[Math.floor((info0.y + ly * info0.h) * info0.ch) * info0.cw + Math.floor((info0.x + lx * info0.w) * info0.cw)];
    };
    if (kind === "cutout") {
      node.classList.add("fv-cut");
      const img = el("img", "", node);
      L.setImgFx(img, L.projUrl(it.src), fxOf(it));
      /* the node box is the visible object: the image hangs off it by its transparent padding */
      const info = L.cutInfo(L.projUrl(it.src));
      if (info) {
        const iw = w / info.w, ih = h / info.h;
        img.style.cssText += `;position:absolute;left:${(-info.x * iw).toFixed(2)}px;top:${(-info.y * ih).toFixed(2)}px;width:${iw.toFixed(2)}px;height:${ih.toFixed(2)}px;max-width:none`;
      }
      node.style.filter = L.cutFilter({ outline: it.outline != null ? it.outline : 5 * u, shadow: { x: 14 * u, y: 20 * u, blur: 24 * u, a: 0.5 } });
      st.base = node.style.filter;
    } else {
      const shape = it.shape || "chamfer";
      const cut = shape === "octagon" ? Math.min(w, h) * 0.29 : shape === "rect" ? 0 : Math.min(w, h) * (it.chamfer || 0.12);
      const sh = el("div", "abs", node);
      L.pos(sh, 0, 0, w, h);
      sh.style.filter = `drop-shadow(${12 * u}px ${18 * u}px ${22 * u}px rgba(0,0,0,.5))`;
      const face = el("div", "face", sh);
      face.style.clipPath = L.chamferClip(w, h, cut);
      face.style.background = it.fill || "#ecebe7";
      if (it.src) { const img = el("img", "", face); L.setImgFx(img, L.projUrl(it.src), fxOf(it)); if (it.fit) img.style.objectFit = it.fit; if (it.pad) { img.style.inset = it.pad * w + "px"; img.style.width = img.style.height = "auto"; img.style.right = img.style.bottom = it.pad * w + "px"; } }
      if (it.text) { const tx = el("div", "fv-label", face, L.md(it.text)); tx.style.cssText += `;position:absolute;inset:${w * 0.08}px;display:flex;align-items:center;justify-content:center;text-align:center;color:${it.ink || "#111"}`; L.fit(tx, (it.size || 90) * u, 24 * u, w * 0.84, h * 0.84); }
      /* the thin outline, offset outward */
      const off = (it.offset != null ? it.offset : 12) * u;
      const ol = L.svg("svg", { class: "ol", width: w + off * 2, height: h + off * 2 }, node);
      ol.style.left = -off + "px"; ol.style.top = -off + "px";
      L.svg("polygon", { points: L.chamfer(w + off * 2, h + off * 2, cut ? cut + off * 0.6 : 0), fill: "none", stroke: it.line || "#111", "stroke-width": 1.6 * u, opacity: 0.75 }, ol);
    }
    if (it.tag) {
      const tg = el("div", "fv-tag fv-chip", node, L.md(it.tag));
      tg.style.fontSize = (it.tagSize || 30) * u + "px";
      tg.style.position = "absolute"; tg.style.left = "50%"; tg.style.top = -0.75 * (it.tagSize || 30) * u + "px";
      tg.style.transform = `translateX(-50%) rotate(${-rot * 0.6}deg)`;
      tg.style.boxShadow = "0 10px 18px -8px rgba(0,0,0,.55)";
      st.tag = tg;
    }
    st.at = (t, t0) => {
      L.resolveIn(node, t, t0, 0.42, { pre: `rotate(${rot}deg)`, from: 0.84, blur: 12, filter: st.base || "", spring: L.SPRING.premium });
      if (st.tag) L.enter(st.tag, t, t0 + 0.3, 0.4, "pop");
      if (st.tag) st.tag.style.transform = `translateX(-50%) rotate(${-rot * 0.6}deg) ` + st.tag.style.transform;
    };
    return st;
  }

  /* The stage box of an item. w is the visible object (the opaque bbox of a cut-out).
     With a region (portrait layouts) y maps into the free area between the title and
     the caption band, a lone hero fills 60-85% of the frame width, and the box always
     stays inside the region: size gives way before position does. */
  function itemGeo(c, it, k, n, R) {
    let w = (it.w || 0.42) * c.safe.w;
    const info = it.kind === "cutout" && it.src ? L.cutInfo(L.projUrl(it.src)) : null;
    const asp = it.h ? (it.h * c.safe.h) / w : info ? (info.h * info.nh) / (info.w * info.nw) : it.ratio || 1.2;
    const p = toStage(c, it.x != null ? it.x : 0.5, it.y != null ? it.y : 0.5);
    if (!R) return { w, h: w * asp, cx: p.x, cy: p.y };
    if (k === 0 && !it.small && c.P) w = clamp(w, c.W * (n > 1 ? 0.56 : 0.62), c.W * 0.85);
    const a = ((it.rot || 0) * Math.PI) / 180, cs = Math.abs(Math.cos(a)), sn = Math.abs(Math.sin(a));
    const rw = (q) => q * cs + q * asp * sn, rh = (q) => q * sn + q * asp * cs;
    const RW = R.x1 - R.x0, RH = R.y1 - R.y0;
    /* only a subject too tall for the room may tuck under the title's paper strips */
    w *= Math.min(1, RW / rw(w), (RH + (k === 0 ? R.tuck || 0 : 0)) / rh(w));
    const hw = rw(w) / 2, hh = rh(w) / 2;
    const y0 = hh * 2 > RH ? R.y1 - hh * 2 : R.y0;
    const cy = R.y0 + (it.y != null ? it.y : 0.5) * RH;
    return { w, h: w * asp, cx: clamp(p.x, R.x0 + hw, R.x1 - hw), cy: clamp(cy, y0 + hh, Math.max(y0 + hh, R.y1 - hh)) };
  }

  /* default positions for 1-4 items: hero first */
  const AUTO = {
    port: [[0.5, 0.56, 0.72], [0.24, 0.2, 0.4], [0.78, 0.3, 0.36], [0.74, 0.8, 0.34]],
    land: [[0.5, 0.55, 0.32], [0.2, 0.4, 0.22], [0.8, 0.45, 0.22], [0.72, 0.8, 0.18]],
  };

  /* The clearest arrow from a label to an object: a start on the label's edge, a landing
     just off the object's edge, 100-300 px apart, the straight run clear of every object,
     label and title. Prefers about 170 px, head-on. Returns {A, T} or null. */
  function arrowPath(r, tgt, hits, rects, u) {
    const starts = [[0.5, 0, 0, -1], [0.5, 1, 0, 1], [0, 0.5, -1, 0], [1, 0.5, 1, 0], [0.18, 0, 0, -1], [0.82, 0, 0, -1], [0.18, 1, 0, 1], [0.82, 1, 0, 1]]
      .map(([a, b, nx, ny]) => ({ x: r.x + a * r.w + nx * 14 * u, y: r.y + b * r.h + ny * 14 * u }));
    const reach = Math.hypot(tgt.w, tgt.h);
    const ends = [];
    for (let k = 0; k < 40; k++) {
      const an = (k / 40) * TAU, ox = Math.cos(an), oy = Math.sin(an);
      for (let d = reach; d > 0; d -= 6 * u) if (tgt.occ(tgt.cx + ox * d, tgt.cy + oy * d)) { ends.push({ x: tgt.cx + ox * (d + 18 * u), y: tgt.cy + oy * (d + 18 * u), ox, oy }); break; }
    }
    const inRect = (px, py, q, m) => px > q.x - m && px < q.x + q.w + m && py > q.y - m && py < q.y + q.h + m;
    let best = null, bc = Infinity;
    for (const A of starts) for (const T of ends) {
      const dx = T.x - A.x, dy = T.y - A.y, len = Math.hypot(dx, dy);
      if (len < 100 * u || len > 300 * u) continue;
      const ux = dx / len, uy = dy / len;
      /* head-on: the arrow travels against the surface's outward direction */
      const cost = Math.abs(len - 170 * u) + (1 + (ux * T.ox + uy * T.oy)) * 90 * u;
      if (cost >= bc) continue;
      let clear = true;
      for (let f = 0.04; f <= 1 && clear; f += 0.06) {
        const px = A.x + dx * f, py = A.y + dy * f;
        if (hits.some((h) => h(px, py)) || inRect(px, py, r, 4 * u) || rects.some((q) => inRect(px, py, q, 4 * u))) clear = false;
      }
      if (clear) { best = { A, T: { x: T.x, y: T.y } }; bc = cost; }
    }
    return best;
  }

  /* when a label lands: on its own word if it is spoken (robust to re-voicing), else its beat */
  const TAU = Math.PI * 2;
  const labelAt = (c, lb, k) => {
    const on = lb.on != null ? L.wordTime(c, lb.on) : c.styled && lb.sync !== false ? L.wordTime(c, lb.text) : null;
    return on != null ? on : (lb.at != null ? lb.at : 2 + k) * c.beat;
  };

  /* ================================================================ collage
     params: title, title_at, title_pos (top|bottom), kicker,
             items: [{src, kind: card|cutout, shape: chamfer|octagon|rect, x, y, w, h|ratio, rot, at, tag, text,
                      halftone (default true), outline (px, cut-outs), z}],
             labels: [{text, x, y, at, on (word: appears when spoken), size, color, plain, arrow: {to: item index | [x, y], bend, at}}],
                      x, y are wishes: at build time each label is measured against the object masks,
                      the title and the other labels, and nudged to the nearest free space inside c.safe.
                      Without on or at a label lands on its own word if the narration says it,
             lines: [[i, j] | {a, b, at}]  hairline connectors between item centres,
             bg: paper|studio|none, push (camera push, default .05), sfx */
  S.collage = {
    cam: "paper",
    /* labels need room: when one finds no free spot the subject first slides aside to open
       a column, then gives way in size. Same attempts in the same order: deterministic. */
    build(root, c) {
      const hasLabels = (c.p.labels || []).length > 0;
      const tries = hasLabels && c.p.layout !== "free" ? [[1, 0], [1, 1], [1, -1], [0.92, 0], [0.92, 1], [0.92, -1], [0.84, 1], [0.84, -1], [0.75, 1], [0.75, -1], [0.66, 0]] : [[1, 0]];
      let st = null;
      for (const [f, side] of tries) {
        root.innerHTML = ""; root._planes = null;
        st = this.layout(root, c, f, side);
        if (st.allFree) break;
      }
      return st;
    },
    layout(root, c, shrink, side) {
      const p = c.p, u = c.u, st = { allFree: true };
      if (p.bg !== "none") { st.bg = p.bg === "studio" ? L.studioBg(root, c) : L.paperBg(root, c); L.layer(st.bg, p.bg_z != null ? p.bg_z : -800); }
      /* depth: background -800, items 0 (or item.z), title +120, connectors / arrows +150, labels +180 */
      const cam = root;
      const auto = AUTO[c.P ? "port" : "land"];
      /* title first: its height decides the room the items get */
      const strip = p.title_strip != null ? !!p.title_strip : c.P;
      let titleBox = null;
      if (p.title) {
        const tb = (st.tb = el("div", "abs", root));
        L.layer(tb, p.title_z != null ? p.title_z : 120);
        tb.style.zIndex = 40;
        const top = p.title_pos !== "bottom";
        L.pos(tb, c.safe.x, c.safe.y, c.safe.w);
        tb.style.display = "flex"; tb.style.flexDirection = "column"; tb.style.gap = 10 * u + "px";
        if (p.kicker) { st.k = el("div", "fv-chip fv-tag", tb, L.md(p.kicker)); st.k.style.fontSize = 30 * u + "px"; st.k.style.alignSelf = "flex-start"; }
        st.h = L.revealWords(tb, p.title, "fv-label", { tilt: strip ? 0.9 : 0 });
        st.h.node.style.lineHeight = strip ? "1.02" : "0.95";
        st.h.node.dataset.lb = strip ? "over" : "1";
        if (strip) st.h.spans.forEach((s) => s.classList.add("fv-strip"));
        const px = (p.size || (c.P ? 150 : 120)) * u;
        const got = L.fitHero(st.h.node, { w: c.safe.w, lines: 2, max: px, min: px * 0.4 });
        if (got < 78 * u && c.P) L.fitHero(st.h.node, { w: c.safe.w, lines: 3, max: px, min: px * 0.4 });
        if (!top) tb.style.top = c.safe.y + c.safe.h - tb.offsetHeight + "px";
        titleBox = { x: c.safe.x, y: tb.offsetTop, w: c.safe.w, h: tb.offsetHeight };
      }
      /* the room the items get, in portrait: the whole frame width, from the title down to the caption band */
      const m = 24 * u;
      const tuck = titleBox && strip ? Math.min(titleBox.h * 0.42, 130 * u) : 0;
      const R = (st.R = p.layout === "free" ? null : {
        x0: m, x1: c.W - m,
        y0: titleBox && p.title_pos !== "bottom" ? titleBox.y + titleBox.h + 16 * u : c.safe.y,
        y1: titleBox && p.title_pos === "bottom" ? titleBox.y - 16 * u : c.safe.y + c.safe.h - 6 * u,
        tuck: p.title_pos === "bottom" ? 0 : tuck,
      });
      const n = (p.items || []).length;
      st.items = (p.items || []).map((it, k) => {
        const a = auto[k] || auto[auto.length - 1];
        const d = { x: a[0], y: a[1], w: a[2], ...it };
        const geo = itemGeo(c, d, k, n, R);
        if (shrink < 1) { geo.w *= shrink; geo.h *= shrink; }
        /* slide aside as a group to open a column for the labels (the image may run under the platform's UI margin) */
        if (side && R) { const hw = geo.w / 2; geo.cx = side > 0 ? Math.max(geo.cx, R.x1 - hw) : Math.min(geo.cx, R.x0 + hw); }
        const s = card(cam, c, d, k, geo);
        L.layer(s.node, it.z != null ? it.z : 0);
        return { d: it, s, at: (it.at != null ? it.at : 1 + k) * c.beat };
      });
      /* heroes: what `match` transitions and the anchor look at */
      st.heroes = st.items.filter((q) => q.d.src).map((q) => ({ node: q.s.node, url: L.projUrl(q.d.src), d: q.d, kind: q.s.kind, rot: q.s.rot, w: q.s.w, h: q.s.h, base: q.s.base, fx: fxOf(q.d), match: !!q.d.match }));
      /* the camera's target for `through` transitions: the hero */
      if (st.items[0]) { const h0 = st.items[0].s; st.target = { x: h0.cx, y: h0.cy, share: h0.w / c.W }; }
      /* ink layer: hairlines + arrows */
      const ink = (st.ink = L.svg("svg", { class: "fv-ink", width: c.W, height: c.H }, cam));
      ink.style.zIndex = 30;
      L.layer(ink, p.ink_z != null ? p.ink_z : 150, { sharp: true });
      st.lines = (p.lines || []).map((ln, k) => {
        const [a, b] = Array.isArray(ln) ? ln : [ln.a, ln.b];
        const A = st.items[a] && st.items[a].s, B = st.items[b] && st.items[b].s;
        if (!A || !B) return null;
        const g = L.svg("g", {}, ink);
        /* edge to edge: shorten by each card's inner radius */
        const dx = B.cx - A.cx, dy = B.cy - A.cy, dl = Math.hypot(dx, dy) || 1, ux = dx / dl, uy = dy / dl;
        const ra = Math.min(A.w, A.h) * 0.5, rb = Math.min(B.w, B.h) * 0.5;
        const P1 = { x: A.cx + ux * ra, y: A.cy + uy * ra }, P2 = { x: B.cx - ux * rb, y: B.cy - uy * rb };
        const e = L.svg("path", { d: `M${P1.x.toFixed(1)} ${P1.y.toFixed(1)} L${P2.x.toFixed(1)} ${P2.y.toFixed(1)}`, stroke: "#111", "stroke-width": 1.6 * u, fill: "none", pathLength: 1, "stroke-dasharray": "1 1", "stroke-dashoffset": 1, opacity: 0.85 }, g);
        const d1 = L.svg("circle", { cx: P1.x, cy: P1.y, r: 5 * u, fill: "#111" }, g), d2 = L.svg("circle", { cx: P2.x, cy: P2.y, r: 5 * u, fill: "#111" }, g);
        const at = (!Array.isArray(ln) && ln.at != null ? ln.at : Math.max(st.items[a].at, st.items[b].at) / c.beat + 0.5) * c.beat;
        return { e, d1, d2, at };
      }).filter(Boolean);
      /* labels with curved arrows */
      st.labels = (p.labels || []).map((lb, k) => {
        const n = el("div", "fv-label", cam, L.md(lb.text));
        n.style.position = "absolute"; n.style.zIndex = 35; n.style.whiteSpace = "nowrap";
        n.dataset.lb = "1";
        L.layer(n, lb.z != null ? lb.z : 180);
        /* body type: at least 4% of the frame height in portrait */
        n.style.fontSize = Math.max(lb.size || 60, c.P ? (0.04 * c.H) / u : 0) * u + "px";
        const accent = lb.color === "accent";
        const inkCol = accent ? C.accent : lb.color || "#111";
        if (lb.bg) { n.style.background = lb.bg; n.style.padding = "0.08em 0.22em 0.12em"; if (lb.color && !accent) n.style.color = lb.color; }
        else if (c.P && !lb.plain) { n.classList.add("fv-sticker"); if (accent) n.classList.add("acc-bg"); }
        else n.style.color = inkCol;
        const q = toStage(c, lb.x != null ? lb.x : 0.1, lb.y != null ? lb.y : 0.1);
        if (R) q.y = R.y0 + (lb.y != null ? lb.y : 0.1) * (R.y1 - R.y0);
        const w = n.offsetWidth, h = n.offsetHeight;
        /* keep labels inside the safe area even at the end of the camera push (+ bob) */
        const kz = 1 / (1 + (p.push != null ? p.push : 0.05) + 0.01), ox = c.W / 2, oy = c.safe.y + c.safe.h * 0.5;
        const ix0 = ox + (c.safe.x - ox) * kz + 4 * u, ix1 = ox + (c.safe.x + c.safe.w - ox) * kz - 4 * u;
        const iy0 = oy + (c.safe.y - oy) * kz + 4 * u, iy1 = oy + (c.safe.y + c.safe.h - oy) * kz - 4 * u;
        const wx = lb.align === "right" ? q.x - w : lb.align === "center" ? q.x - w / 2 : q.x;
        /* where the arrow lands: walk from the label's centre towards the object until it is hit */
        const tgt = lb.arrow && typeof lb.arrow.to === "number" && st.items[lb.arrow.to] ? st.items[lb.arrow.to].s : null;
        const edge = (cx, cy) => {
          const dx = tgt.cx - cx, dy = tgt.cy - cy, dl = Math.hypot(dx, dy) || 1, sx = dx / dl, sy = dy / dl;
          for (let d = 0; d < dl; d += 6 * u) if (tgt.occ(cx + sx * d, cy + sy * d)) return { x: cx + sx * d, y: cy + sy * d, sx, sy, d };
          return { x: tgt.cx, y: tgt.cy, sx, sy, d: dl };
        };
        /* the gap an arrow has to live in: centre-to-edge minus the label's half extent along the ray */
        const gapOf = tgt ? (r) => { const cx = r.x + r.w / 2, cy = r.y + r.h / 2, e = edge(cx, cy); return e.d - Math.min(Math.abs(e.sx) > 1e-3 ? r.w / 2 / Math.abs(e.sx) : 1e9, Math.abs(e.sy) > 1e-3 ? r.h / 2 / Math.abs(e.sy) : 1e9); } : null;
        const hits = st.items.map((q2) => q2.s.occ);
        const spot = L.placeLabel({
          w, h, want: { x: wx, y: q.y - h / 2 }, bounds: { x0: ix0, y0: iy0, x1: ix1, y1: iy1 },
          hit: (px, py) => hits.some((f) => f(px, py)), rects: st.placed || (st.placed = titleBox ? [titleBox] : []),
          gap: gapOf, minGap: 26 * u, maxGap: 300 * u, step: 10 * u, pad: 12 * u,
        });
        if (!spot.free) st.allFree = false;
        const x = spot.x, y = spot.y;
        st.placed.push({ x, y, w, h });
        L.pos(n, x, y);
        n.style.transform = `rotate(${lb.rot || 0}deg)`;
        const at = labelAt(c, lb, k);
        let arrow = null;
        if (lb.arrow) {
          const to = lb.arrow.to;
          let T, A0 = null;
          if (tgt) {
            const best = arrowPath({ x, y, w, h }, tgt, hits, st.placed, u);
            if (best) { T = best.T; A0 = best.A; }
            else { const e = edge(x + w / 2, y + h / 2), off = 16 * u; T = { x: e.x - e.sx * off, y: e.y - e.sy * off }; }
          } else T = toStage(c, (to || [0.5, 0.5])[0], (to || [0.5, 0.5])[1]);
          /* start on the label's edge facing the target */
          const cx = x + w / 2, cy = y + h / 2, dx = T.x - cx, dy = T.y - cy;
          const sx = Math.abs(dx) / (w / 2 + 14 * u), sy = Math.abs(dy) / (h / 2 + 14 * u), sc = Math.max(sx, sy) || 1;
          const A = A0 || { x: cx + dx / sc, y: cy + dy / sc };
          /* bow away from the object so the curve reads and never crosses it */
          let bend = Math.max(0.22, Math.abs(lb.arrow.bend != null ? lb.arrow.bend : 0.28));
          if (tgt) { const al = Math.hypot(T.x - A.x, T.y - A.y) || 1, nx = -(T.y - A.y) / al, ny = (T.x - A.x) / al; if (nx * ((A.x + T.x) / 2 - tgt.cx) + ny * ((A.y + T.y) / 2 - tgt.cy) < 0) bend = -bend; }
          arrow = { d: L.handArrow(ink, A, T, { bend, seed: 11 + k, width: 6 * u, head: 36 * u, color: inkCol, single: true }), at: (lb.arrow.at != null ? lb.arrow.at * c.beat : at + 0.12) };
          /* later labels keep off this arrow */
          for (let f = 0.25; f < 1; f += 0.25) st.placed.push({ x: A.x + (T.x - A.x) * f - 8 * u, y: A.y + (T.y - A.y) * f - 8 * u, w: 16 * u, h: 16 * u });
        }
        return { n, at, arrow, rot: lb.rot || 0 };
      });
      return st;
    },
    update(st, t, c) {
      const p = c.p;
      /* the subject is never still: a slow float, and a nudge every time something lands on it */
      const hits = st.labels.map((l) => l.at);
      st.items.forEach(({ s, at }, k) => {
        s.at(t, at);
        if (!c.lively || t < at) return;
        const ph = k * 1.7, f = t - at;
        let kick = 0;
        for (const a of hits) kick += L.punch(t - a - 0.08);
        const fy = 7 * c.u * Math.sin((TAU * f) / 4.3 + ph) * clamp(f), fr = 0.7 * Math.sin((TAU * f) / 6.1 + ph) * clamp(f);
        s.node.style.transform += ` translateY(${fy.toFixed(2)}px) rotate(${fr.toFixed(3)}deg) scale(${(1 + 0.035 * kick).toFixed(4)})`;
      });
      st.lines.forEach((l) => { const q = eo(seg(t, l.at, l.at + 0.5)); l.e.setAttribute("stroke-dashoffset", (1 - q).toFixed(4)); l.d1.setAttribute("opacity", clamp(q * 4)); l.d2.setAttribute("opacity", clamp(q * 4 - 3)); });
      if (st.h) st.h.at(t, (p.title_at != null ? p.title_at : 0.3) * c.beat);
      if (st.k) L.enter(st.k, t, 0, 0.4, "pop");
      st.labels.forEach((lb) => {
        L.resolveIn(lb.n, t, lb.at, 0.3, { pre: `rotate(${lb.rot}deg)`, from: 0.72, blur: 6, spring: L.SPRING.playful });
        if (lb.arrow) lb.arrow.d.draw(L.EASE.arrive2(seg(t, lb.arrow.at, lb.arrow.at + 0.42)), 1);
      });
      H.outAll([...st.items.map((q) => q.s.node), st.ink, st.tb, ...st.labels.map((l) => l.n)], t, c, 0.22);
    },
    cues(c) {
      const p = c.p, B = c.beat, out = [];
      if (p.title) out.push(L.cue((p.title_at != null ? p.title_at : 0.3) * B - L.SWISH_LEAD, "swish", 2));
      (p.items || []).forEach((it, k) => { const at = (it.at != null ? it.at : 1 + k) * B; out.push(L.cue(at, k === 0 ? "thump" : "paper", k === 0 ? 3 : 1)); if (k) out.push(L.cue(at, "pop", 2)); });
      (p.labels || []).forEach((lb, k) => { const at = labelAt(c, lb, k); out.push(L.cue(at, "pop", 1)); if (lb.arrow) out.push(L.cue(lb.arrow.at != null ? lb.arrow.at * B : at + 0.12, "scribble", 1, { len: 0.42 })); });
      const itAt = (k) => { const it = (p.items || [])[k]; return it ? (it.at != null ? it.at : 1 + k) : 0; };
      (p.lines || []).forEach((ln) => { const [a, b] = Array.isArray(ln) ? ln : [ln.a, ln.b]; const at = !Array.isArray(ln) && ln.at != null ? ln.at : Math.max(itAt(a), itAt(b)) + 0.5; out.push(L.cue(at * B, "tick", 1)); });
      return out;
    },
  };

  /* ================================================================ split
     params: front: {src, title, tag, fill}, back: {src, title, sub, fill},
             at (beat of the split, default 3), dir (v|h), shape (chamfer|octagon|rect), bg (paper|studio) */
  function face(parent, w, h, c, side, cut) {
    const u = c.u;
    const f = el("div", "abs", parent);
    L.pos(f, 0, 0, w, h);
    f.style.clipPath = L.chamferClip(w, h, cut);
    f.style.background = side.fill || "#ecebe7";
    f.style.overflow = "hidden";
    if (side.src) { const img = el("img", "", f); img.style.cssText = "position:absolute;inset:0;width:100%;height:100%;object-fit:cover"; L.setImgFx(img, L.projUrl(side.src), side.halftone === false ? null : { bw: true, halftone: true, contrast: 1.3 }); }
    if (side.title) {
      const bar = el("div", "abs", f);
      bar.style.cssText += `;left:0;right:0;bottom:${h * 0.07}px;display:flex;justify-content:center`;
      f._bar = bar;
      const tx = el("div", "fv-label", bar, L.md(side.title));
      tx.style.cssText += `;background:${side.ink || "#111"};color:#fff;padding:.06em .28em .12em;text-align:center;max-width:${w * 0.9}px`;
      L.fit(tx, (side.size || 120) * u, 30 * u, w * 0.9, h * 0.32);
    }
    return f;
  }
  S.split = {
    cam: "paper",
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      st.bg = p.bg === "studio" ? L.studioBg(root, c) : L.paperBg(root, c);
      L.layer(st.bg, -800);
      const front = p.front || {}, back = p.back || {};
      const w = Math.min(c.safe.w * (c.P ? 1 : 0.6), c.safe.h * 1.1), h = Math.min(c.safe.h * (c.P ? 0.98 : 0.86), w * 1.3);
      const x = c.safe.x + (c.safe.w - w) / 2, y = c.safe.y + (c.safe.h - h) / 2;
      const cut = p.shape === "octagon" ? Math.min(w, h) * 0.29 : p.shape === "rect" ? 0 : Math.min(w, h) * 0.1;
      st.w = w; st.h = h;
      /* the back layer */
      const bk = (st.bk = el("div", "abs", root));
      L.pos(bk, x, y, w, h);
      bk.dataset.obst = "1";
      const bsh = el("div", "abs", bk); L.pos(bsh, 0, 0, w, h);
      bsh.style.filter = `drop-shadow(${12 * u}px ${18 * u}px ${24 * u}px rgba(0,0,0,.45))`;
      face(bsh, w, h, c, { fill: "#f2f1ed", ...back, title: null }, cut);
      const bt = (st.bt = el("div", "abs", bk));
      L.pos(bt, w * 0.08, 0, w * 0.84, h);
      bt.style.cssText += ";display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:" + 18 * u + "px";
      if (back.kicker) { st.bkk = el("div", "fv-chip fv-tag", bt, L.md(back.kicker)); st.bkk.style.fontSize = 28 * u + "px"; }
      if (back.title) { st.btl = el("div", "fv-label", bt, L.md(back.title)); st.btl.style.color = back.ink || "#111"; L.fitHero(st.btl, { w: w * 0.86, lines: 4, max: (back.size || 190) * u, min: 40 * u }); }
      if (back.sub) { st.bsub = L.subWords(bt, back.sub, "fv-tag"); st.bsub.node.style.cssText += `;white-space:normal;font-size:${44 * u}px;line-height:1.15;color:#222;max-width:${w * 0.84}px`; }
      /* the front card, built twice and clipped into halves */
      const v = p.dir !== "h";
      st.halves = [0, 1].map((k) => {
        const o = el("div", "abs", root);
        o.dataset.nolint = ""; /* the halves leave the frame by design */
        L.pos(o, x, y, w, h);
        o.style.filter = `drop-shadow(${12 * u}px ${18 * u}px ${24 * u}px rgba(0,0,0,.5))`;
        const inner = el("div", "abs", o); L.pos(inner, 0, 0, w, h);
        inner.style.clipPath = v ? (k ? "inset(0 0 0 50%)" : "inset(0 50% 0 0)") : (k ? "inset(50% 0 0 0)" : "inset(0 0 50% 0)");
        const ff = face(inner, w, h, c, front, cut);
        o._bar = ff._bar;
        return o;
      });
      const off = 12 * u;
      const ol = (st.ol = L.svg("svg", { width: w + off * 2, height: h + off * 2 }, root));
      ol.style.cssText = `position:absolute;left:${x - off}px;top:${y - off}px;overflow:visible`;
      L.svg("polygon", { points: L.chamfer(w + off * 2, h + off * 2, cut ? cut + off * 0.6 : 0), fill: "none", stroke: "#111", "stroke-width": 1.6 * u, opacity: 0.75 }, ol);
      /* the tear line */
      st.tear = L.svg("line", v ? { x1: off + w / 2, y1: off, x2: off + w / 2, y2: off + h } : { x1: off, y1: off + h / 2, x2: off + w, y2: off + h / 2 }, ol);
      st.tear.setAttribute("stroke", "#fff"); st.tear.setAttribute("stroke-width", 3 * u); st.tear.setAttribute("pathLength", 1); st.tear.setAttribute("stroke-dasharray", "1 1");
      if (front.tag) { st.tag = el("div", "fv-chip fv-tag", root, L.md(front.tag)); st.tag.style.fontSize = 30 * u + "px"; st.tag.style.position = "absolute"; L.pos(st.tag, x + 20 * u, y + 20 * u); st.tag.style.zIndex = 5; }
      st.v = v;
      /* depth: the back layer sits behind the front card */
      L.layer(bk, -90); st.halves.forEach((o) => L.layer(o, 30)); L.layer(ol, 30); if (st.tag) L.layer(st.tag, 120);
      return st;
    },
    update(st, t, c) {
      const p = c.p, B = c.beat, sp = (p.at != null ? p.at : 3) * B;
      const q = L.expo(seg(t, sp, sp + 0.7));
      /* the halves keep creeping apart after the split: nothing holds still */
      const d = (st.v ? st.w : st.h) * (p.spread != null ? p.spread : 0.46) * q + (q > 0 ? 7 * c.u * Math.max(0, t - sp) : 0);
      const inP = L.resolveIn(st.halves[0], t, 0, 0.6, { blur: 12 });
      L.resolveIn(st.halves[1], t, 0, 0.6, { blur: 12 });
      if (q > 0) {
        st.halves.forEach((o, k) => {
          const s = k ? 1 : -1;
          o.style.transform = st.v ? `translateX(${(s * d).toFixed(1)}px) rotate(${(s * 5 * q).toFixed(2)}deg)` : `translateY(${(s * d).toFixed(1)}px) rotate(${(s * 3 * q).toFixed(2)}deg)`;
          if (o._bar) o._bar.style.opacity = 1 - clamp(q * 2.5); /* cut type must not hang off the halves */
        });
      }
      st.ol.style.opacity = clamp(inP * 2) * (1 - clamp(q * 3));
      st.tear.setAttribute("stroke-dashoffset", (1 - eo(seg(t, sp - 0.35, sp))).toFixed(4));
      if (st.tag) { L.enter(st.tag, t, 0.3, 0.4, "pop"); if (q > 0) st.tag.style.opacity = 1 - clamp(q * 3); }
      /* back layer resolves as the halves part */
      L.resolveIn(st.bk, t, sp + 0.05, 0.7, { from: 0.9, blur: 14, expo: true });
      if (st.bkk) L.enter(st.bkk, t, sp + 0.3, 0.4, "pop");
      if (st.btl) { L.resolveIn(st.btl, t, sp + 0.12, 0.35, { from: 0.8, blur: 8, spring: L.SPRING.premium }); if (c.lively && t > sp + 0.5) st.btl.style.transform += ` scale(${(1 + 0.012 * (t - sp - 0.5)).toFixed(4)})`; }
      if (st.bsub) st.bsub.at(t, sp + 0.55, c.fps);
      H.outAll([st.bk, st.ol], t, c, 0.25);
    },
    cues(c) {
      const B = c.beat, sp = (c.p.at != null ? c.p.at : 3) * B;
      return [L.cue(0, "paper", 2), L.cue(sp, "riser", 2, { len: Math.min(1.2, sp) }), L.cue(sp - L.SWISH_LEAD, "swish", 1), L.cue(sp, "impact", 3), L.cue(sp + 0.15, "pop", 1), ...(c.p.back && c.p.back.sub ? [L.cue(sp + 0.55, "tick", 1)] : [])];
    },
  };

  /* ================================================================ cone
     params: title, sub, kicker, at (beat the light comes on), angle (deg, 36), swing (deg, 5),
             x (0..1 source position, .5), pool (true: the floor glow) */
  S.cone = {
    cam: { preset: "drift+dolly-in", amount: 0.55 },
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      const bg = el("div", "abs", root);
      L.pos(bg, 0, 0, c.W, c.H);
      L.layer(bg, -800);
      bg.style.background = "radial-gradient(ellipse 90% 70% at 50% 40%, #121212 0%, #070707 60%, #030303 100%)";
      /* the lamp hangs high, centred on the type */
      st.sx = p.x != null ? c.W * p.x : c.safe.x + c.safe.w / 2; st.sy = Math.max(70 * u, c.safe.y * 0.45);
      st.beam = el("div", "abs", root); L.pos(st.beam, 0, 0, c.W, c.H);
      st.pool = el("div", "abs", root);
      const pw = c.W * 0.9, ph = 160 * u, py = c.safe.y + c.safe.h * 0.95;
      L.pos(st.pool, st.sx - pw / 2, py - ph / 2, pw, ph);
      st.pool.style.background = "radial-gradient(ellipse 50% 50% at 50% 50%, rgba(255,255,255,.22) 0%, rgba(255,255,255,.06) 55%, transparent 70%)";
      /* everything that only exists inside the light */
      st.lit = el("div", "abs", root); L.pos(st.lit, 0, 0, c.W, c.H);
      const box = el("div", "safe", st.lit);
      L.pos(box, c.safe.x, c.safe.y + c.safe.h * 0.24, c.safe.w, c.safe.h * 0.76);
      box.style.alignItems = "center"; box.style.textAlign = "center"; box.style.justifyContent = "center"; box.style.gap = 22 * u + "px";
      if (p.kicker) { st.k = el("div", "fv-step", box, L.esc(p.kicker)); st.k.style.cssText += `;font-size:${28 * u}px;color:#fff;opacity:.85`; }
      /* a darker beam behind the type, so the accent reads */
      st.scrim = el("div", "abs", box);
      st.T = L.revealWords(box, p.title || "", "fv-neon");
      st.t = st.T.node;
      st.t.style.lineHeight = "0.98"; st.t.style.position = "relative";
      /* hero type: 70-85% of the safe width */
      L.fitHero(st.t, { w: c.safe.w * 0.85, lines: p.lines || Math.min(4, String(p.title || "").split("\n").length + 1), max: (p.size || 220) * u, min: 60 * u });
      st.t.style.textShadow = `0 ${4 * u}px ${22 * u}px rgba(0,0,0,.75)`;
      const hot = L.mix(C.accent, "#ffffff", 0.2);
      st.T.spans.forEach((s) => { if (s.classList.contains("acc")) { s.style.color = hot; s.style.textShadow = `0 0 ${3 * u}px rgba(0,0,0,.95), 0 ${3 * u}px ${18 * u}px rgba(0,0,0,.9)`; } });
      if (p.sub) { st.sub = L.subWords(box, p.sub, "fv-tag"); st.sub.node.style.cssText += `;white-space:normal;color:#ddd;font-size:${42 * u}px;max-width:${c.safe.w * 0.75}px;line-height:1.2`; }
      /* the cone auto-fits the measured type: its top corners are the tightest, plus margin for feather + swing */
      const by = box.offsetTop, tT = by + st.t.offsetTop, tw = Math.max(st.t.offsetWidth, st.sub ? st.sub.node.offsetWidth : 0);
      const tcx = c.safe.x + c.safe.w / 2, reach = Math.abs(tcx - st.sx) + tw / 2 + 28 * u;
      st.swing = p.swing != null ? p.swing : 2.5;
      const half = (Math.atan(reach / Math.max(1, tT - st.sy)) * 180) / Math.PI;
      st.ang = Math.max(p.angle || 0, 2 * (half + st.swing + 6));
      L.pos(st.scrim, (c.safe.w - tw) / 2 - 60 * u, st.t.offsetTop - 60 * u, tw + 120 * u, st.t.offsetHeight + 120 * u);
      st.scrim.style.background = "radial-gradient(ellipse 50% 50% at 50% 50%, rgba(0,0,0,.62) 0%, rgba(0,0,0,.45) 55%, transparent 100%)";
      /* the accent's line waits for its word: the second idea lands when it is spoken */
      const tok = String(p.title || "").split("\n");
      let idx = 0;
      st.lineOf = [];
      st.lineAt = tok.map((ln, li) => {
        const ws = ln.split(/\s+/).filter(Boolean);
        ws.forEach(() => st.lineOf.push(li));
        idx += ws.length;
        const acc = ws.find((w) => w.includes("*"));
        return acc && li > 0 ? L.wordTime(c, acc) : null;
      });
      st.dust = el("div", "abs", st.lit); L.pos(st.dust, 0, 0, c.W, c.H);
      const r = L.rng(41);
      st.motes = Array.from({ length: 70 }, () => ({ x: r() * c.W, y: c.safe.y + r() * c.H * 0.7, s: 1 + r() * 3, v: 6 + r() * 16, ph: r() * 6.28 }));
      st.lamp = el("div", "abs", root);
      L.pos(st.lamp, st.sx - 70 * u, st.sy - 26 * u, 140 * u, 52 * u);
      st.lamp.style.cssText += ";border-radius:50%;background:radial-gradient(ellipse at 50% 60%, #fff 0%, #f2f2f2 25%, rgba(255,255,255,.3) 55%, transparent 72%)";
      return st;
    },
    update(st, t, c) {
      const p = c.p, B = c.beat, on = (p.at != null ? p.at : 1) * B;
      /* switch-on flicker: on, off for 2 frames, on */
      const fr = 1 / c.fps;
      let lv = t < on ? 0 : t < on + 2 * fr ? 0.7 : t < on + 4 * fr ? 0.08 : t < on + 5 * fr ? 0.5 : 1;
      if (!c.holdOut) lv *= 1 - ei(seg(t, c.dur - 0.3, c.dur));
      const ang = st.ang, sw = st.swing * Math.sin((t - on) * 0.9);
      const from = 180 - ang / 2 + sw;
      const at = `at ${st.sx.toFixed(1)}px ${st.sy.toFixed(1)}px`;
      const soft = Math.min(7, ang * 0.2);
      st.beam.style.background = `conic-gradient(from ${from.toFixed(2)}deg ${at}, transparent 0deg, rgba(255,255,255,.13) ${soft}deg, rgba(255,255,255,.28) ${ang / 2}deg, rgba(255,255,255,.13) ${ang - soft}deg, transparent ${ang}deg, transparent 360deg)`;
      st.beam.style.webkitMaskImage = st.beam.style.maskImage = `radial-gradient(ellipse 120% 95% ${at}, #000 0%, rgba(0,0,0,.75) 60%, transparent 100%)`;
      st.beam.style.opacity = lv;
      const mask = `conic-gradient(from ${from.toFixed(2)}deg ${at}, transparent 0deg, #000 ${soft * 1.4}deg, #000 ${ang - soft * 1.4}deg, transparent ${ang}deg, transparent 360deg)`;
      st.lit.style.webkitMaskImage = st.lit.style.maskImage = mask;
      st.lit.style.opacity = lv;
      st.pool.style.opacity = p.pool === false ? 0 : lv;
      st.pool.style.transform = `translateX(${(Math.tan((sw * Math.PI) / 180) * -c.safe.h * 0.95).toFixed(1)}px)`;
      st.lamp.style.opacity = 0.25 + 0.75 * lv;
      if (st.k) L.enter(st.k, t, on + 0.2, 0.4, "fade");
      st.T.at(t, on, (k, dflt) => { const a = st.lineAt[st.lineOf[k]]; return a != null ? Math.max(dflt, a - 0.12 + (k - st.lineOf.indexOf(st.lineOf[k])) * 0.067) : dflt; });
      st.t.style.transform = `scale(${(1 + 0.01 * Math.max(0, t - on)).toFixed(4)})`;
      if (st.sub) st.sub.at(t, on + 0.6, c.fps);
      st.dust.innerHTML = st.motes.map((m) => { const y = ((m.y - c.safe.y - m.v * t) % (c.H * 0.7) + c.H * 0.7) % (c.H * 0.7) + c.safe.y; const x = m.x + Math.sin(t * 0.7 + m.ph) * 12; return `<i style="position:absolute;left:${x.toFixed(1)}px;top:${y.toFixed(1)}px;width:${m.s}px;height:${m.s}px;border-radius:50%;background:#fff;opacity:${(0.25 + 0.4 * Math.sin(t + m.ph) ** 2).toFixed(3)}"></i>`; }).join("");
    },
    cues(c) {
      const on = (c.p.at != null ? c.p.at : 1) * c.beat;
      return [L.cue(on, "thump", 3), L.cue(on + 0.07, "zap", 1), L.cue(on, "swell", 2), ...(c.p.sub ? [L.cue(on + 0.6, "tick", 1)] : [])];
    },
  };
})();
