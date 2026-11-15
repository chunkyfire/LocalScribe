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

as_float = long_audio.astype(np.float32) / 32768
pieces = [c for c, _ in engine.stream_chunks(iter([as_float[i:i + 1600] for i in range(0, len(as_float), 1600)]))]
check("Schneiden verliert kein einziges Sample", np.array_equal(np.concatenate(pieces), as_float))
check(f"Kein Stück länger als {engine.MAX_LEN:.0f} s", max(len(p) for p in pieces) <= (engine.MAX_LEN + 0.1) * 16000)
whole = engine.split_long(as_float[:30 * 16000])
check("Auch ein einzelnes Diktat wird an Pausen geteilt (nur reine Stille fällt weg)",
      len(whole) > 1 and max(len(p) for p in whole) <= (engine.MAX_LEN + 0.1) * 16000
      and sum(len(p) for p in whole) >= 24 * 16000)
duration, blocks = engine.decode_file(m4a)
check("M4A wird gelesen", abs(duration - len(long_audio) / 16000) < 1.0, f"({duration:.1f} s)")


class Ctl:
    cfg = {"dictionary": {"Lipaze": "Lipase"}, "microphone": None}
    transcriber = engine.Transcriber(dict(config.DEFAULTS))


ctl = Ctl()
ctl.transcriber.load()
qa = QtWidgets.QApplication(sys.argv)
parts, result = [], {}


def wait(cond, then, *args, t0=None):
    t0 = t0 or time.time()
    if cond():
        return then(*args)
    if time.time() - t0 > 120:
        check("Zeitüberschreitung vor " + then.__name__, False)
        return finish()
    QTimer.singleShot(100, lambda: wait(cond, then, *args, t0=t0))


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
    record("test.wav")
    wait(lambda: "text" in result, after_rec)


def record(name):
    """Mikrofon durch eine Warteschlange ersetzen und 10-ms-Blöcke einspeisen."""
    import queue
    import threading
    job._begin()
    job._queue = queue.Queue()
    (config.DIR / "aufnahmen").mkdir(exist_ok=True)
    job.wav_path = config.DIR / "aufnahmen" / name
    threading.Thread(target=job._run, args=(lambda: (None, job._mic_blocks()), job.wav_path), daemon=True).start()
    audio = long_audio.astype(np.float32) / 32768
    for i in range(0, len(audio), 160):
        job._queue.put(audio[i:i + 160])
    QTimer.singleShot(500, job.stop_recording)


def after_rec():
    check("Aufnahme: Text vollständig", result["err"] == "" and result["text"].count("Oberbauchschmerzen") == 4
          and len(result["text"].split()) >= 136, f"({len(result['text'].split())} Wörter)")
    check("Aufnahme: Dauer stimmt", abs(result["secs"] - len(long_audio) / 16000) < 0.5, f"({result['secs']:.1f} s)")
    check("Aufnahme: Sicherungsdatei danach gelöscht", not (config.DIR / "aufnahmen" / "test.wav").exists())
    # Ein Stück scheitert: Rest läuft weiter, Stelle ist markiert, Ton bleibt liegen
    result.clear()
    real = ctl.transcriber.model.recognize
    calls = []

    def flaky(chunk, **kw):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("Testfehler")
        return real(chunk, **kw)
    ctl.transcriber.model.recognize = flaky
    record("kaputt.wav")
    wait(lambda: "text" in result, after_flaky, real)


def after_flaky(real):
    ctl.transcriber.model.recognize = real
    kept = config.DIR / "aufnahmen" / "kaputt.wav"
    check("Fehler in einem Stück: Rest wird trotzdem erkannt", result["err"] == "" and len(result["text"].split()) > 90)
    check("Fehler in einem Stück: Stelle markiert und gezählt", engine.GAP in result["text"] and job.failed == 1)
    check("Fehler in einem Stück: Tonaufnahme bleibt erhalten", kept.exists() and job.kept == kept)
    check("Liegengebliebene Aufnahme wird gefunden", config.leftover_recordings() == [kept])
    # Absturz nachstellen: Dateikopf meldet Länge null
    raw = bytearray(kept.read_bytes())
    raw[4:8] = (36).to_bytes(4, "little")
    raw[40:44] = (0).to_bytes(4, "little")
    kept.write_bytes(raw)
    result.clear()
    job.start_recovery(kept)
    wait(lambda: "text" in result, after_recovery, kept)


def after_recovery(kept):
    check("Nach Absturz: Aufnahme vollständig nachgeholt",
          result["err"] == "" and result["text"].count("Oberbauchschmerzen") == 4 and len(result["text"].split()) >= 136,
          f"({len(result['text'].split())} Wörter)")
    check("Nach Absturz: Tonaufnahme danach gelöscht", not kept.exists() and config.leftover_recordings() == [])
    old = config.DIR / "aufnahmen" / "alt.wav"
    old.write_bytes(b"0" * 100)
    os.utime(old, (time.time() - 40 * 86400,) * 2)
    check("Vergessene Aufnahmen werden nach der Frist gelöscht", config.purge_recordings(30) == 1 and not old.exists())
    single = ctl.transcriber.transcribe(as_float[:len(speech)])
    check("Diktat per Taste (17,7 s mit Pausen): vollständig",
          single.startswith("Der Patient") and "morgen früh" in single and 33 <= len(single.split()) <= 39,
          f"({len(single.split())} Wörter)")
    quiet = ctl.transcriber.transcribe_stream(iter([long_audio[:18 * 16000].astype(np.float32) / 32768 * 0.003]))
    check("Sehr leise Sprache wird nicht verworfen", quiet.count("Oberbauchschmerzen") == 1, f"({len(quiet.split())} Wörter)")
    silence = ctl.transcriber.transcribe_stream(iter([np.zeros(16000 * 40, np.float32)]))
    check("Stummgeschaltetes Mikrofon ergibt leeren Text (keine erfundenen Wörter)", silence == "", repr(silence))
    rng = np.random.default_rng(5)
    hiss = ctl.transcriber.transcribe_stream(iter([(rng.standard_normal(16000 * 40) * 0.001).astype(np.float32)]))
    check("Raumrauschen ohne Sprache ergibt leeren Text", hiss == "", repr(hiss))
    mixed = np.concatenate([np.zeros(16000 * 20, np.float32), long_audio[:18 * 16000].astype(np.float32) / 32768,
                            np.zeros(16000 * 20, np.float32)])
    mixed += (rng.standard_normal(len(mixed)) * 0.0008).astype(np.float32)
    both = ctl.transcriber.transcribe_stream(iter([mixed[i:i + 160] for i in range(0, len(mixed), 160)]))
    check("Lange Stille vor und nach dem Sprechen: Text vollständig, nichts erfunden",
          both.count("Oberbauchschmerzen") == 1 and both.count("morgen früh") == 1 and 33 <= len(both.split()) <= 39,
          f"({len(both.split())} Wörter)")
    finish()


def finish():
    print("FEHLER:" if failed else "ALLES OK", failed or "", flush=True)
    os._exit(1 if failed else 0)


QTimer.singleShot(0, step_file)
qa.exec()
