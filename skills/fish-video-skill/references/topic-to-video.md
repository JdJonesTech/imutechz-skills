# From a single topic to a finished script

The user may give only a word ("habits", "black holes", "our app"), or ask for topic ideas. This is the method for getting from there to a script. Run it inside the interview, so the user picks the angle *before* creation starts.

## 1. Topic suggestions (when the user has no topic or only a broad area)

Run these in parallel, as haiku subagents:

```bash
fishvideo yt suggest "<area>"                       # what people type: autocomplete
fishvideo yt search "<area>" --n 25 --recent-days 30
fishvideo trends <dir> --topic "<area>" --region <IN|US> --days 30   # research/trends.md: ranked by views/day
```

From these, build **5 topic options**. Each option has:
- **an angle**: a specific question, tension or claim, never just the subject
- **evidence it is trending**: the top recent video's views per day, and how many autocomplete hits it has
- **the format it suits**: one of the style recipes
- **a working hook line**: at most 10 words

Offer them as one `AskUserQuestion` question (4 options plus Other). This is interview question `topic`.

Angle formulas that rank (pick the one that fits the evidence):

| Formula | Example shape |
|---|---|
| Hidden mechanism | "Why X actually happens" / "What really happens when X" |
| Expectation vs reality | "X: what you think vs what's true" |
| Comparison | "A vs B vs C" (works well as a stick-fable or neon chart) |
| Number list | "3 X that Y" (only when the items are real and sourced) |
| Mistake | "Stop doing X" / "You're doing X wrong" |
| Transformation | "From X to Y in N steps" |
| Origin | "The X nobody tells you about" |

## 2. Research the chosen angle

- Facts come from primary sources and are copied into `brief.facts` with their source.
- Top 3 videos on the angle: run `yt subs` on each and read their hooks and their structure. Note what they **miss**; that gap becomes your edge.
- Nouns to visualise: list every concrete object the script will name. Each one becomes an asset search or a drawn element.

## 3. Write the script (you, the main agent)

1. **One sentence.** "This video shows ___ so that the viewer ___." If you can't write it, go back to step 2.
2. **Beats.** Use 4–8 meaning beats from the style recipe: hook, claim, human moment, concept, escalation, turn, payoff, end. Give each beat **one idea** and **one hero visual** (an object, a diagram or a screen moment).
3. **Hook (0–2 s).** Use the chosen hook kind.
   - Name the tension, not the subject.
   - It is the first line of the narration *and* the first frame.
   - Never start with a greeting, the channel name or "In this video".
4. **Narration.**
   - Speech rate by delivery: about 3 words/s (punchy), 2.4 (calm), 2.2 (cinematic).
   - A 30 s Short holds 65–85 words.
   - Use short sentences and second person ("you").
   - Use concrete verbs. Put one surprising fact or number (sourced) by 40% of the runtime.
5. **Open loop.** Promise something in the hook that is paid off in the payoff beat ("…and the third one is why most people fail").
6. **Payoff and end.** Resolve the loop. End with a CTA in one line, or a loop line that flows back into the hook.
7. **On-screen words.** For each beat, pick 1–4 words from its narration as the hero text, and choose the one accent word.
8. **Read it aloud** at the target pace and time it. Cut 10%.

Write the script into `storyboard.yaml` (`say:` per scene), and its one-sentence summary into `brief.summary`.

## 4. Titles, description and tags (from the same research)

- **5 titles**, using the formulas that rank in `research/trends.md`. Each is at most 60 characters, with the hook word first. Put numbers in digits. Don't write clickbait the video doesn't deliver.
- **Description.** The first 2 lines restate the hook and the promise, followed by chapters (for long videos), sources and credits.
- **Tags.** Up to 15: the top recurring tags of the ranking videos, plus your own specific nouns.
- **Hashtags.** 3–5: one broad, two niche, and the format (#shorts).
