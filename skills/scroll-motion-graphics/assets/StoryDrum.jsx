"use client";
/*! StoryDrum.jsx v1.0.0 · ImuTechz · MIT
 *
 * A story told on the faces of a 3D drum that rolls with the scroll.
 * The React port of ScrollMotion.drum(); same markup and CSS (.sd-*).
 *
 * It is a control, not just an animation:
 *   - every face and every caption CTA is a real link
 *   - the rail and the ‹ › buttons jump to a chapter by scrolling the
 *     page, so the scroll and the drum never disagree
 *   - ← → ↑ ↓ Home End step chapters while the drum has focus
 *   - dragging with a mouse or pen rolls it and lets go on the nearest
 *     face (touch is left to native scrolling)
 * Rotation is a pure function of scroll; nothing pins input.
 *
 *   <StoryDrum
 *     title="The story, on a drum."
 *     chapters={[{ n: "Pin a stage", t: "…", d: "…", cta: "Read more", href: "/docs", art: <img … /> }, …]}
 *     LinkComponent={Link}   // optional: next/link or your router's link
 *   />
 */
import { useEffect, useRef, useState } from "react";
import { ScrollMotion, useScrub } from "./ScrollFilm.jsx";

const { clamp01, scrollToProgress, prefersReduced } = ScrollMotion;
const pad2 = (i) => String(i).padStart(2, "0");

