/* Card scenes: terminal (typed commands), end (logo, name, tagline, links,
   call to action) and thumbnail (a single 1280×720 still for YouTube). */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const H = L.H;
  const { el, seg, eo, ei, expo, back, clamp, C } = L;

  /* ================================================================ terminal
     params: kicker, title, lines:[{cmd} | {out} | {comment}], chips[], cps (chars/s) */
  S.terminal = {
    build(root, c) {
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { gap: 26 }));
      const land = c.mode === "land";
      const wrap = el("div", "", b);
      wrap.style.cssText = `display:flex;flex-direction:${land ? "row" : "column"};gap:${48 * c.u}px;align-items:${land ? "center" : "stretch"};width:100%`;
      const head = el("div", "", wrap);
      head.style.flex = land ? "0 0 42%" : "none";
      if (p.kicker) st.k = H.kicker(head, p.kicker, c);
      if (p.title) { st.h = H.headline(head, p.title, c, { size: H.scale(c)[1] * 1.15, lines: 3, w: land ? c.safe.w * 0.42 : c.safe.w }); st.h.node.style.marginTop = 18 * c.u + "px"; }
      st.term = el("div", "term", wrap);
      st.term.style.flex = "1";
      if (c.P) { H.fill(wrap); b.style.justifyContent = "flex-start"; }
      st.term.innerHTML = `<div class="tb"><i></i><i></i><i></i><span style="font-size:${Math.max(28, 16 * c.u)}px">terminal</span></div><div class="tl"></div>`;
      st.tl = st.term.querySelector(".tl");
      st.tl.style.cssText = `padding:${28 * c.u}px ${32 * c.u}px;font-size:${(c.P ? 46 : 32) * c.u}px;line-height:1.6;white-space:pre-wrap;min-height:${(p.lines || []).length * 32 * 1.7 * c.u + 60 * c.u}px`;
      if (p.chips) { st.row = el("div", "row", b); st.chips = p.chips.map((t) => { const e = el("span", "chip", st.row, L.esc(t)); e.style.fontSize = 24 * c.u + "px"; return e; }); }
      // schedule: each command types at cps, then a beat of rest
      const cps = p.cps || 16;
      let at = c.beat * 2;
      st.plan = (p.lines || []).map((ln) => {
        const text = ln.cmd != null ? ln.cmd : ln.out != null ? ln.out : "# " + (ln.comment || "");
        const kind = ln.cmd != null ? "cmd" : ln.out != null ? "out" : "comment";
        const start = at, end = kind === "cmd" ? start + text.length / cps : start + 0.05;
        at = end + (kind === "cmd" ? c.beat * 1.5 : c.beat * 0.5);
        return { text, kind, start, end, cps };
      });
      st.done = at;
      return st;
    },
    update(st, t, c) {
      if (st.k) L.enter(st.k, t, 0, 0.4);
      if (st.h) st.h.at(t, c.beat * 0.5);
      const tp = expo(seg(t, c.beat, c.beat + 0.7));
      st.term.style.opacity = clamp(tp * 2); st.term.style.transform = `translateY(${(1 - tp) * 40}px)`;
      const blink = Math.floor(t * 2.2) % 2 === 0;
      let h = "";
      st.plan.forEach((q, i) => {
        if (t < q.start) return;
        const last = i === st.plan.length - 1 || t < st.plan[i + 1].start;
        if (q.kind === "cmd") {
          const n = Math.min(q.text.length, Math.floor((t - q.start) * q.cps));
          h += (h ? "\n" : "") + `<span class="p">$</span> ${L.esc(q.text.slice(0, n))}`;
          if (last) h += `<span style="display:inline-block;width:.55em;height:1.05em;vertical-align:-0.2em;background:${n < q.text.length || blink ? "#ff6a3d" : "transparent"}"></span>`;
        } else h += (h ? "\n" : "") + `<span class="${q.kind === "out" ? "g" : "c"}">${L.esc(q.text)}</span>`;
      });
      st.tl.innerHTML = h;
      (st.chips || []).forEach((e, i) => L.enter(e, t, Math.min(c.dur - 1, st.done) + i * 0.25, 0.45, "pop"));
      H.outAll([st.b], t, c);
    },
    cues: (c) => {
      const out = [{ lt: c.beat, type: "whoosh" }];
      const cps = c.p.cps || 16;
      let at = c.beat * 2;
      for (const ln of c.p.lines || []) {
        if (ln.cmd != null) { const d = ln.cmd.length / cps; out.push({ lt: at, type: "typing", len: d }, { lt: at + d + 0.3, type: "enter" }); at += d + c.beat * 1.5; }
        else at += c.beat * 0.5;
      }
      return out;
    },
  };

  /* ================================================================ end
     params: name (default brand.name), tagline, links[], cta, logo (bool) */
  /* where the hook's hero sits in frame 0's scene, so the close can land on it */
  function hookHero(c) {
    const f = c.first;
    if (!f || f === c) return null;
    const it = (f.p.items || [])[0];
    const src = it && it.src ? it : f.p.front && f.p.front.src ? { ...f.p.front, kind: "card" } : null;
    if (!src) return null;
    let rect = null;
    if (f.def === window.SCENES.collage) {
      /* build the hook off-screen: its layout is deterministic, whichever worker gets here first */
      const w = L.el("div", "fv-world", document.getElementById("stage"));
      L.pos(w, 0, 0, c.W, c.H); w.style.visibility = "hidden"; w.dataset.p = L.rig.P(f);
      const st = f.def.build(w, f);
      const s = st.items[0] && st.items[0].s;
      if (s) rect = { cx: s.cx, cy: s.cy, w: s.w, rot: s.rot };
      w.remove();
    }
    return { it: src, rect };
  }

  S.end = {
    build(root, c) {
      if (c.P || c.styled) return strongEnd(root, c);
      const p = c.p, st = {};
      const b = (st.b = H.box(root, c, { center: true, gap: 26 }));
      if (p.logo !== false) { st.logo = L.logo(b, c.brand, 200 * c.u); st.logo.node.style.position = "relative"; }
      st.name = el("div", "display", b, L.md(p.name || c.brand.name || ""));
      const px = H.scale(c)[0] * 1.05 * c.u;
      L.fit(st.name, px, px * 0.4, c.safe.w, px * 1.15);
      if (p.tagline) { st.tag = el("div", "serif-it", b, L.md(p.tagline)); st.tag.style.cssText += `;font-size:${H.scale(c)[1] * 0.82 * c.u}px;color:${C.muted};max-width:${c.safe.w}px;line-height:1.15`; }
      if (p.links && p.links.length) { st.row = el("div", "row", b); st.row.style.justifyContent = "center"; st.links = p.links.map((u, i) => { const e = el("span", "chip mono" + (i === 0 ? " ink" : ""), st.row, L.esc(u)); e.style.fontSize = 28 * c.u + "px"; e.style.padding = `${14 * c.u}px ${26 * c.u}px`; return e; }); }
      if (p.cta) { st.cta = el("div", "mono", b, `<span style="color:${C.accent}">→</span> ${L.esc(p.cta)}`); st.cta.style.cssText += `;font-size:${28 * c.u}px;color:${C.muted}`; }
      return st;
    },
    update(st, t, c) {
      if (st.strong) return strongEndAt(st, t, c);
      const B = c.beat;
      if (st.logo) st.logo.at(t, 0);
      L.enter(st.name, t, B, 0.7, "rise", 40);
      if (st.tag) L.enter(st.tag, t, B * 2, 0.6);
      (st.links || []).forEach((e, i) => L.enter(e, t, B * (3 + i * 0.6), 0.5, "pop"));
      if (st.cta) L.enter(st.cta, t, B * 5, 0.6, "fade");
    },
    cues: (c) => [{ lt: 0, type: "swell" }, { lt: c.beat, type: "hit" }, ...(c.p.links || []).map((_, i) => ({ lt: c.beat * (3 + i * 0.6), type: "pop" }))],
  };

  /* The strong close (tall mode, or any styled video): huge title, a clear CTA pill, the
     hook's hero waiting below and growing back to its hook pose as the film ends, so the
     last frame leads into the first. A badge only with a logo file or an explicit name. */
  function strongEnd(root, c) {
    const p = c.p, u = c.u, st = { strong: true };
    const tex = p.bg || c.texture;
    if (tex === "paper") L.layer(L.paperBg(root, c), -800);
    else if (tex === "dark") { st.bg = L.darkBg(root, c); L.layer(st.bg.node, -800); }
    const dark = H.dark(c), ink = L.inkOn(dark);
    const box = (st.box = el("div", "abs", root));
    L.pos(box, c.safe.x, c.safe.y, c.safe.w);
    box.style.cssText += `;display:flex;flex-direction:column;align-items:center;text-align:center;gap:${30 * u}px`;
    const showLogo = p.logo === true || (p.logo !== false && c.brand && (c.brand.logo || c.brand.explicit_name));
    if (showLogo) { st.logo = L.logo(box, c.brand, 120 * u); st.logo.node.style.position = "relative"; }
    /* a list in `lines` is the title's lines; a number is the line limit. Blank names (spaces, zero-width) count as none */
    const clean = (s) => String(s == null ? "" : s).replace(/[\s\u200b-\u200d\ufeff]+/g, " ").trim();
    const listed = Array.isArray(p.lines) ? p.lines.map(String).join("\n") : "";
    const pLines = +p.lines > 0 ? +p.lines : 4;
    let name = clean(listed) ? listed : clean(p.name) ? p.name : clean(c.brand.name) ? c.brand.name : "";
    /* no title at all: the tagline takes the hero's place */
    const tagHero = !name && p.tagline;
    if (tagHero) name = p.tagline;
    if (name) {
      st.T = L.revealWords(box, name, "fv-label", { rise: 30 });
      st.T.node.style.lineHeight = "0.98";
      st.T.node.style.color = ink;
      st.fitT = (max) => L.fitHero(st.T.node, { w: c.safe.w, lines: pLines, max, min: 60 * u });
      st.fitT((p.size || 210) * u);
      st.T.node.dataset.lb = "1";
    }
    if (p.tagline && !tagHero) { st.tag = el("div", "serif-it", box, L.md(p.tagline)); st.tag.style.cssText += `;font-size:${(c.P ? 62 : 48) * u}px;color:${ink};max-width:${c.safe.w}px;line-height:1.1`; st.tag.dataset.lb = "1"; }
    if (p.links && p.links.length) { st.row = el("div", "row", box); st.links = p.links.map((q, i) => { const e = el("span", "chip mono" + (i === 0 ? " ink" : ""), st.row, L.esc(q)); e.style.fontSize = 30 * u + "px"; return e; }); }
    if (p.cta) { st.cta = el("div", "fv-cta", box, `<span>${L.esc(p.cta)}</span><span class="ar">${L.icon("arrow", 66 * u, "#fff", 2.6)}</span>`); st.cta.style.fontSize = (c.P ? 66 : 50) * u + "px"; st.cta.style.transformOrigin = "50% 50%"; st.ar = st.cta.querySelector(".ar"); st.ar.style.display = "grid"; }
    L.layer(box, 120);
    /* the hook's hero below the type */
    const hook = p.loop === false ? null : hookHero(c);
    if (hook) {
      const it = hook.it, url = L.projUrl(it.src), info = it.kind === "cutout" ? L.cutInfo(url) : null;
      const asp = info ? (info.h * info.nh) / (info.w * info.nw) : 1.2;
      /* below the pill, clear of it: the title gives way until the hero has room */
      const need = 300 * u, bot = c.safe.y + c.safe.h - 8 * u;
      if (st.fitT) { let mx = (p.size || 210) * u; while (c.safe.y + box.offsetHeight + 28 * u + need > bot && mx > 90 * u) { mx *= 0.92; st.fitT(mx); } }
      const top = c.safe.y + box.offsetHeight + 28 * u;
      const room = Math.max(120 * u, bot - top);
      /* the small pose tilts 5 degrees: keep its rotated box inside the room */
      const rw = Math.min(c.safe.w * 0.62, room / (asp * 0.996 + 0.087));
      const node = (st.hero = el("div", "fv-cut", root));
      const R0 = hook.rect || { cx: c.W / 2, cy: c.safe.y + c.safe.h / 2, w: rw * 1.7, rot: it.rot || 0 };
      /* the node is laid out at the hook's size and pose; it rests scaled down below the type */
      L.pos(node, R0.cx - R0.w / 2, R0.cy - (R0.w * asp) / 2, R0.w, R0.w * asp);
      const img = el("img", "", node);
      if (info) { const iw = R0.w / info.w, ih = (R0.w * asp) / info.h; img.style.cssText = `position:absolute;left:${(-info.x * iw).toFixed(2)}px;top:${(-info.y * ih).toFixed(2)}px;width:${iw.toFixed(2)}px;height:${ih.toFixed(2)}px;max-width:none`; }
      L.setImgFx(img, url, it.halftone === false ? null : { bw: true, halftone: true, contrast: it.contrast || 1.3 });
      node.style.filter = st.base = L.cutFilter({ outline: it.outline != null ? it.outline : 5 * u, shadow: { x: 14 * u, y: 20 * u, blur: 24 * u, a: 0.5 } });
      node.style.transformOrigin = "50% 50%";
      st.pose = { scale: rw / R0.w, dx: c.safe.x + c.safe.w * 0.5 - R0.cx, dy: top + room / 2 - R0.cy, rot: R0.rot || 0 };
      L.layer(node, -60);
      c.loops = true;
      st.hasHero = true;
      st.heroes = [{ node, url, d: it, kind: it.kind, rot: R0.rot || 0, w: R0.w, h: R0.w * asp, base: st.base, fx: it.halftone === false ? null : { bw: true, halftone: true, contrast: it.contrast || 1.3 }, match: true }];
    }
    /* no hero to come back to: the block sits in the optical centre, in an accent ring */
    if (!st.hasHero) {
      const bh = box.offsetHeight, room = c.safe.h;
      box.style.top = c.safe.y + Math.max(0, (room - bh) * 0.46) + "px";
      const R = Math.min(c.safe.w * 0.54, (bh + 260 * u) / 2), cx = c.safe.x + c.safe.w / 2, cy = c.safe.y + Math.max(0, (room - bh) * 0.46) + bh / 2;
      const ring = (st.ring = L.svg("svg", { width: c.W, height: c.H }, root));
      ring.style.cssText = "position:absolute;left:0;top:0;overflow:visible";
      st.ringA = L.svg("circle", { cx, cy, r: R, fill: "none", stroke: C.accent, "stroke-width": 7 * u, "stroke-linecap": "round", pathLength: 1, "stroke-dasharray": "1 1", "stroke-dashoffset": 1, opacity: 0.55, transform: `rotate(-90 ${cx} ${cy})` }, ring);
      st.ringG = L.svg("g", {}, ring);
      st.ringC = { cx, cy, R };
      L.layer(ring, -60);
      st.amb = H.ambient(root, c);
    }
    return st;
  }
  function strongEndAt(st, t, c) {
    const u = c.u, hand = c.loops ? c.dur - Math.min(0.85, c.dur * 0.2) : Infinity;
    /* the title clears for the growing hero; the CTA stays until the last 0.3 s */
    const out = L.EASE.exit(seg(t, hand, hand + 0.2)), ctaOut = c.loops ? L.EASE.exit(seg(t, c.dur - 0.3, c.dur - 0.12)) : 0;
    if (st.bg) st.bg.at(t);
    if (st.amb) st.amb(t);
    if (st.ringA) { st.ringA.setAttribute("stroke-dashoffset", (1 - L.EASE.camera(seg(t, 0.1, Math.min(1.6, c.dur - 0.4)))).toFixed(4)); st.ring.style.transform = `rotate(${(t * 6).toFixed(2)}deg)`; st.ring.style.transformOrigin = `${st.ringC.cx}px ${st.ringC.cy}px`; }
    if (st.logo) st.logo.at(t, 0);
    if (st.T) st.T.at(t, 0.05);
    if (st.tag) L.resolveIn(st.tag, t, 0.4, 0.3, { from: 0.94, blur: 6, spring: L.SPRING.premium });
    (st.links || []).forEach((e, i) => L.enter(e, t, 0.5 + i * 0.06, 0.4, "pop"));
    if (st.cta) {
      L.resolveIn(st.cta, t, 0.62, 0.3, { from: 0.6, blur: 6, spring: L.SPRING.playful });
      /* the pill breathes, the arrow nudges every beat */
      if (t > 0.62) { const beat = ((t - 0.62) / c.beat) % 2; st.cta.style.transform += ` scale(${(1 + 0.03 * Math.exp(-3.2 * beat)).toFixed(4)})`; st.ar.style.transform = `translateX(${(14 * u * Math.exp(-3.2 * beat)).toFixed(2)}px)`; }
    }
    for (const e of [st.T && st.T.node, st.tag, st.row, st.logo && st.logo.node]) if (e) e.style.opacity = out > 0 ? 1 - out : (e === (st.tag || null) ? e.style.opacity : 1);
    if (st.cta && ctaOut > 0) st.cta.style.opacity = 1 - ctaOut;
    if (st.hero) {
      const P = st.pose, a = L.spring(t - 0.25, L.SPRING.premium), grow = L.EASE.camera(seg(t, hand, c.dur));
      const scale = P.scale * (0.82 + 0.18 * a) * (1 + 0.012 * Math.max(0, t - 0.25)), rest = 7 * Math.sin((t * Math.PI * 2) / 4.3);
      const s = L.lerp(scale, 1, grow), dx = L.lerp(P.dx, 0, grow), dy = L.lerp(P.dy + rest * u, 0, grow), r = L.lerp(P.rot - 5 + 0.8 * Math.sin((t * Math.PI * 2) / 6.1), P.rot, grow);
      st.hero.style.visibility = "visible"; /* a match flight hides it while it flies */
      st.hero.style.opacity = clamp((t - 0.25) * 8);
      st.hero.style.transform = `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px) rotate(${r.toFixed(3)}deg) scale(${s.toFixed(4)})`;
    }
  }

  const p0 = (c) => c.p || {};
  /* A strong thumbnail: huge title (3 words is ideal) in one accent, the hero big on the right,
     hard contrast. params: title, accent (word), kicker, badge, image | hero (project path), hero_cut (bool). */
  function strongThumb(root, c) {
    const p = c.p, W = c.W, Hh = c.H, st = {}, u = Hh / 720;
    const dark = H.dark(c), ink = L.inkOn(dark), src = p.image || p.hero || p.src;
    const bg = el("div", "abs", root); L.pos(bg, 0, 0, W, Hh);
    bg.style.background = dark ? `radial-gradient(ellipse 70% 90% at 72% 50%, ${L.hexA(C.accent, 0.32)} 0%, #0b0b0c 62%)` : c.texture === "paper" ? "transparent" : `radial-gradient(ellipse 70% 90% at 72% 50%, #ffffff 0%, ${C.bg} 70%)`;
    if (c.texture === "paper" && !dark) L.paperBg(root, c);
    root.appendChild(bg);
    const hasHero = !!src;
    if (hasHero) {
      const url = L.projUrl(src), cut = /\.(png|webp|svg)$/i.test(String(src)) && p.hero_cut !== false;
      const fr = el("div", "abs", root);
      if (cut) {
        L.pos(fr, W * 0.5, Hh * 0.03, W * 0.48, Hh * 0.94);
        const img = el("img", "", fr); img.style.cssText = "width:100%;height:100%;object-fit:contain";
        L.setImg(img, url);
        fr.style.filter = L.cutFilter({ outline: 5 * u, shadow: { x: 12 * u, y: 16 * u, blur: 26 * u, a: 0.6 } });
      } else {
        L.pos(fr, W * 0.54, Hh * 0.08, W * 0.5, Hh * 0.84);
        fr.style.cssText += `;overflow:hidden;transform:rotate(3deg);border:${6 * u}px solid ${C.accent};box-shadow:0 ${14 * u}px ${44 * u}px rgba(0,0,0,.6)`;
        const img = el("img", "", fr); img.style.cssText = "width:100%;height:100%;object-fit:cover;filter:contrast(1.15) saturate(1.1)";
        L.setImg(img, url);
      }
    }
    const tw = W * (hasHero ? 0.52 : 0.9), tx = hasHero ? W * 0.04 : W * 0.05;
    const box = el("div", "abs", root);
    L.pos(box, tx, 0, tw);
    box.style.cssText += `;display:flex;flex-direction:column;gap:${16 * u}px;${hasHero ? "" : "align-items:center;text-align:center"}`;
    if (p.kicker) { const k = el("div", "", box, L.esc(p.kicker)); k.style.cssText += `;font:800 ${30 * u}px var(--display);letter-spacing:.02em;text-transform:uppercase;color:${ink};opacity:.82`; }
    /* accent: the *marked* word, or the word named in params.accent */
    const acc = String(p.accent || "").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
    const words = String(p.title || c.brand.name || "").split(/\s+/).filter(Boolean).map((w) => {
      const marked = /^\*.*\*[.,!?:;]*$/.test(w), bare = w.replace(/\*/g, "");
      const hit = marked || (acc && bare.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "") === acc);
      return hit ? `<span class="fv-sw" style="display:inline-block;background:${C.accent};color:${L.isDark(C.accent) ? "#fff" : "#0b0b0b"};padding:0 .14em .04em;margin:0 -.02em">${L.esc(bare)}</span>` : `<span class="fv-sw" style="display:inline-block">${L.esc(bare)}</span>`;
    }).join(" ");
    const h = el("div", "", box, words);
    h.style.cssText += `;font:900 100px/1.03 var(--display);letter-spacing:-.035em;text-transform:uppercase;color:${ink};text-shadow:0 ${5 * u}px ${18 * u}px ${dark ? "rgba(0,0,0,.7)" : "rgba(255,255,255,.3)"}`;
    L.fitHero(h, { w: tw, lines: 3, max: 220 * u, min: 60 * u });
    const badge = String(p.badge || "").trim();
    if (badge && !/^(none|n\/a|null|-+)$/i.test(badge)) { const bd = el("div", "", box, L.esc(badge)); bd.style.cssText += `;align-self:${hasHero ? "flex-start" : "center"};font:800 ${30 * u}px var(--display);color:${dark ? "#0b0b0b" : "#fff"};background:${ink};padding:.24em .6em;border-radius:.3em`; }
    /* the whole block stays in frame */
    box.style.height = "auto";
    { let px = parseFloat(h.style.fontSize); while (box.offsetHeight > Hh * 0.92 && px > 50 * u) { px -= 4 * u; h.style.fontSize = px + "px"; } box.style.top = (Hh - box.offsetHeight) / 2 + "px"; }
    return st;
  }

  /* ================================================================ thumbnail (static)
     params: kicker, title (2–5 words!), accent (one word to colour), badge, shot | image */
  S.thumbnail = {
    build(root, c) {
      if (!(p0(c).shot && L.META[p0(c).shot])) return strongThumb(root, c);
      const p = c.p, st = {};
      const W = c.W, Hh = c.H;
      if (p.shot && L.META[p.shot]) {
        st.w = L.Win(root, { shot: p.shot, url: p.url || "" });
        st.w.layout(W * 0.5, Hh * 0.2, W * 0.56);
        st.w.node.style.transform = "rotate(-3deg)";
      } else if (p.image) {
        const fr = el("div", "card", root); L.pos(fr, W * 0.52, Hh * 0.16, W * 0.52, Hh * 0.68); fr.style.cssText += ";overflow:hidden;transform:rotate(-3deg)";
        const img = el("img", "", fr); img.style.cssText = "width:100%;height:100%;object-fit:cover"; L.setImg(img, "/project/" + p.image);
      }
      const top = el("div", "abs", root); L.pos(top, 56, 44); top.style.cssText += ";display:flex;align-items:center;gap:14px";
      const lg = L.logo(top, c.brand, 46); lg.node.style.position = "relative";
      el("span", "", top, `<b style="font-size:28px;letter-spacing:-.03em;color:${C.ink}">${L.esc(c.brand.name || "")}</b>`);
      const h = el("div", "abs", root); L.pos(h, 56, Hh * 0.24, W * (st.w || p.image ? 0.48 : 0.86));
      const words = String(p.title || "").split(/\s+/).map((w) => (p.accent && w.replace(/[^\w]/g, "").toLowerCase() === p.accent.toLowerCase() ? `<span class="acc">${L.esc(w)}</span>` : L.esc(w))).join(" ");
      h.innerHTML = (p.kicker ? `<div class="mono" style="font-size:18px;letter-spacing:.2em;color:${C.muted};text-transform:uppercase">${L.esc(p.kicker)}</div>` : "") + `<div class="display t" style="line-height:.96;margin-top:18px">${words}</div>`;
      L.fit(h.querySelector(".t"), 120, 40, W * (st.w || p.image ? 0.48 : 0.86), Hh * 0.5);
      if (p.badge) { const bd = el("div", "abs", root); L.pos(bd, 56, Hh * 0.8); bd.innerHTML = `<span class="chip ink" style="font-size:24px"><i class="d"></i>${L.esc(p.badge)}</span>`; }
      return st;
    },
    update(st, t, c) {
      if (st && st.w) st.w.at(Math.max(0, L.META[c.p.shot].count - 10), { z: 1.15, x: L.META[c.p.shot].w / 2, y: L.META[c.p.shot].h * 0.4 }, { cursor: false });
    },
    cues: () => [],
  };
})();
