"""Tempo zweier Modellfassungen an derselben Datei: python tempo.py <Tondatei> [Wiederholungen]"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import numpy as np

from diktat import config, engine

_, blocks = engine.decode_file(sys.argv[1])
audio = np.concatenate(list(blocks))
n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
for label, release in (("neu (Release)", True), ("bisher (int8)", False)):
    if not release:
        config.MODELS["de"] = {k: v for k, v in config.MODELS["de"].items() if k != "release"}
    t = engine.Transcriber(dict(config.DEFAULTS))
    start = time.time()
    t.load()
    loaded = time.time() - start
    times = []
    for _ in range(n):
        start = time.time()
        t.transcribe(audio)
        times.append(round(time.time() - start, 2))
    print(f"{label}: Laden {loaded:.1f} s, {len(audio) / 16000:.1f} s Ton in {times} s", flush=True)
