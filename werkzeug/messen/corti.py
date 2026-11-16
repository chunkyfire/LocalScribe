"""Echte deutsche ärztliche Diktate erkennen lassen: Med-Dictate von Corti (9 Diktate, 2 bis 7 Minuten).

    python corti.py <Ordner> [de|genau|multi]

Die Aufnahmen stammen von Corti-Mitarbeitenden, ohne Patientendaten, mit Wortlaut-Transkript und formatierter
Fassung (Lizenz: CDLA-Permissive-2.0 mit Zusatz von Corti, Nutzung zur Auswertung erlaubt). Erkannt wird wie in der
App mit Schnitt an Sprechpausen. Schreibt corti_<modell>.jsonl mit name, ref (Wortlaut), ref_format, hyp, sec, s.
Die Auswertung macht corti_auswerten.py.
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

work = pathlib.Path(sys.argv[1])
choice = sys.argv[2] if len(sys.argv) > 2 else "de"
path = hf_hub_download("corti/med-dictate", "de/test-00000-of-00001.parquet", repo_type="dataset")
table = pq.read_table(path)
t = engine.Transcriber(dict(config.DEFAULTS, model_choice=choice))
t.load()


def decode(data):
    c = av.open(io.BytesIO(data))
    r = av.AudioResampler(format="s16", layout="mono", rate=16000)
    out = [o.to_ndarray().reshape(-1) for f in c.decode(audio=0) for o in r.resample(f)]
    out += [o.to_ndarray().reshape(-1) for o in r.resample(None)]
    c.close()
    return np.concatenate(out).astype(np.float32) / 32768


with open(work / f"corti_{choice}.jsonl", "w", encoding="utf-8") as f:
    for i in range(table.num_rows):
        row = table.slice(i, 1).to_pylist()[0]
        audio = decode(row["audio"]["bytes"])
        start = time.time()
        hyp = " ".join(t.model.recognize(c, sample_rate=16000) for c in engine.split_long(audio))
        took = time.time() - start
        f.write(json.dumps({"name": row["id"], "ref": row["transcription"], "ref_format": row["transcription_formatted"],
                            "begriffe": row.get("medical_terms") or [], "hyp": hyp, "sec": round(len(audio) / 16000, 1),
                            "s": round(took, 1)}, ensure_ascii=False) + "\n")
        f.flush()
        print(row["id"], f"{len(audio) / 16000:.0f} s Ton in {took:.1f} s", flush=True)
print("fertig")
