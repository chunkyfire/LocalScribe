"""Gesamtablauf ohne Mikrofon und ohne sichtbare Fenster: Erkennung -> Prompt -> Einfügen -> Verlauf."""
import json
import os
import pathlib
import sys
import tempfile
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
import numpy as np
from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import QTimer

from diktat import app as A
from diktat import config, llm

tmp = pathlib.Path(tempfile.mkdtemp(prefix="diktat_test_"))
config.DIR, config.FILE, config.DB, config.ICON = tmp, tmp / "config.json", tmp / "v.sqlite", tmp / "d.ico"
llm.get_key = lambda *a: ""


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        body = json.dumps({"choices": [{"message": {"content": "BEARBEITET: " + req["messages"][1]["content"]}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = HTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=server.serve_forever, daemon=True).start()
GOOD, BAD = f"http://127.0.0.1:{server.server_port}/v1", "http://127.0.0.1:9/v1"

qa = QtWidgets.QApplication(sys.argv)
qa.setQuitOnLastWindowClosed(False)
d = A.Diktat(qa)
d.cfg["llm"].update(enabled=True, base_url=GOOD, model="test", timeout=5)
d.apply_cfg()
pasted, failed = [], []
d.paste = pasted.append
with wave.open(str(ROOT / "test_de.wav")) as w:
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def check(name, ok):
    print("OK  " if ok else "FAIL", name, flush=True)
    if not ok:
        failed.append(name)


def dictate(prompt):
    d.pending += 1
    d.jobs.put({"kind": "dictation", "audio": audio, "seconds": len(audio) / 16000, "prompt": prompt})


def wait(cond, then, t0=None, limit=90):
    t0 = t0 or time.time()
    if cond():
        return then()
    if time.time() - t0 > limit:
        check("Zeitüberschreitung vor " + then.__name__, False)
        return finish()
    QTimer.singleShot(100, lambda: wait(cond, then, t0, limit))


def rows():
    return d.store.db.execute("SELECT text, roh, prompt, woerter, fenster FROM verlauf ORDER BY id").fetchall()


def step1():
    check("Modell geladen", d.ready)
    check("Prompt-Taste registriert", d.hotkey.holds.get("prompt:Glätten") == {"f8"} and d.hotkey.taps["paste_last"] == {"shift", "f7"})
    dictate("")
    wait(lambda: len(pasted) == 1, step2)


def step2():
    r = rows()[-1]
    check("Diktat ohne Prompt eingefügt", pasted[0].startswith("Der Patient") and r[2] == "" and r[3] > 20)
    dictate("Glätten")
    wait(lambda: len(pasted) == 2, step3)


def step3():
    r = rows()[-1]
    check("Diktat mit Prompt: KI-Text eingefügt, Rohtext im Verlauf",
          pasted[1].startswith("BEARBEITET: Der Patient") and pasted[1].endswith(" ") and r[1].startswith("Der Patient") and r[2] == "Glätten")
    d.cfg["llm"]["base_url"] = BAD
    dictate("Glätten")
    wait(lambda: len(pasted) == 3, step4)


def step4():
    r = rows()[-1]
    check("KI nicht erreichbar: unbearbeiteter Text eingefügt", pasted[2].startswith("Der Patient") and r[2] == "")
    check("Hinweis in der Statusleiste", "KI nicht erreichbar" in d.overlay.text)
    d.cfg["llm"]["base_url"] = GOOD
    d.rework("Hallo Welt", "Glätten")
    wait(lambda: len(rows()) == 4, step5)


def step5():
    check("Nachbearbeiten aus dem Verlauf: Ergebnis in Zwischenablage und Verlauf",
          rows()[-1][0] == "BEARBEITET: Hallo Welt" and QtGui.QGuiApplication.clipboard().text() == "BEARBEITET: Hallo Welt"
          and len(pasted) == 3)
    d.on_tap("paste_last")
    check("Letzten Text einfügen", pasted[-1] == "BEARBEITET: Hallo Welt")
    d.store.db.execute("UPDATE verlauf SET zeit = zeit - 40*86400 WHERE id = 1")
    d.cfg["history_days"] = 30
    d.apply_cfg()
    check("alte Einträge werden gelöscht", len(rows()) == 3)
    d.cfg["dictionary"] = {"Lipaze": "Lipase"}
    shots = ROOT / "_shots"
    shots.mkdir(exist_ok=True)
    d.hub.resize(1000, 680)
    for i in range(len(d.hub.pages)):
        d.hub.show_page(i)
        qa.processEvents()
        d.hub.grab().save(str(shots / f"{i}.png"))
    check("Kein Fenstertitel im Verlauf", all(r[4] == "" for r in rows()))
    from diktat.ui import private_mime
    fmts = private_mime("x").formats()
    check("Zwischenablage: vom Windows-Verlauf und der Cloud ausgenommen",
          sum(("CanIncludeInClipboardHistory" in f) or ("CanUploadToCloudClipboard" in f)
              or ("ExcludeClipboardContentFromMonitorProcessing" in f) for f in fmts) == 3)
    d.store.add("GEHEIMWORT-XYZ", 1.0, 0.1)
    d.store.delete(d.store.db.execute("SELECT MAX(id) FROM verlauf").fetchone()[0])
    check("Gelöschtes steht nicht mehr in der Verlaufsdatei", b"GEHEIMWORT-XYZ" not in config.DB.read_bytes())
    d.cfg["history_enabled"] = False
    d.apply_cfg()
    n = len(rows())
    dictate("")
    wait(lambda: len(pasted) == 5, lambda: after_off(n, stored_check))


def stored_check():
    stored = json.loads(config.FILE.read_text(encoding="utf-8"))
    check("Einstellungen gespeichert, kein Schlüssel in der Datei",
          stored["llm"]["enabled"] is True and "key" not in json.dumps(stored["llm"]).lower())
    finish()


def after_off(n, then):
    check("Verlauf ausgeschaltet: wird geleert, neues Diktat wird eingefügt, aber nicht gespeichert",
          n == 0 and len(rows()) == 0 and pasted[-1].startswith("Der Patient"))
    then()


def finish():
    d.hotkey.stop()
    print("FEHLER:" if failed else "ALLES OK", failed or "", flush=True)
    os._exit(1 if failed else 0)


wait(lambda: d.ready, step1)
qa.exec()