export default function StoryDrum({
  chapters,
  title = "The story, on a drum.",
  kicker = "Roll it",
  vhPerChapter = 70,
  LinkComponent = "a",
  onChapter,
}) {
  const ref = useRef(null);
  const stageRef = useRef(null);
  const vpRef = useRef(null);
  const ring = useRef(null);
  const bar = useRef(null);
  const drag = useRef(null);
  const shown = useRef(0);
  const [idx, setIdx] = useState(0);
  const n = chapters.length;
  const step = 360 / n;
  const Go = LinkComponent;

  useScrub(ref, (p) => {
    const f = clamp01(p) * (n - 1);
    const base = Math.floor(f), t = f - base;
    // dwell: a smoothstep inside each step parks the drum on a face, then rolls
    const turn = prefersReduced() ? Math.round(f) : base + t * t * (3 - 2 * t);
    if (ring.current) ring.current.style.transform = `translateZ(calc(var(--r) * -1)) rotateX(${turn * step}deg)`;
    const i = Math.min(n - 1, Math.round(f));
    if (i !== shown.current) { shown.current = i; setIdx(i); if (onChapter) onChapter(i); }
    if (bar.current) bar.current.style.transform = `scaleY(${clamp01(p)})`;
  }, { stageRef });

  // every control seeks by scrolling the page
  const go = (i) => {
    if (!ref.current) return;
    const k = Math.max(0, Math.min(n - 1, i));
    scrollToProgress(ref.current, n > 1 ? k / (n - 1) : 0, { stage: stageRef.current, nudge: 1 });
  };
  const goRef = useRef(go);
  goRef.current = go;

  // drag the drum: a vertical mouse/pen drag scrolls the pinned track
  useEffect(() => {
    const vp = vpRef.current;
    if (!vp) return undefined;
    const swallow = (ev) => { ev.preventDefault(); ev.stopPropagation(); };
    const down = (e) => {
      if (e.button !== 0 || e.pointerType === "touch") return;
      drag.current = { y: e.clientY, s: window.scrollY, moved: false };
    };
    const move = (e) => {
      const d = drag.current;
      if (!d) return;
      const dy = e.clientY - d.y;
      if (Math.abs(dy) > 4) { d.moved = true; vp.classList.add("dragging"); }
      if (d.moved) window.scrollTo({ top: d.s - dy * 3.2, behavior: "instant" });
    };
    const up = () => {
      const d = drag.current;
      drag.current = null;
      vp.classList.remove("dragging");
      if (d && d.moved) {
        const p = ScrollMotion.progressOf(ref.current, "pin", stageRef.current);
        goRef.current(Math.round(p * (n - 1)));
        vp.addEventListener("click", swallow, { capture: true, once: true }); // the click that ends a drag is not a click
        setTimeout(() => vp.removeEventListener("click", swallow, { capture: true }), 50);
      }
    };
    vp.addEventListener("pointerdown", down);
    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerup", up);
    return () => {
      vp.removeEventListener("pointerdown", down);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [n]);

  const onKey = (e) => {
    const k = e.key;
    if (k === "ArrowDown" || k === "ArrowRight") { e.preventDefault(); go(idx + 1); }
    else if (k === "ArrowUp" || k === "ArrowLeft") { e.preventDefault(); go(idx - 1); }
    else if (k === "Home") { e.preventDefault(); go(0); }
    else if (k === "End") { e.preventDefault(); go(n - 1); }
  };

  const c = chapters[idx];
  return (
    <section className="sd" ref={ref} style={{ height: `calc(${n} * ${vhPerChapter}vh + 100vh)` }} aria-label={title}>
      <div className="sd-stage" ref={stageRef}>
        <div className="sd-copy">
          <p className="sd-k">{kicker} · {pad2(idx + 1)} / {pad2(n)}</p>
          <h2 className="sd-title">{title}</h2>
          {/* key={idx} remounts the caption so its CSS entrance plays per chapter */}
          <div className="sd-cap" key={idx}>
            <p className="sd-n">{c.n}</p>
            <h3 className="sd-h">{c.t}</h3>
            {c.d ? <p className="sd-d">{c.d}</p> : null}
            {c.href ? <Go className="sd-cta" href={c.href}>{c.cta || "Open"} <span aria-hidden="true">→</span></Go> : null}
          </div>
          <div className="sd-nav">
            <button type="button" onClick={() => go(idx - 1)} disabled={idx === 0} aria-label="Previous chapter">‹</button>
            <button type="button" onClick={() => go(idx + 1)} disabled={idx === n - 1} aria-label="Next chapter">›</button>
            <span className="sd-tip">scroll, drag or use the arrow keys</span>
          </div>
        </div>
        <div className="sd-viewport" ref={vpRef} tabIndex={0} onKeyDown={onKey} aria-label={`${title} Arrow keys change chapter.`}>
          <div className="sd-ring" ref={ring}>
            {chapters.map((ch, i) => (
              <Go
                key={ch.n}
                href={ch.href || "#"}
                className={`sd-face${i === idx ? " on" : ""}`}
                style={{ transform: `rotateX(${-i * step}deg) translateZ(var(--r))` }}
                tabIndex={i === idx ? 0 : -1}
                aria-hidden={i !== idx}
                draggable={false}
              >
                {/* only the faces next to the one you see carry their art */}
                <span className="sd-face-art">{Math.abs(i - idx) <= 1 ? ch.art || null : null}</span>
                <span className="sd-face-meta">
                  <span className="sd-face-n">{pad2(i + 1)}</span>
                  <span className="sd-face-t">{ch.n}</span>
                  <span className="sd-face-go" aria-hidden="true">↗</span>
                </span>
              </Go>
            ))}
          </div>
        </div>
        <ol className="sd-rail" aria-label="Chapters">
          <i aria-hidden="true"><i ref={bar} /></i>
          {chapters.map((ch, i) => (
            <li key={ch.n} className={i === idx ? "on" : i < idx ? "done" : ""}>
              <button type="button" onClick={() => go(i)} aria-current={i === idx ? "step" : undefined}>{ch.n}</button>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* A small drum that rolls on its own (CSS keyframes) for a preview card.
   Purely decorative: aria-hidden, and still under reduced motion. Uses
   the four-face .sdp rules in scroll-motion.css. */
export function DrumPreview({ faces }) {
  const step = 360 / faces.length;
  return (
    <span className="sdp" aria-hidden="true">
      <span className="sdp-ring">
        {faces.map((art, i) => (
          <span className="sdp-face" key={i} style={{ transform: `rotateX(${-i * step}deg) translateZ(var(--r))` }}>{art}</span>
        ))}
      </span>
    </span>
  );
}
