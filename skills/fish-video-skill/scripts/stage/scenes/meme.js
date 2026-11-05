/* meme: a picture or a short clip with top and bottom captions, a punch-in and an optional reaction inset.
   Everything is a pure function of the scene time t (no Math.random, Date, timers or CSS animations).

   params:
     src        picture (path under the project, e.g. assets/meme/drake.png)   one of src | clip
     clip       clip id (build/clips/<clip>, cut with `memes cut`); frames and fps come from its meta.json
     frames, fps   only to override meta.json
     top, bottom   caption text ("\n" breaks a line); plain text, never markup
     top_at, bottom_at   beat the caption lands on (default 1 and 2.5)
     fit        contain (default: the whole picture over a blurred copy of itself) | full (fill the frame)
     focus      zoom centre as "x% y%" (default "50% 45%")
     punch      extra zoom on the punch-in (default 0.14; 0 turns it off)
     punch_on   beat of the punch-in (default 2.5)
     inset      {src | clip, at (beat, default 3), pos: br | bl | tr | tl (default br), size (share of the frame, default 0.3)}
     sound      cue type played with the punch-in (any type `sounds list` shows); none by default
     sound_at   beat the sound lands on (default punch_on)
     credit     one line of credit under the frame (shown when given)
     loop       true (default) wraps a clip; false holds its last frame */
