"use client";
/*! ScrollFilm.jsx v1.0.0 · ImuTechz · MIT
 *
 * React wrapper for ScrollMotion.film(): a pinned canvas film whose
 * timeline is the scroll position. React renders the DOM (track, stage,
 * HUD, captions); the engine owns the canvas and writes caption
 * opacity/transform every frame. React never re-renders per frame.
 *
 *   import ScrollFilm, { useScrub } from "./ScrollFilm";
 *   import Reels from "./reels";            // or your own reels
 *   import "./scroll-motion.css";
 *
 *   <ScrollFilm
 *     label="How it works"
 *     reels={Reels.all}
 *     captions={[{ kicker: "01 · Orbit", tag: "Pin a stage", title: "…", body: "…", place: "left" }, …]}
 *   />
 *
 * Rules:
 *   - `reels` must be stable (module-level or useMemo): a new array
 *     rebuilds the film.
 *   - one caption per reel; place = "left" | "right" | "bottom" | "top"
 *     (phones always use bottom). Captions are real DOM text.
 *   - never wrap the section in an ancestor with overflow: hidden/auto
 *     (position: sticky stops working).
 *   - Next.js: this is a client component ("use client" above).
 */
import { useEffect, useRef, useState } from "react";
import * as engine from "./scroll-motion.js";

/* scroll-motion.js is UMD. Webpack/Next give us module.exports (as
   .default); Vite serves it as native ESM with no exports, and the file
   registers globalThis.ScrollMotion instead. Accept either. */
export const ScrollMotion =
  (engine && engine.default && engine.default.film && engine.default) ||
  (engine && engine.film && engine) ||
  globalThis.ScrollMotion;

/* useScrub(ref, onFrame, { mode: "pin" | "view", smooth }) — the hook
   behind every scroll-driven section. onFrame(p) runs only while p
   changes; keep it cheap and write styles through refs, not state. */
export function useScrub(ref, onFrame, { mode = "pin", smooth = 0.18, stageRef = null } = {}) {
  const cb = useRef(onFrame);
  cb.current = onFrame; // always call the latest closure, without restarting the loop
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const s = ScrollMotion.scrub(el, (p) => cb.current(p), { mode, smooth, stage: stageRef ? stageRef.current : null });
    return () => s.stop();
  }, [ref, mode, smooth, stageRef]);
}

export default function ScrollFilm({
  reels,
  captions = [],
  label = "Scroll-driven film",
  title = "",
  hint = "Scroll back: it rewinds",
  vhPerReel = 90,
  className = "",
  onReel,
}) {
  const track = useRef(null);
  const stage = useRef(null);
  const canvas = useRef(null);
  const caps = useRef([]);
  const player = useRef(null);
  const [active, setActive] = useState(0);
  const onReelRef = useRef(onReel);
  onReelRef.current = onReel;
  const n = reels.length;

  useEffect(() => {
    if (!track.current || !stage.current || !canvas.current) return undefined;
    const f = ScrollMotion.film({
      track: track.current,
      stage: stage.current,
      canvas: canvas.current,
      reels,
      captions: reels.map((_, i) => caps.current[i] || null),
      onChange: (i, reel) => {
        setActive(i); // a state change only when the reel changes, never per frame
        if (onReelRef.current) onReelRef.current(i, reel);
      },
    });
    player.current = f;
    return () => { f.destroy(); player.current = null; };
  }, [reels]);

  return (
    <section
      className={`smf ${className}`.trim()}
      ref={track}
      style={{ "--smf-n": n, height: `calc(${n} * ${vhPerReel}svh + 100svh)` }}
      aria-label={label}
    >
      <div className="smf-stage" ref={stage}>
        <canvas className="smf-canvas" ref={canvas} aria-hidden="true" />
        <div className="smf-frame">
          <div className="smf-hud" data-keep="">
            {title ? <span className="smf-hud-t">{title}</span> : null}
            {/* the engine writes the counter text; React leaves it empty */}
            <span data-sm-count="" aria-hidden="true" />
            <span className="smf-hud-bar" aria-hidden="true"><i data-sm-bar="" /></span>
          </div>
          {captions.slice(0, n).map((c, i) => (
            <article
              key={i}
              className="smf-cap"
              data-place={c.place || "left"}
              data-keep=""
              ref={(el) => { caps.current[i] = el; }}
              aria-current={i === active ? "step" : undefined}
            >
              <p className="smf-cap-k"><span>{c.kicker}</span>{c.tag ? <span>{c.tag}</span> : null}</p>
              <h3 className="smf-cap-h">{c.title}</h3>
              {c.body ? <p className="smf-cap-d">{c.body}</p> : null}
            </article>
          ))}
          {hint ? <p className="smf-hint" data-keep="" aria-hidden="true">{hint}</p> : null}
        </div>
      </div>
    </section>
  );
}
