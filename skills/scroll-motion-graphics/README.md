# scroll-motion-graphics

An agent skill by **ImuTechz** (v1.0.0, MIT). It turns scroll position into a motion-graphics timeline: a pinned canvas film that scrubs both ways like a video, captions the drawing never runs under, and a 3D story drum you can scroll, drag, click or step with the arrow keys.

This is the method behind the story drum on the ImuTechz home page, the R&D drum and the Founder path film. It is written down so an AI agent (or a person) can build the same thing.

## Try it

Double-click **`assets/demo.html`**. It is one file with zero dependencies and works offline. Scroll through the five reels (orbit, path, stack, wave, close), scroll back to watch them rewind, then roll the drum.

## Install it for an agent

Copy this whole folder into your agent's skills directory:

```text
~/.claude/skills/scroll-motion-graphics/     # Claude Code
.cursor/skills/scroll-motion-graphics/       # Cursor
.opencode/skills/scroll-motion-graphics/     # OpenCode
```

Keep `references/` and `assets/` next to `SKILL.md`. Then ask for the work, for example: *"Add a scroll-scrubbed film to the landing page that explains our four steps, with a drum that links to each docs page."*

## Use the code directly

Vanilla (classic scripts, no build):

```html
<link rel="stylesheet" href="scroll-motion.css">
<script src="scroll-motion.js"></script>
<script src="reels.js"></script>
<script>
  const film = document.querySelector(".smf");
  ScrollMotion.film({
    track: film,
    stage: film.querySelector(".smf-stage"),
    canvas: film.querySelector(".smf-canvas"),
    reels: ScrollReels.all,
    captions: [...film.querySelectorAll(".smf-cap")],
  });
  ScrollMotion.drum(document.querySelector(".sd"));
</script>
```

React and Next.js (client components):

```jsx
import "./scroll-motion.css";
import ScrollFilm from "./ScrollFilm";
import StoryDrum from "./StoryDrum";
import Reels from "./reels";          // import after ScrollFilm

<ScrollFilm title="Five reels" reels={Reels.all} captions={captions} />
<StoryDrum title="Roll the drum." chapters={chapters} />
```

Copy the HTML structure from `demo.html` (or the components), then replace the reels and the words.

## What's inside

| Path | What it is |
| --- | --- |
| `SKILL.md` | The contract: what good looks like, hard rules, build order, checklists, failure modes |
| `references/engine.md` | p from scroll, the idle-stopping loop, `film()`, seeking, React |
| `references/drawing.md` | The pure-reel contract, canvas setup, drawing patterns, palette |
| `references/layout-and-captions.md` | Sticky track and stage, keep-outs, the free rect, the clip, the drum layout |
| `references/motion-grammar.md` | Enter, hold and exit, easing, stagger, dwell, pacing, reduced motion |
| `references/performance-and-a11y.md` | Idle cost, layout order, input rules, keyboard, screen readers, contrast |
| `references/verification.md` | The eight widths, a headless browser script and the manual pass |
| `assets/demo.html` | A runnable demo with everything inlined |
| `assets/scroll-motion.js` | The engine: `scrub`, `film`, `drum`, `scrollToProgress`, helpers (UMD) |
| `assets/reels.js` | Five example reels plus `still()` for thumbnails |
| `assets/scroll-motion.css` | Film and drum styles with light and dark tokens |
| `assets/ScrollFilm.jsx` | React film wrapper plus the `useScrub` hook |
| `assets/StoryDrum.jsx` | React story drum plus `DrumPreview` |
| `assets/preview-*.jpg` | Stills of the demo at 1440 × 900 |

## The rules in one breath

Scroll is the only clock. Reels are pure functions of progress. Words live in the DOM and the drawing stays off them. Never capture input; every control seeks by scrolling. The loop stops when nothing moves. Honour reduced motion. Verify at 360, 390, 414, 768, 1024, 1280, 1440 and 1920.

## Browser support

Current Chrome, Edge, Firefox and Safari 15.4+. It relies on `position: sticky`, `svh` units, `IntersectionObserver`, `ResizeObserver` and Canvas 2D `clip("evenodd")`. `ctx.roundRect` is used when available, with a fallback.

## License

MIT © 2026 ImuTechz. See `LICENSE`.
