"""Live-Transkription in Echtzeit: Ton kommt im Tempo eines echten Mikrofons, Text muss mitlaufen.

Dauert so lange wie die Aufnahme (rund 75 Sekunden).
"""
import os
import pathlib
import queue
import sys
import tempfile
import threading
import time
import wave

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
import numpy as np
from PySide6 import QtWidgets
from PySide6.QtCore import QTimer

from diktat import config, engine
from diktat.longform import LongJob

config.DIR = pathlib.Path(tempfile.mkdtemp(prefix="diktat_test_"))
with wave.open(str(ROOT / "test_de.wav")) as w:
    speech = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
rng = np.random.default_rng(1)
audio = np.concatenate([speech, np.zeros(16000, np.float32)] * 4)
audio += (rng.standard_normal(len(audio)) * 0.0008).astype(np.float32)
total = len(audio) / 16000


class Ctl:
    cfg = {"dictionary": {}, "microphone": None}
    transcriber = engine.Transcriber(dict(config.DEFAULTS))


Ctl.transcriber.load()
qa = QtWidgets.QApplication(sys.argv)
job = LongJob(Ctl())
parts, result, failed = [], {}, []
start = [0.0]
job.part.connect(lambda text, done, _: parts.append((time.time() - start[0], done, len(text.split()))))
job.finished.connect(lambda text, secs, err: result.update(text=text, err=err, at=time.time() - start[0]))


def check(name, ok, extra=""):
    print("OK  " if ok else "FAIL", name, extra, flush=True)
    if not ok:
        failed.append(name)


def feed():
    """10-ms-Blöcke im Tempo eines Mikrofons."""
    for k in range(0, len(audio), 160):
        job._queue.put(audio[k:k + 160].copy())
        ahead = k / 16000 - (time.time() - start[0])
        if ahead > 0:
            time.sleep(ahead)
    job.stop_recording()


def begin():
    job._begin()
    job._queue = queue.Queue()
    (config.DIR / "aufnahmen").mkdir(exist_ok=True)
    job.wav_path = config.DIR / "aufnahmen" / "live.wav"
    start[0] = time.time()
    threading.Thread(target=job._run, args=(lambda: (None, job._mic_blocks()), job.wav_path), daemon=True).start()
    threading.Thread(target=feed, daemon=True).start()
    wait()


def wait():
    if "text" not in result and time.time() - start[0] < total + 60:
        return QTimer.singleShot(200, wait)
    words = [p for p in parts if p[2] > 0]
    lags = [at - done for at, done, _ in parts]
    first = words[0][0] if words else 999
    during = [p for p in words if p[0] < total - 1]
    check("Erster Text erscheint während des ersten Satzes oder kurz danach", first < 8, f"(nach {first:.1f} s)")
    check("Text wächst während der Aufnahme mit", len(during) >= 12 and during[-1][2] >= 100,
          f"({len(during)} Zwischenstände, {during[-1][2] if during else 0} Wörter vor dem Stopp)")
    check("Rückstand bleibt klein", max(lags) < 6, f"(größter Rückstand {max(lags):.1f} s, mittlerer {np.mean(lags):.1f} s)")
    check("Nach dem Stopp ist der Text sofort fertig", result.get("at", 999) - total < 3,
          f"({result.get('at', 999) - total:.1f} s nach dem letzten Ton)")
    text = result.get("text", "")
    check("Text vollständig", result.get("err") == "" and text.count("Oberbauchschmerzen") == 4
          and text.count("morgen früh") == 4 and len(text.split()) >= 136, f"({len(text.split())} Wörter)")
    print("FEHLER:" if failed else "ALLES OK", failed or "", flush=True)
    os._exit(1 if failed else 0)


QTimer.singleShot(0, begin)
qa.exec()
