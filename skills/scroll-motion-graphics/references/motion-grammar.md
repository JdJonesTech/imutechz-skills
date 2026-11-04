# Motion grammar

Scroll-driven motion has one property that timed animation does not: **the reader controls the speed and the direction.** Everything here follows from that. A sequence must read well at any speed, forwards or backwards, and when stopped at any point.

## Every reel has three acts

```text
 t: 0 ─────── 0.25 ─────────────── 0.75 ─────── 1
    │  enter  │        hold         │   exit    │
    build-up    the readable state    settle / hand-off
```

- **Enter** (about the first 25%): things arrive. Lines start drawing, items stagger in, the core grows.
- **Hold** (the middle): the frame is complete enough to read *while the caption is fully visible*. Keep secondary motion here, such as slow rotation, the head travelling or a phase shift, so it does not feel frozen. Nothing new should demand attention.
- **Exit** (the last 25%): resolve, then hand off. The crossfade to the next reel happens around the boundary, and the reel should look finished going into it.

Map this with windows:

```js
const grow   = ease.outCubic(seg(t, 0.00, 0.30));   // enter
const spokes =               seg(t, 0.45, 0.80);    // a second layer, in the hold
const fin    = ease.outCubic(seg(t, 0.78, 1.00));   // resolve
```

## The timeline across reels

| Constant | Default | Meaning |
| --- | --- | --- |
| `cross` | 0.12 | reels crossfade over ±12% of a reel around each boundary |
| `capFade` | 0.10 | a caption fades over 10% of a reel |
| caption visible | `u ∈ [cross + capFade, 1 − cross − capFade]` | about 56% of each reel at full opacity |

The first reel starts fully drawn with its caption up, so the first frame of the pin is never empty. The last reel never fades out, so the film ends on its resolved frame and the page scrolls on.

## Pacing: how tall is the track?

| Content | Scroll per unit |
| --- | --- |
| Film reel | 80 svh (phone) to 90 svh (desktop) per reel, plus 100 svh for the pin |
| Drum chapter | 70 vh per chapter, plus 100 vh |
| Route with N milestones | 40 to 46 vh per milestone, plus 100 svh |
| `view` mode effect (marquee, parallax) | no track: it rides the content |

Too short and a flick of the trackpad skips a whole reel. Too long and readers think the page is stuck. If unsure, use 90 svh per reel and test with a real trackpad and a real phone.

## Easing vocabulary

| Easing | Use it for | Avoid it for |
| --- | --- | --- |
| `smoothstep` (in-out) | the drum's dwell inside each step, crossfades | things that should *land* |
| `outCubic` | items arriving and settling: bars, growth | travel between two places |
| `outBack` | small things popping: nodes, dots, a core | large shapes (the overshoot looks like a glitch) |
| `inOutCubic` | travel from A to B: particles, camera moves | arrivals |
| linear | the travelled length of a line, a playhead, a progress bar | anything with mass |

Linear is right for *progress*. The reader should feel the line advancing in step with their scroll, so the head of a route moves linearly in arc length. Easing goes on the *things it reaches*.

## Stagger

```js
const k = stagger(t, i, n, span);   // item i's local 0..1; starts spread over (1 - span)
```

- `span` ≈ 0.3 to 0.5 gives overlapping arrivals that read as one gesture.
- `span` < `1/n` gives one-at-a-time arrivals, which read as a list. Use these deliberately (milestones, steps).
- Stagger along the reading direction: left to right, top to bottom, or inner ring to outer.

## Dwell: the drum's signature

```js
const f = p * (n - 1), base = Math.floor(f), t = f - base;
const turn = base + t * t * (3 - 2 * t);       // smoothstep inside each step
```

Linear rotation means the drum is almost always between faces. With a smoothstep per step, the derivative is zero at every face, so the drum *parks*: a comfortable stretch of scroll in which a face sits square to the reader, then a quick roll. The site's drums use exactly this, and so does the self-rolling preview, written as CSS keyframes that hold for 18% and roll for 7%.

## Direction symmetry

Scrubbing backwards plays every act in reverse. Check each reel backwards on purpose:

- A route un-draws. That is good.
- Particles fly back out to their scattered positions. That works only because the starting positions come from `hash(i)`, not `Math.random()`.
- One-shot effects (a flash when a node is reached) must be functions of distance-to-node, not events, or they never "un-flash".
- Caption entrances scrub too, because opacity and transform are written from p. That is why caption CSS must not animate them.

## Never on a clock

Do not use a pulsing glow driven by `time`, a CSS `animation` on a reel element, or an idle wobble. All three break purity (the same p gives a different frame), keep the loop alive and drain batteries. If you want life in the hold, derive it from `t`: rotation by `t × π`, phase by `t × 2π`. The one exception is a decorative, aria-hidden preview card such as `DrumPreview`, which is a CSS loop that stops under reduced motion.

## Velocity, with restraint

The R&D page's word roller skews rows by scroll *velocity* (`d = p − lastP`). That is acceptable for a decorative `view`-mode marquee, because it settles to zero skew when scrolling stops. Do not use velocity inside a film reel, because it makes the frame depend on how you arrived at p.

## Reduced motion

| Normal | Reduced |
| --- | --- |
| lerp smoothing toward the scroll target | none: p equals the scroll position |
| drum rolls between faces with dwell | drum snaps face to face (`Math.round(f)`) |
| caption cards slide 14 px as they fade | fade only, no transform |
| `.sd-cap` CSS entrance | `animation: none` |
| smooth `scrollTo` for controls | instant |
| self-rolling preview drum | still, front face |

The content, the order and every control stay the same. Only the in-between movement goes.
