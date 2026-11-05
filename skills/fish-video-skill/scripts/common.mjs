/* Shared Node helpers for the Fish Video Skill: tool discovery, the
   headless browser, a tiny read-only static server and CLI parsing.

   Every Node script in scripts/ imports from here so that paths and
   browser flags are defined once. */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import http from "node:http";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const SKILL = path.resolve(here, "..");
const require = createRequire(path.join(SKILL, "package.json"));

/* ---------------------------------------------------------------- tools */
const BROWSER_CANDIDATES = [
  process.env.BROWSER,
  process.env.BRAVE,
  process.env.CHROME,
  "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/brave-browser",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean);

/** Path of a Chromium-family browser, or throws with a helpful message. */
export function browserPath() {
  for (const p of BROWSER_CANDIDATES) if (fs.existsSync(p)) return p;
  throw new Error("No Chromium browser found. Install Brave/Chrome/Chromium or set BROWSER=/path/to/browser.");
}

/** ffmpeg: $FFMPEG, then ffmpeg-static from node_modules, then PATH. */
export function ffmpegPath() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  try { const p = require("ffmpeg-static"); if (p && fs.existsSync(p)) return p; } catch {}
  return "ffmpeg";
}

export function ffprobePath() {
  if (process.env.FFPROBE) return process.env.FFPROBE;
  try { const p = require("@ffprobe-installer/ffprobe").path; if (p && fs.existsSync(p)) return p; } catch {}
  return "ffprobe";
}

export function puppeteer() { return require("puppeteer-core"); }

/** Launch headless Chromium with the flags that make WebGL/canvas work
    without a GPU and stop background throttling (capture runs for minutes). */
/* Workers that fit the CPU budget. One worker is a software-rendering browser plus an x264 encoder,
   about 3 logical CPUs. FISH_CPU_LIMIT (percent, default 60) is the budget; on Windows the Python
   side also enforces it with a hard cap. Lower priority keeps the user's own apps responsive. */
export function safeWorkers(requested = 4) {
  const cores = os.availableParallelism ? os.availableParallelism() : os.cpus().length;
  const pct = Math.max(5, Math.min(100, +(process.env.FISH_CPU_LIMIT || 60)));
  return Math.max(1, Math.min(requested, Math.floor((cores * pct) / 100 / 3)));
}
try { os.setPriority(os.constants.priority.PRIORITY_BELOW_NORMAL); } catch { /* not allowed here: fine */ }

/* every browser we start, so none outlives the process however it ends */
const LIVE = new Set();
function killAll() { for (const b of LIVE) { try { b.process()?.kill(); } catch { /* already gone */ } } LIVE.clear(); }
process.on("exit", killAll);
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(sig, () => { killAll(); process.exit(1); });

export async function launch(opts = {}) {
  const b = await launchRaw(opts);
  LIVE.add(b);
  b.on("disconnected", () => LIVE.delete(b));
  return b;
}

async function launchRaw({ headless = true, sandbox = false } = {}) {
  return puppeteer().launch({
    executablePath: browserPath(),
    headless,
    protocolTimeout: 900000,
    args: [
      ...(sandbox ? [] : ["--no-sandbox"]),
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
      "--hide-scrollbars",
      "--disable-background-timer-throttling",
      "--disable-renderer-backgrounding",
      "--disable-backgrounding-occluded-windows",
      "--font-render-hinting=none",
      "--autoplay-policy=no-user-gesture-required",
      "--mute-audio",
    ],
  });
}

/* ---------------------------------------------------------------- server */
const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
  ".svg": "image/svg+xml", ".gif": "image/gif", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf",
};

/** Serve the skill at /skill/ and a project folder at /project/ (read-only,
    127.0.0.1 only). Resolves {srv, url}. port 0 picks a free port. */
export function serve(project, port = 0) {
  const roots = { skill: SKILL, project: path.resolve(project) };
  return new Promise((resolve, reject) => {
    const srv = http.createServer((req, res) => {
      const u = new URL(req.url, "http://x");
      const parts = decodeURIComponent(u.pathname).split("/").filter(Boolean);
      const root = roots[parts.shift()];
      if (!root) { res.writeHead(404); return res.end(); }
      const p = path.normalize(path.join(root, ...parts));
      if (!p.startsWith(root)) { res.writeHead(403); return res.end(); }
      fs.stat(p, (err, st) => {
        if (err || !st.isFile()) { res.writeHead(404); return res.end(); }
        res.writeHead(200, { "content-type": TYPES[path.extname(p).toLowerCase()] || "application/octet-stream", "cache-control": "no-cache" });
        fs.createReadStream(p).pipe(res);
      });
    });
    srv.on("error", reject);
    srv.listen(port, "127.0.0.1", () => resolve({ srv, url: `http://127.0.0.1:${srv.address().port}` }));
  });
}

/* ---------------------------------------------------------------- cli */
/** Minimal flag parser: --k v, --flag, positional args. */
export function parseArgs(argv = process.argv.slice(2)) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const k = a.slice(2);
      const v = argv[i + 1];
      if (v != null && !v.startsWith("--")) { out[k] = v; i++; } else out[k] = true;
    } else out._.push(a);
  }
  return out;
}

export function readJSON(f) { return JSON.parse(fs.readFileSync(f, "utf8")); }
export function writeJSON(f, v) { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, JSON.stringify(v, null, 1)); }
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Run main(), print a one-line error and exit 1 on failure. */
export function main(fn) {
  fn().catch((e) => { console.error(`error: ${e && e.stack ? e.stack : e}`); process.exit(1); });
}

/** True when the module at `url` is the script node was started with. */
export function isMain(url) {
  try { return path.resolve(fileURLToPath(url)) === path.resolve(process.argv[1] || ""); } catch { return false; }
}
