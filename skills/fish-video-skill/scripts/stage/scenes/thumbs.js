/* Thumbnail layouts: `thumbnail` with params.layout.

   The plain `thumbnail` scene (cards.js) is still what runs when no layout is named. With
   params.layout this file draws one of five designed templates, at any size (1280x720 for a
   video thumbnail, 1080x1920 for a vertical cover). Used by `fishvideo thumb make`.

     layout: subject   huge title in one accent word + a subject (cut-out with outline and glow, or a framed picture)
             number    one giant figure, a short label under it
             split     before / after on a diagonal split, each half labelled
             caption   a full-bleed frame, a dark scrim, the caption low and left
             frame     the best frame of the video in a card, the title beside it

   params: title, accent (the word to mark; "*word*" also marks), kicker, badge,
           image (subject or frame, project path), baked (true: the PNG already has its outline and glow),
           number, label (number layout), before, after, before_label, after_label (split), bg (dark | light)

   Every layout keeps its text inside c.safe, keeps the bottom-right corner free of text (the duration
   stamp a feed puts there) and is a pure function of time: nothing moves. */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const H = L.H;
  const { el, C } = L;
  const base = S.thumbnail;

  /* Fitting is measured twice: once at build and once again at the first frame, when the fonts and the
     layout are final. Both are pure functions of the page, so the picture never depends on timing. */
  const fits = [];
  function fit(h, w, lines, min, after) {
    const nlines = () => new Set([...h.querySelectorAll(".fv-sw")].map((e) => e.offsetTop)).size || 1;
    const run = () => {
      let px = parseFloat(h.style.fontSize);
      for (let i = 0; i < 40 && px > min && (h.scrollWidth > w + 1 || nlines() > lines); i++) { px *= 0.96; h.style.fontSize = px + "px"; }
      if (after) after();
    };
    run();
    fits.push(run);
  }
  const k = (c) => (c.P ? c.W / 1080 : c.H / 720);
  const zones = (c, art) => {
    const s = c.safe;
    if (!art) return { text: { x: s.x, y: s.y, w: s.w, h: s.h }, art: null, center: true };
    if (c.P) return { text: { x: s.x, y: s.y, w: s.w, h: s.h * 0.4 }, art: { x: s.x, y: s.y + s.h * 0.42, w: s.w, h: s.h * 0.58 }, center: false };
    return { text: { x: s.x, y: s.y, w: s.w * 0.52, h: s.h }, art: { x: s.x + s.w * 0.54, y: s.y, w: s.w * 0.46, h: s.h }, center: false };
  };
  const box = (root, z) => { const b = el("div", "abs", root); L.pos(b, z.x, z.y, z.w, z.h); return b; };
  const isCut = (src, p) => /\.(png|webp|svg)$/i.test(String(src || "")) && p.hero_cut !== false;

  function background(root, c, dark, tint) {
    const bg = el("div", "abs", root); L.pos(bg, 0, 0, c.W, c.H);
    const at = c.P ? "50% 70%" : "76% 50%";
    bg.style.background = dark ? `radial-gradient(ellipse 70% 80% at ${at}, ${L.hexA(tint || C.accent, 0.34)} 0%, #0b0b0c 66%)` : `radial-gradient(ellipse 70% 80% at ${at}, #ffffff 0%, ${C.bg} 74%)`;
    return bg;
  }

  /* the title as words, the marked one on an accent plate */
  function titleHTML(p, c) {
    const acc = String(p.accent || "").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
    return String(p.title || c.brand.name || "").split(/\s+/).filter(Boolean).map((w) => {
      const marked = /^\*.*\*[.,!?:;]*$/.test(w), bare = w.replace(/\*/g, "");
      const hit = marked || (acc && bare.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "") === acc);
      return hit ? `<span class="fv-sw" style="display:inline-block;background:${C.accent};color:${L.isDark(C.accent) ? "#fff" : "#0b0b0b"};padding:0 .14em .04em;margin:0 -.02em">${L.esc(bare)}</span>` : `<span class="fv-sw" style="display:inline-block">${L.esc(bare)}</span>`;
    }).join(" ");
  }

  function kicker(parent, p, c, ink) {
    if (!p.kicker) return null;
    const e = el("div", "", parent, L.esc(p.kicker));
    e.style.cssText += `;font:800 ${30 * k(c)}px var(--display);letter-spacing:.02em;text-transform:uppercase;color:${ink};opacity:.85`;
    return e;
  }
  function badge(parent, p, c, dark, ink, align) {
    const t = String(p.badge || "").trim();
    if (!t || /^(none|n\/a|null|-+)$/i.test(t)) return null;
    const e = el("div", "", parent, L.esc(t));
    e.style.cssText += `;align-self:${align};font:800 ${30 * k(c)}px var(--display);color:${dark ? "#0b0b0b" : "#fff"};background:${ink};padding:.24em .6em;border-radius:.3em`;
    return e;
  }

  /* a column of kicker, title, badge: the title as large as the zone allows, the column centred in it */
  function textColumn(root, c, z, p, dark, o = {}) {
    const ink = o.ink || L.inkOn(dark), b = box(root, z), u = k(c);
    b.style.cssText += `;display:flex;flex-direction:column;gap:${16 * u}px;justify-content:center;${z.center || o.center ? "align-items:center;text-align:center" : ""}`;
    b.style.height = "auto";
    kicker(b, p, c, ink);
    const h = el("div", "", b, titleHTML(p, c));
    h.style.cssText += `;font:900 100px/1.03 var(--display);letter-spacing:-.035em;text-transform:${o.upper === false ? "none" : "uppercase"};color:${ink};text-shadow:0 ${5 * u}px ${18 * u}px ${dark ? "rgba(0,0,0,.7)" : "rgba(255,255,255,.3)"}`;
    L.fitHero(h, { w: z.w, lines: o.lines || 3, max: (o.max || 220) * u, min: 56 * u });
    badge(b, p, c, dark, ink, z.center || o.center ? "center" : "flex-start");
    const place = () => { b.style.top = z.y + (z.h - b.offsetHeight) / 2 + "px"; };
    const run = () => { let px = parseFloat(h.style.fontSize); while (b.offsetHeight > z.h && px > 48 * u) { px -= 4 * u; h.style.fontSize = px + "px"; } place(); };
    fit(h, z.w, o.lines || 3, 48 * u, run);
    return { box: b, h };
  }

  /* ------------------------------------------------------------ subject */
  function subject(root, c) {
    const p = c.p, u = k(c), dark = p.bg ? p.bg === "dark" : true;
    background(root, c, dark);
    const src = p.image || p.hero || p.src, z = zones(c, !!src);
    if (src) {
      const fr = box(root, z.art), url = L.projUrl(src), img = el("img", "", fr);
      L.setImg(img, url);
      if (isCut(src, p)) {
        img.style.cssText = "width:100%;height:100%;object-fit:contain";
        fr.style.filter = p.baked ? "" : L.cutFilter({ outline: 6 * u, shadow: { x: 12 * u, y: 16 * u, blur: 26 * u, a: 0.6 } }) + ` drop-shadow(0 0 ${34 * u}px ${L.hexA(C.accent, 0.55)})`;
      } else {
        const pad = 14 * u;
        L.pos(fr, z.art.x + pad, z.art.y + pad, z.art.w - 2 * pad, z.art.h - 2 * pad);
        fr.style.cssText += `;overflow:hidden;transform:rotate(3deg);border:${6 * u}px solid ${C.accent};box-shadow:0 ${14 * u}px ${44 * u}px rgba(0,0,0,.6)`;
        img.style.cssText = "width:100%;height:100%;object-fit:cover;filter:contrast(1.15) saturate(1.1)";
      }
    }
    textColumn(root, c, z.text, p, dark);
    return {};
  }

  /* ------------------------------------------------------------ number */
  function number(root, c) {
    const p = c.p, u = k(c), dark = p.bg ? p.bg === "dark" : true, ink = L.inkOn(dark);
    background(root, c, dark);
    const s = c.safe, b = box(root, { x: s.x, y: s.y, w: s.w, h: s.h });
    b.style.cssText += `;display:flex;flex-direction:column;justify-content:center;align-items:${c.P ? "center" : "flex-start"};gap:${10 * u}px;${c.P ? "text-align:center" : ""}`;
    b.style.height = "auto";
    kicker(b, p, c, ink);
    /* "66 days": the figure big, the unit beside it in the ink colour at a third of the size */
    const m = /^\s*([^\p{L}]*?\d[^\p{L}]*?)\s*(\p{L}.*)?$/u.exec(String(p.number || "").trim() || "0");
    const n = el("div", "", b, `${L.esc(m ? m[1] : String(p.number))}${m && m[2] ? `<span style="font-size:.34em;letter-spacing:0;margin-left:.2em;color:${ink};text-transform:uppercase;text-shadow:none">${L.esc(m[2])}</span>` : ""}`);
    n.style.cssText += `;font:900 100px/.95 var(--display);letter-spacing:-.05em;color:${C.accent};text-shadow:0 ${8 * u}px ${28 * u}px ${L.hexA(C.accent, 0.45)}`;
    L.fitHero(n, { w: s.w * (c.P ? 1 : 0.9), lines: 1, max: (c.P ? 420 : 400) * u, min: 120 * u });
    const lab = el("div", "", b, titleHTML({ title: p.label || p.title, accent: p.accent }, c));
    lab.style.cssText += `;font:900 100px/1.04 var(--display);letter-spacing:-.03em;text-transform:uppercase;color:${ink}`;
    L.fitHero(lab, { w: s.w * (c.P ? 1 : 0.72), lines: 2, max: Math.min(parseFloat(n.style.fontSize) / 3, 130 * u), min: 48 * u });
    badge(b, p, c, dark, ink, c.P ? "center" : "flex-start");
    const run = () => { let px = parseFloat(n.style.fontSize); while (b.offsetHeight > s.h && px > 100 * u) { px -= 8 * u; n.style.fontSize = px + "px"; } b.style.top = s.y + (s.h - b.offsetHeight) / 2 + "px"; };
    fit(lab, s.w * (c.P ? 1 : 0.72), 2, 40 * u);
    fit(n, s.w * (c.P ? 1 : 0.9), 1, 100 * u, run);
    return {};
  }

  /* ------------------------------------------------------------ split */
  function split(root, c) {
    const p = c.p, u = k(c), dark = true, W = c.W, Hh = c.H;
    background(root, c, dark);
    const pic = (parent, src, css, x, y, w, h, clip) => {
      const f = el("div", "abs", parent); L.pos(f, x, y, w, h);
      f.style.cssText += `;overflow:hidden;clip-path:${clip};background:#222`;
      if (src) { const img = el("img", "", f); img.style.cssText = `width:100%;height:100%;object-fit:cover;${css}`; L.setImg(img, L.projUrl(src)); }
      return f;
    };
    const a = p.before || p.image, b = p.after || p.image;
    const gap = 8 * u;
    if (c.P) {
      pic(root, a, p.before ? "" : "filter:grayscale(1) brightness(.6) blur(3px)", 0, 0, W, Hh, `polygon(0 0, 100% 0, 100% ${50 - 4}%, 0 ${50 + 4}%)`);
      pic(root, b, p.after ? "" : "filter:saturate(1.25) contrast(1.1)", 0, 0, W, Hh, `polygon(0 ${50 + 4}%, 100% ${50 - 4}%, 100% 100%, 0 100%)`);
    } else {
      pic(root, a, p.before ? "" : "filter:grayscale(1) brightness(.6) blur(3px)", 0, 0, W, Hh, `polygon(0 0, 54% 0, 46% 100%, 0 100%)`);
      pic(root, b, p.after ? "" : "filter:saturate(1.25) contrast(1.1)", 0, 0, W, Hh, `polygon(54.6% 0, 100% 0, 100% 100%, 46.6% 100%)`);
    }
    /* labels */
    const s = c.safe;
    const chip = (txt, x, y, alignRight, hot) => {
      const e = el("div", "abs", root, L.esc(txt)); L.pos(e, x, y);
      e.style.cssText += `;font:900 ${44 * u}px var(--display);letter-spacing:.04em;text-transform:uppercase;padding:.2em .6em;border-radius:.3em;color:${hot ? (L.isDark(C.accent) ? "#fff" : "#0b0b0b") : "#f5f5f5"};background:${hot ? C.accent : "rgba(20,20,22,.82)"};${alignRight ? "transform:translateX(-100%)" : ""}`;
    };
    chip(p.before_label || "Before", s.x, s.y, false, false);
    if (c.P) chip(p.after_label || "After", s.x, s.y + s.h * 0.52, false, true);
    else chip(p.after_label || "After", s.x + s.w, s.y, true, true);
    /* the title on a plate across the lower part, short of the bottom-right corner */
    const plate = el("div", "abs", root); const pw = c.P ? s.w : s.w * 0.7;
    L.pos(plate, s.x, 0, pw);
    plate.style.cssText += `;background:rgba(11,11,12,.86);border-left:${10 * u}px solid ${C.accent};padding:${16 * u}px ${28 * u}px;border-radius:${6 * u}px`;
    const h = el("div", "", plate, titleHTML(p, c));
    h.style.cssText += `;font:900 100px/1.03 var(--display);letter-spacing:-.03em;text-transform:uppercase;color:#f5f5f5`;
    L.fitHero(h, { w: pw - 56 * u, lines: 2, max: 120 * u, min: 52 * u });
    fit(h, pw - 56 * u, 2, 44 * u, () => { plate.style.top = s.y + s.h - plate.offsetHeight - (c.P ? 0 : 4 * u) + "px"; });
    return {};
  }

  /* ------------------------------------------------------------ caption */
  function caption(root, c) {
    const p = c.p, u = k(c), W = c.W, Hh = c.H, s = c.safe, dark = true;
    const bg = el("div", "abs", root); L.pos(bg, 0, 0, W, Hh);
    bg.style.background = `radial-gradient(ellipse 80% 90% at 30% 40%, ${L.hexA(C.accent, 0.4)}, #0b0b0c 75%)`;
    if (p.image) { const img = el("img", "abs", root); L.pos(img, 0, 0, W, Hh); img.style.cssText += `;object-fit:cover;transform:scale(1.04);filter:blur(${5 * u}px) brightness(.8) saturate(1.1)`; L.setImg(img, L.projUrl(p.image)); }  /* soft: the frame carries its own words, which must not compete with the caption */
    const sc = el("div", "abs", root); L.pos(sc, 0, 0, W, Hh);
    sc.style.background = (c.P ? "linear-gradient(0deg, rgba(8,8,9,.96) 0%, rgba(8,8,9,.9) 46%, rgba(8,8,9,.55) 62%, rgba(8,8,9,0) 80%)" : "linear-gradient(90deg, rgba(8,8,9,.94) 0%, rgba(8,8,9,.9) 52%, rgba(8,8,9,.6) 66%, rgba(8,8,9,0) 86%)");
    const corner = el("div", "abs", root); L.pos(corner, W * 0.7, Hh * 0.72, W * 0.3, Hh * 0.28);
    corner.style.background = "radial-gradient(ellipse at 100% 100%, rgba(8,8,9,.8), rgba(8,8,9,0) 70%)"; /* the corner a feed covers with a time stamp */
    const z = c.P ? { x: s.x, y: s.y + s.h * 0.48, w: s.w, h: s.h * 0.52 } : { x: s.x, y: s.y, w: s.w * 0.58, h: s.h };
    textColumn(root, c, z, p, dark, { ink: "#f5f5f5", lines: 3, max: 190 });
    return {};
  }

  /* ------------------------------------------------------------ frame */
  function frame(root, c) {
    const p = c.p, u = k(c), dark = p.bg ? p.bg === "dark" : true;
    background(root, c, dark);
    const src = p.image, z = zones(c, !!src);
    if (src) {
      const fr = box(root, z.art), img = el("img", "", fr), pad = 16 * u;
      L.pos(fr, z.art.x + pad, z.art.y + pad, z.art.w - 2 * pad, z.art.h - 2 * pad);
      fr.style.cssText += `;overflow:hidden;transform:rotate(-2deg);border:${8 * u}px solid ${dark ? "#f5f5f5" : "#fff"};border-radius:${10 * u}px;box-shadow:0 ${18 * u}px ${50 * u}px rgba(0,0,0,.65),0 0 0 ${4 * u}px ${C.accent}`;
      img.style.cssText = "width:100%;height:100%;object-fit:cover";
      L.setImg(img, L.projUrl(src));
    }
    textColumn(root, c, z.text, p, dark);
    return {};
  }

  const LAYOUTS = { subject, number, split, caption, frame };
  S.thumbnail = {
    build(root, c) {
      const f = LAYOUTS[String((c.p || {}).layout || "")];
      return f ? f(root, c) : base.build(root, c);
    },
    update(st, t, c) { if (LAYOUTS[String((c.p || {}).layout || "")]) { for (const f of fits.splice(0)) f(); } else if (base.update) base.update(st, t, c); },
    cues: () => [],
  };
})();
