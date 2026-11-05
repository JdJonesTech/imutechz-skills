/* Read-only stills of web pages, with cookie and consent banners hidden.

     node scripts/shot.mjs <project> <url> [<url> ...] [--width 1440] [--height 900] [--dpr 2] [--full] [--wait 2.5] [--keep-banners]

   Writes <project>/assets/shots/<host>-<path>.png and prints one JSON line:
     {"shots": [{url, file, title, hidden, width, height} | {url, error}]}

   Nothing is clicked, typed or submitted: a banner is hidden with CSS, never dismissed, so no consent is given on
   anyone's behalf. Only http(s) pages are opened. */
import fs from "node:fs";
import path from "node:path";
import dns from "node:dns/promises";
import net from "node:net";
import { launch, parseArgs, main, isMain, sleep } from "./common.mjs";

/* containers of the common consent tools, plus the usual home-made ids and classes */
export const BANNER_SELECTORS = [
  "#onetrust-consent-sdk", "#onetrust-banner-sdk", "#CybotCookiebotDialog", "#CybotCookiebotDialogBodyUnderlay", "#cookie-law-info-bar",
  ".cc-window", ".cc-banner", "#cookieConsent", "#cookie-consent", "#cookie-banner", ".cookie-banner", ".cookie-consent", ".cookie-notice",
  "#cookie-notice", "#gdpr-consent", ".gdpr-banner", "#usercentrics-root", "#didomi-host", ".didomi-popup-container", "#truste-consent-track",
  ".truste_box_overlay", "#qc-cmp2-container", ".osano-cm-window", "#hs-eu-cookie-confirmation", ".fc-consent-root", "#sp_message_container",
  "[id^='sp_message_container']", ".evidon-banner", "#axeptio_overlay", ".cky-consent-container", "#iubenda-cs-banner", "#termly-code-snippet-support",
  "[aria-label*='cookie' i][role='dialog']", "[aria-label*='consent' i][role='dialog']",
];

/** True for an address a screenshot must not reach: loopback, private, link-local, unspecified, multicast, reserved. */
export function privateAddress(ip) {
  const v = net.isIP(ip);
  if (v === 4) {
    const [a, b] = ip.split(".").map(Number);
    return a === 0 || a === 10 || a === 127 || a >= 224 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127);
  }
  if (v === 6) {
    const s = ip.toLowerCase();
    const m = s.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
    if (m) return privateAddress(m[1]);
    return s === "::" || s === "::1" || /^f[cd]/.test(s) || /^fe[89ab]/.test(s) || s.startsWith("ff");
  }
  return false;
}

const hostCache = new Map();
/** True when a host must be refused: localhost, .local names, or any address it resolves to is private. */
export async function privateHost(host) {
  const h = String(host || "").replace(/^\[|\]$/g, "").toLowerCase().replace(/\.$/, "");
  if (!h || h === "localhost" || /\.(localhost|local|internal|localdomain)$/.test(h) || h.endsWith(".home.arpa")) return true;
  if (net.isIP(h)) return privateAddress(h);
  if (!hostCache.has(h)) hostCache.set(h, dns.lookup(h, { all: true }).then((r) => r.some((x) => privateAddress(x.address)), () => false));
  return hostCache.get(h);
}

/** A file-safe name for a URL: host plus path, no query string. */
export function slugOf(url) {
  const u = new URL(url);
  const s = (u.hostname.replace(/^www\./, "") + u.pathname).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return s.slice(0, 80) || "page";
}

