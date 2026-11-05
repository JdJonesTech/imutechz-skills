/* Top and bottom meme captions on an image, rendered in the browser.

     node scripts/memecap.mjs <image> <out.png> [--top "TEXT"] [--bottom "TEXT"] [--width 1080]

   The browser shapes the text, so Devanagari and other scripts come out right (Pillow needs an
   extra library for that), and the type is the skill's own: Inter 900, then Noto Sans Devanagari.
   Captions are text, never markup: they are escaped before they reach the page. */
import fs from "node:fs";
import path from "node:path";
import { launch, serve, parseArgs, main, isMain } from "./common.mjs";

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** The page that draws the meme. `img` is a URL the page can load; captions are plain text. */
export function captionHtml({ img, top = "", bottom = "", width = 1080 }) {
  const line = (cls, text) => (text ? `<div class="cap ${cls}">${esc(text).replace(/\\n|\n/g, "<br>")}</div>` : "");
  return `<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="/skill/scripts/stage/fonts.css">
<style>
  html, body { margin: 0; background: #000; }
  #m { position: relative; width: ${Math.round(width)}px; overflow: hidden; }
  #m img { display: block; width: 100%; height: auto; }
  .cap { position: absolute; left: 4%; right: 4%; text-align: center; color: #fff; font: 900 96px/1.04 "Inter", "Noto Sans Devanagari", sans-serif;
         text-transform: uppercase; letter-spacing: -0.01em; -webkit-text-stroke: 0.09em #000; paint-order: stroke fill; overflow-wrap: break-word; }
  .top { top: 3%; } .bottom { bottom: 3%; }
</style></head><body><div id="m"><img id="i" src="${esc(img)}">${line("top", top)}${line("bottom", bottom)}</div></body></html>`;
}

/** Runs in the page: the largest type at which each caption stays inside 30% of the picture's height. */
export function fitCaptions() {
  const m = document.getElementById("m"), H = m.getBoundingClientRect().height, W = m.getBoundingClientRect().width;
  const sizes = [];
  for (const c of document.querySelectorAll(".cap")) {
    let lo = 14, hi = Math.round(W * 0.115);
    const fits = (px) => { c.style.fontSize = px + "px"; return c.scrollHeight <= H * 0.3 && c.scrollWidth <= c.clientWidth + 1; };
    if (!fits(hi)) { for (let k = 0; k < 12; k++) { const mid = (lo + hi) / 2; if (fits(mid)) lo = mid; else hi = mid; } c.style.fontSize = Math.floor(lo) + "px"; }
    sizes.push(parseFloat(c.style.fontSize));
  }
  return { width: Math.round(W), height: Math.round(H), sizes };
}

if (isMain(import.meta.url)) main(async () => {
  const a = parseArgs();
  const [image, out] = a._;
  if (!image || !out) throw new Error('usage: node scripts/memecap.mjs <image> <out.png> [--top "TEXT"] [--bottom "TEXT"] [--width 1080]');
  if (!fs.existsSync(image)) throw new Error(`missing file: ${image}`);
  const top = typeof a.top === "string" ? a.top : "", bottom = typeof a.bottom === "string" ? a.bottom : "";
  const width = Math.min(4096, Math.max(240, Math.round(+a.width || 1080)));
  const { srv, url } = await serve(path.dirname(path.resolve(image)));
  const b = await launch();
  try {
    const p = await b.newPage();
    await p.setViewport({ width, height: 800, deviceScaleFactor: 1 });
    await p.setRequestInterception(true);
    p.on("request", (r) => {
      const u = r.url();
      if (u === `${url}/` || u === `${url}/meme.html`) r.respond({ status: 200, contentType: "text/html; charset=utf-8", body: captionHtml({ img: `/project/${encodeURIComponent(path.basename(image))}`, top, bottom, width }) });
      else if (u.startsWith(url)) r.continue();
      else r.abort();                                   // the page needs nothing from the network
    });
    await p.goto(`${url}/meme.html`, { waitUntil: "load" });
    await p.evaluate(async () => { await document.fonts.ready; const i = document.getElementById("i"); if (!i.complete) await new Promise((res) => { i.onload = i.onerror = res; }); });
    const box = await p.evaluate(fitCaptions);
    if (!box.height) throw new Error("the image did not load");
    fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
    await (await p.$("#m")).screenshot({ path: out });
    console.log(JSON.stringify({ out, ...box }));
  } finally {
    await b.close();
    srv.close();
  }
});
