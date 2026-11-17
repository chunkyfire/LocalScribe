"""Dekodieren mit Wortschatz (diktat/beam.py) an den Corti-Diktaten messen.

    python wortschatz_corti.py <Ordner> [beam=8] [gewicht=2] [wortschatz=kern|kern+texte|kern+begriffe]

Rechnet die Encoder-Ausgaben einmal (enc.pkl im Ordner) und dekodiert dann; so lassen sich Varianten in einer
Minute vergleichen. wortschatz: "kern" = nur die Kernliste der App; "texte" = dazu die Lexikonwörter aus den
Wortlaut-Transkripten, so wie die App sie aus eigenen Texten lernt (wortschatz.from_text); "begriffe" = dazu die
von Corti markierten Fachbegriffe. Schreibt corti_ws_<wortschatz>_b<beam>.jsonl; Auswertung: corti_auswerten.py.
"""
import io
import json
import pathlib
import pickle
import sys
import time
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
try:
    import sounddevice  # noqa: F401
except Exception:
    sys.modules["sounddevice"] = types.ModuleType("sounddevice")
import av
import numpy as np
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from diktat import beam, config, engine, wortschatz

work = pathlib.Path(sys.argv[1])
width = int(sys.argv[2]) if len(sys.argv) > 2 else 8
weight = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
lex = sys.argv[4] if len(sys.argv) > 4 else "kern+texte"
t = engine.Transcriber(dict(config.DEFAULTS, beam=0))
t.load()
asr = beam._inner(t.model)
cache = work / "enc.pkl"
if cache.exists():
    rows = pickle.load(open(cache, "rb"))
else:
    table = pq.read_table(hf_hub_download("corti/med-dictate", "de/test-00000-of-00001.parquet", repo_type="dataset"))
    rows = []
    for i in range(table.num_rows):
        row = table.slice(i, 1).to_pylist()[0]
        c = av.open(io.BytesIO(row["audio"]["bytes"]))
        r = av.AudioResampler(format="s16", layout="mono", rate=16000)
        out = [o.to_ndarray().reshape(-1) for f in c.decode(audio=0) for o in r.resample(f)]
        out += [o.to_ndarray().reshape(-1) for o in r.resample(None)]
        c.close()
        audio = np.concatenate(out).astype(np.float32) / 32768
        encs = []
        for chunk in engine.split_long(audio):
            eo, el = asr._encode(*asr._preprocessor(chunk[None, :], np.array([len(chunk)], dtype=np.int64)))
            encs.append(eo[0, : int(el[0])].copy())
        rows.append({"name": row["id"], "ref": row["transcription"], "ref_format": row["transcription_formatted"],
                     "begriffe": row.get("medical_terms") or [], "sec": round(len(audio) / 16000, 1), "enc": encs})
        print(row["id"], "Encoder fertig", flush=True)
    pickle.dump(rows, open(cache, "wb"))
terms = wortschatz.terms({})
if "texte" in lex:
    terms += wortschatz.from_text(" ".join(r["ref"] + " " + r["ref_format"] for r in rows))
if "begriffe" in lex:
    terms += [b for r in rows for b in r["begriffe"]]
print(len(terms), "Begriffe im Wortschatz, aktiv:", beam.install(t.model, terms, width, weight))
name = work / f"corti_ws_{lex.replace('+', '_')}_b{width}.jsonl"
with open(name, "w", encoding="utf-8") as f:
    for row in rows:
        start = time.time()
        parts = []
        for e in row["enc"]:
            tokens, times, _ = next(iter(asr._decoding(e[None], np.array([e.shape[0]]))))
            parts.append(asr._decode_tokens(tokens, times, None).text)
        out = {k: row[k] for k in ("name", "ref", "ref_format", "begriffe", "sec")}
        out.update(hyp=" ".join(p for p in parts if p), s=round(time.time() - start, 1))
        f.write(json.dumps(out, ensure_ascii=False) + "\n")
print("fertig:", name)
