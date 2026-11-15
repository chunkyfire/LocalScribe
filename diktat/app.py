"""LocalScribe: Tastenkürzel, lokale Erkennung, optionale KI-Nachbearbeitung, Einfügen."""
import logging
import logging.handlers
import os
import queue
import sys
import threading
import time

if sys.stderr is None:  # pythonw hat keine Konsole
    sys.stdout = sys.stderr = open(os.devnull, "w")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("DO_NOT_TRACK", "1")

from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets
from PySide6.QtCore import QTimer, Signal

from . import config, engine, llm, winio
from .hub import Hub, keys_text
from .ui import Overlay, Store, make_icon, make_pixmap, private_mime

log = logging.getLogger("diktat")
INSTANCE = "LocalScribe-instanz"


class Diktat(QtCore.QObject):
    sig_start, sig_tap = Signal(str), Signal(str)
    sig_stop, sig_cancel, sig_lock = Signal(), Signal(), Signal()
    sig_ready = Signal(str)
    sig_status = Signal(str)
    sig_result = Signal(object)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.cfg = config.load()
        self.store = Store(config.DB)
        self.recorder = engine.Recorder()
        self.recorder.device_name = self.cfg.get("microphone")
        self.transcriber = engine.Transcriber(self.cfg)
        self.overlay = Overlay(self.recorder)
        self.ready = self.recording = False
        self.pending = 0
        self.prompt = ""  # Prompt der laufenden Aufnahme
        self.jobs = queue.Queue()
        self._clip_backup = None
        self._restore = QTimer(self, singleShot=True, interval=900, timeout=self._restore_clipboard)

        self.sig_start.connect(self.on_start)
        self.sig_stop.connect(self.on_stop)
        self.sig_cancel.connect(self.on_cancel)
        self.sig_lock.connect(self.on_lock)
        self.sig_tap.connect(self.on_tap)
        self.sig_ready.connect(self.on_ready)
        self.sig_status.connect(self.on_status)
        self.sig_result.connect(self.on_result)

        self.hub = Hub(self)
        self.tray = QtWidgets.QSystemTrayIcon(make_icon(), self)
        self.menu = QtWidgets.QMenu()
        self.menu.addAction("LocalScribe öffnen", self.hub.open)
        self.menu.addAction("Letzten Text kopieren",
                            lambda: QtGui.QGuiApplication.clipboard().setMimeData(private_mime(self.store.last())))
        self.menu.addSeparator()
        self.menu.addAction("Beenden", self.quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(lambda why: self.hub.open()
                                    if why == QtWidgets.QSystemTrayIcon.Trigger else None)
        self.tray.show()

        self.cleanup()
        self._cleanup = QTimer(self, interval=3600_000, timeout=self.cleanup)
        self._cleanup.start()
        self.hotkey = None
        self.start_hotkey()
        self.set_status("Modell lädt …")
        self.overlay.set_mode("message", "Modell lädt …")
        threading.Thread(target=self._load, daemon=True).start()
        threading.Thread(target=self._worker, daemon=True).start()

    # ---------- Schnittstelle für das App-Fenster ----------
    parse_keys = staticmethod(winio.parse_keys)
    input_devices = staticmethod(engine.input_devices)
    autostart_enabled = staticmethod(winio.autostart_enabled)
    set_autostart = staticmethod(winio.set_autostart)
    keep_awake = staticmethod(winio.keep_awake)

    @staticmethod
    def create_shortcuts():
        winio.create_shortcuts(str(config.ICON))

    def cleanup(self):
        """Aufbewahrungsfrist durchsetzen: alte Verlaufseinträge und liegengebliebene Aufnahmen löschen."""
        try:
            if not self.cfg.get("history_enabled", True):
                self.store.clear()
            gone = self.store.prune(self.cfg.get("history_days"))
            audio = config.purge_recordings(self.cfg.get("history_days"))
            if gone or audio:
                log.info("Aufgeräumt: %d Verlaufseinträge, %d Aufnahmen gelöscht", gone, audio)
        except Exception:
            log.exception("Aufräumen fehlgeschlagen")

    def remember(self, text, seconds, latency, raw="", prompt=""):
        """In den Verlauf schreiben – nur, wenn er eingeschaltet ist."""
        if self.cfg.get("history_enabled", True):
            self.store.add(text, seconds, latency, raw, prompt)
            self.hub.refresh()

    def apply_cfg(self):
        """Geänderte Einstellungen speichern und sofort wirksam machen."""
        config.save(self.cfg)
        self.transcriber.cfg = self.cfg
        self.recorder.device_name = self.cfg.get("microphone")
        self.cleanup()
        self.start_hotkey()
        if self.ready:
            self.set_status(self.ready_text())

    def rework(self, text, prompt_name):
        """Einen Verlaufseintrag mit einem Prompt nachbearbeiten; Ergebnis landet in der Zwischenablage."""
        self.pending += 1
        self.overlay.set_mode("processing")
        self.jobs.put({"kind": "rework", "text": text, "prompt": prompt_name, "seconds": 0.0})

    # ---------- Tasten ----------
    def start_hotkey(self):
        if self.hotkey:
            self.hotkey.stop()
        holds = {"dictate": self.cfg["hotkey_hold"]}
        if self.cfg["llm"].get("enabled"):
            for p in self.cfg.get("prompts") or []:
                if p.get("hotkey") and p.get("name"):
                    holds["prompt:" + p["name"]] = p["hotkey"]
        taps = {"paste_last": self.cfg.get("hotkey_paste_last") or []}
        self.hotkey = winio.Hotkey(holds, self.cfg.get("hotkey_lock"), taps,
                                   self.sig_start.emit, self.sig_stop.emit, self.sig_cancel.emit,
                                   self.sig_lock.emit, self.sig_tap.emit)
        self.hotkey.start()

    def ready_text(self):
        return f"Bereit · {keys_text(self.cfg['hotkey_hold'])} halten"

    def set_status(self, text):
        self.tray.setToolTip(f"LocalScribe – {text}")
        self.hub.set_status(text)

    def quit(self):
        if self.hub.busy():
            box = QtWidgets.QMessageBox(self.hub)
            box.setWindowTitle("LocalScribe beenden")
            box.setText("Es läuft noch eine Aufnahme oder Transkription. Beim Beenden geht der noch nicht "
                        "erkannte Teil nicht verloren: Die Tonaufnahme bleibt liegen und wird beim nächsten "
                        "Start angeboten.")
            yes = box.addButton("Trotzdem beenden", QtWidgets.QMessageBox.DestructiveRole)
            box.addButton("Weiterlaufen lassen", QtWidgets.QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not yes:
                return
        winio.keep_awake(False)
        self.hotkey.stop()
        self.recorder.stop()
        self.tray.hide()
        self.app.quit()

    # ---------- Modell und Arbeitsschlange ----------
    def _load(self):
        try:
            self.transcriber.load(self.sig_status.emit)
            self.sig_ready.emit("")
        except Exception as e:
            log.exception("Modell konnte nicht geladen werden")
            self.sig_ready.emit(str(e) or type(e).__name__)

    def on_status(self, text):
        self.set_status(text)
        self.overlay.set_mode("message", text)

    def on_ready(self, error):
        if error:
            self.set_status("Modellfehler (siehe diktat.log)")
            self.overlay.flash("Modell konnte nicht geladen werden", 6000)
            return
        self.ready = True
        self.set_status(self.ready_text())
        self.overlay.flash(f"Bereit – {keys_text(self.cfg['hotkey_hold'])} halten und sprechen", 3500)

    def _worker(self):
        while True:
            job = self.jobs.get()
            out = {k: v for k, v in job.items() if k != "audio"}
            out.update(error="", warn="", raw="", text="")
            start = time.time()
            try:
                cfg = self.cfg
                if job["kind"] == "dictation":
                    clean = engine.postprocess(self.transcriber.transcribe(job["audio"]), cfg)
                else:
                    clean = job["text"]
                out["raw"] = out["text"] = clean
                prompt = config.prompt_by_name(cfg, job.get("prompt") or "")
                if not (prompt and cfg["llm"].get("enabled")):
                    out["prompt"] = ""
                elif clean.strip():
                    try:
                        text = llm.run(cfg["llm"], prompt.get("text", ""), clean)
                        if job["kind"] == "dictation" and cfg.get("trailing_space", True) \
                                and not text.endswith("\n"):
                            text += " "
                        out["text"] = text
                    except Exception as e:
                        log.warning("KI-Nachbearbeitung fehlgeschlagen: %s", e)
                        out["warn"] = str(e) or type(e).__name__
                        out["prompt"] = ""
            except Exception as e:
                log.exception("Erkennung fehlgeschlagen")
                out["error"] = str(e) or type(e).__name__
            out["latency"] = time.time() - start
            self.sig_result.emit(out)

    # ---------- Ablauf ----------
    def beep(self, *freqs):
        if self.cfg.get("sounds"):
            engine.tone(freqs)

    def on_start(self, ident):
        if self.recording:
            return
        if not self.ready:
            self.hotkey.reset()
            self.overlay.flash("Modell lädt noch …")
            return
        try:
            self.recorder.start()
        except Exception:
            log.exception("Mikrofon lässt sich nicht öffnen")
            self.hotkey.reset()
            self.overlay.flash("Mikrofon nicht verfügbar")
            return
        if ident.startswith("prompt:"):
            self.prompt = ident[len("prompt:"):]
        else:
            self.prompt = self.cfg["llm"].get("auto_prompt") or "" if self.cfg["llm"].get("enabled") else ""
        self.recording = True
        self.beep(660, 880)
        self.overlay.set_mode("recording")

    def on_lock(self):
        if self.recording:
            self.beep(880, 880)
            self.overlay.set_mode("locked")

    def on_cancel(self):
        if not self.recording:
            return
        self.recorder.stop()
        self.recording = False
        self.beep(330)
        self._settle()

    def on_stop(self):
        if not self.recording:
            return
        audio = self.recorder.stop()
        self.recording = False
        seconds = len(audio) / engine.RATE
        if seconds < float(self.cfg.get("min_seconds", 0.3)):
            self._settle()
            return
        self.beep(880, 660)
        self.pending += 1
        self.overlay.set_mode("processing")
        self.jobs.put({"kind": "dictation", "audio": audio, "seconds": seconds, "prompt": self.prompt})

    def on_tap(self, ident):
        if ident == "paste_last":
            text = self.store.last()
            if text:
                self.paste(text)
            else:
                self.overlay.flash("Der Verlauf ist leer")

    def on_result(self, out):
        self.pending = max(0, self.pending - 1)
        if out["error"]:
            self.overlay.flash("Erkennung fehlgeschlagen (siehe diktat.log)", 4000)
            return
        text = out["text"]
        if out["kind"] == "rework":
            if out["warn"]:
                self.overlay.flash(f"KI: {out['warn']}"[:90], 6000)
                return
            self.remember(text, 0.0, out["latency"], out["raw"], out["prompt"])
            QtGui.QGuiApplication.clipboard().setMimeData(private_mime(text))
            self.overlay.flash("Ergebnis kopiert")
            return
        log.info("%.1f s Audio in %.2f s verarbeitet (%d Zeichen%s)", out["seconds"], out["latency"],
                 len(text), ", Prompt " + out["prompt"] if out["prompt"] else "")
        if not text.strip():
            if not self.recording:
                self.overlay.flash("Kein Text erkannt – Mikrofon prüfen")
            return
        self.remember(text, out["seconds"], out["latency"], out["raw"], out["prompt"])
        self.paste(text)
        if out["warn"] and not self.recording:
            self.overlay.flash("KI nicht erreichbar – unbearbeiteter Text eingefügt", 5000)
        else:
            self._settle()

    def _settle(self):
        if self.recording:
            return
        self.overlay.set_mode("processing" if self.pending else "idle")

    # ---------- Einfügen ----------
    def paste(self, text):
        cb = QtGui.QGuiApplication.clipboard()
        if self.cfg.get("restore_clipboard", True) and not self._restore.isActive():
            try:
                src = cb.mimeData()
                backup = QtCore.QMimeData()
                for fmt in src.formats():
                    backup.setData(fmt, src.data(fmt))
                self._clip_backup = backup
            except Exception:
                log.exception("Zwischenablage nicht sicherbar")
                self._clip_backup = None
        self._restore.stop()
        cb.setMimeData(private_mime(text))
        self._send_when_free(0)

    def _send_when_free(self, tries):
        # Strg+V erst senden, wenn keine Modifikatortaste mehr gedrückt ist
        if winio.modifiers_down() and tries < 100:
            QTimer.singleShot(20, lambda: self._send_when_free(tries + 1))
            return
        QTimer.singleShot(50, self._send)

    def _send(self):
        try:
            winio.send_paste()
        except Exception:
            log.exception("Einfügen fehlgeschlagen")
            self.overlay.flash("Einfügen fehlgeschlagen – Text liegt in der Zwischenablage", 4000)
            return
        if self.cfg.get("restore_clipboard", True):
            self._restore.start()

    def _restore_clipboard(self):
        backup, self._clip_backup = self._clip_backup, None
        try:
            cb = QtGui.QGuiApplication.clipboard()
            if backup is not None and backup.formats():
                cb.setMimeData(backup)
            else:
                cb.clear()
        except Exception:
            log.exception("Zwischenablage nicht wiederherstellbar")


def selftest(path):
    """Ohne Oberfläche: Audiodatei erkennen; Ergebnis auf die Konsole und ins Protokoll."""
    cfg = config.load()
    t = engine.Transcriber(cfg)
    t.load()
    start = time.time()
    seconds, blocks = engine.decode_file(path)
    text = engine.postprocess(t.transcribe_stream(blocks), cfg)
    import keyring
    log.info("Schlüsselspeicher: %s", type(keyring.get_keyring()).__name__)
    line = f"Selbsttest: {seconds or 0:.1f} s Audio in {time.time() - start:.2f} s -> {text!r}"
    log.info(line)
    print(line)


def already_running() -> bool:
    """Läuft die App schon, dessen Fenster nach vorn holen."""
    sock = QtNetwork.QLocalSocket()
    sock.connectToServer(INSTANCE)
    if not sock.waitForConnected(300):
        return False
    winio.allow_foreground()
    sock.write(b"show")
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


def main():
    config.migrate()
    config.DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(config.LOG, maxBytes=500_000, backupCount=1, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s %(message)s")
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
        logging.getLogger().addHandler(logging.StreamHandler())
        selftest(sys.argv[2])
        return
    winio.set_app_id()
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(config.APP)
    app.setWindowIcon(make_icon())
    if already_running():
        return
    if not config.ICON.exists():  # Symbol für die Verknüpfungen
        make_pixmap(256).save(str(config.ICON), "ICO")
    diktat = Diktat(app)
    QtNetwork.QLocalServer.removeServer(INSTANCE)
    server = QtNetwork.QLocalServer(app)

    def on_connect():
        conn = server.nextPendingConnection()
        conn.disconnected.connect(conn.deleteLater)
        diktat.hub.open()
    server.newConnection.connect(on_connect)
    server.listen(INSTANCE)
    if "--hidden" not in sys.argv:
        diktat.hub.open()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
