# Website-tour capture

Filming a real website or web app is the strongest proof a video can offer. This method produces smooth, repeatable, frame-exact footage of any page, including canvas, WebGL and CSS-animated pages, plus a data track of the cursor, clicks and keys that the stage turns into a drawn cursor, ripples, key badges and camera moves.

## Virtual time (the core trick)

A headless screenshot takes 50–300 ms. If the page's clocks keep running in real time, every animation jumps between frames. `scripts/vt.js` is injected with `evaluateOnNewDocument` *before* any page script, and it replaces:
- `performance.now`, `Date` and `Date.now`, which return `epoch + virtual now`
- `setTimeout`, `setInterval` and their clear functions, which go into a queue ordered by virtual due time
- `requestAnimationFrame` and `cancelAnimationFrame`, which are queued and run once per advance
- **Web Animations** (CSS transitions and keyframes), through `document.getAnimations()`: each animation is paused and its `currentTime` set from virtual time. An animation past its end is really `finish()`ed, so its finish events fire.
- `fetch`, which is wrapped to count in-flight requests (`__vt.pending()`)

`__vt.advance(ms)` runs every timer due within the window in order, then one rAF batch, then syncs the animations. The recorder calls it with exactly `1000/fps` before each screenshot, then waits for `pending() == 0` (network answers arrive while page time stands still). The result:
- Particle heroes, counters and transitions are perfectly smooth at 30 fps, however slow the capture is.
- A re-capture is close to identical.

Limits:
- Animations driven by `<video>` playback, CSS `scroll-timeline`, or Web Workers' own clocks are not virtualised. Prefer pages without those, or hold still while they play.
- Pages that poll the wall clock through `new Date()` *inside workers* will drift; this is rare.

## Recording a shot (`capture.mjs`)

Shots are listed in the storyboard. `fishvideo storyboard` writes `build/captures.json`, and `fishvideo capture <dir> [shot…]` records them to `build/cap/<id>/00000.jpg …` plus `meta.json`, which holds:
- `w`, `h`, `dpr`, `fps`, `count`
- `marks {name: frame}`
- `frames[{x, y, d, c, k, s}]`: the pointer, button down, a click this frame, a key this frame, and scrollY
- `errors`

```yaml
captures:
  - id: docs
    url: https://example.com/docs
    viewport: {w: 1440, h: 810}     # 16:9 page; 1280x720 is lighter
    dpr: 1.5                        # 1.5–2 keeps text sharp when the camera zooms
    theme: light                    # prefers-color-scheme
    storage: {theme: light}         # localStorage before load
    session: {intro-played: "1"}    # sessionStorage before load (skip intros)
    hide: [".cookie-banner", "#chat-widget"]
    settle: 1500                    # ms of virtual time before recording
    actions:
      - {mark: index}
      - {hold: 30}                                  # frames
      - {move: {text: "Search"}, frames: 22}        # move to the element whose text starts with "Search"
      - {click: true, after: 10}
      - {mark: ctrlk}
      - {key: k, mods: [Control]}                   # recorded as a key-combo badge
      - {type: "streming", per_char: 3}
      - {mark: type}
      - {wait: 1.2}                                 # seconds
      - {key: Enter}
      - {mark: landed}
      - {scroll: {text: "Streaming"}, offset: 120, frames: 40}
      - {move: {sel: "h2#api"}, dx: -40, frames: 18}
      - {eval: "document.querySelector('details')?.setAttribute('open','')"}
  - {id: home, url: "https://example.com", auto: {seconds: 10}}   # automatic tour
```

Each action:
- `hold: n` holds for n frames; `wait: s` holds for s seconds.
- `mark: name` names the current frame. Use it for scene `from`, `cam` keys and callout timing.
- `move: {sel | text | x,y, dx, dy}` moves along a gentle quadratic arc with ease-in-out, like a hand, over `frames` (or `s`). Hover states fire, because it is a real `page.mouse`.
- `click` presses for 2 frames, then holds for `after`. `fake: true` draws a ripple without clicking.
- `type` types per character, with key sounds.
- `key` presses with modifiers.
- `scroll: {sel | text | y | by}` is an eased scroll over `frames`.
- `eval` runs a script in the page (use it sparingly, for example to open a disclosure).

`auto: {seconds, stops, step}`: holds on the hero, sweeps the cursor, then scrolls about 0.85 viewport per stop, marking `s0`, `s1`, …

## Directing the tour

1. **Plan the shot list from the script.** Each `tour` scene needs one shot (or one marked section of a shot) that shows exactly what is being said.
2. **Record about 1.5× the scene length.** The scene picks a window with `from` and `speed` (1.0–1.6). `storyboard` warns when the footage is shorter than the scene.
3. **Move with purpose.** The cursor goes to what the narration names, rests 0.5–1 s, then acts. Keep the path short, and don't circle.
4. **Camera:**
   - Start wide (`z: 1`).
   - Push in (`z: 1.15–1.35`) on the element being discussed, with explicit `x,y` in page pixels so the frame is stable.
   - Pull back before the cut.
   - Don't zoom past 1.5 unless `dpr ≥ 2`.
5. **Callouts:**
   - One at a time, ≤ 6 words, with one `*accent*` word.
   - Anchor to page coordinates (`page: {x, y}`) so the callout follows the camera.
   - Time it from a mark (`m`, `d`).
6. **Light and dark:** to show both, capture two shots, or click the site's own theme toggle on camera.

## Safety and etiquette (read-only)

- Film public pages, the user's own product, or the user's local dev server only.
- Never sign in, submit forms, purchase, post, or click anything destructive. Typing into a search box is fine.
- Don't film personal data (other people's names, emails or dashboards). Use staging or demo data.
- Hide cookie banners and chat widgets rather than clicking them away.
- A dev server is the user's: never stop or restart it. Capture against it as a visitor.
- If the UI shows numbers it measures *from the recording browser* (FPS, tokens/s, latency), hide them. They describe the headless capture, not the product.

## Troubleshooting

| Problem | Fix |
|---|---|
| Black WebGL canvas | The launch flags `--use-angle=swiftshader --enable-unsafe-swiftshader` (already set). |
| Intro animation or splash on every shot | `session`/`storage` flags that the site uses to skip it, or a longer `settle`. |
| Text selector not found | Use `sel:` with a stable selector. `text:` matches the start of an element's text, case-insensitively. |
| Lazy images still blank | Increase `settle`, add `{wait: 0.5}` after scrolls, or `{eval: "window.scrollTo(0, document.body.scrollHeight)"}` then back during settle. |
| Footage jumps when the page loads a font late | Add `wait_for: "body.fonts-ready"`, or a longer settle. |
| Captures too heavy | Use `dpr: 1` and quality 80. A 10 s shot at 1440×810 dpr 1.5 is about 300 JPEGs, about 60 MB. |
