"""Sprechertrennung an echten Gesprächen mit bekannten Sprechern messen.

    python gespraech.py <parquet mit audio, timestamps_start, timestamps_end, speakers> [Anzahl] [nur_zwei]

Datensätze im Format von diarizers-community (VoxConverse, CallHome). Läuft durch dieselbe
Pausenerkennung wie die App. Gemessen wird der Anteil der Sprechzeit, der dem richtigen Sprecher
zugeordnet ist (nach bester Zuordnung der Nummern), und ob die Zahl der Sprecher stimmt.
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

from diktat import engine, sprecher


def decode(data):
    c = av.open(io.BytesIO(data))
    r = av.AudioResampler("flt", "mono", 16000)
    out = [g.to_ndarray()[0] for f in c.decode(audio=0) for g in r.resample(f)]
    return np.concatenate(out)


limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
only_two = len(sys.argv) > 3
total_ok = total_all = 0.0
rows = []
pf = pq.ParquetFile(sys.argv[1])
done = 0
for batch in pf.iter_batches(batch_size=1):
    r = batch.to_pylist()[0]
    ref = sorted(zip(r["timestamps_start"], r["timestamps_end"], r["speakers"]))
    names = sorted({s for _, _, s in ref})
    if only_two and len(names) != 2:
        continue
    audio = decode(r["audio"]["bytes"])[: 15 * 60 * 16000]
    t0 = time.time()
    pos, pieces = 0.0, []
    for chunk, still in engine.stream_chunks(audio[i:i + 1600] for i in range(0, len(audio), 1600)):
        secs = len(chunk) / 16000
        if not still and len(chunk) >= 0.2 * 16000:
            pieces.append((pos, pos + secs, sprecher.embed(chunk)))
        pos += secs
    labels = sprecher.cluster([p[2] for p in pieces], [p[1] - p[0] for p in pieces])
    took = time.time() - t0
    # Überlappung je (erkannter Sprecher, wahrer Sprecher) in Sekunden
    found = sorted(set(labels))
    table = np.zeros((len(found), len(names)))
    for (a, b, _), label in zip(pieces, labels):
        for s, e, who in ref:
            if e <= a:
                continue
            if s >= b:
                break
            table[found.index(label), names.index(who)] += min(b, e) - max(a, s)
    best = 0.0
    k = min(len(found), len(names))
    if len(found) <= 7 and len(names) <= 7:
        for perm in itertools.permutations(range(len(names)), k) if len(found) <= len(names) else \
                [None]:
            if perm is None:
                best = max(sum(table[f, n] for f, n in zip(p, range(len(names))))
                           for p in itertools.permutations(range(len(found)), k))
                break
            best = max(best, sum(table[f, n] for f, n in zip(range(len(found)), perm)))
    else:
        best = table.max(axis=1).sum()
    share = best / max(1e-9, table.sum())
    total_ok += best
    total_all += table.sum()
    rows.append((len(audio) / 16000, len(names), len(found), share, took))
    print(f"{len(audio) / 16000:5.0f} s  wahr {len(names)} Sprecher, erkannt {len(found)}  richtig zugeordnet {share:.0%}  ({took:.0f} s)", flush=True)
    done += 1
    if done >= limit:
        break
print(f"\n{len(rows)} Gespräche: {total_ok / total_all:.1%} der Sprechzeit richtig zugeordnet; "
      f"Sprecherzahl stimmt bei {sum(1 for r in rows if r[1] == r[2])} von {len(rows)}")
