/* Live-capture scenes: tour (a recorded website/product shot in a browser
   window with camera moves, cursor, click ripples and callouts) and image
   (a still with a slow push-in).

   tour params:
     shot        capture id (build/cap/<shot>)
     url         text shown in the address bar
     from        start frame, or a mark name recorded during capture
     speed       capture frames per output frame (1 = real time; 1.3 = brisk)
     eyebrow, title, bullets[]   the side panel (top panel in portrait)
     cam         [{m: mark, d: frame offset, z: zoom, x, y}] camera keys (x/y in page px; omit to follow the cursor)
     callouts    [{text, m|t0, d, len, page:{x,y} | x,y (0..1 of window), align}]
     full        true = window fills the safe area, no panel
     frame       browser (default: window chrome + url bar) | inset (no chrome, white border + drop
                 shadow on a brand-coloured background; for desktop recordings) | none (bare picture)
     bg          inset background (CSS colour/gradient, default the brand accent)
     cursor      true | false | "glow" (white arrow ~1.5x with a soft halo, glowing click ripples)
     zoom        "auto" or {z, ease, hold, gap}: virtual camera zooms to the cursor (1.6-2x) around
                 clicks and pulls back after them / on a scroll jump (used when `cam` is not given)
     spotlight   [{m|t0, d, len, rect:{x,y,w,h} | follow: true, size:{w,h}, r, dim}]   page px; dims
                 everything outside a soft-edged rounded cut-out (dim .66)
     highlight   [{m|t0, d, len, rect:{x,y,w,h}, kind: marker|underline|box}]   marks the text being read */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const H = L.H;
  const { el, seg, eo, ei, back, clamp, C } = L;

  const markF = (shot, v) => (typeof v === "string" ? L.mark$(shot, v) : v || 0);

  S.tour = {
    build(root, c) {
      const p = c.p, st = {};
      const sf = c.safe, land = c.mode === "land";
      st.panel = !p.full && (p.title || p.eyebrow);
      let wx = sf.x, wy = sf.y, ww = sf.w, wh = sf.h;
      if (st.panel) {
        const pn = (st.pn = el("div", "abs", root));
        if (land) { const pw = Math.round(sf.w * 0.25); L.pos(pn, sf.x + sf.w - pw, sf.y, pw, sf.h); ww = sf.w - pw - 48 * c.u; pn.style.display = "flex"; pn.style.flexDirection = "column"; pn.style.justifyContent = "center"; }
        else { L.pos(pn, sf.x, sf.y, sf.w); }
        pn.style.gap = 18 * c.u + "px";
        if (p.eyebrow) { st.eb = H.kicker(pn, p.eyebrow, c); }
        st.tt = el("div", "serif", pn, L.md(p.title || ""));
        st.tt.style.cssText += `;color:${C.ink};line-height:1.04;max-width:${land ? sf.w * 0.25 : sf.w}px`;
        const tpx = (land ? 56 : 64) * c.u;
        L.fit(st.tt, tpx, tpx * 0.5, land ? sf.w * 0.25 : sf.w, tpx * (land ? 4.4 : 2.3));
        st.bl = (land ? p.bullets || [] : []).map((b) => { const e = el("div", "", pn, `<i style="width:9px;height:9px;border-radius:50%;background:${C.accent};flex:none;transform:translateY(-4px)"></i><span>${L.md(b)}</span>`); e.style.cssText = `display:flex;gap:14px;align-items:baseline;font-size:${26 * c.u}px;line-height:1.3;color:${C.fg}`; return e; });
        if (!land) { const ph = pn.offsetHeight + 34 * c.u; wy = sf.y + ph; wh = sf.h - ph; }
      }
      const frame = (st.frame = p.frame || "browser");
      if (frame === "inset") {
        st.ibg = el("div", "abs", root);
        L.pos(st.ibg, 0, 0, c.W, c.H);
        st.ibg.style.background = p.bg || `radial-gradient(ellipse 90% 70% at 40% 30%, ${L.hexA(C.accent, 0.82)} 0%, ${C.accent} 55%, color-mix(in srgb, ${C.accent} 70%, #000) 100%)`;
        root.insertBefore(st.ibg, root.firstChild);
        L.layer(st.ibg, -600);
        const bd = 12 * c.u;
        wx += bd; wy += bd; ww -= bd * 2; wh -= bd * 2;
      }
      /* fit: contain (default) | cover; portrait inset/none recordings default to cover (a crop that follows the cursor) */
      const cover = p.fit === "cover" || (p.fit == null && c.P && frame !== "browser");
      st.w = L.Win(root, { shot: p.shot, url: p.url || "", bare: frame !== "browser", cursor: p.cursor, cover });
      const r = st.w.layout(wx, wy, ww, wh);
      if (frame === "inset") { st.w.node.style.borderRadius = 16 * c.u + "px"; st.w.node.style.boxShadow = `0 0 0 ${12 * c.u}px #fff, 0 ${50 * c.u}px ${90 * c.u}px -${30 * c.u}px rgba(0,0,0,.6), 0 ${8 * c.u}px ${20 * c.u}px rgba(0,0,0,.2)`; }
      if (r.h < wh) { st.w.node.style.top = wy + (wh - r.h) / 2 + "px"; st.w.Y = wy + (wh - r.h) / 2; }
      if (r.w < ww) { st.w.node.style.left = wx + (ww - r.w) / 2 + "px"; st.w.X = wx + (ww - r.w) / 2; }
      /* spotlight: an SVG dim layer with a blurred rounded hole (mask) */
      if ((p.spotlight || []).length) {
        const id = "fvspot-" + c.index;
        const sv = (st.spot = L.svg("svg", { width: c.W, height: c.H }, root));
        sv.style.cssText = "position:absolute;left:0;top:0;z-index:5;pointer-events:none";
        sv.innerHTML = `<defs><filter id="${id}-b" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${14 * c.u}"/></filter><mask id="${id}-m" maskUnits="userSpaceOnUse" x="0" y="0" width="${c.W}" height="${c.H}"><rect width="${c.W}" height="${c.H}" fill="#fff"/><rect class="hole" fill="#000" filter="url(#${id}-b)"/></mask></defs><rect class="dim" width="${c.W}" height="${c.H}" fill="#000" mask="url(#${id}-m)" opacity="0"/><rect class="edge" fill="none" stroke="rgba(255,255,255,.7)" opacity="0"/>`;
        st.hole = sv.querySelector(".hole"); st.dim = sv.querySelector(".dim"); st.edge = sv.querySelector(".edge");
      }
      st.hls = (p.highlight || []).map((d) => { const n = el("div", "hl " + (d.kind || "marker"), root); n.style.opacity = 0; n.style.zIndex = 4; return { d, n }; });
      st.cos = (p.callouts || []).map((d) => { const n = el("div", "callout", root, d.html || L.md(d.text || "")); n.style.opacity = 0; n.style.fontSize = 26 * c.u + "px"; return { d, n }; });
      return st;
    },
    update(st, t, c) {
      const p = c.p, sp = p.speed || 1;
      const f0 = markF(p.shot, p.from);
      const f = f0 + t * L.FPS * sp;
      const keys = (p.cam || [{ f: 0, z: 1 }]).map((k) => ({ ...k, f: (k.m != null ? markF(p.shot, k.m) : k.f || 0) + (k.d || 0) }));
      const camv = !p.cam && p.zoom ? L.autoCam(p.shot, f, typeof p.zoom === "object" ? p.zoom : {}) : L.cam(p.shot, keys, f);
      const r = st.w.at(f, camv, { cursor: p.cursor !== false });
      const ltOf = (d) => (d.m != null ? (markF(p.shot, d.m) + (d.d || 0) - f0) / (L.FPS * sp) : d.t0 || 0.8);
      /* page rect -> stage rect, through the camera */
      const toStage = (rc) => { const a = st.w.map({ x: rc.x, y: rc.y }, r), b = st.w.map({ x: rc.x + rc.w, y: rc.y + rc.h }, r); return { x: st.w.X + a.x, y: st.w.Y + a.y, w: b.x - a.x, h: b.y - a.y }; };
      if (st.spot) {
        let best = null, ba = 0;
        for (const d of p.spotlight) {
          const a = ltOf(d), b = d.len ? a + d.len : c.dur - 0.2;
          const q = L.inout(t, a, 0.45, b, 0.4);
          if (q > ba) { ba = q; best = { d, a }; }
        }
        if (best) {
          const d = best.d;
          let rc;
          if (d.follow || !d.rect) { const fc = L.focusAt(p.shot, Math.round(clamp(f, 0, st.w.meta.count - 1)), 8); const sz = d.size || { w: 420, h: 220 }; rc = toStage({ x: fc.x - sz.w / 2, y: fc.y - sz.h / 2, w: sz.w, h: sz.h }); }
          else rc = toStage(d.rect);
          const pad = (d.pad != null ? d.pad : 14) * c.u, grow = (1 - L.expo(seg(t, best.a, best.a + 0.55))) * 120 * c.u;
          /* the cut-out stays inside the recording */
          const vx0 = st.w.X, vy0 = st.w.Y + st.w.BARH, vx1 = vx0 + st.w.VW, vy1 = vy0 + st.w.VH;
          const x = Math.max(vx0, rc.x - pad - grow), y = Math.max(vy0, rc.y - pad - grow), w = Math.min(vx1, rc.x + rc.w + pad + grow) - x, h = Math.min(vy1, rc.y + rc.h + pad + grow) - y, rr = (d.r != null ? d.r : 18) * c.u;
          for (const e of [st.hole, st.edge]) { e.setAttribute("x", x.toFixed(1)); e.setAttribute("y", y.toFixed(1)); e.setAttribute("width", Math.max(0, w).toFixed(1)); e.setAttribute("height", Math.max(0, h).toFixed(1)); e.setAttribute("rx", rr); }
          st.edge.setAttribute("stroke-width", 2 * c.u);
          st.dim.setAttribute("opacity", ((d.dim != null ? d.dim : 0.66) * ba).toFixed(3));
          st.edge.setAttribute("opacity", (ba * 0.5).toFixed(3));
        } else { st.dim.setAttribute("opacity", 0); st.edge.setAttribute("opacity", 0); }
      }
      st.hls.forEach(({ d, n }) => {
        const a = ltOf(d), b = d.len ? a + d.len : c.dur - 0.2;
        const vis = L.inout(t, a, 0.2, b, 0.3);
        if (vis <= 0.001 || !d.rect) { n.style.opacity = 0; return; }
        const rc = toStage(d.rect), k = d.kind || "marker";
        if (k === "underline") L.pos(n, rc.x, rc.y + rc.h + 2 * c.u, rc.w, 6 * c.u);
        else { const pd = (k === "box" ? 8 : 3) * c.u; L.pos(n, rc.x - pd, rc.y - pd, rc.w + pd * 2, rc.h + pd * 2); }
        const g = eo(seg(t, a, a + 0.35));
        n.style.opacity = vis;
        n.style.transform = k === "box" ? `scale(${(0.9 + 0.1 * L.back(seg(t, a, a + 0.35), 2)).toFixed(4)})` : `scaleX(${g.toFixed(4)})`;
        n.style.transformOrigin = k === "box" ? "50% 50%" : "0 50%";
      });
      const q = L.expo(seg(t, 0, 0.6));
      st.w.node.style.opacity = clamp(q * 1.6);
      st.w.node.style.transform = `translateY(${(1 - q) * 50}px) scale(${0.96 + 0.04 * q})`;
      if (st.pn) {
        const a = eo(seg(t, 0.25, 0.85));
        L.show(st.pn, a, `translate${c.mode === "land" ? "X" : "Y"}(${(1 - a) * 30}px)`);
        st.bl.forEach((e, i) => L.enter(e, t, 1 + i * c.beat * 2, 0.5, "left"));
      }
      st.cos.forEach(({ d, n }) => {
        const a = d.m != null ? (markF(p.shot, d.m) + (d.d || 0) - f0) / (L.FPS * sp) : d.t0 || 0.8;
        const b = d.len ? a + d.len : c.dur - 0.2;
        let x, y;
        if (d.page) { const pt = st.w.map(d.page, r); x = st.w.X + clamp(pt.x, 40, st.w.VW - 40); y = st.w.Y + clamp(pt.y, 60, st.w.VH); }
        else { x = st.w.X + (d.x != null ? d.x : 0.5) * st.w.VW; y = st.w.Y + (d.y != null ? d.y : 0.85) * (st.w.VH + st.w.BARH); }
        const pr = L.inout(t, a, 0.4, b, 0.3), bk = back(seg(t, a, a + 0.45), 2);
        n.style.opacity = clamp(pr); n.style.visibility = pr > 0.01 ? "visible" : "hidden";
        const w = n.offsetWidth, al = d.align || "center";
        let xx = al === "right" ? x - w : al === "center" ? x - w / 2 : x;
        xx = clamp(xx, c.safe.x, c.safe.x + c.safe.w - w);
        n.style.left = xx + "px"; n.style.top = clamp(y, c.safe.y, c.safe.y + c.safe.h - n.offsetHeight) + "px";
        n.style.transform = `scale(${0.8 + 0.2 * bk})`;
      });
      H.outAll([st.w.node, st.pn, st.spot, ...st.hls.map((h) => h.n)], t, c, 0.25);
    },
    busy: true,
    cam: "screen",
    cues: (c) => {
      const p = c.p, sp = p.speed || 1, f0 = markF(p.shot, p.from);
      const ltOf = (d) => (d.m != null ? (markF(p.shot, d.m) + (d.d || 0) - f0) / (L.FPS * sp) : d.t0 || 0.8);
      const out = L.capCues(p.shot, f0, sp, 0, c.dur).concat([L.cue(-L.SWISH_LEAD, "whoosh", 2)]).concat((p.callouts || []).map((d) => L.cue(ltOf(d), "pop", 2)));
      if (!p.cam && p.zoom) for (const fm of L.autoCamMoves(p.shot, typeof p.zoom === "object" ? p.zoom : {})) { const lt = (fm - f0) / (L.FPS * sp) - L.SWISH_LEAD; if (lt > 0 && lt < c.dur) out.push(L.cue(lt, "swish", 1)); }
      for (const d of p.spotlight || []) out.push(L.cue(ltOf(d), "swell", 2));
      for (const d of p.highlight || []) out.push(d.kind === "box" ? L.cue(ltOf(d), "pop", 1) : L.cue(ltOf(d), "scribble", 1, { len: 0.35 }));
      return out;
    },
  };

  /* ================================================================ stepcard
     "STEP N" between the steps of a screen explainer.
     params: n, title, sub, label ("Step"), bg (ink|accent|paper) */
  S.stepcard = {
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      const bg = p.bg || "ink";
      if (bg === "paper") L.paperBg(root, c);
      else { const b = el("div", "abs", root); L.pos(b, 0, 0, c.W, c.H); b.style.background = bg === "accent" ? `radial-gradient(ellipse at 40% 30%, ${L.hexA(C.accent, 0.85)}, ${C.accent} 60%)` : "radial-gradient(ellipse at 50% 40%, #1c1c1c, #0b0b0b 70%)"; }
      const fg = bg === "paper" ? "#111" : "#fff", hi = bg === "accent" ? "#111" : C.accent;
      const box = (st.b = H.box(root, c, { center: true, gap: 10 }));
      st.l = el("div", "fv-step", box, L.esc((p.label || "Step").toUpperCase()));
      st.l.style.cssText += `;font-size:${34 * u}px;color:${fg};opacity:.85`;
      st.n = L.slideWords(box, String(p.n != null ? p.n : 1).padStart(2, "0"), "fv-label", { dist: 520 * u });
      st.n.node.style.cssText += `;color:${hi};line-height:.9;font-size:${(c.P ? 360 : 300) * u}px`;
      if (p.title) { st.t = L.subWords(box, p.title, "fv-label"); st.t.node.style.cssText += `;color:${fg};white-space:normal;max-width:${c.safe.w}px;line-height:1`; L.fit(st.t.node, 96 * u, 36 * u, c.safe.w, 96 * u * 2.1); }
      if (p.sub) { st.s = el("div", "fv-tag", box, L.md(p.sub)); st.s.style.cssText += `;white-space:normal;color:${fg};opacity:.75;font-size:${36 * u}px;margin-top:${12 * u}px;max-width:${c.safe.w}px`; }
      return st;
    },
    update(st, t, c) {
      L.enter(st.l, t, 0, 0.35, "fade");
      st.n.at(t, 0.1);
      if (st.t) st.t.at(t, 0.45, c.fps);
      if (st.s) L.enter(st.s, t, 0.9, 0.4, "rise");
      H.outAll([st.b], t, c, 0.25);
    },
    cues: (c) => [L.cue(0.1 - L.SWISH_LEAD, "swish", 2), L.cue(0.45, "hit", 3), ...(c.p.title ? [L.cue(0.45, "pop", 1)] : [])],
  };

  /* image params: src (project-relative), title, caption, fit ("cover"|"contain"), push (zoom amount, 0.06) */
  /* The styled image. params.treat: auto (default) | none. params.frame: auto | cover | card.
     paper ground: a large halftone card with a shadow. dark ground: the photo covers the frame,
     graded, on a far plane (parallax), with a slow Ken Burns, a scrim and a glow frame. */
  function styledImage(root, c) {
    const p = c.p, u = c.u, st = { styled: true }, url = L.projUrl(p.src), dark = H.dark(c), paper = c.texture === "paper" || p.bg === "paper";
    const treat = p.treat !== "none" && p.treat !== false;
    const cover = p.frame === "cover" || (p.frame !== "card" && !paper);
    st.cover = cover;
    if (paper && p.bg !== "none") L.layer(L.paperBg(root, c), -800);
    if (cover) {
      const w = (st.wrap = el("div", "abs", root));
      L.pos(w, 0, 0, c.W, c.H);
      w.style.overflow = "hidden"; w.style.background = "#000";
      st.img = el("img", "", w);
      st.img.style.cssText = `position:absolute;inset:0;width:100%;height:100%;object-fit:${p.fit || "cover"};transform-origin:50% 45%`;
      L.setImg(st.img, url);
      if (treat) st.img.style.filter = dark ? "contrast(1.14) saturate(.82) brightness(.74)" : "contrast(1.1) saturate(.9)";
      L.layer(w, -320);
      if (treat) {
        const t1 = el("div", "abs", root); L.pos(t1, 0, 0, c.W, c.H); t1.style.background = `linear-gradient(180deg, rgba(0,0,0,.8) 0%, rgba(0,0,0,.28) 34%, rgba(0,0,0,.14) 58%, rgba(0,0,0,.82) 100%), radial-gradient(ellipse 80% 60% at 50% 50%, ${L.hexA(C.accent, 0.12)}, transparent 75%)`; t1.dataset.nolint = "";
        L.layer(t1, -40);
        st.glow = el("div", "abs", root);
        const m = 26 * u;
        L.pos(st.glow, m, m, c.W - 2 * m, c.H - 2 * m);
        st.glow.style.cssText += `;border:${3 * u}px solid ${L.hexA(C.accent, 0.8)};border-radius:${18 * u}px;box-shadow:0 0 ${34 * u}px ${L.hexA(C.accent, 0.5)}, inset 0 0 ${60 * u}px ${L.hexA(C.accent, 0.22)}`;
        L.layer(st.glow, -20);
      }
    }
    const b = (st.b = H.box(root, c, { gap: 24, justify: "flex-start" }));
    if (p.title) { st.h = H.headline(b, p.title, c, { size: H.scale(c)[1], lines: 2 }); st.h.node.style.color = cover ? "#fff" : L.inkOn(dark); if (cover) st.h.node.style.textShadow = `0 ${3 * u}px ${22 * u}px rgba(0,0,0,.8)`; }
    const gapBox = H.fill(el("div", "", b));
    gapBox.style.position = "relative"; gapBox.style.width = "100%";
    if (!cover) {
      st.fr = el("div", "", gapBox);
      st.fr.style.cssText = `position:absolute;inset:0;filter:drop-shadow(${14 * u}px ${20 * u}px ${26 * u}px rgba(0,0,0,.5));transform-origin:50% 50%`;
      const f = el("div", "abs", st.fr);
      f.style.cssText += `;inset:0;overflow:hidden;background:#ddd;clip-path:${L.chamferClip(c.safe.w, Math.max(200 * u, gapBox.clientHeight), 44 * u)}`;
      st.img = el("img", "", f);
      st.img.style.cssText = `position:absolute;inset:0;width:100%;height:100%;object-fit:${p.fit || "cover"};transform-origin:50% 45%`;
      L.setImgFx(st.img, url, treat ? (paper ? { bw: true, halftone: true, contrast: p.contrast || 1.3 } : { bw: false, halftone: false }) : null);
      if (treat && !paper) st.img.style.filter = "contrast(1.1) saturate(.92)";
    }
    if (p.caption) { st.cap = el("div", "lede", b, L.md(p.caption)); st.cap.style.cssText += `;font-size:${(c.P ? 56 : 36) * u}px;line-height:1.12;font-weight:650;color:${cover ? "#fff" : L.inkOn(dark)};${cover ? `text-shadow:0 ${2 * u}px ${14 * u}px rgba(0,0,0,.85)` : ""}`; }
    if (p.credit) { st.cr = el("div", "foot", b, L.esc(p.credit)); st.cr.style.cssText += `;font-size:${Math.max(24, H.scale(c)[3]) * u}px;${cover ? "color:rgba(255,255,255,.72)" : ""}`; }
    return st;
  }
  function styledImageAt(st, t, c) {
    const p = c.p, push = p.push != null ? p.push : 0.12;
    if (st.h) st.h.at(t, 0);
    /* a slow Ken Burns: linear, with a drift across the subject */
    const k = clamp(t / c.dur), sc = (st.cover ? 1.06 : 1.03) + push * k, dx = (p.pan != null ? p.pan : 26) * c.u * (0.5 - k), dy = 16 * c.u * (k - 0.5);
    st.img.style.transform = `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px) scale(${sc.toFixed(4)})`;
    if (st.wrap) st.wrap.style.opacity = clamp(t * 8 + 0.4);
    if (st.fr) L.resolveIn(st.fr, t, 0.05, 0.3, { from: 0.86, blur: 8, spring: L.SPRING.premium, pre: "rotate(-1.2deg)" });
    if (st.glow) st.glow.style.opacity = (0.72 + 0.2 * Math.sin((t * Math.PI * 2) / 1.1)).toFixed(3);
    if (st.cap) L.resolveIn(st.cap, t, 0.75, 0.3, { from: 0.94, blur: 6, spring: L.SPRING.premium });
    if (st.cr) L.enter(st.cr, t, 1.4, 0.4, "fade");
    H.outAll([st.b, st.fr], t, c);
  }

  S.image = {
    build(root, c) {
      if (c.styled || c.P) return styledImage(root, c);
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { gap: 22, justify: "flex-start" }));
      if (p.title) st.h = H.headline(b, p.title, c, { size: H.scale(c)[1], lines: 2 });
      const fr = el("div", "card", b);
      fr.style.cssText += ";position:relative;flex:1;width:100%;min-height:0;overflow:hidden;padding:0";
      st.img = el("img", "", fr);
      st.img.style.cssText = `position:absolute;inset:0;width:100%;height:100%;object-fit:${p.fit || "cover"};transform-origin:50% 45%`;
      L.setImg(st.img, "/project/" + String(p.src || "").replace(/^\/+/, ""));
      st.fr = fr;
      if (p.caption) { st.cap = el("div", "lede", b, L.md(p.caption)); st.cap.style.fontSize = H.scale(c)[2] * c.u + "px"; }
      if (p.credit) { st.cr = el("div", "foot", b, L.esc(p.credit)); st.cr.style.fontSize = H.scale(c)[3] * c.u + "px"; }
      return st;
    },
    update(st, t, c) {
      if (st.styled) return styledImageAt(st, t, c);
      if (st.h) st.h.at(t, 0);
      L.enter(st.fr, t, c.beat, 0.6);
      st.img.style.transform = `scale(${1 + (c.p.push != null ? c.p.push : 0.06) * (t / c.dur)})`;
      if (st.cap) L.enter(st.cap, t, c.beat * 3, 0.5);
      if (st.cr) L.enter(st.cr, t, c.beat * 3, 0.5, "fade");
      H.outAll([st.b], t, c);
    },
    cues: (c) => [{ lt: c.beat, type: "whoosh" }],
  };
})();
