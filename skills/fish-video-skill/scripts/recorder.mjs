/* Frame-exact recorder for live web pages.

   A Shot opens a page on virtual time (vt.js): the page's clocks, timers,
   requestAnimationFrame and Web Animations only move when we call
   __vt.advance(1000/fps). Each frame advances exactly one frame of page
   time, waits for in-flight fetches while time stands still, and saves a
   JPEG — so canvas hero animations and CSS transitions come out perfectly
   smooth however slow the screenshot is.

   The pointer is a real puppeteer mouse (hover states fire). Its path,
   clicks and keys are written to meta.json, and the stage draws the cursor,
   click ripples and key badges from that data at render time. */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { sleep } from "./common.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const VT = fs.readFileSync(path.join(here, "vt.js"), "utf8");
export const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);

export class Shot {
  /**
   * @param browser puppeteer Browser
   * @param id      shot id (folder name)
   * @param outRoot captures root (build/cap)
   * @param o       {w, h, dpr, fps, quality, theme, storage, hide, css}
   */
  constructor(browser, id, outRoot, o = {}) {
    this.browser = browser;
    this.id = id;
    this.dir = path.join(outRoot, id);
    this.w = o.w || 1440;
    this.h = o.h || 810;
    this.dpr = o.dpr || 2;
    this.fps = o.fps || 30;
    this.quality = o.quality || 88;
    this.theme = o.theme || "light";
    this.storage = o.storage || {};
    this.session = o.session || {};
    this.hide = o.hide || [];
    this.css = o.css || "";
    this.frames = [];
    this.mouse = { x: this.w * 0.62, y: this.h * 0.66 };
    this.down = false;
    this.pendingClick = 0;
    this.pendingKey = null;
    this.marks = {};
    this.errors = [];
  }

  /** Open url on virtual time and settle it (unrecorded) for settle ms. */
  async open(url, { settle = 1200, waitFor = null, realSettle = false } = {}) {
    fs.rmSync(this.dir, { recursive: true, force: true });
    fs.mkdirSync(this.dir, { recursive: true });
    this.ctx = await this.browser.createBrowserContext();
    const p = (this.page = await this.ctx.newPage());
    await p.setViewport({ width: this.w, height: this.h, deviceScaleFactor: this.dpr });
    await p.emulateMediaFeatures([
      { name: "prefers-color-scheme", value: this.theme },
      { name: "prefers-reduced-motion", value: "no-preference" },
    ]);
    p.on("pageerror", (e) => { this.errors.push(e.message); console.log(`  [${this.id}] pageerror: ${e.message.slice(0, 160)}`); });
    await p.evaluateOnNewDocument((ls, ss) => {
      try { for (const k in ls) localStorage.setItem(k, ls[k]); } catch (e) {}
      try { for (const k in ss) sessionStorage.setItem(k, ss[k]); } catch (e) {}
    }, this.storage, this.session);
    await p.evaluateOnNewDocument(VT);
    const css = [
      "html{scroll-behavior:auto!important}",
      "::-webkit-scrollbar{display:none}",
      "nextjs-portal{display:none!important}",
      ...this.hide.map((s) => `${s}{display:none!important}`),
      this.css,
    ].join("\n");
    await p.evaluateOnNewDocument((css) => {
      const add = () => { const s = document.createElement("style"); s.textContent = css; (document.head || document.documentElement).appendChild(s); };
      if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", add); else add();
    }, css);
    this.cdp = await p.createCDPSession();
    await p.goto(url, { waitUntil: "load", timeout: 180000 });
    if (realSettle) await sleep(settle); else await this.settle(settle);
    if (waitFor) await p.waitForSelector(waitFor, { timeout: 60000 });
    await p.mouse.move(this.mouse.x, this.mouse.y);
    return p;
  }

  /** Advance virtual time in real time without recording (page settling). */
  async settle(ms) {
    const steps = Math.ceil(ms / 33);
    for (let i = 0; i < steps; i++) {
      await this.page.evaluate(() => window.__vt && window.__vt.advance(33.333));
      await sleep(10);
    }
  }

  async waitNet(max = 8000) {
    const t0 = Date.now();
    for (;;) {
      const n = await this.page.evaluate(() => (window.__vt ? window.__vt.pending() : 0));
      if (!n || Date.now() - t0 > max) break;
      await sleep(40);
    }
  }

