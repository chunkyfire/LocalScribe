"""Echte deutsche Medizin-Aufnahmen erkennen lassen: MultiMed (Le-Duc et al., ACL 2025, MIT-Lizenz).

    python multimed.py <Ordner> <de|multi> [split]

Lädt den deutschen Teil (von Ärztekanälen auf YouTube, von Menschen transkribiert), erkennt jede
Aufnahme so, wie die App es tut (Schnitt an Sprechpausen), und schreibt Soll und Ist nach
multimed_<modell>_<split>.jsonl. Die Auswertung macht auswerten.py.
Braucht: pip install pyarrow
"""
import io
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import av
import numpy as np
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from diktat import config, engine

work, choice = pathlib.Path(sys.argv[1]), sys.argv[2]
label = choice
if pathlib.Path(choice).is_dir():           # statt eines eingebauten Modells ein Ordner mit ONNX-Dateien
    label = pathlib.Path(choice).name
    config.MODELS["ordner"] = dict(config.MODELS["de"], path=str(pathlib.Path(choice).resolve()))
    choice = "ordner"
split = sys.argv[3] if len(sys.argv) > 3 else "test"
path = hf_hub_download("leduckhai/MultiMed", f"German/{split}-00000-of-00001.parquet", repo_type="dataset")
table = pq.read_table(path)
print(table.schema, table.num_rows, flush=True)
t = engine.Transcriber(dict(config.DEFAULTS, model_choice=choice))
t.load()


def decode(data):
    c = av.open(io.BytesIO(data))
    r = av.AudioResampler(format="s16", layout="mono", rate=16000)
    out = [o.to_ndarray().reshape(-1) for f in c.decode(audio=0) for o in r.resample(f)]
    out += [o.to_ndarray().reshape(-1) for o in r.resample(None)]
    c.close()
    return np.concatenate(out).astype(np.float32) / 32768


text_col = next(n for n in table.column_names if n in ("text", "transcription", "sentence", "transcript"))
total = start = 0.0
start = time.time()
with open(work / f"multimed_{label}_{split}.jsonl", "w", encoding="utf-8") as f:
    for i in range(table.num_rows):
        row = table.slice(i, 1).to_pylist()[0]
        try:
            audio = decode(row["audio"]["bytes"])
            hyp = " ".join(t.model.recognize(c, sample_rate=16000) for c in engine.split_long(audio))
        except Exception as e:
            hyp, audio = "!" + str(e), np.zeros(0)
        total += len(audio) / 16000
        f.write(json.dumps({"ref": row[text_col], "hyp": hyp, "sec": round(len(audio) / 16000, 2)}, ensure_ascii=False) + "\n")
        if i % 100 == 0:
            f.flush()
            print(i, f"{total / 60:.1f} min Ton, {time.time() - start:.0f} s", flush=True)
print("fertig", table.num_rows, f"{total / 60:.1f} min", flush=True)
