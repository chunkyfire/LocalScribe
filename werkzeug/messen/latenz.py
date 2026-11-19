"""Wie lange dauert es vom Loslassen der Taste bis zum Text? Gemessen über den Weg der App (8-Bit-Modell, Dekodieren
mit Wortschatz, Nachbearbeitung) für Diktate von 5 bis 60 Sekunden, mit allen Kernen und mit 4 und 2 Rechenfäden
(so viel hat ein einfacher Bürorechner). Die Kerne des Messrechners sind meist schneller als die eines Kliniklaptops;
die Zeilen mit 4 und 2 Fäden sind deshalb eine untere Schranke, kein Ersatz für eine Messung am Zielgerät.

    python latenz.py <Ordner mit WAV-Dateien, 16 kHz mono>
"""
import pathlib, platform, statistics, sys, time, wave

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
from diktat import config, engine

files = sorted(pathlib.Path(sys.argv[1]).glob("*.wav"))


def audio(p):
    w = wave.open(str(p)); a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    assert w.getframerate() == 16000 and w.getnchannels() == 1
    return a


def clip(seconds):
    """So viele Sätze aneinander, bis die Dauer erreicht ist."""
    parts, total = [], 0
    for f in files:
        a = audio(f); parts.append(a); total += len(a)
        if total >= seconds * 16000:
            break
    return np.concatenate(parts)[: int(seconds * 16000)]


print("Rechner:", platform.processor() or platform.machine(), flush=True)
clips = {s: clip(s) for s in (5, 15, 30, 60)}
for threads in (0, 4, 2):
    cfg = dict(config.DEFAULTS, threads=threads)
    t = engine.Transcriber(cfg); t.load()
    t.transcribe(clips[5])                                   # aufwärmen
    row = []
    for s, a in clips.items():
        took = []
        for _ in range(3):
            start = time.perf_counter(); engine.postprocess(t.transcribe(a), cfg); took.append(time.perf_counter() - start)
        row.append(f"{s:>2d} s Ton: {statistics.median(took):.2f} s")
    print(f"{'alle Kerne' if not threads else str(threads) + ' Fäden':>10s} | " + " | ".join(row), flush=True)
    del t
print("FERTIG", flush=True)