  /** Record one frame: advance 1/fps of page time, wait for network, save. */
  async frame() {
    const p = this.page;
    await p.evaluate((ms) => window.__vt.advance(ms), 1000 / this.fps);
    await this.waitNet();
    await sleep(6);
    const { data } = await this.cdp.send("Page.captureScreenshot", { format: "jpeg", quality: this.quality, optimizeForSpeed: true });
    const n = this.frames.length;
    fs.writeFileSync(path.join(this.dir, String(n).padStart(5, "0") + ".jpg"), Buffer.from(data, "base64"));
    const scrollY = await p.evaluate(() => window.scrollY);
    this.frames.push({ x: +this.mouse.x.toFixed(1), y: +this.mouse.y.toFixed(1), d: this.down ? 1 : 0, c: this.pendingClick, k: this.pendingKey, s: Math.round(scrollY) });
    this.pendingClick = 0;
    this.pendingKey = null;
    if (n % 30 === 0) process.stdout.write(`  [${this.id}] frame ${n}\r`);
  }

  mark(name) { this.marks[name] = this.frames.length; }
  async hold(n) { for (let i = 0; i < n; i++) await this.frame(); }

  /** Move the pointer along a gentle quadratic arc, like a hand. */
  async moveTo(x, y, n = 18) {
    const x0 = this.mouse.x, y0 = this.mouse.y;
    const mx = (x0 + x) / 2 + (y - y0) * 0.12, my = (y0 + y) / 2 - (x - x0) * 0.12;
    for (let i = 1; i <= n; i++) {
      const t = ease(i / n);
      const a = (1 - t) * (1 - t), b = 2 * (1 - t) * t, c = t * t;
      this.mouse.x = a * x0 + b * mx + c * x;
      this.mouse.y = a * y0 + b * my + c * y;
      await this.page.mouse.move(this.mouse.x, this.mouse.y);
      await this.frame();
    }
  }

  /** Centre of the first element matching a CSS selector or containing text. */
  async locate({ sel, text }) {
    const r = await this.page.evaluate((sel, text) => {
      let el = null;
      if (sel) el = document.querySelector(sel);
      if (!el && text) {
        const all = [...document.querySelectorAll("a,button,h1,h2,h3,h4,p,li,span,label,[role=button],[role=tab]")];
        el = all.find((e) => e.children.length < 6 && (e.textContent || "").trim().toLowerCase().startsWith(text.toLowerCase()));
      }
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return { x: b.left + b.width / 2, y: b.top + b.height / 2, top: b.top + window.scrollY, w: b.width, h: b.height };
    }, sel || null, text || null);
    if (!r) throw new Error(`[${this.id}] not found: ${sel || text}`);
    return r;
  }

  async click(after = 6, { fake = false } = {}) {
    this.down = true;
    if (!fake) await this.page.mouse.down();
    this.pendingClick = 1;
    await this.frame();
    await this.frame();
    if (!fake) await this.page.mouse.up();
    this.down = false;
    await this.hold(after);
  }

  async key(k, n = 2, mods = []) {
    for (const m of mods) await this.page.keyboard.down(m);
    await this.page.keyboard.press(k);
    for (const m of mods.slice().reverse()) await this.page.keyboard.up(m);
    this.pendingKey = (mods.length ? mods.join("+") + "+" : "") + k;
    await this.hold(n);
  }

  async type(str, perChar = 3) {
    for (const ch of str) {
      await this.page.keyboard.type(ch);
      this.pendingKey = ch;
      await this.hold(perChar);
    }
  }

  async scrollTo(y, n = 30) {
    const y0 = await this.page.evaluate(() => window.scrollY);
    const max = await this.page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);
    y = Math.max(0, Math.min(max, y));
    for (let i = 1; i <= n; i++) {
      const yy = Math.round(y0 + (y - y0) * ease(i / n));
      await this.page.evaluate((v) => window.scrollTo({ top: v, behavior: "instant" }), yy);
      await this.frame();
    }
  }

  async eval(fn, ...args) { return this.page.evaluate(fn, ...args); }

  async close() {
    const meta = { id: this.id, fps: this.fps, w: this.w, h: this.h, dpr: this.dpr, count: this.frames.length, marks: this.marks, frames: this.frames, errors: this.errors };
    fs.writeFileSync(path.join(this.dir, "meta.json"), JSON.stringify(meta));
    await this.ctx.close();
    console.log(`  [${this.id}] ${this.frames.length} frames -> ${this.dir}`);
    return meta;
  }
}
