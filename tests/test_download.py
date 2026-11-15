"""Erster Start: Das Sprachmodell wird wirklich heruntergeladen (650 MB, braucht Internet, dauert Minuten).

Prüft, dass der Fortschritt im Fenster ankommt, dass erst danach diktiert werden kann, dass das Modell
im eigenen Ordner liegt und beim zweiten Start ohne Netz gefunden wird. Läuft in einem leeren
Temp-Ordner und rührt das echte Modell nicht an.
"""
import os
import pathlib
import shutil
import sys
import tempfile
import time

tmp = pathlib.Path(tempfile.mkdtemp(prefix="diktat_dl_"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["HF_HUB_CACHE"] = str(tmp / "hf")           # so tun, als hätte der Rechner noch kein Modell
os.environ["HF_HOME"] = str(tmp / "hfhome")
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from PySide6 import QtWidgets
from PySide6.QtCore import QTimer

from diktat import app as A
from diktat import config, llm, modelle

config.DIR, config.FILE, config.DB, config.ICON = tmp, tmp / "config.json", tmp / "v.sqlite", tmp / "d.ico"
llm.get_key = lambda: ""
failed, seen, early = [], [], []


def check(name, ok, extra=""):
    print("OK  " if ok else "FAIL", name, extra, flush=True)
    if not ok:
        failed.append(name)


qa = QtWidgets.QApplication(sys.argv)
qa.setQuitOnLastWindowClosed(False)
d = A.Diktat(qa)
start = time.time()


def poll():
    if d.download is not None:
        seen.append((d.download, d.hub.loadbar.isVisibleTo(d.hub), d.hub.banner.isVisibleTo(d.hub), d.overlay.text))
        if not early:
            d.on_start("hold")                 # Diktierversuch mitten im Download
            early.append((d.recording, d.overlay.text))
    if not d.ready and time.time() - start < 1500:
        return QTimer.singleShot(300, poll)
    fractions = [s[0] for s in seen]
    check("Download startet sichtbar", bool(seen) and all(s[1] and s[2] for s in seen), f"({len(seen)} Messpunkte)")
    check("Fortschritt wächst von unter 20 % bis über 90 %",
          bool(fractions) and min(fractions) < 0.2 and max(fractions) > 0.9 and fractions == sorted(fractions),
          str([round(f, 2) for f in fractions[::max(1, len(fractions) // 8)]]))
    check("Leiste zeigt Prozent und Megabyte", any("%" in s[3] and "MB" in s[3] for s in seen), seen[len(seen) // 2][3] if seen else "")
    check("Diktieren während des Downloads startet nicht, sagt aber warum",
          bool(early) and not early[0][0] and "geladen" in early[0][1], str(early))
    check("Danach bereit, Balken weg", d.ready and not d.hub.loadbar.isVisibleTo(d.hub) and not d.hub.banner.isVisibleTo(d.hub))
    m = config.MODELS["de"]
    files = ["config.json", "vocab.txt", "nemo128.onnx", "*-model.int8.onnx*"]
    path = modelle.find(m["repo"], m["revision"], files)
    check("Modell liegt im eigenen Ordner", bool(path) and str(tmp / "modelle") in path
          and (pathlib.Path(path) / modelle.MARK).exists(), str(path))
    calls = []
    again = modelle.fetch(m["repo"], m["revision"], files, lambda a, b: calls.append(a))
    check("Zweiter Start lädt nichts", again == path and not calls)
    print(f"Dauer {time.time() - start:.0f} s")
    print("FEHLER:" if failed else "ALLES OK", failed or "", flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    os._exit(1 if failed else 0)


QTimer.singleShot(300, poll)
qa.exec()
