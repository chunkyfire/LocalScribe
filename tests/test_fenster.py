"""Das Fenster ohne Bildschirm aufbauen und prüfen: Seite Aufnahme (Startzustand in jeder Fenstergröße ohne
Überlappen und Abschneiden, laufende Aufnahme), Zeile der Aufträge, Warten auf die Namenserkennung."""
import copy
import os
import pathlib
import sys
import tempfile
import time
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
from PySide6 import QtWidgets

from diktat import config, llm, schutz, sprecher
from diktat.ui import Store

config.DIR = pathlib.Path(tempfile.mkdtemp())
config.FILE = config.DIR / "config.json"
(config.DIR / "aufnahmen").mkdir()
llm.get_key = lambda *a: ""
sprecher.ready = lambda: True
failed = []


def check(name, ok, extra=""):
    print(("OK   " if ok else "FAIL ") + name, extra if not ok else "")
    if not ok:
        failed.append(name)


class Ctl:
    ready = True
    transcriber = listener = None

    class _S:
        def connect(self, f):
            pass
    sig_heard = _S()

    def __init__(self):
        self.cfg = copy.deepcopy(config.DEFAULTS)
        self.cfg["llm"].update(enabled=True, model="m", base_url="https://openrouter.ai/api/v1")
        self.store = Store(tempfile.mktemp(suffix=".sqlite"))
        self.shield_calls, self.shield_answer = [], False

    def shield_start(self, force=False, retry=False):
        self.shield_calls.append((force, retry))
        return self.shield_answer

    def listen_start(self, who=None): return ""
    def listen_stop(self): pass
    def remember(self, *a): pass
    def keep_awake(self, on): pass
    def create_shortcuts(self): pass
    def apply_cfg(self): pass
    def rework(self, t, n): pass
    def seen(self): pass
    def input_devices(self): return ["Mikrofon"]
    def parse_keys(self, t): return [x for x in t.replace(" ", "").split("+") if x]
    def autostart_enabled(self): return False
    def set_autostart(self, on): pass


app = QtWidgets.QApplication(sys.argv)
from diktat.hub import Hub

ctl = Ctl()
hub = Hub(ctl)
hub.show()
hub.show_page(1)
V = hub.pages[1][1]


def settle(n=6):
    for _ in range(n):
        app.processEvents()


def hero(size):
    """Liegen Zeit, Wellenform, Startknopf und „Datei laden“ ganz im Bereich, untereinander und in voller Höhe?"""
    hub.resize(*size)
    settle()
    H = V.hero
    parts = [H.clock] + ([H.wave] if H.wave.isVisible() else []) + [H.go, H.file]
    rects = [w.geometry() for w in parts]
    inside = all(H.rect().contains(r) for r in rects)
    below = all(rects[i].bottom() < rects[i + 1].top() for i in range(len(rects) - 1))
    whole = H.clock.height() == H.clock.high and H.go.height() >= 48
    return inside and below and whole and V.hero.isVisible(), (H.height(), H.scale, [(r.top(), r.bottom()) for r in rects])


check("Aufträge der Aufnahme: Visite, Meeting-Protokoll, Arztbrief, Pflegebericht", V.task_names == list(config.ON_RECORD), V.task_names)
ok, why = hero((1000, 680))
check("Startzustand in der üblichen Fenstergröße: nichts überlappt, nichts abgeschnitten", ok and V.hero.scale == (1.0, True), why)
ok, why = hero((860, 560))
check("Startzustand im kleinsten Fenster", ok, why)
hub.set_download(0.07, "Sprachmodell wird einmalig geladen · 7 % (66 von 910 MB)")
ok, why = hero((1000, 680))
check("Startzustand mit dem Band für den Download darüber", ok, why)
ok, why = hero((860, 560))
check("Startzustand im kleinsten Fenster mit Band", ok, why)
hub.set_download(None, "")
hub.resize(1000, 680)
settle()
V.info("Mikrofon nicht gefunden.", bad=True)
ok, why = hero((1000, 680))
check("Fehlermeldung im Startzustand hat Platz", ok and V.hero.note.isVisible(), why)
V.info("")
check("Zeit: jede Ziffer gleich breit", (lambda c: (c.setText("11:11"), c.width())[1] == (c.setText("00:00"), c.width())[1])(V.live_clock))
V.live_clock.setText("1:02:03")
check("Zeit über einer Stunde wird breiter, nicht abgeschnitten", V.live_clock.width() > (V.live_clock.setText("00:00"), V.live_clock.width())[1])

