/*! reels.js v1.0.0 · ImuTechz · MIT
 *
 * Five example reels for ScrollMotion.film(). Each reel is
 *   { name, draw(ctx, t, env) }
 * and is a pure function of its local progress t ∈ [0, 1] and env:
 * no state between frames, no clock, no Math.random. Scroll back and
 * the reel plays backwards, frame for frame.
 *
 * Every reel lays itself out inside env.free — the largest rectangle
 * that misses every caption and HUD — so the drawing never needs to
 * be clipped (the engine clips anyway, as a safety net).
 *
 *   orbit  — one timeline, many moving parts
 *   path   — a route that draws (and un-draws) with the scroll
 *   stack  — staggered bars that build and settle
 *   wave   — phase from p, rhythm without a clock
 *   close  — scattered particles resolve onto one mark
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./scroll-motion.js"));
  else root.ScrollReels = factory(root.ScrollMotion);
})(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : this, function (SM) {
  "use strict";
  const { clamp01, lerp, seg, smoothstep, ease, stagger, hash, rgba, mix, route, strokeTo } = SM;
  const TAU = Math.PI * 2;
  const mono = (px) => `500 ${px}px ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace`;

  /* ── 1. orbit ─────────────────────────────────────────── */
  const orbit = {
    name: "orbit",
    draw(ctx, t, env) {
      const { free: F, colors: C } = env;
      const cx = F.x + F.w / 2, cy = F.y + F.h / 2;
      const R = Math.min(F.w, F.h) * 0.46;
      if (R < 8) return;
      const grow = ease.outCubic(seg(t, 0, 0.3));
      const tilt = lerp(1, 0.36, ease.inOut(seg(t, 0.15, 0.85)));
      const rings = [{ r: 0.42, m: 5 }, { r: 0.7, m: 8 }, { r: 0.98, m: 12 }];

      // rings, back halves first
      rings.forEach((ring, k) => {
        const r = R * ring.r * lerp(0.6, 1, ease.outCubic(seg(t, 0.05 + k * 0.08, 0.45 + k * 0.08)));
        ctx.strokeStyle = rgba(C.ink, 0.14);
        ctx.lineWidth = 1;
        ctx.setLineDash(k === 2 ? [2, 7] : []);
        ctx.beginPath(); ctx.ellipse(cx, cy, r, r * tilt, 0, 0, TAU); ctx.stroke();
      });
      ctx.setLineDash([]);

      // satellites, depth-sorted
      const sats = [];
      rings.forEach((ring, k) => {
        const r = R * ring.r;
        for (let j = 0; j < ring.m; j++) {
          const a = (j / ring.m) * TAU + t * Math.PI * (k % 2 ? -1 : 1) * (1 + k * 0.35) + k;
          const z = Math.sin(a);
          const on = ease.outBack(stagger(seg(t, 0.08, 0.7), j + k * 4, 12 + 8, 0.3));
          sats.push({ x: cx + Math.cos(a) * r, y: cy + z * r * tilt, z, k, on });
        }
      });
      sats.sort((a, b) => a.z - b.z);

      // spokes appear in the second half
      const spokes = seg(t, 0.45, 0.8);
      if (spokes > 0) {
        ctx.lineWidth = 1;
        for (const s of sats) {
          if (s.k !== 1) continue;
          ctx.strokeStyle = rgba(C.accent, 0.28 * spokes * (0.5 + 0.5 * (s.z + 1) / 2));
          ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(lerp(cx, s.x, spokes), lerp(cy, s.y, spokes)); ctx.stroke();
        }
      }

      for (const s of sats) {
        if (s.on <= 0) continue;
        const depth = (s.z + 1) / 2;
        const size = lerp(2.2, 5.5, depth) * s.on * (R > 120 ? 1 : 0.7);
        ctx.fillStyle = s.k === 1 ? rgba(C.accent, lerp(0.45, 1, depth)) : rgba(C.ink, lerp(0.25, 0.8, depth));
        ctx.beginPath(); ctx.arc(s.x, s.y, Math.max(0, size), 0, TAU); ctx.fill();
      }

      // the core, with a halo
      const cr = R * 0.13 * grow;
      const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr * 3.2 + 1);
      halo.addColorStop(0, rgba(C.accent, 0.35)); halo.addColorStop(1, rgba(C.accent, 0));
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(cx, cy, cr * 3.2 + 1, 0, TAU); ctx.fill();
      ctx.fillStyle = rgba(C.accent2, 1); ctx.beginPath(); ctx.arc(cx, cy, cr, 0, TAU); ctx.fill();
      ctx.fillStyle = rgba(C.surface, 1); ctx.beginPath(); ctx.arc(cx, cy, cr * 0.36, 0, TAU); ctx.fill();

      if (R > 90) {
        ctx.font = mono(11); ctx.textAlign = "center"; ctx.fillStyle = rgba(C.ink, 0.5);
        ctx.fillText("p " + env.p.toFixed(2), cx, cy + R * tilt + 26);
      }
    },
  };

  /* ── 2. path ──────────────────────────────────────────── */
  const STEPS = ["pin", "measure", "draw", "caption", "drum", "verify", "ship"];
  const path = {
    name: "path",
    draw(ctx, t, env) {
      const { free: F, colors: C } = env;
      if (F.w < 40 || F.h < 40) return;
      const n = STEPS.length, tall = F.h > F.w * 1.05;
      const nodes = [];
      for (let i = 0; i < n; i++) {
        const u = i / (n - 1);
        nodes.push(tall
          ? [F.x + F.w * (0.5 + Math.sin(u * Math.PI * 3.2) * 0.34), F.y + F.h * (0.06 + u * 0.88)]
          : [F.x + F.w * (0.04 + u * 0.92), F.y + 30 + (F.h - 74) * (0.5 + Math.sin(u * Math.PI * 2.4 + 0.4) * 0.5)]);
      }
      const { samples, at, total } = route(nodes);
      const L = seg(t, 0.04, 0.92) * total; // a lead-in and a hold so the ends get screen time

      // the route ahead: a faint dotted preview
      ctx.setLineDash([2, 9]); ctx.lineCap = "round"; ctx.lineWidth = 2;
      ctx.strokeStyle = rgba(C.ink, 0.18);
      ctx.beginPath(); samples.forEach(([x, y], k) => (k ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.stroke();
      ctx.setLineDash([]);

      // the route travelled
      let head = samples[0];
      if (L > 0) {
        const g = ctx.createLinearGradient(nodes[0][0], nodes[0][1], nodes[n - 1][0], nodes[n - 1][1]);
        g.addColorStop(0, rgba(C.accent2)); g.addColorStop(1, rgba(C.accent));
        ctx.strokeStyle = g; ctx.lineWidth = env.mobile ? 3 : 4;
        head = strokeTo(ctx, samples, L);
      }

      // milestones pop with an overshoot as the head reaches them
      ctx.textAlign = "center";
      ctx.font = mono(env.mobile ? 10.5 : 12);
      for (let i = 0; i < n; i++) {
        const [x, y] = nodes[i];
        const reach = clamp01((L - at[i] + total * 0.012) / (total * 0.04));
        if (reach <= 0) {
          ctx.fillStyle = rgba(C.bg); ctx.strokeStyle = rgba(C.ink, 0.32); ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.arc(x, y, 5, 0, TAU); ctx.fill(); ctx.stroke();
          ctx.fillStyle = rgba(C.ink, 0.36);
        } else {
          const r = (env.mobile ? 8 : 11) * ease.outBack(reach);
          ctx.fillStyle = rgba(C.accent, 0.16 * reach);
          ctx.beginPath(); ctx.arc(x, y, r * 2.1, 0, TAU); ctx.fill();
          ctx.fillStyle = rgba(C.accent2); ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
          ctx.fillStyle = rgba(C.surface); ctx.beginPath(); ctx.arc(x, y, r * 0.36, 0, TAU); ctx.fill();
          ctx.fillStyle = rgba(C.ink, 0.5 + 0.4 * reach);
        }
        if (tall) { ctx.textAlign = x > F.x + F.w / 2 ? "right" : "left"; ctx.fillText(STEPS[i], x + (x > F.x + F.w / 2 ? -20 : 20), y + 4); }
        else ctx.fillText(STEPS[i], x, y + (i % 2 === 0 ? 34 : -24));
      }

      // the head: a glow that leads the line (no pulse: frames are pure)
      if (L > 0 && L < total) {
        const gr = ctx.createRadialGradient(head[0], head[1], 0, head[0], head[1], 26);
        gr.addColorStop(0, rgba(C.accent, 0.55)); gr.addColorStop(1, rgba(C.accent, 0));
        ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(head[0], head[1], 26, 0, TAU); ctx.fill();
        ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(head[0], head[1], 3.2, 0, TAU); ctx.fill();
      }
    },
  };

  /* ── 3. stack ─────────────────────────────────────────── */
  const stack = {
    name: "stack",
    draw(ctx, t, env) {
      const { free: F, colors: C } = env;
      if (F.w < 40 || F.h < 40) return;
      const n = env.mobile || F.w < 420 ? 9 : 14;
      const vals = Array.from({ length: n }, (_, i) => 0.22 + 0.68 * smoothstep(0.15 + 0.85 * ((i + 1) / n)) * (0.75 + 0.25 * hash(i, 3)));
      const base = F.y + F.h * 0.9, top = F.y + F.h * 0.08, gap = F.w / n, bw = gap * 0.56;
      const build = seg(t, 0, 0.72);

      // grid
      ctx.strokeStyle = rgba(C.ink, 0.08); ctx.lineWidth = 1;
      for (let g = 0; g <= 4; g++) {
        const y = lerp(base, top, g / 4);
        ctx.beginPath(); ctx.moveTo(F.x, y); ctx.lineTo(F.x + F.w, y); ctx.stroke();
      }
      ctx.strokeStyle = rgba(C.ink, 0.35);
      ctx.beginPath(); ctx.moveTo(F.x, base); ctx.lineTo(F.x + F.w, base); ctx.stroke();

      // bars: each has its own window inside the reel, and lands with an ease
      const tops = [];
      let best = 0;
      vals.forEach((v, i) => { if (v > vals[best]) best = i; });
      for (let i = 0; i < n; i++) {
        const k = ease.outCubic(stagger(build, i, n, 0.32));
        const h = (base - top) * vals[i] * k;
        const x = F.x + gap * i + (gap - bw) / 2;
        const grd = ctx.createLinearGradient(0, base - h, 0, base);
        const c = i === best ? C.accent : mix(C.ink, C.accent, i / (n - 1) * 0.55);
        grd.addColorStop(0, rgba(c, i === best ? 1 : 0.85)); grd.addColorStop(1, rgba(c, i === best ? 0.75 : 0.35));
        ctx.fillStyle = grd;
        const rr = Math.min(6, bw / 2, h / 2);
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(x, base - h, bw, h, [rr, rr, 0, 0]); else ctx.rect(x, base - h, bw, h);
        ctx.fill();
        tops.push([x + bw / 2, base - h - 10]);
      }

      // a trend line through the tops, drawn once the bars have landed
      const line = seg(t, 0.62, 0.96);
      if (line > 0) {
        const { samples, total } = route(tops, 16);
        ctx.strokeStyle = rgba(C.accent2, 0.9); ctx.lineWidth = 2; ctx.setLineDash([]);
        const head = strokeTo(ctx, samples, line * total);
        ctx.fillStyle = rgba(C.accent2); ctx.beginPath(); ctx.arc(head[0], head[1], 4, 0, TAU); ctx.fill();
      }

      if (F.w > 260) {
        ctx.font = mono(11); ctx.textAlign = "left"; ctx.fillStyle = rgba(C.ink, 0.5);
        ctx.fillText(String(Math.round(build * 100)).padStart(3, " ") + "%", F.x, top - 10);
      }
    },
  };

  /* ── 4. wave ──────────────────────────────────────────── */
  const wave = {
    name: "wave",
    draw(ctx, t, env) {
      const { free: F, colors: C } = env;
      if (F.w < 40 || F.h < 40) return;
      const rows = env.mobile ? 9 : 13;
      const ampMax = (F.h / rows) * 1.1; // rows are inset by the largest swing, so no crest leaves F
      const amp0 = ampMax * lerp(0.25, 1, smoothstep(seg(t, 0, 0.35)));
      const rowY = (r) => F.y + ampMax + (F.h - 2 * ampMax) * (r / (rows - 1));
      const phase = t * TAU * 1.5;
      const step = Math.max(3, F.w / 140);
      ctx.lineWidth = env.mobile ? 1.4 : 1.8; ctx.lineCap = "round";
      for (let r = 0; r < rows; r++) {
        const y0 = rowY(r);
        const c = mix(C.ink, C.accent, r / (rows - 1));
        ctx.strokeStyle = rgba(c, lerp(0.25, 0.95, r / (rows - 1)));
        ctx.beginPath();
        for (let x = 0; x <= F.w + 0.5; x += step) {
          const u = x / F.w;
          const env1 = Math.sin(Math.PI * u);
          const y = y0 + Math.sin(u * TAU * 1.6 + phase + r * 0.45) * amp0 * env1 * env1;
          x ? ctx.lineTo(F.x + x, y) : ctx.moveTo(F.x + x, y);
        }
        ctx.stroke();
      }
      // a playhead that rides the middle row: position = t
      const mid = Math.floor(rows / 2), u = lerp(0.04, 0.96, t);
      const y0 = rowY(mid), e = Math.sin(Math.PI * u);
      const hx = F.x + u * F.w, hy = y0 + Math.sin(u * TAU * 1.6 + phase + mid * 0.45) * amp0 * e * e;
      ctx.strokeStyle = rgba(C.ink, 0.22); ctx.lineWidth = 1; ctx.setLineDash([3, 6]);
      ctx.beginPath(); ctx.moveTo(hx, F.y); ctx.lineTo(hx, F.y + F.h); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = rgba(C.accent2); ctx.beginPath(); ctx.arc(hx, hy, 6, 0, TAU); ctx.fill();
      ctx.fillStyle = rgba(C.surface); ctx.beginPath(); ctx.arc(hx, hy, 2.2, 0, TAU); ctx.fill();
    },
  };

  /* ── 5. close ─────────────────────────────────────────── */
  const close = {
    name: "close",
    draw(ctx, t, env) {
      const { free: F, colors: C } = env;
      if (F.w < 30 || F.h < 30) return;
      const cx = F.x + F.w / 2, cy = F.y + F.h / 2, R = Math.min(F.w, F.h) * 0.4;
      const M = env.mobile ? 110 : 160, outer = Math.round(M * 0.62);
      const go = seg(t, 0, 0.8);
      for (let i = 0; i < M; i++) {
        // the mark: an outer ring and an inner hexagon (six aperture blades)
        let tx, ty;
        if (i < outer) {
          const a = (i / outer) * TAU - Math.PI / 2;
          tx = cx + Math.cos(a) * R; ty = cy + Math.sin(a) * R;
        } else {
          const k = i - outer, per = (M - outer) / 6, side = Math.floor(k / per), f = (k % per) / per;
          const a0 = side * TAU / 6 - Math.PI / 2, a1 = a0 + TAU / 6, r = R * 0.52;
          tx = cx + lerp(Math.cos(a0), Math.cos(a1), f) * r; ty = cy + lerp(Math.sin(a0), Math.sin(a1), f) * r;
        }
        const sx = F.x + hash(i, 1) * F.w, sy = F.y + hash(i, 2) * F.h;
        const e = ease.inOutCubic(stagger(go, i % 40, 40, 0.6));
        const bend = Math.sin(e * Math.PI) * 40 * (hash(i, 5) - 0.5);
        const x = lerp(sx, tx, e) + bend, y = lerp(sy, ty, e) - bend;
        const landed = e > 0.98;
        ctx.fillStyle = landed ? rgba(i < outer ? C.ink : C.accent, 0.9) : rgba(C.ink, lerp(0.25, 0.6, e));
        ctx.beginPath(); ctx.arc(x, y, landed ? 2.4 : lerp(1.4, 2.2, e), 0, TAU); ctx.fill();
      }
      // the mark resolves: ring stroke and a core, once everything lands
      const fin = ease.outCubic(seg(t, 0.78, 1));
      if (fin > 0) {
        ctx.strokeStyle = rgba(C.accent, 0.7 * fin); ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(cx, cy, R * 1.12, -Math.PI / 2, -Math.PI / 2 + TAU * fin); ctx.stroke();
        ctx.fillStyle = rgba(C.accent2, fin);
        ctx.beginPath(); ctx.arc(cx, cy, R * 0.16 * ease.outBack(fin), 0, TAU); ctx.fill();
      }
    },
  };

  const all = [orbit, path, stack, wave, close];

  /* paint one reel as a still into its own canvas (drum faces, posters):
     the same pure function, at a fixed t, with no keep-outs */
  function still(canvas, reel, t, colors, inset = 14) {
    // layout size, not getBoundingClientRect: a drum face is 3D-transformed,
    // and its projected box is not the size the canvas is drawn at
    const W = Math.max(1, canvas.clientWidth), H = Math.max(1, canvas.clientHeight), dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    reel.draw(ctx, t, {
      W, H, dpr, mobile: true, colors, keep: [], reduce: true, alpha: 1, p: t, index: 0,
      free: { x: inset, y: inset, w: W - 2 * inset, h: H - 2 * inset },
    });
  }

  return { orbit, path, stack, wave, close, all, still };
});
