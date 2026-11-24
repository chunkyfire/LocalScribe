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

from diktat import config, llm, schutz, sprecher, visite
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


check("Prompts der Aufnahme: Visite, Meeting-Protokoll, Arztbrief, Pflegebericht", V.task_names == list(config.ON_RECORD), V.task_names)
ok, why = hero((1000, 680))
check("Startzustand in der üblichen Fenstergröße: nichts überlappt, nichts abgeschnitten", ok and V.hero.scale == (1.0, True), why)
check("Übliche Fenstergröße: Der Knopf heißt ausgeschrieben „Neue Aufnahme“", "Neue Aufnahme" in V.new_btn.text()
      and V.title.width() >= V.title.sizeHint().width())
ok, why = hero((860, 560))
check("Startzustand im kleinsten Fenster", ok, why)
check("Kleinstes Fenster: Überschrift und Knopf für die neue Aufnahme sind nicht abgeschnitten",
      V.title.width() >= V.title.sizeHint().width() and V.new_btn.width() >= V.new_btn.sizeHint().width()
      and V.new_btn.text() == "＋", (V.title.width(), V.title.sizeHint().width(), V.new_btn.text()))
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

# Einstellungen, LLM: eine Liste „Anbieter“ mit Noirdoc, kurze Modellliste, eigener Modellname, Schlüssel bleibt beim Anbieter
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


def pick(name):
    """Einen Anbieter in der Liste wählen, wie ein Klick."""
    i = L.provider.findText(name)
    L.provider.setCurrentIndex(i)
    L._provider_picked(i)
    settle()


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
names = [L.provider.itemText(i) for i in range(L.provider.count()) if L.provider.itemText(i)]
check("Eine Liste „Anbieter“: OpenRouter, Noirdoc, IONOS, STACKIT, die lokalen, zuletzt die eigene Adresse",
      names[:2] == ["OpenRouter", "Noirdoc"] and names[-1].startswith("Eigene Adresse") and len(names) == 7
      and not hasattr(L, "preset"), names)
check("Gewählt ist der gespeicherte Anbieter; die Adresse steht nur bei eigenen Servern daneben",
      L.provider.currentText() == "OpenRouter" and L.url.isHidden() and L.delete.isHidden(), L.provider.currentText())
