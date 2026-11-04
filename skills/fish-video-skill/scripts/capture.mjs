/* Record the live website / product shots a storyboard needs.

     node scripts/capture.mjs <project> [shotId ...] [--list]

   Reads <project>/build/captures.json (written by `fishvideo storyboard`
   from the storyboard's `captures:` list) and writes, per shot,
   <project>/build/cap/<id>/NNNNN.jpg + meta.json.

   A shot is either a scripted action list or an automatic tour:

     { "id": "home", "url": "https://example.com", "viewport": {"w":1440,"h":810},
       "theme": "light", "settle": 1500,
       "actions": [ {"hold": 20}, {"mark": "hero"},
                    {"move": {"text": "Pricing"}, "frames": 22}, {"click": true, "after": 20},
                    {"scroll": {"text": "Features"}, "offset": 120, "frames": 40},
                    {"type": "hello", "per_char": 3}, {"key": "k", "mods": ["Control"]},
                    {"warm": "/docs/intro"}, {"click": true},
                    {"until": "location.pathname.startsWith('/docs/')", "timeout": 30},
                    {"wait": 1.5} ] }

     { "id": "tour", "url": "https://example.com", "auto": {"seconds": 10} }

   Read-only by design: the recorder never submits forms unless an action
   explicitly clicks a button, and the skill's rules forbid doing that on
   anyone's production site. */
import fs from "node:fs";
import path from "node:path";
import { launch, parseArgs, readJSON, main, isMain } from "./common.mjs";
import { Shot } from "./recorder.mjs";

const toFrames = (a, fps, key = "frames", def = 18) => (a.s != null ? Math.max(1, Math.round(a.s * fps)) : a[key] != null ? a[key] : def);

/** Run one scripted action against a Shot. Exported for tests. */
export async function runAction(s, a) {
  const fps = s.fps;
  if (a.hold != null) return s.hold(a.hold);
  if (a.wait != null) return s.hold(Math.round(a.wait * fps));
  if (a.mark) return s.mark(a.mark);
  if (a.move) {
    const m = a.move;
    const pt = m.x != null ? { x: m.x, y: m.y } : await s.locate(m);
    return s.moveTo(pt.x + (m.dx || 0), pt.y + (m.dy || 0), toFrames(a, fps));
  }
  if (a.click) return s.click(a.after != null ? a.after : 8, { fake: !!a.fake });
  if (a.type != null) return s.type(String(a.type), a.per_char || 3);
  if (a.key) return s.key(a.key, a.after || 4, a.mods || []);
  if (a.scroll) {
    const m = a.scroll;
    let y;
    if (m.y != null) y = m.y;
    else if (m.by != null) y = (await s.eval(() => window.scrollY)) + m.by;
    else y = (await s.locate(m)).top - (a.offset != null ? a.offset : 110);
    return s.scrollTo(y, toFrames(a, fps, "frames", 36));
  }
  if (a.eval) return s.eval((src) => (0, eval)(src), a.eval);
  /* real-time wait while page time stands still: client-side navigations,
     slow API answers, a route the dev server compiles on first visit */
  if (a.until) {
    const t0 = Date.now();
    for (;;) {
      if (await s.eval((src) => { try { return !!(0, eval)(src); } catch (e) { return false; } }, a.until)) break;
      if (Date.now() - t0 > (a.timeout || 30) * 1000) throw new Error(`[${s.id}] until timed out: ${a.until}`);
      await new Promise((r) => setTimeout(r, 150));
    }
    return s.settle(a.settle || 300);
  }
  /* open a URL once in a throwaway tab so its first (slow) compile is not filmed */
  if (a.warm) {
    const u = new URL(a.warm, await s.eval(() => location.href)).href;
    const wp = await s.ctx.newPage();
    await wp.goto(u, { waitUntil: "load", timeout: 180000 }).catch(() => {});
    await new Promise((r) => setTimeout(r, 2000));
    return wp.close();
  }
  throw new Error(`[${s.id}] unknown action ${JSON.stringify(a)}`);
}

/** An automatic tour: hold on the hero, sweep the cursor, then scroll the
    page in viewport-sized steps, marking s0, s1, ... at each stop. */
export function autoActions(auto, vp, fps = 30) {
  const secs = auto.seconds || 10;
  const total = Math.round(secs * fps);
  const stops = Math.max(1, auto.stops || Math.round(secs / 3.2));
  const acts = [{ mark: "s0" }, { hold: Math.round(fps * 0.8) }, { move: { x: vp.w * 0.5, y: vp.h * 0.42 }, frames: Math.round(fps * 0.8) }];
  let used = Math.round(fps * 1.6);
  const per = Math.max(fps, Math.floor((total - used) / stops));
  for (let k = 1; k <= stops; k++) {
    acts.push({ scroll: { by: Math.round(vp.h * (auto.step || 0.85)) }, frames: Math.round(per * 0.45) });
    acts.push({ mark: "s" + k });
    acts.push({ move: { x: vp.w * (k % 2 ? 0.34 : 0.66), y: vp.h * 0.55 }, frames: Math.round(per * 0.3) });
    acts.push({ hold: per - Math.round(per * 0.45) - Math.round(per * 0.3) });
    used += per;
  }
  if (total > used) acts.push({ hold: total - used });
  return acts;
}

export async function recordShot(browser, spec, outRoot) {
  const vp = spec.viewport || { w: 1440, h: 810 };
  const s = new Shot(browser, spec.id, outRoot, {
    w: vp.w, h: vp.h, dpr: spec.dpr || 1.5, fps: spec.fps || 30, quality: spec.quality || 88,
    theme: spec.theme || "light", storage: spec.storage, session: spec.session, hide: spec.hide, css: spec.css,
  });
  await s.open(spec.url, { settle: spec.settle != null ? spec.settle : 1500, waitFor: spec.wait_for || null });
  const acts = spec.auto ? autoActions(spec.auto, vp, s.fps) : spec.actions || [{ hold: 90 }];
  for (const a of acts) await runAction(s, a);
  if (!s.frames.length) await s.hold(1);
  return s.close();
}

if (isMain(import.meta.url)) main(async () => {
  const args = parseArgs();
  const project = args._[0];
  if (!project) throw new Error("usage: node scripts/capture.mjs <project> [shotId ...]");
  const spec = readJSON(path.join(project, "build", "captures.json"));
  const want = args._.slice(1);
  const shots = spec.shots.filter((s) => !want.length || want.includes(s.id));
  if (args.list) { for (const s of spec.shots) console.log(s.id, s.url); return; }
  if (!shots.length) { console.log("no shots to capture"); return; }
  const out = path.join(project, "build", "cap");
  fs.mkdirSync(out, { recursive: true });
  const b = await launch();
  const report = [];
  try {
    for (const sh of shots) {
      const t0 = Date.now();
      console.log(`shot ${sh.id}: ${sh.url}`);
      const meta = await recordShot(b, sh, out);
      report.push({ id: sh.id, frames: meta.count, seconds: +((Date.now() - t0) / 1000).toFixed(1), errors: meta.errors.length });
    }
  } finally {
    await b.close();
  }
  console.log(JSON.stringify(report));
});
