"""Lange Aufnahmen und Audiodateien: stückweise erkennen, Text wächst mit."""
import logging
import queue
import threading
import time
import wave
from pathlib import Path

import numpy as np
from PySide6 import QtCore
from PySide6.QtCore import Signal

from . import config, engine

log = logging.getLogger("diktat")


class LongJob(QtCore.QObject):
    """Ein Auftrag: Datei transkribieren oder vom Mikrofon aufnehmen, bis stop() kommt."""
    part = Signal(str, float, float)      # bisheriger Text, Sekunden fertig, Gesamtdauer (-1 = offen)
    finished = Signal(str, float, str)    # Text, Sekunden Audio, Fehlermeldung

    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.level = 0.0
        self.running = False
        self.wav_path = None
        self._cancel = False
        self._queue = None
        self._stream = None
        self._rate = engine.RATE

    # ----- Datei
    def start_file(self, path):
        self._begin()
        threading.Thread(target=self._run_file, args=(str(path),), daemon=True).start()

    def _run_file(self, path):
        text, seconds, error = "", 0.0, ""
        try:
            total, blocks = engine.decode_file(path)
            done = [0.0]

            def on_part(so_far, secs):
                done[0] = secs
                self.part.emit(so_far, secs, total or -1.0)
            text = self.ctl.transcriber.transcribe_stream(blocks, on_part, lambda: self._cancel)
            seconds = done[0]
        except Exception as e:
            log.exception("Datei konnte nicht transkribiert werden")
            error = str(e) or type(e).__name__
        self._end(text, seconds, error)

    # ----- Mikrofon
    def start_recording(self):
        """Öffnet das Mikrofon; wirft bei Fehlern sofort (im Hauptthread)."""
        import sounddevice as sd
        self._begin()
        self._queue = queue.Queue()
        device = engine._device_index(self.ctl.cfg.get("microphone"))
        try:
            try:
                self._open(sd, device, engine.RATE)
            except Exception:
                self._open(sd, device, int(sd.query_devices(device, "input")["default_samplerate"]))
        except Exception:
            self.running = False
            raise
        folder = config.DIR / "aufnahmen"
        folder.mkdir(parents=True, exist_ok=True)
        self.wav_path = folder / time.strftime("%Y-%m-%d_%H-%M-%S.wav")
        threading.Thread(target=self._run_recording, daemon=True).start()

    def _open(self, sd, device, rate):
        self._rate = rate
        self._stream = sd.InputStream(samplerate=rate, channels=1, dtype="float32", device=device,
                                      blocksize=0, callback=self._callback)
        self._stream.start()

    def _callback(self, indata, frames, t, status):
        mono = indata[:, 0].copy()
        self.level = float(np.sqrt(np.mean(mono * mono))) if len(mono) else 0.0
        self._queue.put(mono)

    def stop_recording(self):
        """Aufnahme beenden; der Rest wird noch fertig geschrieben."""
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                log.exception("Audiostream ließ sich nicht sauber schließen")
        self.level = 0.0
        if self._queue is not None:
            self._queue.put(None)

    def _mic_blocks(self, wav):
        """Blöcke vom Mikrofon; schreibt nebenbei die Sicherungsdatei."""
        while True:
            block = self._queue.get()
            if block is None:
                return
            if self._rate != engine.RATE:
                n = max(1, int(len(block) * engine.RATE / self._rate))
                block = np.interp(np.linspace(0, len(block) - 1, n), np.arange(len(block)),
                                  block).astype(np.float32)
            wav.writeframes((np.clip(block, -1, 1) * 32767).astype(np.int16).tobytes())
            yield block

    def _run_recording(self):
        text, seconds, error = "", 0.0, ""
        try:
            with wave.open(str(self.wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(engine.RATE)
                done = [0.0]

                def on_part(so_far, secs):
                    done[0] = secs
                    self.part.emit(so_far, secs, -1.0)
                text = self.ctl.transcriber.transcribe_stream(self._mic_blocks(wav), on_part,
                                                               lambda: self._cancel)
                seconds = done[0]
        except Exception as e:
            log.exception("Aufnahme konnte nicht transkribiert werden")
            error = str(e) or type(e).__name__
        if not error:
            # Text ist da (oder verworfen): die Sicherungsdatei wird nicht mehr gebraucht
            try:
                Path(self.wav_path).unlink()
                self.wav_path = None
            except OSError:
                log.warning("Sicherungsdatei %s nicht löschbar", self.wav_path)
        self._end(text, seconds, error)

    # ----- gemeinsam
    def cancel(self):
        self._cancel = True
        self.stop_recording()

    def _begin(self):
        self.running, self._cancel, self.wav_path = True, False, None

    def _end(self, text, seconds, error):
        if text:
            text = engine.postprocess(text, {"dictionary": self.ctl.cfg.get("dictionary"),
                                             "trailing_space": False})
        self.running = False
        self.finished.emit(text, seconds, "" if self._cancel and not error else error)
