"""Welche Schnitt-Einstellung verliert am wenigsten? Gemessen am vorgelesenen Text selbst.

Aufruf:  python vergleich_schnitt.py <Arbeitsordner> [Minuten]
Braucht stunde.wav und vergleich.json aus stunde.py.
"""
import difflib
import json
import pathlib
import re
import sys
import time
import wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import numpy as np

from diktat import config, engine

work = pathlib.Path(sys.argv[1])
minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
RATE = 16000


def content(text):
    """Inhaltswörter (ab 4 Buchstaben) und Zahlen; der Zähler „Befund N.“ zählt nicht mit."""
    return [t for t in re.findall(r"[a-zäöüß]{4,}|\d+", text.lower()) if t != "befund"]


sentences = (work / "saetze.txt").read_text(encoding="utf-8").splitlines()
with wave.open(str(work / "stunde.wav")) as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
base = json.loads((work / "vergleich.json").read_text(encoding="utf-8"))
audio = audio[: int(minutes * 60 * RATE)]
# Wie viele Sätze liegen in diesem Ausschnitt? Der letzte erkannte Satzanfang des Ausschnitts entscheidet.
t = engine.Transcriber(dict(config.DEFAULTS))
t.load()
tail = t.model.recognize(audio[-20 * RATE:][: 12 * RATE], sample_rate=RATE)
print("Ende des Ausschnitts:", tail[-80:], flush=True)
n_sent = int(sys.argv[3]) if len(sys.argv) > 3 else 0


def score(name, texts, n):
    ref = [w for s in sentences[:n] for w in content(re.sub(r"^Befund \d+\. ", "", s))]
    got = content(" ".join(texts))
    lost = changed = 0
    worst = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ref, got, autojunk=False).get_opcodes():
        if tag == "delete":
            lost += i2 - i1
            worst.append((i2 - i1, " ".join(ref[i1:i2])))
        elif tag == "replace":
            changed += i2 - i1
    worst = sorted(worst, reverse=True)[:3]
    print(f"{name:38s} fehlend {lost:4d}  anders {changed:4d}  von {len(ref)}  "
          f"({100 * (1 - (lost + changed) / len(ref)):.1f} % richtig)  größte Lücken: {[w for _, w in worst]}", flush=True)


def run(name, min_pause, max_len, n):
    seg = engine.Segmenter(min_pause=min_pause, max_len=max_len)
    start, texts, lens = time.time(), [], []
    for i in range(0, len(audio), 1600):
        for c in seg.feed(audio[i:i + 1600]) + ([] if i + 1600 < len(audio) else seg.flush()):
            lens.append(len(c) / RATE)
            texts.append(t.model.recognize(c, sample_rate=RATE))
    score(f"{name} [{len(lens)} Stücke, max {max(lens):.1f} s, {time.time() - start:.0f} s]", texts, n)


if not n_sent:
    print("Dritter Parameter fehlt: Zahl der Sätze im Ausschnitt")
    sys.exit(1)
score("Satz für Satz einzeln (Bestfall)", [base[str(i)] for i in range(1, n_sent + 1)], n_sent)
for name, mp, ml in (("Pause 0,3 s / höchstens 12 s", 0.3, 12.0), ("Pause 0,2 s / höchstens 12 s", 0.2, 12.0),
                     ("Pause 0,5 s / höchstens 12 s", 0.5, 12.0), ("Pause 0,3 s / höchstens 8 s", 0.3, 8.0),
                     ("Pause 0,3 s / höchstens 18 s", 0.3, 18.0)):
    run(name, mp, ml, n_sent)