# laufende Aufnahme: Knopf, Zeit und Pegel
V.recording = True
V._rec_look(True)
V._state()
settle()
check("Aufnahme läuft: Knopf heißt Stopp, Zeile mit Zeit und Pegel ist da, der Startzustand weg",
      V.rec.text().strip() == "Stopp" and V.rec.objectName() == "recPillOn" and V.pulse.isVisible() and not V.hero.isVisible())
V.live_wave.feed(0.1)
check("Pegel kommt an", max(V.live_wave.levels) > 0.3)
V.recording = False
V._rec_look(False)
V._state()
settle()
check("Aufnahme beendet: Knopf wieder Aufnahme, Zeile weg", V.rec.text().strip() == "Aufnahme" and not V.pulse.isVisible())

# Auftrag bei fehlender Namenserkennung: laden und danach von selbst weitermachen, keine Fehlermeldung
state = {"blocked": True}
schutz.blocked = lambda server: state["blocked"]
llm.run = lambda server, instruction, text, key=None: "ERGEBNIS"
V.text.setPlainText("Herr Beispiel in Zimmer 12.")
V._state()
ctl.shield_answer = True
V._task("Pflegebericht")
check("Fehlt die Namenserkennung, wird sie geladen und der Auftrag wartet",
      "wird einmalig geladen" in V.note.text() and len(hub.shield_queue) == 1 and "Pflegebericht" not in V.waiting
      and ctl.shield_calls == [(True, False)], (V.note.text(), ctl.shield_calls))
hub.set_shield(0.43, "Namenserkennung wird einmalig geladen · 43 % (126 von 293 MB)")
check("Der Stand steht unten links", hub.shield_bar.isVisible() and "43 %" in hub.shield_note.text())
state["blocked"] = False
hub.set_shield(None, "")
end = time.time() + 5
while time.time() < end and not ((V.result or {}).get("texts") or {}).get("Pflegebericht"):
    settle(2)
    time.sleep(0.02)
check("Danach läuft der Auftrag von selbst", ((V.result or {}).get("texts") or {}).get("Pflegebericht") == "ERGEBNIS"
      and not hub.shield_queue and not hub.shield_bar.isVisible(), V.result)

def missing(*a, **k):
    raise llm.LlmError(schutz.MISSING)
state["blocked"], ctl.shield_answer, ctl.shield_calls, llm.run = True, False, [], missing
V._task("Visite")
end = time.time() + 5
while time.time() < end and "Visite" not in (V.errors.get("text_errors") or {}):
    settle(2)
    time.sleep(0.02)
check("Lässt sie sich nicht laden: eine Meldung, kein Kreislauf", ctl.shield_calls == [(True, False)] and "Visite" in (V.errors.get("text_errors") or {}), (ctl.shield_calls, V.errors))

# Einstellungen, LLM: Noirdoc als Anbieter, kurze Modellliste, eigener Modellname, Schlüssel bleibt beim Anbieter
keys, asked = {"OpenRouter": "or-geheim"}, []
llm.get_key = lambda profile="": keys.get(profile, "")
llm.set_key = lambda key, profile="": keys.__setitem__(profile, key) if key else keys.pop(profile, None)
answers = {"api.noirdoc.de": ["gemini-3.1-flash-lite", "gemini-4-hydrogen", "gpt-6-luna"]}


def fake_models(server, key=None):
    asked.append((llm.host_of(server["base_url"]), key))
    return answers.get(llm.host_of(server["base_url"]), [])


def wait(done):
    end = time.time() + 5
    while time.time() < end and not done():
        settle(2)
        time.sleep(0.02)
    return done()


llm.list_models = fake_models
hub.show_page(4)
S = hub.pages[4][1]
S.show_tab(1)
L = S.pages[1]
settle()
area = L.findChildren(QtWidgets.QScrollArea)[0]
hub.resize(1000, 680)
settle()
check("Einstellungen, LLM: Die Karten sind nicht breiter als das Fenster, kein Knopf ist abgeschnitten",
      area.widget().width() <= area.viewport().width() and L.fetch.geometry().right() <= L.fetch.parentWidget().width(),
      (area.widget().width(), area.viewport().width()))
check("Modell für Brief und Übergabe: Der Eintrag ist von vorn zu lesen", L.v_writer.lineEdit().cursorPosition() == 0
      and L.v_writer.currentText().startswith("Standard"), L.v_writer.currentText())
