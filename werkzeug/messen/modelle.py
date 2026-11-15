"""Andere Sprachmodelle an denselben Aufnahmen messen (alle laufen über onnx-asr auf der CPU).

    python modelle.py <Ausgabeordner> <Tondatei> [...]

Schreibt je Modell <kurzname>.jsonl. Die Stücke werden wie in der App an Sprechpausen geschnitten
und für Modelle, die Zusammenhang brauchen, bis 20 s zusammengelegt.
"""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import numpy as np
import onnx_asr

from diktat import engine

out, files = pathlib.Path(sys.argv[1]), sys.argv[2:]
MODELS = [
    ("canary", "nemo-canary-1b-v2", "int8", {"language": "de"}),
    ("whisper_turbo_de", "onnx-community/whisper-large-v3-turbo-german-ONNX", "q4", {"language": "de"}),
]


def merged(pieces, limit=20.0):
    cur = []
    for p in pieces:
        if cur and (sum(len(c) for c in cur) + len(p)) / 16000 > limit:
            yield np.concatenate(cur)
            cur = []
        cur.append(p)
    if cur:
        yield np.concatenate(cur)


audios = {}
for path in files:
    _, blocks = engine.decode_file(path)
    audios[pathlib.Path(path).stem] = np.concatenate(list(blocks))
for short, name, quant, kw in MODELS:
    try:
        t0 = time.time()
        model = onnx_asr.load_model(name, quantization=quant)
        print(short, "geladen in %.0f s" % (time.time() - t0), flush=True)
        with open(out / f"{short}.jsonl", "w", encoding="utf-8") as f:
            for stem, audio in audios.items():
                start = time.time()
                hyp = " ".join(model.recognize(c, sample_rate=16000, **kw) for c in merged(engine.split_long(audio)))
                f.write(json.dumps({"name": stem, "hyp": hyp, "sec": round(len(audio) / 16000, 1),
                                    "rechenzeit": round(time.time() - start, 1)}, ensure_ascii=False) + "\n")
                print(short, stem, "%.1f s" % (time.time() - start), flush=True)
    except Exception as e:
        print(short, "FEHLER:", repr(e)[:400], flush=True)
print("fertig", flush=True)
