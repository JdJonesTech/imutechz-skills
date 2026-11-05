# Long-format roadmap and explainer videos

Load this when the video is longer than about 3 minutes and walks through stages: a roadmap, a learning path, a "how to become X".

## What was measured (November 2026)

Five popular videos were downloaded for analysis only, measured with `reference.py analyse --threshold 0.2`, and sampled by eye every 20 seconds.

| Channel and video | Format | Cuts per minute | Median shot |
|---|---|---|---|
| Akber Shaikh, AI Engineer Roadmap 2026 | Presenter with pop-up graphics | 17.2 | 2.8 s |
| CodeHead, A Practical Guide to Becoming an AI Engineer | No presenter: dark node map, memes, real screenshots | 7.1 | 4.3 s |
| Sajjaad Khader, How to Become a $300K AI Engineer | Presenter with level-by-level animation | 5.7 | 7.3 s |
| Fireship, This video was made with code | Code, logos, occasional meme | 5.2 | 6.3 s |
| ByteByteGo, 8 Most Important System Design Concepts | Animated diagrams only | 1.6 | 20.1 s |

**Limit of these numbers:** scene detection undercounts animation, because movement inside a shot is not a cut. ByteByteGo looks far busier than 1.6 suggests. Five videos and a 20-second sample show a pattern, not a rule.

## What to do with it

- Without a presenter, the map must be the recurring character. Return to it at every chapter: open wide, then push in to the current stop (`roadmap`, `open_wide`).
- Show the real thing. A real website behind a concept reads as proof; capture it read-only and remove or crop cookie banners.
- Use a change of picture every few seconds, but let the narration set the pace. One real user rejected a fast cut as "extra paced" and approved a rewritten, slower version at about 2.9 words/s with real pauses.
- **Look for empty frames yourself.** Technical QA passes on a frame with an empty bottom half. Tile the video and open the sheet; `qa` now warns on flat regions, but it cannot judge whether a frame is good.

## Memes without copyright claims

Memes from films and shows are usually copyrighted, and they can get a video claimed or muted. Silent films published before 1931 are a practical licence-safe source. Wikimedia Commons hosts many, with a licence field to check.

- Strip the audio track: a restoration may carry a newer score.
- A caption turns any clip into a joke about the topic ("ME vs EVERY NEW AI TOOL").
- **Open every moment you use.** Some films from this era contain racist gags, including blackface. Choose exact seconds, not whole reels.
- Public domain does not stop an automated claim on a restored print. Say so in the review.
- Exact viral sounds are rarely licensed. Use a credited equivalent, such as a CC-licensed sad trombone, and tell the user it is not the original.
