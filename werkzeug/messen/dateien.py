"""Eigene Aufnahmen erkennen: python dateien.py <Ausgabe.jsonl> <de|multi> <Tondatei> [...]"""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import numpy as np

from diktat import config, engine

out, choice, files = sys.argv[1], sys.argv[2], sys.argv[3:]
t = engine.Transcriber(dict(config.DEFAULTS, model_choice=choice))
t.load()
with open(out, "w", encoding="utf-8") as f:
    for path in files:
        _, blocks = engine.decode_file(path)
        audio = np.concatenate(list(blocks))
        start = time.time()
        hyp = " ".join(t.model.recognize(c, sample_rate=16000) for c in engine.split_long(audio))
        f.write(json.dumps({"name": pathlib.Path(path).stem, "hyp": hyp, "sec": round(len(audio) / 16000, 1),
                            "rechenzeit": round(time.time() - start, 1)}, ensure_ascii=False) + "\n")
print("fertig", flush=True)
