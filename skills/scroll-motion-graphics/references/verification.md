# Verification

"It looks fine on my laptop" is not verification. A scroll film has to hold at every width, in both directions, in both themes and with reduced motion. Run the automated pass, then the manual one. Do not call it done until both are clean.

## The widths

| Width × height | Stands for |
| --- | --- |
| 360 × 740 | small Android |
| 390 × 844 @2x | iPhone 12 to 15 |
| 414 × 896 | large iPhone |
| 768 × 1024 | tablet portrait (film is mobile-layout, drum is stacked) |
| 1024 × 768 | tablet landscape / small laptop (drum goes three-column) |
| 1280 × 800 | laptop |
| 1440 × 900 | desktop (the preview stills are taken here) |
| 1920 × 1080 | large desktop |

## What to check at every width

1. **No console errors or warnings**, and no uncaught exceptions.
2. **No horizontal overflow**: `document.documentElement.scrollWidth <= innerWidth`.
3. **Each reel shows at its position.** Scroll to p = (i + 0.6) / n: the HUD says reel i + 1, caption i is at opacity 1, and the canvas actually drew something.
4. **Reels are distinct.** The canvas hashes at the n positions are all different.
5. **Nothing under the captions.** Inside every visible keep-out rect (inset 2 px), the canvas alpha is 0.
6. **It seeks both ways.** The canvas hash at p = 0.33 is identical after scrolling 0.33, then 0.88, then 0.33.
7. **Idle is idle.** Once settled, zero `requestAnimationFrame` calls in one second.
8. **The drum is a control.** ArrowDown on the focused viewport advances it one chapter, and the next button advances it again. On desktop, a rail button jumps to its chapter and a mouse drag rolls the drum back. Every face is a link with art painted on it, and exactly one face is tabbable.
9. **Anchors seek.** `#reel-stack` scrolls the film to reel 3.

Then once more with `prefers-reduced-motion: reduce` (the drum rotation is a whole multiple of 360/n, and caption animation is `none`) and once with `prefers-color-scheme: dark` (screenshot it and look).

## The script (puppeteer-core + an installed Chrome or Brave)

