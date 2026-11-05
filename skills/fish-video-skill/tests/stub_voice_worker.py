"""A stand-in for scripts/voicelab_worker.py: speech-like tones and a transcript read back from a sidecar file.
No models. Environment: STUB_F0 (Hz, default 120), STUB_BAD_SEEDS (comma list: the transcript drops the last word for those seeds),
STUB_LOG (a file that gets one line per job)."""
import json
import os
import struct
import sys
import wave

import numpy as np

SR = 24000


def write(path, x):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def speak(text, f0, word_s):
    t = np.arange(int(word_s * SR)) / SR
    env = np.minimum(1, np.minimum(t, word_s - t) / 0.02)
    tone = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 12)) * env * 0.12
    gap = np.zeros(int(0.04 * SR))
    return np.concatenate([np.concatenate([tone, gap]) for _ in text.split()] + [np.zeros(int(0.1 * SR))])


def main():
    job = json.loads(sys.stdin.read())
    if os.environ.get("STUB_LOG"):
        with open(os.environ["STUB_LOG"], "a") as fh:
            fh.write(job["op"] + "\n")
    op, res = job["op"], {"ok": True}
    if op == "probe":
        res["modules"] = {m: True for m in ("chatterbox", "kokoro", "faster_whisper", "perth", "torchaudio", "torch", "numpy")}
    elif op == "tts":
        items = []
        for it in job["items"]:
            f0 = float(os.environ.get("STUB_F0", 120))
            # a higher cfg_weight (Chatterbox) or speed (Kokoro) makes each word shorter, as the real engines do
            word_s = 0.42 * (1 - (float(it["cfg_weight"]) - 0.25)) if "cfg_weight" in it else 0.36 / float(it.get("speed", 1.0))
            x = speak(it["text"], f0, word_s)
            write(it["out"], x)
            with open(it["out"] + ".txt", "w") as fh:
                json.dump({"text": it["text"], "seed": it.get("seed"), "word_s": word_s}, fh)
            items.append({"out": it["out"], "sr": SR, "duration": len(x) / SR, "seconds": 0.0})
        res["items"] = items
    elif op == "transcribe":
        bad = {int(v) for v in os.environ.get("STUB_BAD_SEEDS", "").split(",") if v}
        out = {}
        for f in job["files"]:
            side = f + ".txt"
            if os.path.exists(side):
                meta = json.load(open(side))
                words = meta["text"].split()
                if meta["seed"] in bad and len(words) > 1:
                    words = words[:-1]
            else:                                        # a file the stub did not make: it hears nothing
                words = []
            step = 0.3
            out[f] = [{"text": w.strip(".,!?"), "start": round(i * step, 3), "end": round((i + 0.9) * step, 3)} for i, w in enumerate(words)]
        res["words"] = out
    elif op == "quality":
        res["quality"] = {f: {"stoi": 0.9, "pesq": 3.0, "si_sdr": 10.0} for f in job["files"]}
    print(json.dumps(res))


if __name__ == "__main__":
    main()
