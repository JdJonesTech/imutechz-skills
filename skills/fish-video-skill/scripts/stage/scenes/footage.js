/* footage: a stock clip played from pre-extracted frames
   (build/clips/<clip>/f_00001.jpg ... at the project fps), full-bleed or in a
   card, with treatments.

   params:
     clip       clip id (folder under build/clips)
     frames     number of extracted frames
     fps        frames per second of the extraction (default: the project fps)
     from       first frame (1-based, default 1)
     speed      playback rate (1)
     loop       true = wrap around, false = hold the last frame (default true)
     fit        full | card (default full)
     treat      [bw, halftone, grain]   (also accepted as booleans: bw: true, ...)
     grade      warm | cool | teal-orange
     title, kicker, title_at (beat, 1), title_pos (bottom|top|center)
     push       slow push-in amount (.06)
     shape      card shape: chamfer | octagon | rect (card fit) */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const H = L.H;
  const { el, seg, eo, ei, clamp, C } = L;

  const GRADE = {
    warm: "sepia(.22) saturate(1.18) hue-rotate(-8deg) contrast(1.05)",
    cool: "saturate(.9) hue-rotate(10deg) brightness(1.02) contrast(1.06)",
    "teal-orange": "url(#fv-tealorange) saturate(1.15) contrast(1.05)",
  };
  const has = (p, k) => (Array.isArray(p.treat) ? p.treat.includes(k) : p[k] === true || (typeof p.treat === "string" && p.treat.split(/[ ,]+/).includes(k)));
  L.clipUrl = (clip, n) => `/project/build/clips/${clip}/f_${String(n).padStart(5, "0")}.jpg`;

  S.footage = {
    busy: true,
    cam: "drift",
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      const card = p.fit === "card";
      let x = 0, y = 0, w = c.W, h = c.H;
      if (card) {
        st.bg = c.texture === "paper" || !p.bg || p.bg === "paper" ? L.paperBg(root, c) : L.studioBg(root, c);
        w = c.safe.w * (c.P ? 1 : 0.78); h = Math.min(c.safe.h * 0.72, w * (c.P ? 1.15 : 0.5625), c.safe.h - (p.title ? 190 * u : 0));
        if (!c.P) w = Math.min(w, h / 0.5625);
        x = c.safe.x + (c.safe.w - w) / 2; y = c.safe.y + (p.title ? 0 : (c.safe.h - h) * 0.5);
      }
      const wrap = (st.wrap = el("div", "abs", root));
      L.pos(wrap, x, y, w, h);
      if (card) wrap.style.filter = `drop-shadow(${12 * u}px ${18 * u}px ${24 * u}px rgba(0,0,0,.5))`;
      /* depth: full-bleed footage is an overscanned plane so camera moves never show an edge */
      if (card) L.layer(st.bg, -800);
      L.layer(wrap, 0, card ? {} : { cover: true, overscan: 1.08 });
      const fr = (st.fr = el("div", "abs", wrap));
      L.pos(fr, 0, 0, w, h);
      fr.style.overflow = "hidden";
      fr.style.background = "#111";
      if (card) {
        const cut = p.shape === "octagon" ? Math.min(w, h) * 0.29 : p.shape === "rect" ? 0 : Math.min(w, h) * 0.08;
        fr.style.clipPath = L.chamferClip(w, h, cut);
        const off = 12 * u;
        const ol = L.svg("svg", { width: w + off * 2, height: h + off * 2 }, root);
        ol.style.cssText = `position:absolute;left:${x - off}px;top:${y - off}px;overflow:visible`;
        L.svg("polygon", { points: L.chamfer(w + off * 2, h + off * 2, cut ? cut + off * 0.6 : 0), fill: "none", stroke: "#111", "stroke-width": 1.6 * u, opacity: 0.75 }, ol);
        st.ol = ol;
      }
      st.img = el("img", "", fr);
      st.img.style.cssText = `position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transform-origin:50% 45%`;
      const f = [];
      if (has(p, "bw") || has(p, "halftone")) f.push("grayscale(1) contrast(1.18)");
      if (p.grade && GRADE[p.grade] && !(has(p, "bw") || has(p, "halftone"))) f.push(GRADE[p.grade]);
      st.img.style.filter = f.join(" ");
      if (has(p, "halftone")) {
        /* a printed screen: 45deg dot grid multiplied over the B&W frame */
        const ht = el("div", "abs", fr);
        const D = Math.hypot(w, h);
        L.pos(ht, (w - D) / 2, (h - D) / 2, D, D);
        const cell = Math.max(6, Math.round(7 * u));
        ht.style.cssText += `;transform:rotate(45deg);mix-blend-mode:multiply;opacity:.55;background-image:radial-gradient(circle, rgba(0,0,0,.9) 0 32%, transparent 46%);background-size:${cell}px ${cell}px`;
        const lift = el("div", "abs", fr); L.pos(lift, 0, 0, w, h);
        lift.style.cssText += ";mix-blend-mode:screen;background:rgba(255,255,255,.08)";
      }
      if (has(p, "grain")) { st.grain = el("div", "abs", fr); L.pos(st.grain, 0, 0, w, h); st.grain.style.cssText += ";mix-blend-mode:overlay;opacity:.22;background-size:220px 220px"; }
      /* a scrim under the title */
      if (p.title && !card) {
        const sc = el("div", "abs", fr); L.pos(sc, 0, 0, w, h);
        sc.style.background = p.title_pos === "top" ? "linear-gradient(180deg, rgba(0,0,0,.6) 0%, transparent 45%)" : "linear-gradient(0deg, rgba(0,0,0,.72) 0%, rgba(0,0,0,.25) 35%, transparent 60%)";
        const vg = el("div", "abs", fr); L.pos(vg, 0, 0, w, h);
        vg.style.background = "radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,.45) 100%)";
      }
      if (p.title) {
        const tb = (st.tb = el("div", "abs", root));
        const pos = p.title_pos || (card ? "below" : "bottom");
        const tw = c.safe.w;
        if (card) L.pos(tb, c.safe.x, y + h + 40 * u, tw);
        else L.pos(tb, c.safe.x, pos === "top" ? c.safe.y : pos === "center" ? c.safe.y + c.safe.h * 0.35 : c.safe.y + c.safe.h * 0.6, tw, pos === "top" ? undefined : c.safe.h * 0.4);
        tb.style.cssText += `;display:flex;flex-direction:column;gap:${12 * u}px;justify-content:${pos === "top" ? "flex-start" : "flex-end"};align-items:flex-start`;
        if (p.kicker) { st.k = el("div", "fv-chip fv-tag", tb, L.md(p.kicker)); st.k.style.fontSize = 30 * u + "px"; if (!card) { st.k.style.background = C.accent; } }
        st.h = L.slideWords(tb, p.title, "fv-label", { dist: 360 * u });
        st.h.node.style.color = card ? "#111" : "#fff";
        if (!card) st.h.node.style.textShadow = "0 4px 24px rgba(0,0,0,.45)";
        const px = (p.size || 108) * u;
        L.fit(st.h.node, px, px * 0.4, tw, px * 2.1);
        L.layer(tb, 160);
      }
      if (st.ol) L.layer(st.ol, 0);
      return st;
    },
    update(st, t, c) {
      const p = c.p;
      const fps = p.fps || c.fps, n = Math.max(1, p.frames || 1), f0 = p.from || 1;
      let k = Math.floor(t * fps * (p.speed || 1) + 1e-6);
      k = p.loop === false ? Math.min(k, n - 1) : ((k % n) + n) % n;
      L.setImg(st.img, L.clipUrl(p.clip, f0 + k));
      st.img.style.transform = `scale(${(1.02 + (p.push != null ? p.push : 0.06) * L.eio(t / c.dur)).toFixed(5)})`;
      if (st.grain) { const f = Math.round(t * c.fps); st.grain.style.backgroundImage = `url(${L.grainTiles()[f % 6]})`; st.grain.style.backgroundPosition = `${(f * 53) % 220}px ${(f * 29) % 220}px`; }
      if (p.fit === "card") { L.resolveIn(st.wrap, t, 0, 0.6, { blur: 12 }); if (st.ol) st.ol.style.opacity = eo(seg(t, 0.2, 0.6)); }
      else { const q = L.portal(seg(t, 0, 0.6)); st.wrap.style.opacity = clamp(q * 2); }
      const ta = (p.title_at != null ? p.title_at : 1) * c.beat;
      if (st.k) L.enter(st.k, t, ta - 0.15, 0.4, "pop");
      if (st.h) st.h.at(t, ta);
      H.outAll([st.tb], t, c, 0.25);
    },
    cues(c) {
      const ta = (c.p.title_at != null ? c.p.title_at : 1) * c.beat;
      return [L.cue(-L.SWISH_LEAD, "whoosh", 2), ...(c.p.title ? [L.cue(ta - L.SWISH_LEAD, "swish", 2), L.cue(ta + 0.2, "hit", 3)] : []), ...(c.p.kicker ? [L.cue(ta - 0.15, "pop", 1)] : [])];
    },
  };
})();