presets = [L.preset.itemText(i) for i in range(L.preset.count())]
check("Noirdoc steht in der Liste der Server, gleich nach OpenRouter",
      presets.index("Noirdoc") == presets.index("OpenRouter") + 1, presets)
check("Die bisherige Wahl bleibt wählbar und gewählt", L.model_name() == "m" and L.active == "OpenRouter", (L.model_name(), L.active))
check("Bei OpenRouter steht die kurze Liste oben, Gemini 4 Hydrogen zuerst",
      [L.model.itemData(i) for i in range(4)] == [m for m, _ in llm.picks("https://openrouter.ai/api/v1")]
      and L.model.itemData(0) == "google/gemini-4-hydrogen@low", [L.model.itemData(i) for i in range(L.model.count())])
L.preset.setCurrentIndex(presets.index("Noirdoc"))
L._preset(presets.index("Noirdoc"))
settle()
check("Noirdoc gewählt: Adresse und Vorgabe Gemini 4 Hydrogen mit wenig Nachdenken",
      L.url.text() == "https://api.noirdoc.de/v1" and L.model_name() == "gemini-4-hydrogen@low" and L.active == "Noirdoc",
      (L.url.text(), L.model_name(), L.active))
check("Der Schlüssel von OpenRouter geht nicht an Noirdoc", L._live()[1] == "" and not asked
      and "einfügen" in L.key.placeholderText(), (L._live()[1], asked, L.key.placeholderText()))
check("Hinweis zu Noirdoc steht da", "Noirdoc" in L.advice.text() and L.advice.isVisible())
L.key.setText("px-probe")
L.save()
check("Speichern legt den Anbieter Noirdoc mit eigenem Schlüssel an; der von OpenRouter bleibt",
      keys == {"OpenRouter": "or-geheim", "Noirdoc": "px-probe"}
      and [p["name"] for p in ctl.cfg["llm_profiles"]] == ["OpenRouter", "Noirdoc"]
      and ctl.cfg["llm"]["profile"] == "Noirdoc" and ctl.cfg["llm"]["model"] == "gemini-4-hydrogen@low",
      (keys, ctl.cfg["llm_profiles"], ctl.cfg["llm"]))
check("Nach dem Speichern eines Schlüssels fragt LocalScribe die Modellliste ab",
      wait(lambda: "Verbunden" in L.status.text()) and asked == [("api.noirdoc.de", None)], (L.status.text(), asked))
names = [L.model.itemData(i) for i in range(L.model.count())]
check("Liste vom Server: nur was er meldet, die kurze Liste oben, der Rest unter dem Strich",
      names == ["gemini-4-hydrogen@low", "gemini-3.1-flash-lite", None, "gemini-4-hydrogen", "gpt-6-luna"]
      and L.model_name() == "gemini-4-hydrogen@low", names)
ask = QtWidgets.QInputDialog.getText
QtWidgets.QInputDialog.getText = staticmethod(lambda *a, **k: ("mein-modell@low", True))
L._add_model()
check("Eigener Modellname über +: gewählt, gemerkt, entfernbar",
      L.model_name() == "mein-modell@low" and ctl.cfg["llm_models"] == {"api.noirdoc.de": ["mein-modell@low"]}
      and not L.drop.isHidden(), (L.model_name(), ctl.cfg.get("llm_models")))
QtWidgets.QInputDialog.getText = staticmethod(lambda *a, **k: ("google/gemma-4-31B-it", True))
L._add_model()
check("Ein Modell eines Anbieters ohne Verschwiegenheitsverpflichtung nimmt LocalScribe bei Noirdoc nicht an",
      L.model_name() == "mein-modell@low" and "nicht an" in L.note.text(), (L.model_name(), L.note.text()))
QtWidgets.QInputDialog.getText = ask
L._drop_model()
check("Entfernen: zurück zur Vorgabe", L.model_name() == "gemini-4-hydrogen@low" and ctl.cfg["llm_models"]["api.noirdoc.de"] == []
      and L.drop.isHidden(), (L.model_name(), ctl.cfg["llm_models"]))
asked.clear()
L._preset(presets.index("OpenRouter"))
check("Zurück zu OpenRouter: dessen Modell und Schlüssel kommen mit",
      L.active == "OpenRouter" and L.model_name() == "m" and L._live()[1] is None and "gespeichert" in L.key.placeholderText()
      and wait(lambda: asked == [("openrouter.ai", None)]), (L.active, L.model_name(), asked))
L._pick()

print("FEHLER:" if failed else "ALLES OK", failed or "")
sys.exit(1 if failed else 0)
