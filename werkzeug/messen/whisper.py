"""Whisper large-v3-turbo (deutsch nachtrainiert) auf der CPU gegen dieselben Dateien messen.

    python whisper.py <Ausgabe.jsonl> <int8|float32> <Tondatei> [...]

Braucht faster-whisper (eigene Umgebung, nicht die der App). Rechnet bewusst ohne Grafikkarte:
LocalScribe muss auf einem Büro- oder Klinikrechner laufen.
"""
import json
import pathlib
import sys
import time

from faster_whisper import WhisperModel

out, kind, files = sys.argv[1], sys.argv[2], sys.argv[3:]
start = time.time()
model = WhisperModel("jimmymeister/whisper-large-v3-turbo-german-ct2", device="cpu", compute_type=kind)
print(f"geladen in {time.time() - start:.1f} s", flush=True)
with open(out, "w", encoding="utf-8") as f:
    for path in files:
        start = time.time()
        segments, info = model.transcribe(path, language="de", beam_size=5, vad_filter=True)
        hyp = " ".join(s.text.strip() for s in segments)
        took = time.time() - start
        f.write(json.dumps({"name": pathlib.Path(path).stem, "hyp": hyp, "sec": round(info.duration, 1),
                            "rechenzeit": round(took, 1)}, ensure_ascii=False) + "\n")
        print(pathlib.Path(path).stem, round(info.duration, 1), "s Ton in", round(took, 1), "s", flush=True)
print("fertig", flush=True)