```js
// verify.mjs: node verify.mjs  (puppeteer-core only; no browser download)
import puppeteer from "puppeteer-core";
import { pathToFileURL } from "node:url";
import crypto from "node:crypto";

const BROWSER = process.env.BROWSER || "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe";
const URL_ = pathToFileURL(process.argv[2] || "assets/demo.html").href;
const SIZES = [[360, 740], [390, 844, 2], [414, 896], [768, 1024], [1024, 768], [1280, 800], [1440, 900], [1920, 1080]];
const fails = [];
const ok = (c, m) => c || fails.push(m);

const browser = await puppeteer.launch({
  executablePath: BROWSER, headless: "new",
  args: ["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--hide-scrollbars"],
});

async function open(w, h, dpr = 1, media = []) {
  const page = await browser.newPage(), errors = [];
  page.on("console", (m) => ["error", "warning"].includes(m.type()) && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(e.message));
  await page.evaluateOnNewDocument(() => {            // count rAF calls for the idle check
    window.__raf = 0; const r = requestAnimationFrame.bind(window);
    window.requestAnimationFrame = (cb) => (window.__raf++, r(cb));
  });
  await page.setViewport({ width: w, height: h, deviceScaleFactor: dpr });
  if (media.length) await page.emulateMediaFeatures(media);
  await page.goto(URL_, { waitUntil: "load" });
  return { page, errors };
}

async function filmTo(page, p) {                       // scroll, then wait for the lerp to settle
  await page.evaluate((p) => {
    const f = document.getElementById("film"), s = f.querySelector(".smf-stage");
    scrollTo({ top: f.getBoundingClientRect().top + scrollY + p * (f.offsetHeight - s.offsetHeight), behavior: "instant" });
  }, p);
  await page.waitForFunction(() => {
    const f = document.getElementById("film"), s = f.querySelector(".smf-stage");
    return __demo.player.p === ScrollMotion.progressOf(f, "pin", s);
  });
}
const hash = (page) => page.evaluate(() => document.querySelector(".smf-canvas").toDataURL())
  .then((d) => crypto.createHash("sha1").update(d).digest("hex"));

const alphaUnderKeeps = (page) => page.evaluate(() => {
  const cv = document.querySelector(".smf-canvas"), ctx = cv.getContext("2d"), dpr = cv.width / cv.clientWidth;
  let max = 0;
  for (const k of __demo.player.keeps) {
    const x = Math.max(0, Math.ceil((k.x + 2) * dpr)), y = Math.max(0, Math.ceil((k.y + 2) * dpr));
    const w = Math.min(cv.width, Math.floor((k.x + k.w - 2) * dpr)) - x;
    const h = Math.min(cv.height, Math.floor((k.y + k.h - 2) * dpr)) - y;
    if (w <= 0 || h <= 0) continue;
    const d = ctx.getImageData(x, y, w, h).data;
    for (let i = 3; i < d.length; i += 4) max = Math.max(max, d[i]);
  }
  return max;
});

for (const [w, h, dpr] of SIZES) {
  const { page, errors } = await open(w, h, dpr);
  ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${w}: overflow`);
  const hashes = [];
  for (let i = 0; i < 5; i++) {
    await filmTo(page, i === 4 ? 0.97 : (i + 0.6) / 5);
    const hud = await page.$eval("[data-sm-count]", (e) => e.textContent);
    ok(hud.startsWith(String(i + 1).padStart(2, "0")), `${w}: reel ${i} HUD ${hud}`);
    ok((await alphaUnderKeeps(page)) === 0, `${w}: reel ${i} drew under a caption`);
    hashes.push(await hash(page));
    if (w === 390 || w === 1440) await page.screenshot({ path: `shots/w${w}-reel${i + 1}.jpg`, quality: 80 });
  }
  ok(new Set(hashes).size === 5, `${w}: reels not distinct`);
  await filmTo(page, 0.33); const a = await hash(page);
  await filmTo(page, 0.88); await filmTo(page, 0.33);
  ok(a === (await hash(page)), `${w}: forward/back differ`);
  const r0 = await page.evaluate(() => __raf);
  await new Promise((r) => setTimeout(r, 1000));
  ok((await page.evaluate(() => __raf)) === r0, `${w}: rAF while idle`);
  // …drum: focus .sd-viewport, press ArrowDown, expect __demo.drum.index === 1, etc.
  ok(errors.length === 0, `${w}: console: ${errors.join(" | ")}`);
  await page.close();
}
await browser.close();
console.log(fails.length ? "FAIL\n- " + fails.join("\n- ") : "ALL CHECKS PASSED");
process.exit(fails.length ? 1 : 0);
```

Notes on the script:

- **Use `behavior: "instant"`** in test scrolls. The demo sets `scroll-behavior: smooth` on `html`, and `"auto"` would animate.
- **Wait for the settle, not a fixed timeout.** Compare the player's `p` to `progressOf()`. They are exactly equal once the lerp snaps.
- The SwiftShader flags make headless rendering deterministic on machines without a GPU. They are needed for WebGL and harmless for Canvas 2D.
- Expose a debug handle (`window.__demo = { player, drum }`) from your page wiring. The tests rely on `player.p`, `player.keeps` and `drum.index`.
- For your own page, swap the selectors (`#film`, `.smf-stage`, `[data-sm-count]`) for yours, and keep the checks.

## Preview stills

Take them at 1440 × 900, DPR 1, JPEG quality 80, at a p inside each reel's hold (u ≈ 0.65):

```js
await filmTo(page, 0.13);  await page.screenshot({ path: "assets/preview-orbit.jpg", type: "jpeg", quality: 80 });
await filmTo(page, 0.33);  await page.screenshot({ path: "assets/preview-path.jpg",  type: "jpeg", quality: 80 });
await filmTo(page, 0.985); await page.screenshot({ path: "assets/preview-close.jpg", type: "jpeg", quality: 80 });
```

Each should be under 150 KB. Flat backgrounds and line art compress well, and the demo's stills are about 40 to 50 KB.

## The manual pass (10 minutes, every time)

- [ ] **Trackpad**: scroll slowly through, then fling. Every reel should get a readable hold and nothing should skip.
- [ ] **Scroll backwards** through the whole film. Does every reel rewind meaningfully?
- [ ] **Stop mid-crossfade.** Is the frame acceptable as a still?
- [ ] **Real phone**: flick through. Does the stage stay pinned when the URL bar hides? Do the bottom-sheet captions leave room for the drawing?
- [ ] **Keyboard only**: Tab to the drum, use the arrows, Enter on a face, Tab to the rail. Is the focus always visible?
- [ ] **Screen reader** (VoiceOver or NVDA): read the section. Is the whole story there in order, without the canvas?
- [ ] **Reduced motion** at the OS level: the drum snaps, nothing slides, and the content is complete.
- [ ] **Dark mode** at the OS level: no light-mode leftovers in the canvas, and caption contrast holds.
- [ ] **Zoom to 200%**: captions still fit, and there is no horizontal scroll.
- [ ] **Idle**: leave the tab open on the film for a minute. The performance panel should show no frames being produced.
