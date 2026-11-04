/* Virtual time for frame-exact capture of a live page.

   Injected before any page script (puppeteer evaluateOnNewDocument). The
   page's clocks, timers, requestAnimationFrame and Web Animations (CSS
   transitions / keyframes) stop following the wall clock and only move when
   the recorder calls window.__vt.advance(ms). Every captured frame is then
   exactly 1/30 s after the last one, however long the screenshot took, so
   canvas particle fields and CSS motion come out perfectly smooth.

   window.__vt.pending() reports fetches still in flight, so the recorder can
   wait for real network answers while virtual time stands still. */
(() => {
  if (window.__vt) return;
  let now = 0;
  const epoch = Date.now();
  const perf0 = performance.now();
  const pnow = () => perf0 + now;
  try { performance.now = pnow; } catch (e) {}
  try { Object.defineProperty(performance, "now", { value: pnow, configurable: true }); } catch (e) {}

  const RealDate = Date;
  function VDate(...a) {
    if (!new.target) return new RealDate(epoch + now).toString();
    return a.length ? new RealDate(...a) : new RealDate(epoch + now);
  }
  VDate.prototype = RealDate.prototype;
  VDate.now = () => epoch + now;
  VDate.parse = RealDate.parse;
  VDate.UTC = RealDate.UTC;
  window.Date = VDate;

  let tid = 1;
  const timers = new Map();
  const add = (fn, ms, args, repeat) => {
    const id = tid++;
    const d = Math.max(repeat ? 1 : 0, Number(ms) || 0);
    timers.set(id, { fn, at: now + d, args, iv: repeat ? d : 0, seq: id });
    return id;
  };
  window.setTimeout = (fn, ms, ...args) => add(fn, ms, args, false);
  window.setInterval = (fn, ms, ...args) => add(fn, ms, args, true);
  window.clearTimeout = window.clearInterval = (id) => { timers.delete(id); };

  let rq = new Map();
  let rid = 1;
  window.requestAnimationFrame = (cb) => { const id = rid++; rq.set(id, cb); return id; };
  window.cancelAnimationFrame = (id) => { rq.delete(id); };

  let inflight = 0;
  const realFetch = window.fetch && window.fetch.bind(window);
  if (realFetch) {
    window.fetch = (...a) => {
      inflight++;
      const p = realFetch(...a);
      p.then(() => { inflight--; }, () => { inflight--; });
      return p;
    };
  }

  const run = (fn, args) => {
    try { if (typeof fn === "function") fn(...(args || [])); else (0, eval)(String(fn)); }
    catch (e) { console.error("[vt] " + (e && e.message)); }
  };

  function syncAnimations() {
    let list = [];
    try { list = document.getAnimations(); } catch (e) { return; }
    for (const a of list) {
      try {
        if (a.__vtDone) continue;
        if (a.__vt0 == null) {
          a.__vt0 = now - (Number(a.currentTime) || 0);
          a.pause();
        }
        const ct = now - a.__vt0;
        const end = a.effect ? a.effect.getComputedTiming().endTime : Infinity;
        /* a finished animation must really finish, so its finish events
           (and code waiting on them) run */
        if (isFinite(end) && ct >= end && a.playbackRate >= 0) { a.__vtDone = true; a.finish(); }
        else a.currentTime = ct;
      } catch (e) {}
    }
  }

  window.__vt = {
    advance(ms) {
      const target = now + ms;
      for (let guard = 0; guard < 20000; guard++) {
        let best = null, bid = 0;
        for (const [id, t] of timers) {
          if (t.at <= target && (!best || t.at < best.at || (t.at === best.at && t.seq < best.seq))) { best = t; bid = id; }
        }
        if (!best) break;
        now = Math.max(now, best.at);
        if (best.iv) best.at += best.iv; else timers.delete(bid);
        run(best.fn, best.args);
      }
      now = target;
      const q = rq;
      rq = new Map();
      for (const cb of q.values()) run(cb, [pnow()]);
      syncAnimations();
      return now;
    },
    sync: syncAnimations,
    now: () => now,
    pending: () => inflight,
  };
})();
