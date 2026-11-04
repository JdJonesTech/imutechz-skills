/* Single frames and the legibility lint.

     node scripts/stills.mjs <project> --platform youtube --at 1.5,8,12 [--out dir] [--scale 1]
     node scripts/stills.mjs <project> --platform youtube --every 4
     node scripts/stills.mjs <project> --platform youtube --scenes        one still per scene (at 80%)
     node scripts/stills.mjs <project> --platform youtube --lint [--min 22]
     node scripts/stills.mjs <project> --platform thumbnail --at 0 --out out.png

   --lint renders every scene at the moment its entrances have settled
   (65% and 92% of its length) and reports text that leaves the stage or the
   safe area, text clipped by its own box, and text below the minimum size.
   Output: <project>/build/<platform>/lint.json and a JSON line on stdout. */
import fs from "node:fs";
import path from "node:path";
import { launch, serve, parseArgs, writeJSON, main, isMain } from "./common.mjs";
import { openStage, timelineSize } from "./frames.mjs";

if (isMain(import.meta.url)) main(async () => {
  const a = parseArgs();
  const project = a._[0];
  if (!project) throw new Error("usage: node scripts/stills.mjs <project> --platform p (--at t,t | --every s | --scenes | --lint)");
  const platform = a.platform || "youtube";
  const { W, H } = timelineSize(project, platform);
  const outDir = path.join(project, "build", platform, "stills");
  fs.mkdirSync(outDir, { recursive: true });
  const { srv, url } = await serve(project);
  const b = await launch();
  try {
    const { p, info, errors } = await openStage(b, url, platform, W, H, +(a.scale || 1));
    const items = await p.evaluate(() => window.STAGE.items());
    if (a.lint) {
      const issues = [];
      for (const it of items) {
        for (const k of [0.65, 0.92]) {
          const t = it.t0 + (it.t1 - it.t0) * k;
          issues.push(...(await p.evaluate((t, m) => window.STAGE.lint(t, m), t, a.min ? +a.min : undefined)));
        }
      }
      // one entry per (scene, kind, text)
      const seen = new Set();
      const all = issues.filter((q) => { const k = `${q.scene}|${q.kind}|${q.text}`; if (seen.has(k)) return false; seen.add(k); return true; });
      const uniq = all.filter((q) => q.severity !== "warn"), warnings = all.filter((q) => q.severity === "warn");
      const rep = { platform, W, H, scenes: items.length, issues: uniq, warnings, errors };
      writeJSON(path.join(project, "build", platform, "lint.json"), rep);
      console.log(JSON.stringify({ lint: uniq.length, warnings: warnings.length, errors: errors.length }));
      return;
    }
    let times = [];
    if (a.every) for (let t = 0.5; t < info.duration; t += +a.every) times.push(+t.toFixed(2));
    else if (a.scenes) times = items.map((it) => +(it.t0 + (it.t1 - it.t0) * 0.8).toFixed(2));
    else times = String(a.at != null ? a.at : "0").split(",").map(Number);
    const files = [];
    for (const t of times) {
      await p.evaluate((t) => window.STAGE.renderAt(t), t);
      const f = a.out && times.length === 1 ? a.out : path.join(a.out || outDir, `${platform}-${t.toFixed(2).padStart(7, "0")}.png`);
      fs.mkdirSync(path.dirname(f), { recursive: true });
      const sc = +(a.scale || 1);
      await p.screenshot({ path: f, ...(sc !== 1 ? { clip: { x: 0, y: 0, width: W, height: H, scale: sc } } : {}) });
      files.push(f);
    }
    console.log(JSON.stringify({ stills: files, errors: errors.length }));
  } finally {
    await b.close();
    srv.close();
  }
});
