"""Eigene Aufnahmen erkennen: python dateien.py <Ausgabe.jsonl> <de|genau|multi|Modellordner> <Tondatei> [...]"""
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import numpy as np

from diktat import config, engine

out, choice, files = sys.argv[1], sys.argv[2], sys.argv[3:]
if pathlib.Path(choice).is_dir():           # statt eines eingebauten Modells ein Ordner mit ONNX-Dateien
    config.MODELS["ordner"] = dict(config.MODELS["de"], path=str(pathlib.Path(choice).resolve()))
    choice = "ordner"
cfg = dict(config.DEFAULTS, model_choice=choice)
if choice == "ordner" and not list(pathlib.Path(config.MODELS["ordner"]["path"]).glob("*int8*")):
    cfg["quantization"] = None              # Ordner mit ungekürzten Gewichten
if os.environ.get("LS_QUANT") == "none":     # ungekürzte Gewichte (2,5 GB) statt int8
    cfg["quantization"] = None
t = engine.Transcriber(cfg)
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