check("Die bisherige Wahl bleibt wählbar und gewählt", L.model_name() == "m" and L.active == "OpenRouter", (L.model_name(), L.active))
check("Bei OpenRouter steht die kurze Liste oben, Gemini 4 Hydrogen zuerst",
      [L.model.itemData(i) for i in range(4)] == [m for m, _ in llm.picks("https://openrouter.ai/api/v1")]
      and L.model.itemData(0) == "google/gemini-4-hydrogen@low", [L.model.itemData(i) for i in range(L.model.count())])
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt
before = L.model.currentIndex()
for _ in range(3):
    QtWidgets.QApplication.sendEvent(L.model, QtGui.QWheelEvent(
        QtCore.QPointF(10, 10), L.model.mapToGlobal(QtCore.QPoint(10, 10)).toPointF(), QtCore.QPoint(0, 0), QtCore.QPoint(0, 120),
        Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
check("Das Mausrad über einem Auswahlfeld verstellt nichts", L.model.currentIndex() == before and L.model_name() == "m",
      (before, L.model.currentIndex()))
pick("Noirdoc")
check("Noirdoc gewählt: Adresse und Vorgabe Gemini 4 Hydrogen mit wenig Nachdenken",
      L.url.text() == "https://api.noirdoc.de/v1" and L.model_name() == "gemini-4-hydrogen@low" and L.active == "Noirdoc"
      and L.url.isHidden(), (L.url.text(), L.model_name(), L.active))
check("Der Schlüssel von OpenRouter geht nicht an Noirdoc", L._live()[1] == "" and not asked
      and "einfügen" in L.key.placeholderText(), (L._live()[1], asked, L.key.placeholderText()))
check("Hinweis zu Noirdoc steht beim Info-Zeichen neben dem Modell", "Noirdoc" in L.advice.toolTip())
L.key.setText("px-probe")
L.save()
check("Speichern legt den Anbieter Noirdoc mit eigenem Schlüssel an; der von OpenRouter bleibt",
      keys == {"OpenRouter": "or-geheim", "Noirdoc": "px-probe"}
      and [p["name"] for p in ctl.cfg["llm_profiles"]] == ["OpenRouter", "Noirdoc"]
      and ctl.cfg["llm"]["profile"] == "Noirdoc" and ctl.cfg["llm"]["model"] == "gemini-4-hydrogen@low"
      and L.provider.currentText() == "Noirdoc", (keys, ctl.cfg["llm_profiles"], ctl.cfg["llm"]))
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
L._drop_model()
check("Entfernen: zurück zur Vorgabe", L.model_name() == "gemini-4-hydrogen@low" and ctl.cfg["llm_models"]["api.noirdoc.de"] == []
      and L.drop.isHidden(), (L.model_name(), ctl.cfg["llm_models"]))
asked.clear()
pick("OpenRouter")
check("Zurück zu OpenRouter: dessen Modell und Schlüssel kommen mit",
      L.active == "OpenRouter" and L.model_name() == "m" and L._live()[1] is None and "gespeichert" in L.key.placeholderText()
      and wait(lambda: asked == [("openrouter.ai", None)]), (L.active, L.model_name(), asked))
pick("Eigene Adresse …")
check("Eigene Adresse: Das Feld für die Adresse erscheint, kein fremder Schlüssel geht mit",
      not L.url.isHidden() and L.url.text() == "" and L.active == "" and L._live()[1] == "", (L.active, L._live()[1]))
L.url.setText("https://ki.klinik.example/v1")
QtWidgets.QInputDialog.getText = staticmethod(lambda *a, **k: ("haus-modell", True))
L._add_model()
L.key.setText("haus-geheim")
L.save()
check("Speichern macht daraus einen eigenen Anbieter mit eigenem Schlüssel, in der Liste unter den bekannten",
      keys.get("ki.klinik.example") == "haus-geheim" and ctl.cfg["llm"]["profile"] == "ki.klinik.example"
      and L.provider.currentText() == "ki.klinik.example" and not L.delete.isHidden() and not L.url.isHidden()
      and ctl.cfg["llm"]["model"] == "haus-modell", (keys, ctl.cfg["llm"], L.provider.currentText()))
L._delete()
check("Löschen nimmt den eigenen Anbieter und seinen Schlüssel wieder heraus",
      "ki.klinik.example" not in keys and [p["name"] for p in ctl.cfg["llm_profiles"]] == ["OpenRouter", "Noirdoc"], keys)
QtWidgets.QInputDialog.getText = ask
pick("Noirdoc")
L.save()
schutz.blocked = lambda server: False

# Einstellungen, Prompts: Sammlung, drei Haken, Menüpunkte links
S.show_tab(2)
P = S.pages[2]
settle()
check("Reiter Prompts: die Sammlung steht dort, nicht mehr unter LLM",
      [S.tabs.button(i).text() for i in range(3)] == ["Allgemein", "LLM", "Prompts"] and P.list.count() == len(ctl.cfg["prompts"])
      and not hasattr(L, "list"))
row = [p["name"] for p in ctl.cfg["prompts"]].index("E-Mail")
P.list.setCurrentRow(row)
check("Ab Werk: Was kein Knopf auf der Seite Aufnahme ist, steht in der Auswahlliste „Meine Prompts“",
      not P.on_record.isChecked() and P.on_list.isChecked() and not P.on_pin.isChecked())
P.new_prompt(name="Tumorboard-Notiz", text="Schreibe eine Notiz für das Tumorboard.")
P.on_pin.setChecked(True)
P.menu["Wortschatz"].setChecked(False)
P.save()
pinned = [b.property("prompt") for b in hub.pins]
check("Angepinnter Prompt steht als Menüpunkt links, unter Übergabe",
      pinned == ["Tumorboard-Notiz"] and hub.nav.indexOf(hub.pins[0]) == hub.nav.indexOf(hub.buttons.button(2)) + 1, pinned)
check("Abgewählter Menüpunkt verschwindet aus der Leiste, die anderen bleiben",
      hub.buttons.button(3).isHidden() and not hub.buttons.button(2).isHidden() and ctl.cfg["menu_hidden"] == ["Wortschatz"])
P.menu["Wortschatz"].setChecked(True)
P.save()
check("Wieder angekreuzt, steht er wieder da", not hub.buttons.button(3).isHidden() and ctl.cfg["menu_hidden"] == [])

# Einstellungen, Prompts: Das Zeichen neben der Anweisung formuliert aus oder verbessert (wie auf der Seite Aufnahme)
hub.show_page(4)
S.show_tab(2)
P.list.setCurrentRow(P.list.count() - 1)
polished = []
llm.chat = lambda server, system, user, json_mode=False, key=None: polished.append((server["model"], system, user)) or "„Schreibe eine kurze Notiz für das Tumorboard. Übernimm nur, was gesagt wurde, und erfinde nichts.“"
before = P.text.toPlainText()
P._spark()
check("Reiter Prompts: Das KI-Zeichen schreibt die Anweisung neu, mit dem eingestellten Modell, Name und Eingabe gehen mit",
      wait(lambda: P.text.toPlainText().startswith("Schreibe eine kurze Notiz")) and polished[-1][1] == config.POLISH
      and polished[-1][0] == ctl.cfg["llm"]["model"] and before in polished[-1][2] and P.name.text() in polished[-1][2]
      and P.spark.isEnabled() and "nicht gespeichert" in P.note.text(), (polished[-1:], P.note.text()))
P.text.undo()
check("Strg + Z holt die alte Anweisung zurück", P.text.toPlainText() == before, P.text.toPlainText())
P.text.setPlainText("")
P._spark()
check("Ohne Text fragt das Zeichen niemanden", len(polished) == 1 and "Erst Stichworte" in P.note.text(), P.note.text())
P.text.setPlainText(before)
hub.show_page(1)

# Seite Aufnahme: Auswahlliste, eigener Prompt, angepinnter Prompt
ran = []
llm.run = lambda server, instruction, text, key=None: ran.append((instruction, text)) or "ERGEBNIS"
hub.show_page(1)
V._new()
settle()
check("Neben der Überschrift steht „Neue Aufnahme“; der kleine Knopf „Neu“ in der Leiste ist weg",
      "Neue Aufnahme" in V.new_btn.text() and not [b for b in V.bar.findChildren(QtWidgets.QPushButton) if b.text() == "Neu"])
V.text.setPlainText("Herr Beispiel in Zimmer 12.")
V._state()
settle()
listed = [a.text() for a in V.more.menu().actions() if a.text()]
check("Auswahlliste „Meine Prompts“: was nicht als Knopf dasteht, dazu der Weg in die Sammlung",
      "Tumorboard-Notiz" in listed and "E-Mail" in listed and "Visite" not in listed and listed[-1].startswith("Sammlung"), listed)
check("Zeile „Eigener Prompt“ steht unter den Knöpfen; ohne Text ist „Ausführen“ aus",
      V.own.isVisible() and not V.own_run.isEnabled() and V.own_keep.isHidden())
V.own_text.setPlainText("Zusammenfassung mit Fokus auf den Zeitplan")
V._own_run()
check("Eigener Prompt: läuft mit genau diesem Text als Anweisung, Ergebnis als eigener Block",
      wait(lambda: ((V.result or {}).get("texts") or {}).get(V.OWN) == "ERGEBNIS")
      and ran[-1] == ("Zusammenfassung mit Fokus auf den Zeitplan", "Herr Beispiel in Zimmer 12."), ran[-1:])
# Hinweiszeilen der Klinik-Prompts: unter dem Eintrag zu sehen, aber nicht in dem, was „Kopieren“ nimmt
import diktat.hub as hubmod
copies, _button = [], hubmod.copy_button
hubmod.copy_button = lambda get_text, text="Kopieren": copies.append(get_text) or _button(get_text, text)
llm.run = lambda server, instruction, text, key=None: "S:\n- Befinden gut\n\nNicht diktiert: Untersuchungsbefund, Beurteilung"
V._task("Visite")
wait(lambda: "Nicht diktiert" in (((V.result or {}).get("texts") or {}).get("Visite") or ""))
settle()
hubmod.copy_button = _button
box = next(b for b in V.text_boxes if b.findChild(QtWidgets.QLabel, "boxTitle").text() == "Visite")
hints = [l.text() for l in box.findChildren(QtWidgets.QLabel, "hint")]
shown = [l.text() for l in box.findChildren(QtWidgets.QLabel) if l.objectName() not in ("hint", "boxTitle", "muted")]
copied = [get() for get in copies]
check("„Nicht diktiert“ steht als Hinweis unter dem Eintrag und wird nicht mitkopiert",
      hints == ["Nicht diktiert: Untersuchungsbefund, Beurteilung"] and "S:\n- Befinden gut" in shown
      and "S:\n- Befinden gut" in copied and not [c for c in copied if "Nicht diktiert" in c], (hints, shown, copied))
llm.run = lambda server, instruction, text, key=None: ran.append((instruction, text)) or "ERGEBNIS"
sent = []
llm.chat = lambda server, system, user, json_mode=False, key=None: sent.append((server["model"], system, user)) or "„Fasse zusammen. Übernimm nur, was gesagt wurde, und erfinde nichts.“"
V._spark()
check("Das KI-Zeichen formuliert die kurze Eingabe aus: schnelles Modell, Eingabe und Transkript gehen mit, ohne Anführungszeichen",
      wait(lambda: V.own_text.toPlainText().startswith("Fasse zusammen")) and sent[-1][0] == "gemini-3.1-flash-lite"
      and sent[-1][1] == config.SPARK and "Fokus auf den Zeitplan" in sent[-1][2] and "Zimmer 12" in sent[-1][2]
      and V.spark.isEnabled(), sent[-1:])
QtWidgets.QInputDialog.getText = staticmethod(lambda *a, **k: ("Zeitplan", True))
V._own_keep()
QtWidgets.QInputDialog.getText = ask
kept = config.prompt_by_name(ctl.cfg, "Zeitplan")
check("In die Sammlung: als Prompt gespeichert und sofort in der Auswahlliste",
      kept and kept["text"].startswith("Fasse zusammen") and "Zeitplan" in [a.text() for a in V.more.menu().actions()], kept)
hub._nav(hub.PIN)
settle()
check("Angepinnter Prompt: eigene Seite mit seinem Namen, die Aufnahme beginnt leer, die vorige liegt unter Gespeichert",
      V.pin == "Tumorboard-Notiz" and V.title.toolTip() == "Tumorboard-Notiz" and hub.pins[0].isChecked() and V.hero.isVisible()
      and "Tumorboard-Notiz" in V.hero.hint.text() and len(V.store.rows()) >= 1, (V.pin, V.title.text()))
ran.clear()
V.text.setPlainText("Fall eins im Tumorboard.")
V._recorded("Fall eins im Tumorboard.", 12.0, "")
check("Nach dem Stopp läuft der angepinnte Prompt von selbst",
      wait(lambda: ((V.result or {}).get("texts") or {}).get("Tumorboard-Notiz") == "ERGEBNIS")
      and ran[-1][0] == "Schreibe eine Notiz für das Tumorboard.", ran)
hub.show_page(1)
check("Zurück zu „Aufnahme“: wieder die normale Seite", V.pin == "" and V.title.text() == "Aufnahme" and hub.buttons.button(1).isChecked()
      and not V.hero.hint.isVisible())

# Listen: Klick öffnet, Stift und X beim Überfahren, Papierkorb mit Zurückholen
V._tab(1)
settle()
rows = [V.lists[0][1].itemAt(i).widget() for i in range(V.lists[0][1].count() - 1)]
count = len(rows)
check("Gespeichert: eine Zeile je Aufnahme, die Zeichen erscheinen erst beim Überfahren, unten keine Knöpfe mehr",
      count >= 2 and all(b.isHidden() for b in rows[0].signs) and [b.toolTip() for b in rows[0].signs] == ["Umbenennen", "In den Papierkorb"])
rows[0].enterEvent(QtGui.QEnterEvent(QtCore.QPointF(5, 5), QtCore.QPointF(5, 5), QtCore.QPointF(5, 5)))
check("Beim Überfahren stehen Stift und X da", all(not b.isHidden() for b in rows[0].signs))
rows[0].signs[1].click()
settle()
check("X legt die Zeile in den Papierkorb, ohne Auswählen",
      V.lists[0][1].count() - 1 == count - 1 and V.lists[1][1].count() - 1 == 1 and "(1)" in V.tabs.button(2).text())
V._tab(2)
settle()
gone = V.lists[1][1].itemAt(0).widget()
check("Papierkorb: Zurückholen und endgültig löschen", [b.toolTip() for b in gone.signs] == ["Zurückholen", "Endgültig löschen"])
gone.signs[0].click()
settle()
check("Zurückholen bringt die Zeile wieder", V.lists[0][1].count() - 1 == count and V.lists[1][1].count() - 1 == 0)
V._tab(1)
settle()
first = V.lists[0][1].itemAt(0).widget()
first.on_open()
settle()
check("Klick auf die Zeile öffnet die Aufnahme", V.stack.currentIndex() == 0 and V.case is not None and V.text.toPlainText().strip() != "")

# Übergabe: Bereich Pflege schreibt den Pflegebericht, sonst nichts
hub.show_page(2)
U = hub.pages[2][1]
settle()
check("Übergabe: vier Bereiche, „Neuer Fall“ neben der Überschrift, kein Erklärtext auf der Seite",
      [b.text() for b in U.frames.buttons()] == ["Notaufnahme", "Normalstation", "Intensivstation", "Pflege"]
      and "Neuer Fall" in U.new_btn.text() and not [w for w in U.findChildren(QtWidgets.QLabel) if "Kein Medizinprodukt" in w.text()])
U._frame_picked(3)
U.text.setPlainText("Herr Beispiel vor dem Bett sitzend vorgefunden.")
settle()
check("Bereich Pflege: Der Knopf heißt „Pflegebericht schreiben“", U.go.text() == "Pflegebericht schreiben" and U.frame() == "pflege")
ran.clear()
jev_calls = []
visite.triage = lambda *a, **k: jev_calls.append("jev")
visite.analyse = lambda *a, **k: jev_calls.append("brief")
U._analyse()
check("Er schreibt den Pflegebericht mit dem Prompt der Sammlung; Ersteinschätzung und Arztbrief laufen nicht",
      wait(lambda: ((U.result or {}).get("texts") or {}).get("Pflegebericht") == "ERGEBNIS") and not jev_calls
      and ran[-1] == (config.prompt_by_name(ctl.cfg, "Pflegebericht")["text"], "Herr Beispiel vor dem Bett sitzend vorgefunden."),
      (ran[-1:], jev_calls))
case = U.case
U._new()
U._frame_picked(0)
U._open(case)
check("Der Fall merkt sich den Bereich Pflege", U.frame() == "pflege" and U.go.text() == "Pflegebericht schreiben", U.frame())
U._frame_picked(0)

# Keine Seite ist breiter als ihr Fenster: Sonst schneidet das Fenster die Karten rechts ab (so bis 2.1.1 unter
# Einstellungen, Allgemein, wegen eines Ankreuzfelds mit einem Text von 960 Pixeln in einer Zeile).
from diktat.hub import Check
wide = []
for size in ((1000, 680), (860, 560)):
    hub.resize(*size)
    settle()
    for i, (name, page) in enumerate(hub.pages):
        hub.show_page(i)
        for k, sub in enumerate(getattr(page, "pages", None) or [page]):
            if hasattr(page, "show_tab"):
                page.show_tab(k)
            settle()
            if sub.minimumSizeHint().width() > sub.width():
                wide.append((size, name, k, "Seite", sub.minimumSizeHint().width(), sub.width()))
            for area in sub.findChildren(QtWidgets.QScrollArea):
                inner = area.widget()
                if inner is not None and area.isVisible() and inner.width() > area.viewport().width() + 1:
                    wide.append((size, name, k, inner.width(), area.viewport().width()))
check("Keine Seite ist breiter als ihr Fenster, in der Standardgröße und in der kleinsten Größe", not wide, wide)
hub.resize(1000, 680)
settle()
long = Check("Einmal am Tag von selbst nach Updates fragen (bei GitHub; von dir wird dabei nichts übertragen). "
             "Gibt es eines, leuchtet unten links der Knopf „Update“.")
check("Ankreuzfeld mit langem Text: Der Text bricht um, statt Breite zu fordern",
      long.minimumSizeHint().width() < 200 and long.heightForWidth(300) > long.heightForWidth(900) >= 18
      and long.text().startswith("Einmal am Tag"), (long.minimumSizeHint().width(), long.heightForWidth(300), long.heightForWidth(900)))
long.resize(400, long.heightForWidth(400))
long.click()
check("Es bleibt ein Ankreuzfeld: Klick schaltet um, auch auf dem Text", long.isChecked() and long.hitButton(QtCore.QPoint(300, 30)))
check("Einstellungen: Die Ankreuzfelder mit langen Texten brechen um",
      all(isinstance(w, Check) for w in (hub.settings.auto_check, hub.settings.signs, hub.settings.warm, L.protect, L.fix)))

print("FEHLER:" if failed else "ALLES OK", failed or "")
sys.exit(1 if failed else 0)