(function () {
  "use strict";
  const S = (window.SCENES = window.SCENES || {});
  const { el, seg, clamp } = L;
  const url = (p) => "/project/" + String(p || "").replace(/^\/+/, "");

  /* frame n (0-based) of a clip or the single picture */
  function show(img, q, t, fps, loop) {
    if (q.clip) {
      const n = Math.max(1, q.frames || 1);
      let k = Math.floor(t * (q.fps || fps) + 1e-6);
      k = loop === false ? Math.min(k, n - 1) : ((k % n) + n) % n;
      L.setImg(img, L.clipUrl(q.clip, 1 + k));
    } else L.setImg(img, url(q.src));
  }

  S.meme = {
    busy: true,
    cam: "drift",
    build(root, c) {
      const p = c.p, u = c.u, st = {};
      st.bg = c.texture === "paper" ? L.paperBg(root, c) : L.studioBg(root, c);
      L.layer(st.bg, -800);
      /* the frame: the safe area, minus a credit line when there is one */
      const credH = p.credit ? 48 * u : 0;
      const fx = c.safe.x, fy = c.safe.y, fw = c.safe.w, fh = c.safe.h - credH;
      st.main = { src: p.src, clip: p.clip, frames: p.frames, fps: p.fps };
      const wrap = (st.wrap = el("div", "abs", root));
      L.pos(wrap, fx, fy, fw, fh);
      wrap.style.cssText += ";overflow:hidden;background:#111;border-radius:" + 14 * u + "px;box-shadow:0 " + 14 * u + "px " + 40 * u + "px rgba(0,0,0,.45)";
      L.layer(wrap, 0);
      const full = p.fit === "full";
      if (!full) {
        st.back = el("img", "", wrap);
        st.back.style.cssText = "position:absolute;inset:-6%;width:112%;height:112%;object-fit:cover;filter:blur(" + 28 * u + "px) brightness(.55)";
      }
      st.img = el("img", "", wrap);
      st.img.style.cssText = `position:absolute;inset:0;width:100%;height:100%;object-fit:${full ? "cover" : "contain"};transform-origin:${p.focus || "50% 45%"}`;
      /* captions: heavy outlined type, fitted to the frame, plain text only */
      const cap = (text, pos) => {
        const n = el("div", "", wrap);
        n.textContent = String(text);
        n.style.cssText = `position:absolute;left:4%;width:92%;${pos}:3%;text-align:center;color:#fff;text-transform:uppercase;white-space:pre-line;overflow-wrap:break-word;` +
          `font:900 100px/1.05 "Inter","Noto Sans Devanagari",sans-serif;-webkit-text-stroke:${0.1}em #000;paint-order:stroke fill;transform-origin:50% ${pos === "top" ? "0" : "100%"}`;
        L.fit(n, 100 * u * (c.P ? 0.8 : 1), 28 * u, fw * 0.92, fh * 0.28);
        return n;
      };
      if (p.top) st.top = cap(p.top, "top");
      if (p.bottom) st.bottom = cap(p.bottom, "bottom");
      /* the reaction inset: a small framed picture in a corner */
      const ins = p.inset;
      if (ins && (ins.src || ins.clip)) {
        const side = Math.min(fw, fh) * clamp(ins.size != null ? ins.size : 0.3, 0.12, 0.5), m = 22 * u, pos = ins.pos || "br";
        const x = pos.includes("l") ? m : fw - side - m, y = pos.includes("t") ? m + (st.top ? fh * 0.2 : 0) : fh - side - m - (st.bottom ? fh * 0.2 : 0);
        const box = (st.ins = el("div", "abs", wrap));
        L.pos(box, x, Math.max(m, y), side, side);
        box.style.cssText += `;overflow:hidden;border:${5 * u}px solid #fff;border-radius:${18 * u}px;box-shadow:0 ${8 * u}px ${24 * u}px rgba(0,0,0,.5);background:#111;transform-origin:50% 50%`;
        st.insImg = el("img", "", box);
        st.insImg.style.cssText = "position:absolute;inset:0;width:100%;height:100%;object-fit:cover";
        st.insQ = ins;
      }
      if (p.credit) {
        st.cr = el("div", "abs foot", root);
        st.cr.textContent = String(p.credit);
        L.pos(st.cr, fx, fy + fh + 6 * u, fw);
        st.cr.style.cssText += `;font-size:${Math.max(30 * u, 30)}px;opacity:.85`;
        L.layer(st.cr, 160);
      }
      return st;
    },
    update(st, t, c) {
      const p = c.p, beat = c.beat;
      show(st.img, st.main, t, c.fps, p.loop);
      if (st.back) show(st.back, st.main, t, c.fps, p.loop);
      /* the picture drifts in slowly and punches in on the beat */
      const tp = (p.punch_on != null ? p.punch_on : 2.5) * beat, amt = p.punch != null ? p.punch : 0.14;
      const z = 1 + 0.03 * (t / c.dur) + amt * L.spring(t - tp, L.SPRING.playful);
      st.img.style.transform = `scale(${z.toFixed(5)})`;
      L.resolveIn(st.wrap, t, 0, 0.45, { blur: 10 });
      const slam = (n, at) => {
        if (!n) return;
        const q = L.back(seg(t, at, at + 0.22), 1.8);
        n.style.opacity = clamp(seg(t, at, at + 0.08)).toFixed(3);
        n.style.transform = `scale(${(1.35 - 0.35 * q).toFixed(4)})`;
      };
      slam(st.top, (p.top_at != null ? p.top_at : 1) * beat);
      slam(st.bottom, (p.bottom_at != null ? p.bottom_at : 2.5) * beat);
      if (st.ins) {
        const at = (st.insQ.at != null ? st.insQ.at : 3) * beat;
        show(st.insImg, st.insQ, Math.max(0, t - at), c.fps, true);
        const q = L.back(seg(t, at, at + 0.35), 1.7);
        st.ins.style.opacity = clamp(seg(t, at, at + 0.1)).toFixed(3);
        st.ins.style.transform = `scale(${q.toFixed(4)}) rotate(${(-4 * (1 - q)).toFixed(3)}deg)`;
      }
      if (st.cr) L.enter(st.cr, t, beat * 2, 0.4, "fade");
      L.H.outAll([st.wrap, st.cr].filter(Boolean), t, c, 0.25);
    },
    cues(c) {
      const p = c.p, b = c.beat, out = [L.cue(-L.SWISH_LEAD, "whoosh", 2)];
      const tp = (p.punch_on != null ? p.punch_on : 2.5) * b;
      if ((p.punch != null ? p.punch : 0.14) > 0) out.push(L.cue(tp, "hit", 2));
      if (p.sound) out.push(L.cue((p.sound_at != null ? p.sound_at : p.punch_on != null ? p.punch_on : 2.5) * b, String(p.sound), 3));
      if (p.inset && (p.inset.src || p.inset.clip)) out.push(L.cue((p.inset.at != null ? p.inset.at : 3) * b, "pop", 2));
      return out;
    },
  };
})();
