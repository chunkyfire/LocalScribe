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

from . import __version__, config, engine, felder, handy, korrektor, llm, winio, wortschatz
from .hub import Hub, keys_text
from .ui import Overlay, Store, make_icon, make_pixmap, private_mime

log = logging.getLogger("diktat")
INSTANCE = "LocalScribe-instanz"


class Diktat(QtCore.QObject):
    sig_start, sig_tap = Signal(str), Signal(str)
    sig_stop, sig_cancel, sig_lock = Signal(), Signal(), Signal()
    sig_ready = Signal(str)
    sig_status = Signal(str)
    sig_download = Signal(float, float)   # geladene Bytes, Gesamtgröße (Modell-Download)
    sig_shield = Signal(float, float, str)  # Namenserkennung: geladene Bytes, Gesamtgröße, "" | "ok" | Fehlertext
    sig_heard = Signal(str, str)      # gehörter Text, Fehlermeldung (Wörterbuch: Wort einsprechen)
    sig_result = Signal(object)
    sig_phone = Signal(object)        # Aufnahme vom Telefon (Handy als Mikrofon)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.cfg = config.load()
        self.store = Store(config.DB)
        self.recorder = engine.Recorder()
        self.fields = felder.Fields()         # Sprungmarken im zuletzt eingefügten Text
        self.recorder.set_warm(self.cfg.get("mic_warm"), self.cfg.get("microphone"))
        self.transcriber = engine.Transcriber(self.cfg)
        self.overlay = Overlay(self.recorder)
        self.ready = self.recording = False
        self.listener = None              # Seite, die gerade ein eingesprochenes Wort erwartet
        self.heard_audio = None
        self.download = None              # Anteil des Modell-Downloads, solange er läuft
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
        self.sig_download.connect(self.on_download)
        self.sig_shield.connect(self.on_shield)
        self.shield_loading, self.shield_failed = False, 0.0
        self.sig_result.connect(self.on_result)
        self.sig_phone.connect(self.on_phone)
        self.phone = None
        self.target = 0
        QTimer.singleShot(0, self.start_phone)

        self.hub = Hub(self)
        self.tray = QtWidgets.QSystemTrayIcon(make_icon(), self)
        self.menu = QtWidgets.QMenu()
        self.menu.addAction("LocalScribe öffnen", self.hub.open)
        self.profile_menu = self.menu.addMenu("Profil")
        self.profile_menu.aboutToShow.connect(lambda: self.hub.profile_actions(self.profile_menu))
        self.menu.aboutToShow.connect(lambda: self.profile_menu.menuAction().setVisible(config.profiles_on()))
        self.menu.addAction("Letzten Text kopieren",
                            lambda: QtGui.QGuiApplication.clipboard().setMimeData(private_mime(self.store.last())))
        self.menu.addSeparator()
        self.menu.addAction("Beenden", self.quit)
        self.restart_action = QtGui.QAction("", self.menu, triggered=self.restart_new)
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
        self.offered = ""                    # Nummer der neueren Fassung, auf die das Fenster schon hinweist
        self._watch = QTimer(self, interval=600_000, timeout=self.watch_update)
        self._watch.start()
        self.asked = 0.0                     # wann zuletzt bei GitHub nach einer neueren Fassung gefragt wurde
        self._ask = QTimer(self, interval=3 * 3600_000, timeout=self.ask_update)
        self._ask.start()
        QTimer.singleShot(25_000, self.ask_update)
        QTimer.singleShot(1500, self.after_start)

    # ---------- Schnittstelle für das App-Fenster ----------
    parse_keys = staticmethod(winio.parse_keys)
    input_devices = staticmethod(engine.input_devices)
    autostart_enabled = staticmethod(winio.autostart_enabled)
    set_autostart = staticmethod(winio.set_autostart)
    keep_awake = staticmethod(winio.keep_awake)

    @staticmethod
    def create_shortcuts():
        winio.create_shortcuts(str(config.ICON))

    def after_start(self):
        """Nach einem Update einmal zeigen, was neu ist; alte Fassungen wegräumen; nach einer neueren sehen."""
        from . import pflege
        seen = self.cfg.get("seen_version", "")
        if seen and pflege.number(seen) != pflege.number(__version__):
            config.backup(f"vor-{__version__}")      # Stand der Einstellungen vor dem Wechsel der Fassung
        if seen and pflege.number(seen) < pflege.number(__version__):
            self.hub.announce(seen)
        elif seen != __version__:
            self.seen()
        threading.Thread(target=pflege.tidy, daemon=True).start()
        self.watch_update()

    def seen(self):
        self.cfg["seen_version"] = __version__
        config.save(self.cfg)

    def watch_update(self):
        """Hat jemand (hier oder an einem anderen Rechner am selben Ordner) eine neuere Fassung eingerichtet?
        Dann weist das Fenster darauf hin. Liest nur eine kleine Datei im Programmordner, fragt nichts im Netz."""
        from . import pflege
        try:
            version = pflege.pending()
        except OSError:
            return
        if version and version != self.offered:
            if not self.offered:
                self.menu.insertAction(self.menu.actions()[-1], self.restart_action)
            self.offered = version
            self.restart_action.setText(f"Fassung {version} starten")
            self.hub.offer_restart(version)

    def ask_update(self):
        """Nur wenn in den Einstellungen eingeschaltet: einmal am Tag still bei GitHub nach einer neueren Fassung
        fragen. Gibt es eine, leuchtet unten links im Fenster der Update-Knopf. Gesendet wird nur die Anfrage."""
        from . import pflege
        if not self.cfg.get("update_check") or self.offered or not pflege.program():
            return
        if time.time() - self.asked < 23 * 3600:
            return
        self.asked = time.time()
        self.hub.settings._check(quiet=True)

    def restart_new(self):
        from . import pflege
        if self.hub.busy():
            return self.hub.news_note("Erst die laufende Aufnahme oder Transkription beenden.")
        pflege.restart()
        self.quit()

    def uninstall(self, data: bool):
        """Verknüpfungen, Autostart und Programmordner entfernen, auf Wunsch auch die eigenen Daten samt Schlüsseln."""
        from . import pflege
        winio.remove_shortcuts()
        winio.set_autostart(False)
        if data:
            for name in [""] + [p.get("name", "") for p in self.cfg.get("llm_profiles", [])]:
                try:
                    llm.set_key("", name)
                except Exception:
                    pass
            logging.shutdown()               # gibt diktat.log frei, sonst bleibt der Datenordner liegen
        pflege.remove(pflege.program(), data)
        self.quit()

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

    def listen_start(self, who=None) -> str:
        """Aufnahme für „Wort einsprechen“ und das Stimmtraining beginnen. who: die Seite, die zuhört.
        Gibt eine Fehlermeldung zurück oder ""."""
        self.listener = who
        if not self.ready:
            return "Das Sprachmodell lädt noch."
        if self.recording:
            return "Es läuft gerade ein Diktat."
        try:
            self.recorder.start()
        except Exception as e:
            return f"Mikrofon nicht verfügbar: {e}"
        self.recording = True
        return ""

    def listen_stop(self):
        """Aufnahme beenden; das Ergebnis kommt über sig_heard."""
        if not self.recording:
            return
        audio = self.recorder.stop()
        self.recording = False
        self.heard_audio = audio          # Stimmtraining: nur falls der vorgelesene Satz aufgehoben werden soll

        def work():
            try:
                self.sig_heard.emit(self.transcriber.transcribe(audio), "")
            except Exception as e:
                log.exception("Einsprechen fehlgeschlagen")
                self.sig_heard.emit("", str(e) or type(e).__name__)
        threading.Thread(target=work, daemon=True).start()

    def apply_cfg(self):
        """Geänderte Einstellungen speichern und sofort wirksam machen."""
        config.save(self.cfg)
        self.transcriber.cfg = self.cfg
        self.recorder.set_warm(self.cfg.get("mic_warm"), self.cfg.get("microphone"))
        self.cleanup()
        self.start_hotkey()
        self.start_phone()
        if self.ready and self.cfg.get("model_choice", "de") != self.transcriber.loaded:
            # anderes Sprachmodell gewählt: im Hintergrund laden, bis dahin ruht das Diktieren
            self.ready = False
            self.set_status("Sprachmodell wird gewechselt …")
            threading.Thread(target=self._load, daemon=True).start()
        elif self.ready:
            self.set_status(self.ready_text())
            self.shield_start()

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
        taps = {"paste_last": self.cfg.get("hotkey_paste_last") or [],
                "next_field": self.cfg.get("hotkey_next_field") or [],
                "target": self.cfg.get("hotkey_target") or []}
        self.hotkey = winio.Hotkey(holds, self.cfg.get("hotkey_lock"), taps,
                                   self.sig_start.emit, self.sig_stop.emit, self.sig_cancel.emit,
                                   self.sig_lock.emit, self.sig_tap.emit)
        self.hotkey.start()

    def capture_keys(self, callback):
        """Einstellungen: die nächste Tastenkombination an callback melden (None beendet das Lauschen)."""
        if self.hotkey:
            self.hotkey.grab(callback)

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
        if self.phone:
            self.phone.stop()
        self.recorder.warm = False           # Mikrofon beim Beenden sicher schließen
        self.recorder.stop()
        llm.release(self.cfg["llm"])       # lokales Sprachmodell aus dem Grafikspeicher nehmen
        self.tray.hide()
        self.app.quit()
        # Kein Rest im Hintergrund: Bleibt nach dem Beenden ein Thread hängen (Audiotreiber, Netz), liefe der Prozess
        # unsichtbar weiter und hielte den Programmordner fest. Nach drei Sekunden ist deshalb in jedem Fall Schluss.
        last = threading.Timer(3.0, lambda: os._exit(0))
        last.daemon = True
        last.start()

    # ---------- Modell und Arbeitsschlange ----------
    def _load(self):
        try:
            self.transcriber.load(lambda done, total: self.sig_download.emit(float(done), float(total)))
            self.sig_ready.emit("")
        except Exception as e:
            log.exception("Modell konnte nicht geladen werden")
            self.sig_ready.emit(str(e) or type(e).__name__)

    def retry_load(self):
        """Noch einmal versuchen, das Sprachmodell zu laden (Knopf in der Fehlermeldung)."""
        self.hub.set_error("")
        self.set_status("Modell lädt …")
        threading.Thread(target=self._load, daemon=True).start()

    def on_status(self, text):
        self.set_status(text)
        self.overlay.set_mode("message", text)

    def on_download(self, done, total):
        """Erster Start: Das Sprachmodell wird geladen. Sichtbar im Fenster, in der Leiste und im Infobereich."""
        mb = 1024 * 1024
        if self.download is None and not self.hub.isVisible():
            self.hub.open()              # auch beim stillen Start zeigen, warum es noch nicht losgeht
        self.download = done / total if total else 0.0
        text = f"Sprachmodell wird einmalig geladen · {self.download * 100:.0f} % ({done / mb:.0f} von {total / mb:.0f} MB)"
        if done >= total > 0:
            text = "Sprachmodell wird eingerichtet …"
        self.set_status(text)
        self.hub.set_download(self.download, text)
        self.overlay.set_progress(text, self.download)

    def shield_start(self, force=False, retry=False) -> bool:
        """Die Namenserkennung laden, wenn sie fehlt und ein Server außerhalb dieses Rechners mit eingeschaltetem
        Schutz eingestellt ist (force: immer, wenn sie fehlt; retry: auch kurz nach einem Fehlschlag, per Klick in
        den Einstellungen). Der Fortschritt steht unten links im Fenster. Gibt True zurück, solange geladen wird.
        So scheitert kein Auftrag daran, dass sie fehlt."""
        from . import schutz
        if self.shield_loading:
            return True
        server = self.cfg.get("llm") or {}
        wanted = (force and not schutz.ready()) or (bool((server.get("base_url") or "").strip()) and schutz.blocked(server))
        if not wanted or (time.time() - self.shield_failed < 60 and not retry):
            return False                        # nichts zu laden, oder gerade fehlgeschlagen: nicht im Kreis versuchen
        self.shield_loading = True

        def work():
            try:
                schutz.prepare(lambda done, total: self.sig_shield.emit(float(done), float(total), ""))
                self.sig_shield.emit(1.0, 1.0, "ok")
            except Exception as e:
                self.sig_shield.emit(0.0, 0.0, str(e) or type(e).__name__)
        threading.Thread(target=work, daemon=True).start()
        return True

    def on_shield(self, done, total, state):
        if state:
            self.shield_loading = False
            if state != "ok":
                self.shield_failed = time.time()
                log.warning("Namenserkennung nicht geladen: %s", state)
            self.hub.set_shield(None, "" if state == "ok" else state)
            return
        mb, part = 1024 * 1024, done / total if total else 0.0
        self.hub.set_shield(part, f"Namenserkennung wird einmalig geladen · {part * 100:.0f} % "
                                  f"({done / mb:.0f} von {total / mb:.0f} MB)")

    def on_ready(self, error):
        self.download = None
        self.hub.set_download(None, "")
        self.hub.set_error("")
        if error:
            self.set_status("Sprachmodell fehlt – Details im Fenster")
            self.hub.set_error(error)
            self.hub.open()
            self.overlay.flash("Modell konnte nicht geladen werden", 6000)
            return
        self.ready = True
        self.recorder.set_warm(self.cfg.get("mic_warm"), self.cfg.get("microphone"))
        self.set_status(self.ready_text())
        self.overlay.flash(f"Bereit – {keys_text(self.cfg['hotkey_hold'])} halten und sprechen", 3500)
        self.shield_start()

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
                    if korrektor.enabled(cfg) and clean.strip():
                        clean, fixed = korrektor.correct(clean, cfg["llm"], memory=cfg.get("corrections"))
                        if fixed:
                            log.info("Fachkorrektur: %d Wort/Wörter ersetzt", len(fixed))
                    if wortschatz.grow(cfg, clean):
                        config.save(cfg)
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
            self.overlay.flash("Modell lädt noch …" if self.download is None
                               else f"Sprachmodell wird noch geladen ({self.download * 100:.0f} %) – gleich geht es los")
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
        note = engine.audio_note(audio)
        if note == "stumm":
            self._settle()
            self.overlay.flash(engine.NOTES[note], 6000)
            return
        self.beep(880, 660)
        self.pending += 1
        self.overlay.set_mode("processing")
        self.jobs.put({"kind": "dictation", "audio": audio, "seconds": seconds, "prompt": self.prompt, "note": note})

    def on_tap(self, ident):
        if ident == "target":
            return self.toggle_target()
        if ident == "next_field":
            step = self.fields.next()
            if step is None:
                self.overlay.flash("Keine Sprungmarke mehr offen")
            else:
                self._field_when_free(step, 0)
            return
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
        elif out.get("note") and not self.recording:
            self._settle()
            self.overlay.flash(engine.NOTES[out["note"]], 5000)
        else:
            self._settle()

    def _settle(self):
        if self.recording:
            return
        self.overlay.set_mode("processing" if self.pending else "idle")

    # ---------- Handy als Mikrofon ----------
    def start_phone(self):
        """Den Empfang für das Telefon ein- oder ausschalten, je nach Einstellung."""
        want = self.cfg.get("phone") or {}
        if self.phone and (not want.get("enabled") or self.phone.token != want.get("token")
                           or self.phone.port != int(want.get("port") or handy.PORT)):
            self.phone.stop()
            self.phone = None
        if want.get("enabled") and want.get("token") and not self.phone:
            try:
                self.phone = handy.Server(self._from_phone, want["token"], want.get("port"))
                self.phone.start()
            except Exception as e:
                log.exception("Handy-Mikrofon nicht startbar")
                self.phone = None
                self.overlay.flash(f"Handy als Mikrofon nicht startbar: {e}", 6000)

    def _from_phone(self, audio):
        """Läuft im Thread des Webservers: prüfen, dann an die Oberfläche übergeben. Gibt einen Ablehnungsgrund zurück."""
        if not self.ready:
            return "Das Sprachmodell am Rechner lädt noch. Gleich noch einmal versuchen."
        if len(audio) / engine.RATE < float(self.cfg.get("min_seconds", 0.3)):
            return "Die Aufnahme war zu kurz."
        if engine.audio_note(audio) == "stumm":
            return "Es kam kein Ton an. Mikrofon am Telefon prüfen."
        self.sig_phone.emit(audio)
        return ""

    def on_phone(self, audio):
        self.beep(880, 660)
        self.pending += 1
        self.overlay.set_mode("processing")
        self.jobs.put({"kind": "dictation", "audio": audio, "seconds": len(audio) / engine.RATE, "prompt": "",
                       "note": engine.audio_note(audio)})

    # ---------- Zielfenster ----------
    def toggle_target(self):
        """Das Fenster, das gerade vorn ist, als Ziel merken; ein zweiter Druck löst es wieder."""
        if getattr(self, "target", 0):
            self.target = 0
            self.overlay.flash("Zielfenster gelöst – Text geht wieder dorthin, wo der Cursor steht", 3000)
            return
        hwnd = winio.foreground()
        title = winio.window_title(hwnd).strip()
        if not hwnd or not title or "LocalScribe" in title:
            self.overlay.flash("Kein Fenster zum Merken – erst in das Zielprogramm klicken", 3000)
            return
        self.target = hwnd
        self.overlay.flash("Zielfenster: " + (title if len(title) < 46 else title[:44] + "…"), 3000)

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
        self.fields.pasted(text)
        cb.setMimeData(private_mime(text))
        self._send_when_free(0)

    def _field_when_free(self, step, tries):
        # erst bewegen, wenn die Tasten des Kürzels losgelassen sind (sonst würde Umschalt mitmarkieren)
        if winio.modifiers_down() and tries < 100:
            QTimer.singleShot(20, lambda: self._field_when_free(step, tries + 1))
            return
        try:
            winio.send_field(*step)
        except Exception:
            log.exception("Sprungmarke nicht ansteuerbar")

    def _send_when_free(self, tries):
        # Strg+V erst senden, wenn keine Modifikatortaste mehr gedrückt ist
        if winio.modifiers_down() and tries < 100:
            QTimer.singleShot(20, lambda: self._send_when_free(tries + 1))
            return
        QTimer.singleShot(50, self._send)

    def _send(self):
        target = getattr(self, "target", 0)
        if target and not winio.window_alive(target):
            self.target = target = 0
            self.overlay.flash("Zielfenster ist geschlossen – Text geht dorthin, wo der Cursor steht", 4000)
        if target and winio.foreground() != target:
            if not winio.focus(target):
                self.overlay.flash("Zielfenster nicht erreichbar – Text liegt in der Zwischenablage", 4000)
                return
            QTimer.singleShot(180, self._paste_now)         # dem Fenster Zeit geben, den Fokus zu übernehmen
            return
        self._paste_now()

    def _paste_now(self):
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
    from . import sprecher
    stats = {"turns": sprecher.Turns(), "words": []} if sprecher.ready() else {}
    text = engine.postprocess(t.transcribe_stream(blocks, stats=stats), cfg)
    who = ""
    if stats:                            # prüft auch, dass beide Modelle der Sprechertrennung im Paket laufen
        labels, step = stats["turns"].finish()
        who = f" [{len(set(sprecher.assign(stats['words'], labels, step)))} Sprecher]"
    import keyring
    log.info("Schlüsselspeicher: %s", type(keyring.get_keyring()).__name__)
    from . import ort
    line = f"Selbsttest {__version__} aus {ort.here() or 'dem Quelltext'}: {seconds or 0:.1f} s Audio in {time.time() - start:.2f} s{who} -> {text!r}"
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
    if getattr(sys, "frozen", False):
        # Läuft LocalScribe schon aus einem ANDEREN Ordner? Dann würde hier nur dessen Fenster aufgehen, und der
        # andere Ordner bliebe gesperrt (nicht löschbar), ohne dass man sieht, warum.
        # Dieselbe Installation in einer anderen Fassung (fassungen\…) zählt nicht als anderer Ordner.
        from . import ort
        here = os.path.normcase(str(ort.root()))
        if "--nach-update" in sys.argv:      # die bisherige Fassung beendet sich gerade: kurz auf sie warten
            for _ in range(60):
                if not winio.others():
                    break
                time.sleep(0.25)
            QtNetwork.QLocalServer.removeServer(INSTANCE)
        elsewhere = [(pid, path) for pid, path in winio.others()
                     if os.path.normcase(str(ort.root_of(os.path.dirname(path)))) != here]
        if elsewhere:
            box = QtWidgets.QMessageBox()
            box.setWindowTitle("LocalScribe läuft schon")
            box.setIcon(QtWidgets.QMessageBox.Question)
            box.setText("LocalScribe läuft bereits, aber aus einem anderen Ordner:\n\n"
                        + "\n".join(sorted({os.path.dirname(path) for _, path in elsewhere}))
                        + f"\n\nDu startest gerade die Fassung {__version__} aus:\n\n{ort.root()}"
                        "\n\nSolange die andere läuft, lässt sich ihr Ordner nicht löschen.")
            mine = box.addButton("Die andere beenden und diese starten", QtWidgets.QMessageBox.AcceptRole)
            box.addButton("Bei der anderen bleiben", QtWidgets.QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is mine:
                if not winio.end([pid for pid, _ in elsewhere]):
                    QtWidgets.QMessageBox.warning(None, "LocalScribe", "Die andere Fassung ließ sich nicht beenden. "
                                                  "Bitte über den Task-Manager beenden (Reiter Details, LocalScribe.exe).")
                    return
                QtNetwork.QLocalServer.removeServer(INSTANCE)
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
    if getattr(sys, "frozen", False):
        threading.Thread(target=winio.follow, daemon=True).start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
