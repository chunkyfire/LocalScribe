"""Sprechertrennung an einem zusammengesetzten Gespräch prüfen.

    python dialog.py <Ordner mit 01.mp3, 02.mp3, ...> <Sprecherfolge, z. B. ABABABABAB> [Pause in Sekunden]

Jede Datei ist ein Redebeitrag. Die Beiträge werden mit Pausen aneinandergehängt und laufen dann durch
dieselbe Pausenerkennung, Erkennung und Sprechertrennung wie eine Aufnahme in der App. Ausgegeben werden
das Gespräch, wie die App es schreibt, und der Anteil der Sprechzeit beim richtigen Sprecher.
"""
import itertools
import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import av

from diktat import config, engine, sprecher


def decode(path):
    c = av.open(str(path))
    r = av.AudioResampler("flt", "mono", 16000)
    out = [g.to_ndarray()[0] for f in c.decode(audio=0) for g in r.resample(f)]
    out += [g.to_ndarray()[0] for g in r.resample(None)]
    return np.concatenate(out)


folder, order = pathlib.Path(sys.argv[1]), sys.argv[2]
gap = float(sys.argv[3]) if len(sys.argv) > 3 else 0.6
files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".m4a"))
assert len(files) == len(order), f"{len(files)} Dateien, {len(order)} Sprecher"
audio, ref, pos = [], [], 0.0
for path, who in zip(files, order):
    a = decode(path)
    ref.append((pos, pos + len(a) / 16000, who))
    audio += [a, np.zeros(int(gap * 16000), dtype=np.float32)]
    pos += len(a) / 16000 + gap
audio = np.concatenate(audio)
cfg = dict(config.DEFAULTS)
t = engine.Transcriber(cfg)
t.load()
sprecher.prepare()
start = time.time()
pos, pieces = 0.0, []
for chunk, still in engine.stream_chunks(audio[i:i + 1600] for i in range(0, len(audio), 1600)):
    secs = len(chunk) / 16000
    if not still and len(chunk) >= 0.2 * 16000:
        pieces.append((pos, pos + secs, engine.postprocess(t.transcribe(chunk), cfg).strip(), sprecher.embed(chunk)))
    pos += secs
labels = sprecher.cluster([p[3] for p in pieces], [p[1] - p[0] for p in pieces])
took = time.time() - start
print(sprecher.dialogue([p[2] for p in pieces], labels))
names, found = sorted(set(order)), sorted(set(labels))
table = np.zeros((len(found), len(names)))
for (a, b, _, _), label in zip(pieces, labels):
    for s, e, who in ref:
        table[found.index(label), names.index(who)] += max(0.0, min(b, e) - max(a, s))
k = min(len(found), len(names))
best = max(sum(table[f, n] for f, n in zip(fs, ns))
           for fs in itertools.permutations(range(len(found)), k) for ns in itertools.combinations(range(len(names)), k))
print(f"\n{len(audio) / 16000:.0f} s Gespräch, {len(order)} Beiträge, {len(pieces)} Äußerungen erkannt, "
      f"Sprecher: {len(found)} erkannt, {len(names)} wahr; richtig zugeordnet {100 * best / table.sum():.1f} % der Sprechzeit; "
      f"{took:.1f} s Rechenzeit")
