# Voice direction

## The default voice

| | |
|---|---|
| Provider | **ElevenLabs** (default) |
| Voice | `fydPJq00SigRIaPxWgiS`, English (India): https://elevenlabs.io/voices/fydPJq00SigRIaPxWgiS |
| Model | `eleven_multilingual_v2` |
| Settings | stability 0.42 · similarity_boost 0.8 · style 0.18 · use_speaker_boost true · speed 0.96 (max 1.12) |
| Context | `previous_text` / `next_text` sent with every line (`use_context: true`), so the intonation carries across lines |
| Endpoint | `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128`, header `xi-api-key` |
| Key | `ELEVENLABS_API_KEY` from the environment, or from a **gitignored** `.env` in the project or skill folder. Never printed, logged, written to metadata, or committed. |
| Fallback | **edge-tts** `en-IN-NeerjaNeural`, rate -6%, pitch +0 Hz. It is free and needs internet. It is used automatically when no key is set, or when an ElevenLabs call fails; the run prints a `!!` line saying so, and `metadata.json` records `stand_in_for`. |

These settings match `Promotion/src/explainer/voice.config.json`, which is used for the ImuTechz explainer. Change them per project in `brief.yaml` under `voice:`.

```yaml
voice:
  provider: elevenlabs          # elevenlabs | edge-tts | none
  language: en-IN
  elevenlabs: {voice_id: fydPJq00SigRIaPxWgiS, model_id: eleven_multilingual_v2,
               voice_settings: {stability: 0.42, similarity_boost: 0.8, style: 0.18, use_speaker_boost: true, speed: 0.96}}
  fallback: {provider: edge-tts, voice: en-IN-NeerjaNeural, rate: "-6%"}
  pronunciations: {IMURUN: "Imu run", GGUF: "G G U F", ImuTechz: "Imu techs"}
```

## Word timings

- **ElevenLabs** returns `alignment.characters` with start and end times per character. `voice.eleven_words` groups characters into words on whitespace. A word is timed by its *letters and digits only*, so a trailing comma does not stretch the word.
- **edge-tts** emits `WordBoundary` events (offset and duration in 100 ns ticks). The script locates each one in the spoken string to get a character index.
- Both are mapped back to **displayed** words through the `{shown|spoken}` units. Captions therefore show "GGUF" while the voice says "G G U F".

## Respelling: `{shown|spoken}`

Write what the viewer should *read* on the left and what the voice should *say* on the right.

| Shown | Spoken | Why |
|---|---|---|
| `{GGUF\|G G U F}` | letters | Acronyms spelled out |
| `{SQL\|sequel}` | a word | Acronyms said as words, where that is the convention |
| `{v0.3\|version zero point three}` | expanded | Versions |
| `{10,631\|ten thousand six hundred and thirty-one}` | words | Big numbers (en-IN may otherwise say "ten thousand, six thirty-one") |
| `{2.1×\|two point one times}` | words | Symbols |
| `{C++\|C plus plus}` | words | Punctuation in names |
| `{Ctrl K\|Control K}` | full | Keys |
| `{imutechz.in\|Imu techs dot in}` | spoken URL | Domains |
| `{Qwen\|Kwen}`, `{Phi\|Fye}`, `{LoRA\|Lora}` | phonetic | Brand and model names |
| `{R&D\|R and D}` | words | Ampersands |
| `{₹499\|four hundred and ninety-nine rupees}` | words | Currency, in the locale's order |

Put recurring words in `voice.pronunciations` once. They are applied to every line as whole words, but never inside an existing pair.

## Directing the read

- **Write for the ear.** Use short sentences, and put the verb early. Give one idea per line, because each line is one TTS call, one clip and one caption group.
- **Punctuation is direction.**
  - A comma is a short breath.
  - An ellipsis `…` is a held, thinking pause; use it before a reveal.
  - A colon sets up a list or payoff.
  - An em dash is an aside.
  - Question marks lift the pitch, so avoid them unless you mean them.
- **Emphasis:** the TTS stresses the new information at the end of a sentence. Put the key word last: "…runs on *your machine*."
- **Numbers:** say them once, clearly. Don't stack two numbers in one sentence.
- **Pace:** ElevenLabs speed 0.92–1.0 for explainers, 1.0–1.08 for promos. edge-tts rate -8% to +4%.
  - If a scene has a fixed `bars` and the line overruns, cut words before you speed up.
  - Never exceed `max_speed` 1.12 or `max_rate` +8%.
- **Consistency:** keep one voice per video, and keep settings identical across lines. Changing the text of one line re-voices only that line, because clips are cached by text and settings.

## Locales

| Locale | ElevenLabs | edge-tts fallback voices | Notes |
|---|---|---|---|
| en-IN (default) | `fydPJq00SigRIaPxWgiS` | `en-IN-NeerjaNeural` (f), `en-IN-PrabhatNeural` (m) | about 145 wpm; Indian number words ("lakh", "crore") only if the brand uses them |
| hi-IN | any multilingual_v2 voice with `language_code: hi` | `hi-IN-SwaraNeural` (f), `hi-IN-MadhurNeural` (m) | about 130 wpm; captions in Devanagari (Noto Sans Devanagari is bundled); keep product names in Latin script |
| en-US | multilingual voices | `en-US-AriaNeural`, `en-US-AndrewMultilingualNeural`, `en-US-GuyNeural` | about 155 wpm |
| en-GB | | `en-GB-SoniaNeural`, `en-GB-RyanNeural` | about 150 wpm |
| ta-IN, bn-IN, mr-IN, te-IN | multilingual_v2 | `ta-IN-PallaviNeural`, `bn-IN-TanishaaNeural`, `mr-IN-AarohiNeural`, `te-IN-ShrutiNeural` | check whether the caption font covers the script; add a Noto face via `brand.font_files` |
| es, fr, de | multilingual_v2 | `es-ES-ElviraNeural`, `fr-FR-DeniseNeural`, `de-DE-KatjaNeural` | text expands 15–30%; recheck the fits |

List voices with `python scripts/voice.py voices --locale en-IN`. The command lists edge-tts voices, plus your ElevenLabs voices when a key is set.

## No narration

Set `voice: {provider: none}` for a music-only cut. Scenes then size from their animation, captions are empty, and on-screen text has to carry the message. Use kinetic and bullets more, and add 1–2 bars to every text scene.

## Checklist

- [ ] Every acronym, number, symbol and brand word is respelled.
- [ ] I listened to the first and last line and to every number.
- [ ] No line is longer than about 20 words.
- [ ] The run says which provider was used. If it was the fallback, the user knows.