/** Runs in the page: hide known consent containers, then fixed or sticky boxes that talk about cookies. Returns how many it hid. */
export function hideBanners(selectors) {
  let n = 0;
  const hide = (e) => { if (e && e.style && e.style.display !== "none") { e.style.setProperty("display", "none", "important"); n++; } };
  for (const s of selectors) { try { document.querySelectorAll(s).forEach(hide); } catch { /* a selector this browser rejects */ } }
  const vw = window.innerWidth, vh = window.innerHeight;
  for (const e of document.querySelectorAll("body *")) {
    const cs = getComputedStyle(e);
    if (cs.position !== "fixed" && cs.position !== "sticky") continue;
    const r = e.getBoundingClientRect();
    if (r.width < 200 || r.height < 40 || r.width * r.height > vw * vh * 0.6) continue;   // a full-page layer is the page itself
    const text = (e.innerText || "").slice(0, 600);
    if (/cookie|consent|gdpr|privacy preferences/i.test(text) && /accept|agree|allow|reject|manage|preferences|got it|ok/i.test(text)) hide(e);
  }
  // a consent tool often locks scrolling on <html> or <body>
  for (const e of [document.documentElement, document.body]) if (e && getComputedStyle(e).overflow === "hidden") e.style.setProperty("overflow", "auto", "important");
  return n;
}

if (isMain(import.meta.url)) main(async () => {
  const a = parseArgs();
  const [project, ...urls] = a._;
  if (!project || !urls.length) throw new Error("usage: node scripts/shot.mjs <project> <url> [<url> ...] [--full] [--width 1440] [--height 900] [--dpr 2]");
  for (const u of urls) if (!/^https?:\/\//i.test(u)) throw new Error(`only http(s) pages can be captured: ${String(u).slice(0, 60)}`);
  const allowPrivate = !!a["allow-private"];
  if (!allowPrivate) for (const u of urls) if (await privateHost(new URL(u).hostname)) throw new Error(`refused a local or private address: ${String(u).slice(0, 80)} (pass --allow-private if you mean it)`);
  const W = Math.round(+a.width || 1440), H = Math.round(+a.height || 900), dpr = Math.min(3, Math.max(1, +a.dpr || 2));
  const wait = Math.min(15, Math.max(0, a.wait != null ? +a.wait : 2.5));
  const outDir = path.join(project, "assets", "shots");
  fs.mkdirSync(outDir, { recursive: true });
  /* Chrome keeps its sandbox here (a page is untrusted) unless we run as root or FISH_NO_SANDBOX=1 */
  const sandbox = !(process.getuid && process.getuid() === 0) && process.env.FISH_NO_SANDBOX !== "1";
  let b;
  try { b = await launch({ sandbox }); } catch (e) {
    if (!sandbox) throw e;
    throw new Error(`Chrome would not start with its sandbox (${String(e && e.message ? e.message : e).split("\n")[0].slice(0, 120)}). Set FISH_NO_SANDBOX=1 to run it without the sandbox.`);
  }
  const shots = [];
  try {
    for (const url of urls) {
      const p = await b.newPage();
      try {
        await p.setViewport({ width: W, height: H, deviceScaleFactor: dpr });
        if (!allowPrivate) {
          await p.setRequestInterception(true);       // a public page must not reach into this machine or its network
          p.on("request", async (r) => {
            try {
              const u = new URL(r.url());
              if (/^https?:$/.test(u.protocol) && await privateHost(u.hostname)) return r.abort("blockedbyclient");
            } catch { /* data: and blob: URLs parse fine; anything odd falls through */ }
            r.continue().catch(() => {});
          });
        }
        try { await p.goto(url, { waitUntil: "networkidle2", timeout: 35000 }); } catch (e) { if (!/timeout/i.test(String(e))) throw e; /* a busy page: shoot what has loaded */ }
        await sleep(wait * 1000);
        const hidden = a["keep-banners"] ? 0 : await p.evaluate(hideBanners, BANNER_SELECTORS);
        if (hidden) await sleep(250);
        const file = path.join(outDir, `${slugOf(url)}.png`);
        await p.screenshot({ path: file, fullPage: !!a.full });
        shots.push({ url, file, title: (await p.title()).slice(0, 140), hidden, width: W, height: H, dpr });
      } catch (e) {
        shots.push({ url, error: String(e && e.message ? e.message : e).slice(0, 200) });
      } finally {
        await p.close();
      }
    }
  } finally {
    await b.close();
  }
  console.log(JSON.stringify({ shots }));
});
