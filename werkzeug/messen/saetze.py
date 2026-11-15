"""Vorgelesene Sätze erkennen: <Ordner>/saetze.txt und s0001.wav … (aus tests/langzeit/tts.ps1).

    python saetze.py <Ordner> <de|multi>     -> saetze_<modell>.jsonl mit Soll und Ist
"""
import json
import pathlib
import sys
import wave

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import numpy as np

from diktat import config, engine

work, choice = pathlib.Path(sys.argv[1]), sys.argv[2]
t = engine.Transcriber(dict(config.DEFAULTS, model_choice=choice))
t.load()
refs = (work / "saetze.txt").read_text(encoding="utf-8").splitlines()
with open(work / f"saetze_{choice}.jsonl", "w", encoding="utf-8") as f:
    for i, ref in enumerate(refs):
        with wave.open(str(work / f"s{i + 1:04d}.wav")) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        hyp = " ".join(t.model.recognize(c, sample_rate=16000) for c in engine.split_long(audio))
        f.write(json.dumps({"ref": ref, "hyp": hyp, "sec": round(len(audio) / 16000, 2)}, ensure_ascii=False) + "\n")
print("fertig", len(refs), flush=True)
