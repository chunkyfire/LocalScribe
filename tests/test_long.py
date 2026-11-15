"""Lange Aufnahme und Datei-Transkription ohne Mikrofon und ohne sichtbare Fenster prüfen."""
import os
import pathlib
import sys
import tempfile
import time
import wave

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
import av
import numpy as np
from PySide6 import QtWidgets
from PySide6.QtCore import QTimer

from diktat import config, engine
from diktat.longform import LongJob

tmp = pathlib.Path(tempfile.mkdtemp(prefix="diktat_test_"))
config.DIR = tmp
failed = []


def check(name, ok, extra=""):
    print("OK  " if ok else "FAIL", name, extra, flush=True)
    if not ok:
        failed.append(name)


with wave.open(str(ROOT / "test_de.wav")) as w:
    speech = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)

# 1) Testsatz viermal hintereinander als M4A (AAC, 44,1 kHz) – wie eine Sprachmemo vom Handy
m4a = tmp / "memo.m4a"
long_audio = np.concatenate([speech, np.zeros(16000, np.int16)] * 4)
with av.open(str(m4a), "w") as out:
    stream = out.add_stream("aac", rate=44100)
    res = av.AudioResampler(format="fltp", layout="mono", rate=44100)
    frame = av.AudioFrame.from_ndarray(long_audio.reshape(1, -1), format="s16", layout="mono")
    frame.sample_rate = 16000
    for f in res.resample(frame) + res.resample(None):
        for packet in stream.encode(f):
            out.mux(packet)
    for packet in stream.encode(None):
        out.mux(packet)

pieces = list(engine.stream_chunks(iter([long_audio[i:i + 1600].astype(np.float32) / 32768
                                         for i in range(0, len(long_audio), 1600)])))
check("Kein Stück länger als 18 s (darüber verliert das Modell Text)",
      max(len(p) for p in pieces) <= 18.1 * 16000 and sum(len(p) for p in pieces) == len(long_audio))
check("Auch ein einzelnes Diktat wird ab 18 s geteilt",
      max(len(p) for p in engine.split_long(long_audio[:30 * 16000].astype(np.float32) / 32768)) <= 18.1 * 16000)
duration, blocks = engine.decode_file(m4a)
check("M4A wird gelesen", abs(duration - len(long_audio) / 16000) < 1.0, f"({duration:.1f} s)")


class Ctl:
    cfg = {"dictionary": {"Lipaze": "Lipase"}, "microphone": None}
    transcriber = engine.Transcriber(dict(config.DEFAULTS))


ctl = Ctl()
ctl.transcriber.load()
qa = QtWidgets.QApplication(sys.argv)
parts, result = [], {}


def wait(cond, then, t0=None):
    t0 = t0 or time.time()
    if cond():
        return then()
    if time.time() - t0 > 120:
        check("Zeitüberschreitung vor " + then.__name__, False)
        return finish()
    QTimer.singleShot(100, lambda: wait(cond, then, t0))


job = LongJob(ctl)
job.part.connect(lambda text, done, total: parts.append((len(text), done, total)))
job.finished.connect(lambda text, secs, err: result.update(text=text, secs=secs, err=err))


def step_file():
    job.start_file(m4a)
    wait(lambda: "text" in result, after_file)


def after_file():
    text = result["text"]
    check("Datei: kein Fehler", result["err"] == "", result["err"])
    check("Datei: alle vier Durchgänge vollständig erkannt",
          text.count("Oberbauchschmerzen") == 4 and text.count("morgen früh") == 4 and len(text.split()) >= 136,
          f"({len(text.split())} Wörter)")
    check("Datei: Wörterbuch angewendet", "Lipase" in text and "Lipaze" not in text)
    check("Datei: Fortschritt in mehreren Stücken", len(parts) >= 2 and parts[-1][2] > 0 and parts[-1][1] <= parts[-1][2] + 1)
    check("Datei: Absätze gesetzt", "\n\n" in text)
    result.clear()
    job.start_file(tmp / "gibtsnicht.mp3")
    wait(lambda: "text" in result, after_missing)


def after_missing():
    check("Fehlende Datei: verständlicher Fehler, kein Absturz", result["err"] != "" and result["text"] == "")
    result.clear()
    # Aufnahme: Mikrofon durch eine Warteschlange ersetzen und 10-ms-Blöcke einspeisen
    import queue
    import threading
    job._begin()
    job._queue = queue.Queue()
    (config.DIR / "aufnahmen").mkdir(exist_ok=True)
    job.wav_path = config.DIR / "aufnahmen" / "test.wav"
    threading.Thread(target=job._run_recording, daemon=True).start()
    audio = long_audio.astype(np.float32) / 32768
    for i in range(0, len(audio), 160):
        job._queue.put(audio[i:i + 160])
    QTimer.singleShot(500, job.stop_recording)
    wait(lambda: "text" in result, after_rec)


def after_rec():
    check("Aufnahme: Text vollständig", result["err"] == "" and result["text"].count("Oberbauchschmerzen") == 4
          and len(result["text"].split()) >= 136, f"({len(result['text'].split())} Wörter)")
    check("Aufnahme: Dauer stimmt", abs(result["secs"] - len(long_audio) / 16000) < 0.5, f"({result['secs']:.1f} s)")
    check("Aufnahme: Sicherungsdatei danach gelöscht", not (config.DIR / "aufnahmen" / "test.wav").exists())
    finish()


def finish():
    print("FEHLER:" if failed else "ALLES OK", failed or "", flush=True)
    os._exit(1 if failed else 0)


QTimer.singleShot(0, step_file)
qa.exec()
