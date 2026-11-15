"""Sprechertrennung an echten Dateien prüfen: python sprecher.py <Datei1> <Datei2> ...

Hängt die Dateien mit kurzer Pause hintereinander (als wären es abwechselnde Redebeiträge), lässt die
echte Kette laufen und zeigt, welcher Sprecher je Äußerung erkannt wurde.
"""
import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
from diktat import config, engine, sprecher

cfg = dict(config.DEFAULTS)
t = engine.Transcriber(cfg)
t.load()
parts, bounds, pos = [], [], 0.0
for path in sys.argv[1:]:
    _, blocks = engine.decode_file(path)
    audio = np.concatenate(list(blocks))
    parts += [audio, np.zeros(int(0.8 * engine.RATE), dtype=np.float32)]
    bounds.append((pos, pos + len(audio) / engine.RATE, pathlib.Path(path).stem))
    pos += len(audio) / engine.RATE + 0.8
audio = np.concatenate(parts)
stats = {"pieces": []}
start = time.time()
t.transcribe_stream((audio[i:i + 1600] for i in range(0, len(audio), 1600)), stats=stats)
pieces = stats["pieces"]
labels = sprecher.cluster([p[1] for p in pieces], [p[2] for p in pieces])
print(f"{len(audio) / engine.RATE:.0f} s Ton in {time.time() - start:.1f} s, {len(pieces)} Äußerungen, {len(set(labels))} Sprecher")
print("Dateien:", ", ".join(f"{name} {a:.0f}–{b:.0f} s" for a, b, name in bounds))
for (text, voice, secs), label in zip(pieces, labels):
    print(f"Sprecher {label} ({secs:4.1f} s{'' if voice is not None else ', ohne Abdruck'}): {text[:70]}")
