"""Lange Aufnahmen und Audiodateien: stückweise erkennen, Text wächst mit.

Grundsätze für die Aufnahme
- Der Ton wird laufend in eine Sicherungsdatei geschrieben. Stürzt die App ab oder fällt der Strom
  aus, ist bis auf den letzten Augenblick alles da und lässt sich beim nächsten Start nachholen.
- Die Sicherungsdatei wird gelöscht, sobald der Text vollständig vorliegt. Sie bleibt nur liegen,
  wenn etwas schiefging (dann steht im Fenster, wo sie liegt).
- Ein einzelnes misslungenes Stück bricht nichts ab; die Stelle wird im Text markiert.
"""
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
    """Ein Auftrag: Datei transkribieren oder vom Mikrofon aufnehmen, bis stop_recording() kommt."""
    part = Signal(str, float, float)      # bisheriger Text, Sekunden fertig, Gesamtdauer (-1 = offen)
    finished = Signal(str, float, str)    # Text, Sekunden Audio, Fehlermeldung

    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.level = 0.0
        self.running = False
        self.wav_path = None        # Sicherungsdatei der laufenden oder letzten Aufnahme
        self.kept = None            # Sicherungsdatei, die wegen eines Problems liegen blieb
        self.failed = 0             # Stücke, die nicht erkannt werden konnten
        self.overflows = 0          # vom Audiotreiber gemeldete Aussetzer
        self.noisy = False          # sehr lautes Grundrauschen: Erkennung unzuverlässiger
        self.last_block = 0.0       # Zeitpunkt des letzten Mikrofon-Blocks (für die Überwachung)
        self._cancel = False
        self._queue = None
        self._stream = None
        self._rate = engine.RATE

    # ----- Datei
    def start_file(self, path):
        self._begin()
        threading.Thread(target=self._run, args=(lambda: engine.decode_file(str(path)), None),
                         daemon=True).start()

    def start_recovery(self, path):
        """Liegengebliebene Sicherungsdatei nachträglich transkribieren; bei Erfolg wird sie gelöscht."""
        self._begin()
        path = Path(path)
        seconds = max(0, path.stat().st_size - 44) / 2 / engine.RATE
        threading.Thread(target=self._run, args=(lambda: (seconds, engine.recover_wav(path)), path),
                         daemon=True).start()

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
        self.last_block = time.time()
        folder = config.DIR / config.RECORDINGS
        folder.mkdir(parents=True, exist_ok=True)
        self.wav_path = folder / time.strftime("%Y-%m-%d_%H-%M-%S.wav")
        threading.Thread(target=self._run, args=(lambda: (None, self._mic_blocks()), self.wav_path),
                         daemon=True).start()

    def _open(self, sd, device, rate):
        self._rate = rate
        self._stream = sd.InputStream(samplerate=rate, channels=1, dtype="float32", device=device,
                                      blocksize=0, callback=self._callback)
        self._stream.start()

    def _callback(self, indata, frames, t, status):
        if status:
            self.overflows += 1
        mono = indata[:, 0].copy()
        self.level = float(np.sqrt(np.mean(mono * mono))) if len(mono) else 0.0
        self.last_block = time.time()
        self._queue.put(mono)

    def mic_alive(self) -> bool:
        """Liefert das Mikrofon noch Ton? (False z. B. nach Abziehen des USB-Mikrofons)"""
        stream = self._stream
        return stream is not None and stream.active and time.time() - self.last_block < 2.0

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

    def _mic_blocks(self):
        """Blöcke vom Mikrofon; schreibt nebenbei die Sicherungsdatei."""
        wav = None
        try:
            wav = wave.open(str(self.wav_path), "wb")
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(engine.RATE)
        except OSError:
            log.exception("Sicherungsdatei nicht anlegbar – Aufnahme läuft ohne Sicherung weiter")
        try:
            while True:
                block = self._queue.get()
                if block is None:
                    return
                if self._rate != engine.RATE:
                    n = max(1, int(len(block) * engine.RATE / self._rate))
                    block = np.interp(np.linspace(0, len(block) - 1, n), np.arange(len(block)),
                                      block).astype(np.float32)
                if wav is not None:
                    try:
                        wav.writeframes((np.clip(block, -1, 1) * 32767).astype(np.int16).tobytes())
                    except OSError:   # z. B. Datenträger voll: lieber weiter transkribieren als abbrechen
                        log.exception("Sicherungsdatei nicht mehr beschreibbar")
                        wav = None
                yield block
        finally:
            if wav is not None:
                try:
                    wav.close()
                except OSError:
                    log.exception("Sicherungsdatei nicht schließbar")

    # ----- gemeinsam
    def _run(self, open_source, backup):
        """open_source() -> (Dauer oder None, Blockstrom). backup: Datei, die nach Erfolg gelöscht wird."""
        text, error, done, stats = "", "", [0.0], {}
        try:
            total, blocks = open_source()

            def on_part(so_far, secs):
                done[0] = secs
                self.part.emit(so_far, secs, total or -1.0)
            text = self.ctl.transcriber.transcribe_stream(blocks, on_part, lambda: self._cancel, stats)
        except Exception as e:
            log.exception("Transkription abgebrochen")
            error = str(e) or type(e).__name__
        self.failed = stats.get("failed", 0)
        self.noisy = bool(stats.get("noisy"))
        if self.overflows:
            log.warning("Audiotreiber meldete %d Aussetzer während der Aufnahme", self.overflows)
        if backup is not None:
            complete = not error and not self.failed
            if complete or self._cancel:
                # Text ist vollständig da (oder die Aufnahme wurde verworfen): Ton wird nicht mehr gebraucht
                try:
                    Path(backup).unlink(missing_ok=True)
                except OSError:
                    log.warning("Sicherungsdatei %s nicht löschbar", backup)
                    self.kept = Path(backup)
            else:
                self.kept = Path(backup)
        if text:
            text = engine.postprocess(text, {"dictionary": self.ctl.cfg.get("dictionary"),
                                             "trailing_space": False})
        self.running = False
        self.finished.emit(text, done[0], "" if self._cancel and not error else error)

    def cancel(self):
        self._cancel = True
        self.stop_recording()

    def _begin(self):
        self.running, self._cancel = True, False
        self.wav_path = self.kept = None
        self.failed = self.overflows = 0
        self.noisy = False
