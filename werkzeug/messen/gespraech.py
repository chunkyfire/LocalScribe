"""Sprechertrennung an echten Gesprächen mit bekannten Sprechern messen.

    python gespraech.py <parquet mit audio, timestamps_start, timestamps_end, speakers> [Anzahl] [SAME=0.42 ...]

Datensätze im Format von diarizers-community (VoxConverse, CallHome). Der Ton läuft durch dieselbe Klasse wie in
der App (sprecher.Turns). Gemessen wird der Anteil der Sprechzeit, der dem richtigen Sprecher zugeordnet ist (nach
bester Zuordnung der Nummern; Sprache, die keinem Sprecher zugeordnet wurde, zählt als falsch), und ob die Zahl
der Sprecher stimmt. Weitere Argumente wie SAME=0.36 überschreiben Konstanten aus sprecher.py.
"""
import io
import itertools
import pathlib
import sys
import time
import types

import numpy as np
import pyarrow.parquet as pq

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
import av

from diktat import sprecher


def decode(data):
    c = av.open(io.BytesIO(data))
    r = av.AudioResampler("flt", "mono", 16000)
    return np.concatenate([g.to_ndarray()[0] for f in c.decode(audio=0) for g in r.resample(f)])


limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
for arg in sys.argv[3:]:
    name, value = arg.split("=")
    setattr(sprecher, name, float(value))
ok = total = 0.0
rows = []
for n, batch in enumerate(pq.ParquetFile(sys.argv[1]).iter_batches(batch_size=1)):
    if n >= limit:
        break
    r = batch.to_pylist()[0]
    ref = sorted(zip(r["timestamps_start"], r["timestamps_end"], r["speakers"]))
    names = sorted({s for _, _, s in ref})
    audio = decode(r["audio"]["bytes"])[: 15 * 60 * 16000]
    began = time.time()
    turns = sprecher.Turns()
    for i in range(0, len(audio), 16000):
        turns.feed(audio[i:i + 16000])
    labels, step = turns.finish()
    took = time.time() - began
    found = sorted(set(labels[labels > 0].tolist()))
    truth = np.zeros((len(names), len(labels)), bool)
    for s, e, who in ref:
        truth[names.index(who), int(s / step):int(e / step) + 1] = True
    table = np.zeros((max(1, len(found)), len(names)))
    for fi, f in enumerate(found):
        for ni in range(len(names)):
            table[fi, ni] = ((labels == f) & truth[ni]).sum() * step
    missed = ((labels == 0) & truth.any(axis=0)).sum() * step
    k = min(len(found), len(names))
    if k and len(found) <= 7 and len(names) <= 7:
        if len(found) <= len(names):
            best = max(sum(table[f, p] for f, p in zip(range(len(found)), perm))
                       for perm in itertools.permutations(range(len(names)), k))
        else:
            best = max(sum(table[f, m] for f, m in zip(perm, range(len(names))))
                       for perm in itertools.permutations(range(len(found)), k))
    else:
        best = table.max(axis=1).sum()
    whole = table.sum() + missed
    ok += best
    total += whole
    rows.append((len(names), len(found)))
    print(f"{len(audio) / 16000:5.0f} s  wahr {len(names)} Sprecher, erkannt {len(found)}  richtig zugeordnet "
          f"{best / max(whole, 1e-9):.0%}  ({took:.0f} s)", flush=True)
print(f"\n{len(rows)} Gespräche: {ok / total:.1%} der Sprechzeit richtig zugeordnet; "
      f"Sprecherzahl stimmt bei {sum(a == b for a, b in rows)} von {len(rows)}")
