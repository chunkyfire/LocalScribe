"""Fassung 0.8: Schreibweisen, Stimmtraining, Sprecher trennen, Fachkorrektur mit Türsteher, Modellordner."""
import json
import pathlib
import sys
import tempfile

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from diktat import config, engine, korrektor, modelle, sprecher, training

failed = []


def check(name, ok, extra=""):
    print("OK  " if ok else "FAIL", name, extra)
    if not ok:
        failed.append(name)


cfg = dict(config.DEFAULTS, dictionary={}, snippets={}, commands={}, trailing_space=False)

# ----- Schreibweisen
t = engine.postprocess("Pantoprazol 40 mg100, Metoprololsuccinat 47,5 mg101, Tresiba 20 Einheiten 100.", cfg)
check("Einnahmeschema wird getrennt", "40 mg 1-0-0" in t and "47,5 mg 1-0-1" in t and "20 Einheiten 1-0-0" in t, t)
t = engine.postprocess("Glukose 5 g 100 ml, Ibuprofen 600 mg 1200 mg, Amoxicillin 1000 mg.", cfg)
check("Mengenangaben bleiben", t == "Glukose 5 g 100 ml, Ibuprofen 600 mg 1200 mg, Amoxicillin 1000 mg.", t)
t = engine.postprocess("Vitalparameter RR140 zu 90, Hertz, Frequenz 85. Limitierung 0090 Grad.", cfg)
check("Blutdruck, Herzfrequenz, Neutral-Null", t == "Vitalparameter RR 140 zu 90, Herzfrequenz 85. Limitierung 0-0-90 Grad.", t)
t = engine.postprocess("58-jähriger Patientin reduziertem Allgemeinzustand. Die Patientin klagt über Schmerzen.", cfg)
check("Patient in / Patientin", t == "58-jähriger Patient in reduziertem Allgemeinzustand. Die Patientin klagt über Schmerzen.", t)
check("Englischer Einwurf am Anfang fällt weg", engine.LEADING.sub("", "Hey! 58-jähriger Patient") == "58-jähriger Patient"
      and engine.LEADING.sub("", "Heyde-Syndrom bekannt") == "Heyde-Syndrom bekannt")
check("Eingeschobener Vokal", engine.postprocess("Moxonoidin", cfg) == "Moxonidin", engine.postprocess("Moxonoidin", cfg))
check("Wörterbuch greift über Bindestrich",
      engine.postprocess("Set-Implantation", dict(cfg, dictionary={"Set Implantation": "Stentimplantation"})) == "Stentimplantation")

voc = dict(cfg, vocabulary=["RIVA", "Trimbow", "Tresiba", "Brinkkötter"])
t = engine.postprocess("Stent im Riba, Trimbo und Trossiba, Rücksprache mit Brinkötter. Der Riva ist frei, die Rippe nicht.", voc)
check("Eigene Begriffe werden am Klang erkannt",
      t == "Stent im RIVA, Trimbow und Tresiba, Rücksprache mit Brinkkötter. Der RIVA ist frei, die Rippe nicht.", t)
check("Ohne eigene Begriffe bleibt es", "Riba" in engine.postprocess("Stent im Riba", cfg))

# ----- Stimmtraining
read, learned, open_ = training.learn(
    "Koronare Dreigefäßerkrankung, Zustand nach Stentimplantation im RIVA vor sechs Monaten.",
    "Coronare 3-Gefäßerkrankung, Zustand nach Set-Implantation im Riba vor sechs Monaten.")
check("Training lernt Hörfehler", read and ("Riba", "RIVA") in learned and ("Set Implantation", "Stentimplantation") in learned, str(learned))
read, learned, open_ = training.learn("Cave: Nierenfunktion beachten.", "Kabel Nierenfunktion beachten.")
check("Training lernt keine echten Wörter um", read and not learned and open_ == [("Kabel", "Cave")], str((learned, open_)))
read, learned, open_ = training.learn("Im Verlauf rückläufige Entzündungsparameter.", "Im Verlauf rückläufiger Entzündungsparameter.")
check("Training lernt keine Beugungsformen", read and not learned, str(learned))
check("Anderer Satz gelesen: nichts lernen", training.learn("Pantoprazol vierzig Milligramm.", "Das Wetter ist heute schön.") == (False, [], []))
n = sum(len(v) for v in training.material().values())
check("Lesematerial vorhanden", n >= 150, f"({n} Sätze in {len(training.material())} Themen)")

# ----- Sprecher
# Zeitleiste: 0 bis 2 s Sprecher 2, Pause, 3 bis 5 s Sprecher 1 (Nummern der Gruppierung), Schritt 0,1 s
_line = np.array([2] * 20 + [0] * 10 + [1] * 20, np.int16)
_words = [("Guten", 0.2), ("Tag.", 0.8), ("Hallo.", 3.1), ("Ja.", 2.6), ("Gut.", 4.5)]
who = sprecher.assign(_words, _line, 0.1)
check("Wörter bekommen den Sprecher ihres Zeitpunkts, Nummern nach erstem Auftreten", who == [1, 1, 2, 2, 2], str(who))
check("Wort in einer Lücke: wie das zeitlich nächste", sprecher.assign([("a", 0.5), ("b", 2.4), ("c", 4.0)], _line, 0.1) == [1, 1, 2])
check("Wechsel rückt ans Satzende", sprecher._tidy("Wie geht es? Mir geht es gut.".split(), [1, 1, 1, 1, 2, 2, 2]) == [1, 1, 1, 2, 2, 2, 2]
      and sprecher._tidy("Wie geht es? Mir geht es gut.".split(), [1, 1, 2, 2, 2, 2, 2]) == [1, 1, 1, 2, 2, 2, 2])
check("Einzelnes Wort mitten im Satz ist kein Redebeitrag, ein eigener Satz schon",
      sprecher._tidy("Guten Morgen, Frau Bergmann. Ja. Bitte".split(), [1, 2, 1, 1, 2, 1]) == [1, 1, 1, 1, 2, 1])
talk = sprecher.dialogue(["Guten Tag.", "Hallo. Ja.", "Wie geht es?", "Gut."], [1, 2, 1, 2])
check("Gesprächstext", talk == "Sprecher 1: Guten Tag.\n\nSprecher 2: Hallo. Ja.\n\nSprecher 1: Wie geht es?\n\nSprecher 2: Gut.", talk)
check("Eine Stimme: keine Sprecherzeilen", sprecher.dialogue(["a", "b"], [1, 1]) == "")
check("Segmentierungsmodell liegt der App bei", sprecher.SEGMENTER.exists())
if sprecher.ready():
    import wave as _wave
    with _wave.open(str(pathlib.Path(__file__).with_name("test_de.wav"))) as _w:
        _a = np.frombuffer(_w.readframes(_w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    _t = sprecher.Turns()
    for _i in range(0, len(_a), 1600):
        _t.feed(_a[_i:_i + 1600])
    _lab, _step = _t.finish()
    check("Ein Sprecher im Testdiktat: genau eine Stimme, Sprache erkannt",
          _t.speakers == 1 and (_lab > 0).mean() > 0.5, f"{_t.speakers} Sprecher, {(_lab > 0).mean():.0%} Sprache")

# ----- Fachkorrektur
ok = [("Set", "Stent"), ("Riba", "RIVA"), ("Trossiba", "Tresiba"), ("Prägensolom", "Prednisolon"), ("Retroximab", "Rituximab")]
no = [("Monaten", "Monate"), ("Lunge", "Zunge"), ("Kabel", "Tisch"), ("Bisoprolol", "Metoprolol"), ("Tablette", "50 mg"),
      ("Patient", "Patientin ist wach und orientiert"), ("Erdjobschema", "ERGO-Schema"), ("Hydralacin", "Hydrochlorothiazid"), ("gürtelförmiger", "keilförmiger"), ("Oberbauchschmerz", "Obere Bauchschmerz")]
check("Fachkorrektur ist ab Werk aus", not korrektor.enabled(dict(config.DEFAULTS))
      and korrektor.enabled(dict(config.DEFAULTS, llm_fix=True, llm={"model": "m", "base_url": "http://localhost:1/v1"})))
check("Türsteher lässt Hörfehler durch", all(korrektor.accept(h, p) for h, p in ok), str([x for x in ok if not korrektor.accept(*x)]))
check("Türsteher hält Umformulierungen auf", not any(korrektor.accept(h, p) for h, p in no), str([x for x in no if korrektor.accept(*x)]))
text, done = korrektor.correct("Zustand nach Set-Implantation, Patient stabil.", {},
                               lambda s, u: json.dumps({"Set": "Stent", "stabil": "instabil", "Patient": "Patientin"}))
check("Korrektur übernimmt nur Geprüftes", text == "Zustand nach Stent-Implantation, Patient stabil." and done == [("Set", "Stent")], text)
text, done = korrektor.correct("Unverändert.", {}, lambda s, u: "kein JSON")
check("Kaputte Antwort ändert nichts", text == "Unverändert." and not done)

# ----- Mikrofon offen halten
class _Stream:
    def __init__(self, **kw):
        self.kw, self.open = kw, False

    def start(self):
        self.open = True

    def stop(self):
        self.open = False

    def close(self):
        pass


opened = []
engine.sd.InputStream = lambda **kw: opened.append(_Stream(**kw)) or opened[-1]
_real_device_index = engine._device_index
engine._device_index = lambda name: None
rec = engine.Recorder()
block = np.ones((1600, 1), dtype=np.float32)           # 0,1 s
rec.set_warm(True)
for _ in range(10):
    rec._callback(block * 0.5, 1600, None, None)       # eine Sekunde vor dem Tastendruck
rec.start()
for _ in range(5):
    rec._callback(block, 1600, None, None)
audio = rec.stop()
check("Offenes Mikrofon: Viertelsekunde Vorlauf, kein neuer Stream", len(opened) == 1 and opened[0].open
      and 0.5 + 0.25 <= len(audio) / 16000 <= 0.5 + 0.4 and audio[0] == 0.5 and audio[-1] == 1.0, f"{len(audio) / 16000:.2f} s")
rec.set_warm(False)
check("Ausgeschaltet: Mikrofon ist zu", not opened[0].open)
rec.start()
rec._callback(block, 1600, None, None)
audio = rec.stop()
check("Ohne Dauerbetrieb: öffnen, aufnehmen, schließen", len(opened) == 2 and not opened[1].open and len(audio) == 1600)

# ----- Modellordner
with tempfile.TemporaryDirectory() as tmp:
    old = config.DIR
    config.DIR = pathlib.Path(tmp)
    path = modelle.folder() / modelle._name("a/b", "0123456789abcdef")
    path.mkdir(parents=True)
    check("Unvollständiger Download zählt nicht", modelle.find("a/b", "0123456789abcdef", ["*"]) is None)
    (path / modelle._mark(["*"])).write_text("x")
    check("Geladenes Modell wird ohne Netz gefunden", modelle.find("a/b", "0123456789abcdef", ["*"]) == str(path))
    # Modell aus einem Release: Prüfsumme, Fortsetzen, kein zweiter Download
    import hashlib
    src = pathlib.Path(tmp) / "quelle"
    src.mkdir()
    (src / "a.bin").write_bytes(b"x" * 300000)
    (src / "b.txt").write_bytes(b"hallo")
    rel = {"name": "test-1", "url": src.as_uri() + "/",
           "files": {n: [(src / n).stat().st_size, hashlib.sha256((src / n).read_bytes()).hexdigest()] for n in ("a.bin", "b.txt")}}
    steps = []
    got = modelle.fetch_release(rel, lambda a, b: steps.append((a, b)))
    check("Release-Modell geladen und geprüft", (pathlib.Path(got) / "a.bin").stat().st_size == 300000
          and steps and steps[-1] == (300005, 300005), str(steps[-2:]))
    steps.clear()
    check("Release-Modell wird nicht doppelt geladen", modelle.fetch_release(rel, lambda a, b: steps.append(a)) == got and not steps)
    bad = dict(rel, name="test-2", files=dict(rel["files"], **{"b.txt": [5, "0" * 64]}))
    try:
        modelle.fetch_release(bad)
        check("Beschädigte Datei wird verworfen", False)
    except RuntimeError:
        check("Beschädigte Datei wird verworfen", modelle.find_release(bad) is None
              and not (modelle.folder() / "test-2" / "b.txt").exists())
    config.DIR = old

# ---- 0.9.4: Tonqualität, virtuelles Standardmikrofon, weite Lautsuche, c/k/z ----
from diktat import fach
check("Stumme Aufnahme wird erkannt", engine.audio_note(np.zeros(16000, dtype=np.float32)) == "stumm")
check("Leise Aufnahme wird erkannt", engine.audio_note(np.full(16000, 0.005, dtype=np.float32)) == "leise")
loud = np.sin(np.arange(16000) / 5).astype(np.float32) * 3
check("Übersteuerte Aufnahme wird erkannt", engine.audio_note(np.clip(loud, -1, 1)) == "laut")
check("Normale Aufnahme bleibt ohne Hinweis", engine.audio_note(np.sin(np.arange(16000) / 5).astype(np.float32) * 0.3) == "")
_devs = [{"name": "Microsoft Soundmapper - Input", "max_input_channels": 2, "hostapi": 0},
         {"name": "Line 1 (Virtual Audio Cable)", "max_input_channels": 2, "hostapi": 0},
         {"name": "Mikrofon (USB Microphone)", "max_input_channels": 1, "hostapi": 0}]
_sd = engine.sd
_keep = (getattr(_sd, "query_devices", None), getattr(_sd, "default", None))
_sd.default = type("D", (), {"hostapi": 0})()
_sd.query_devices = lambda *a, kind=None, **k: _devs[1] if kind == "input" else _devs
check("Virtuelles Standardmikrofon wird übersprungen", _real_device_index(None) == 2, str(_real_device_index(None)))
check("Gewähltes Mikrofon gilt weiter", _real_device_index("Line 1 (Virtual Audio Cable)") == 1)
_sd.query_devices = lambda *a, kind=None, **k: _devs[2] if kind == "input" else _devs
check("Echtes Standardmikrofon bleibt Standard", _real_device_index(None) is None)
_sd.query_devices, _sd.default = _keep
for heard, want in [("Coronare", "Koronare"), ("exacerbierte", "exazerbierte"), ("Hydralacin", "Hydralazin"),
                    ("Lymphardenopathie", "Lymphadenopathie"), ("Lungfunktion", "Lungenfunktion"),
                    ("inhaltiger", "inhalativer"), ("Pempolyzomap", "Pembrolizumab"), ("Retroximab", "Rituximab"),
                    ("Chiprofloxacin", "Ciprofloxacin"), ("Kandesartan", "Candesartan"), ("viseralen", "viszeralen")]:
    got = fach.correct("Befund: " + heard + " heute.")
    check(f"{heard} -> {want}", want in got, got)
for word in ["Hautturgor", "Mundspatel", "Wiedervorstellung", "Stauungsbedingt", "Pulmonalvenösen", "Organomegalie",
             "Processus", "Carcinom", "Frakturspalt", "Beatmungsschwierigkeiten"]:
    got = fach.correct("Befund: " + word + " heute.")
    check(f"{word} bleibt", word in got, got)

# ---- Vorgelesene Sätze aufheben (freiwillig, ab Werk aus) ----
with tempfile.TemporaryDirectory() as tmp:
    old = config.DIR
    config.DIR = pathlib.Path(tmp)
    check("Ohne Aufnahmen ist der Zähler null", training.kept() == (0, 0.0))
    path = training.keep(np.sin(np.arange(32000) / 9).astype(np.float32) * 0.4, "Der Patient ist kardiopulmonal stabil.")
    training.keep(np.zeros(16000, dtype=np.float32), "Zweiter Satz.")
    rows = [json.loads(l) for l in open(training.store() / "index.jsonl", encoding="utf-8")]
    check("Verzeichnis nennt Datei, Satz und Dauer", rows[0]["text"] == "Der Patient ist kardiopulmonal stabil." and rows[0]["sec"] == 2.0
          and rows[0]["audio"] == path.name, str(rows[0]))
    check("Zähler stimmt", training.kept() == (2, 3.0), str(training.kept()))
    check("Löschen entfernt alles", training.clear() == 2 and training.kept() == (0, 0.0) and not list(training.store().glob("*")))
    check("Aufheben ist ab Werk aus", config.DEFAULTS.get("training_keep") is False)
    config.DIR = old
# Aus Aufnahme mit Transkript lernen: Ton wird nur gelesen
with tempfile.TemporaryDirectory() as tmp:
    import wave as _wave
    wav = pathlib.Path(tmp) / "befund.wav"
    w = _wave.open(str(wav), "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(np.zeros(16000, dtype="<i2").tobytes()); w.close()
    check("Ohne Textdatei kein Partner", training.partner(wav) is None)
    wav.with_suffix(".txt").write_text("Der Patient erhält Trossiba nicht, sondern Tresiba bei Bronchiektasie.", encoding="utf-8")
    check("Transkript mit gleichem Namen wird gefunden", training.partner(wav) == wav.with_suffix(".txt"))
    class _T:
        def transcribe(self, audio):
            return "Der Patient erhält Trossiba nicht, sondern Tressiba bei Bronchiektasie."
    _c = {"dictionary": {}, "learned": [], "learn_terms": False, "base_dictionary": False}
    before = sorted(p.name for p in pathlib.Path(tmp).iterdir())
    ok, new, words = training.from_recording(_T(), _c, wav, wav.with_suffix(".txt").read_text(encoding="utf-8"))
    check("Lernt Verhörer und Fachwörter aus Aufnahme und Transkript",
          ok and ("Tressiba", "Tresiba") in new and _c["dictionary"].get("Tressiba") == "Tresiba" and words >= 1
          and "Bronchiektasie" in _c["learned"], str((ok, new, words, _c)))
    check("Dabei wird nichts gespeichert", sorted(p.name for p in pathlib.Path(tmp).iterdir()) == before)
    ok, new, words = training.from_recording(_T(), _c, wav, "Ein ganz anderer Text über das Wetter von morgen früh.")
    check("Passt das Transkript nicht zur Aufnahme, wird nichts gelernt", not ok and not new and not words)

# ---- 0.9.7: kurze Namen aus der Kernliste, zerlegte Begriffe, Schreibweisen ----
for heard, want in [("Trimbo", "Trimbow"), ("Trossiba", "Tresiba"), ("Nabik", "Nabic"), ("Sdemi", "STEMI"),
                    ("Metoprololsoxinat", "Metoprololsuccinat"), ("Settimplantation", "Stentimplantation"),
                    ("Sevilla mehr", "Sevelamer"), ("Dosier Aerosol", "Dosieraerosol"), ("Pleurer Gauss", "Pleuraerguss"),
                    ("Semitendinosus Szene", "Semitendinosussehne")]:
    got = fach.correct("Befund: " + heard + " heute.")
    check(f"{heard} -> {want}", want in got, got)
for text in ["Der Patient kommt aus Sevilla.", "Herr Meyer und Frau Bergmann.", "Hallo Kowalski, bitte Kalium geben.",
             "Wir sehen mehr davon.", "Trimbow und Tresiba wie bisher."]:
    check(f"bleibt: {text}", fach.correct(text) == text, fach.correct(text))
check("30er-Regel", engine.tidy("Actrapid nach Dreißiger Regel") == "Actrapid nach 30er-Regel")
check("Grad Celsius ergänzt", engine.tidy("38 Grad Celsi Fieber, 37 Grad Celsius") == "38 Grad Celsius Fieber, 37 Grad Celsius")

# ---- 0.9.9: Sprungmarken ----
from diktat import felder
f = felder.Fields()
check("Text ohne Marken: nichts zu springen", f.pasted("Kein Feld hier. ") == 0 and f.next() is None)
t = "Anamnese: [ ]\nBefund: [Befund]\nEnde"
check("Marken werden gefunden", f.pasted(t) == 2 and f.active())
doc, caret = t, len(t)
def play(step, typed=""):
    global doc, caret
    move, n = step
    caret += move
    doc = doc[:caret] + typed + doc[caret + n:]
    caret += len(typed)
play(f.next(), "Husten seit drei Tagen")
f.pasted("Husten seit drei Tagen")           # das Diktat ins Feld beendet die Runde nicht
play(f.next(), "unauffällig")
check("Felder werden nacheinander gefüllt", doc == "Anamnese: Husten seit drei Tagen\nBefund: unauffällig\nEnde", doc)
check("Danach ist keine Marke mehr offen", f.next() is None)
f.pasted("A [ ] B [ ] ")
play_doc = "A [ ] B [ ] "
doc, caret = play_doc, len(play_doc)
play(f.next()); play(f.next())
check("Überspringen ohne Eingabe stimmt auch", doc == "A  B  ", repr(doc))

# ---- 0.10.0: Schutz vor dem Versand, diktierte Satzzeichen, Türsteher für große Modelle, Anbieter ----
from diktat import schutz, llm
m = schutz.Mask(model=False)
src = ("Herr Meier, geboren am 12.03.1957, wohnhaft Hauptstraße 12, 51373 Leverkusen. Frau Dr. Schmidt-Kowalski hat angerufen, "
       "Telefon 0214 131234, Mail anna.schmidt@praxis.de, Fallnummer 20261234567. Patientin Müller klagt über Dyspnoe. "
       "Morbus Parkinson bekannt. Pantoprazol 40 mg 1-0-0, RR 140/90, Limitierung 0-0-90 Grad, Epoetin 4000 IE, Fieber 38,7.")
hidden = m.hide(src)
for secret in ["Meier", "12.03.1957", "Hauptstraße", "Leverkusen", "Schmidt", "131234", "anna.schmidt", "20261234567", "Müller"]:
    check(f"Schutz: {secret} verlässt den Rechner nicht", secret not in hidden, hidden)
for keep in ["Parkinson", "Pantoprazol 40 mg 1-0-0", "RR 140/90", "0-0-90 Grad", "4000 IE", "38,7", "Dyspnoe"]:
    check(f"Schutz: {keep} bleibt lesbar", keep in hidden, hidden)
check("Schutz: Antwort wird zurückübersetzt", m.show(hidden) == src)
check("Schutz: derselbe Name bekommt denselben Platzhalter", schutz.Mask(model=False).hide("Herr Meier und Frau Meier").count("[NAME_1]") == 2)
check("Schutz gilt für fremde Server, nicht für den eigenen Rechner",
      schutz.needed({"base_url": "https://openrouter.ai/api/v1"}) and not schutz.needed({"base_url": "http://localhost:11434/v1"})
      and not schutz.needed({"base_url": "https://openrouter.ai/api/v1", "protect": False}))
_ready, schutz.ready = schutz.ready, lambda: False
check("Ohne Namenserkennung geht nichts an fremde Server",
      schutz.blocked({"base_url": "https://openrouter.ai/api/v1"}) and not schutz.blocked({"base_url": "http://localhost:11434/v1"})
      and not schutz.blocked({"base_url": "https://openrouter.ai/api/v1", "protect": False}))
try:
    llm.run({"base_url": "https://openrouter.ai/api/v1", "model": "m"}, "Glätten", "Herr Meier kam.")
    check("Ohne Namenserkennung: Nachbearbeitung sendet nicht", False)
except llm.LlmError as e:
    check("Ohne Namenserkennung: Nachbearbeitung sendet nicht", "nichts gesendet" in str(e))
check("Ohne Namenserkennung: Fachkorrektur lässt den Text unverändert und sendet nicht",
      korrektor.correct("Herr Meier hat Hahnstau.", {"base_url": "https://openrouter.ai/api/v1", "model": "m"}) == ("Herr Meier hat Hahnstau.", []))
schutz.ready = lambda: True          # ab hier wie mit geladenem Modell; die Tests unten rechnen nur mit Regeln (Mask(model=False))
check("Name aus mehreren Wörtern hinter der Anrede wird ganz ersetzt",
      "Demirci" not in schutz.Mask(model=False).hide("Frau Aylin Demirci kam heute.") and "Lindqvist" not in schutz.Mask(model=False).hide("Hausarzt ist Dr. med. Petra Lindqvist."))
sent = {}
def fake(system, user):
    sent["text"] = user
    return '{"Kabel": "Cave", "Meier": "Maier", "Hahnstau": "Harnstau"}'
old_chat, llm.chat = llm.chat, lambda cfg, system, user, json_mode=False, key=None: fake(system, user)
fixed, done = korrektor.correct("Herr Meier hat Hahnstau. Kabel Nierenfunktion.", {"base_url": "https://openrouter.ai/api/v1", "model": "m"})
llm.chat = old_chat
check("Fachkorrektur schickt die geschützte Fassung", "Meier" not in sent["text"] and "[NAME_1]" in sent["text"], sent["text"])
check("Fachkorrektur ersetzt im Original und lässt Namen in Ruhe", fixed == "Herr Meier hat Harnstau. Cave Nierenfunktion.", fixed)

signs = engine.spoken("Operationsbericht neuer Absatz, Eingriff, Doppelpunkt Kraniotomie, neue Zeile, Operateur Doppelpunkt, Doktor Williams, "
                      "neuer Absatz. Kein Schwindelpunkt Fieber verneint, Komma, Husten auch Punkt der wichtigste Punkt ist der Zeitpunkt Punkt "
                      "Wert 3 Komma 5 Klammer auf links Klammer zu")
check("Diktierte Satzzeichen", signs == "Operationsbericht.\n\nEingriff: Kraniotomie.\nOperateur: Doktor Williams.\n\nKein Schwindel. Fieber verneint, "
      "Husten auch. Der wichtigste Punkt ist der Zeitpunkt. Wert 3,5 (links)", repr(signs))
check("Satzzeichen sind ab Werk aus", "Punkt" in engine.postprocess("Befund unauffällig Punkt", dict(config.DEFAULTS)))
check("Satzzeichen eingeschaltet", engine.postprocess("Befund unauffällig Punkt", dict(config.DEFAULTS, spoken_punctuation=True)).strip() == "Befund unauffällig.")

yes = [("Hahnstau", "Harnstau"), ("neumonischen", "pneumonischen"), ("perkotanes", "perkutanes"), ("Atem Note", "Atemnot"),
       ("und dann sind Tron", "Ondansetron"), ("Kabel", "Cave"), ("Lisenophril", "Lisinopril"), ("Belastungsdisplühl", "Belastungsdyspnoe")]
nope = [("Plumpe", "Pumpe"), ("Maria", "Mund"), ("Zuschauer", "Zuweisung"), ("Nabic", "Natriumbicarbonat"), ("Folgeschaden", "Folgeschäden"),
        ("paragelaufen", "paravasal gelaufen"), ("verätzt", "reseziert"), ("Wimmer", "Termin")]
check("Türsteher für große Modelle lässt Hörfehler durch", all(korrektor.accept(h, p) for h, p in yes), str([x for x in yes if not korrektor.accept(*x)]))
check("Türsteher für große Modelle hält Umdeutungen auf", not any(korrektor.accept(h, p) for h, p in nope), str([x for x in nope if korrektor.accept(*x)]))
long_text = "Der Befund ist unauffällig. " * 80
check("Lange Texte gehen in Stücken an das Sprachmodell", len(korrektor._pieces(long_text)) >= 3 and "".join(korrektor._pieces(long_text)) == long_text)
out = korrektor.correct("Kabel Nierenfunktion beachten, der Tisch bleibt.", {}, lambda s, u: '{"Kabel": "Cave", "Tisch": "Fisch"}', memory=[["Tisch", "Fisch"]])
check("Eigene Berichtigungen gelten ohne Türsteher", out[0] == "Cave Nierenfunktion beachten, der Fisch bleibt.", str(out))
check("Schlüssel je Anbieter getrennt", llm._account("IONOS") == "llm_api_key:IONOS" and llm._account() == "llm_api_key")
# ---- 0.10.1: Zielfenster ----
check("Zielfenster hat eine eigene Taste", config.DEFAULTS.get("hotkey_target") == ["shift", "f9"])
# ---- 0.11.0: Handy als Mikrofon ----
import ssl as _ssl
import tempfile as _tf
import urllib.request as _rq
from diktat import handy
got = []
srv = handy.Server(lambda audio: got.append(audio) or "", "geheim123", 0, pathlib.Path(_tf.mkdtemp()))
srv.port = 48765
srv.start()
ctx = _ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = _ssl.CERT_NONE
def _call(path, data=None):
    try:
        with _rq.urlopen(_rq.Request("https://127.0.0.1:48765" + path, data=data), context=ctx, timeout=10) as r:
            return r.status, r.read()
    except Exception as e:
        return getattr(e, "code", 0), b""
tone = (np.sin(np.arange(16000) / 10) * 12000).astype("<i2").tobytes()
check("Handy: Seite nur mit dem Kürzel aus dem QR-Code", _call("/")[0] == 403 and _call("/?k=falsch")[0] == 403 and b"Aufnehmen" in _call("/?k=geheim123")[1])
check("Handy: Ton ohne Kürzel wird abgewiesen", _call("/audio?k=x", tone)[0] == 403 and not got)
code, body = _call("/audio?k=geheim123", tone)
check("Handy: Ton kommt als Diktat an", code == 200 and json.loads(body)["ok"] and len(got) == 1 and len(got[0]) == 16000 and abs(float(got[0].max()) - 12000 / 32768) < 0.01, str((code, body)))
check("Handy: QR-Code ist ein PNG mit der Adresse", handy.qr_png(srv.url())[:4] == b"\x89PNG" and srv.url().endswith(":48765/?k=geheim123"))
srv.stop()
# ---- 0.12.0: Dekodieren mit Wortschatz ----
from diktat import beam, wortschatz
_v = {0: " Lis", 1: "ino", 2: "pril", 3: " und", 4: "eno", 5: "phril", 6: "s", 7: ","}
_b = beam.Bias(_v, ["Lisinopril"], 2.0)
def _bonus(seq):
    st, total = _b.start, 0.0
    for tok in seq:
        st, d = _b.step(st, tok)
        total += d
    return total + _b.close(st)
check("Wortschatz: ganzer Begriff behält den Bonus", _bonus([0, 1, 2, 3]) == 6.0 and _bonus([0, 1, 2, 7]) == 6.0)
check("Wortschatz: wird kein Begriff daraus, bleibt nichts", _bonus([0, 4, 5, 3]) == 0.0 and _bonus([0, 1, 3]) == 0.0)
check("Wortschatz: gebeugte Form zählt wie der Begriff, nicht mehr", _bonus([0, 1, 2, 6, 3]) == 6.0)
_cfg = {"learned": []}
_n = wortschatz.grow(_cfg, "Herr Mustermann: Diagnose Bronchiektasie, Therapie besprochen.")
check("Wortschatz: lernt Fachwörter aus dem Lexikon, keine Namen",
      _n >= 2 and "Diagnose" in _cfg["learned"] and "Mustermann" not in _cfg["learned"], str(_cfg))
check("Wortschatz: nichts doppelt, abschaltbar", wortschatz.grow(_cfg, "Diagnose") == 0
      and wortschatz.grow({"learn_terms": False, "learned": []}, "Diagnose") == 0)
_f = pathlib.Path(_tf.mkdtemp()) / "brief.txt"
_f.write_text("Diagnose: Glomerulonephritis. Therapie mit Prednisolon.", encoding="utf-8")
_c2 = {"learned": [], "learn_terms": False}
_r = wortschatz.learn_files(_c2, [_f, _f.with_name("fehlt.txt")])
check("Wortschatz: liest eigene Texte ein", _r == (len(_c2["learned"]), ["fehlt.txt"]) and "Diagnose" in _c2["learned"],
      str((_r, _c2)))
check("Wortschatz: Kernliste und eigene Begriffe zählen mit",
      {"Kreatinin", "Trimbow", "Prednisolon"} <= set(wortschatz.terms({"vocabulary": ["Trimbow"], "learned": ["Prednisolon"]})))
check("Wortschatz: ab Werk an", config.DEFAULTS.get("beam") == 8 and config.DEFAULTS.get("learn_terms") is True)
# ---- 0.14.0: Visite & Übergabe ----
from diktat import visite
_answer = 'Hier das Ergebnis:\n```json\n{"documentation": {"anamnese": "Sturz von [NAME_1].", "befund": "GCS 15", "procedere": ""}, "safetyAlerts": [{"context": "Antikoagulation", "suggestion": "cCT"}], "followUpQuestions": [{"question": "a"}, {"question": "b"}, {"question": "c"}, {"question": "d"},], "codes": []}\n```'
_r = visite.analyse({"llm": {"model": "x"}}, "Herr Müller ist gestürzt.", ask=lambda system, user: _answer)
check("Visite: liest JSON trotz Text, Code-Zaun und überzähligem Komma", _r["documentation"]["befund"] == "GCS 15", str(_r))
check("Visite: höchstens drei Rückfragen", len(_r["followUpQuestions"]) == 3)
check("Visite: Arztbrief nur aus gefüllten Abschnitten", visite.letter(_r) == "Anamnese:\nSturz von [NAME_1].\n\nBefund:\nGCS 15", visite.letter(_r))
try:
    visite.parse("Das kann ich nicht.")
    check("Visite: Antwort ohne JSON ist ein Fehler", False)
except llm.LlmError:
    check("Visite: Antwort ohne JSON ist ein Fehler", True)
_seen = {}
def _fake_chat(server, system, user, json_mode=False, key=None):
    _seen.update(system=system, user=user, timeout=server.get("timeout"))
    return '{"documentation": {"anamnese": "[NAME_1] gestürzt"}}'
_old_chat, llm.chat = llm.chat, _fake_chat
_r = visite.analyse({"llm": {"model": "x", "base_url": "https://beispiel.de/v1"}}, "Herr Müller, geboren am 03.04.1950, ist gestürzt.")
llm.chat = _old_chat
check("Visite: fremder Server sieht keine Namen und Daten", "Müller" not in _seen["user"] and "03.04.1950" not in _seen["user"], _seen.get("user", ""))
check("Visite: Namen stehen im Ergebnis wieder da", "Müller" in _r["documentation"]["anamnese"], str(_r))
check("Visite: lange Wartezeit und eigene Anweisung", _seen["timeout"] >= 120 and _seen["system"].startswith(visite.PROMPT[:40])
      and visite.prompt({"visite_prompt": "Eigene Anweisung"}) == "Eigene Anweisung")
# Visite: Jev-Ersteinschätzung und Wahl des Modells für den Arztbrief
from diktat import jev as _jev
_sent = {}
def _fake_jev(server, path, body):
    _sent.update(path=path, body=body, timeout=server.get("timeout"))
    return {"model": "typesafe/jev-test", "answers": {
        "placement": {"type": "choice", "choice": "emergency_department", "probabilities": {"emergency_department": 0.97, "urgent_care_practice": 0.03}},
        "specialty": {"type": "choice", "choice": "trauma_surgery", "probabilities": {"trauma_surgery": 0.6}},
        "lab_profile": {"type": "choice", "choice": "basis2", "probabilities": {"basis2": 0.7}},
        "ct_contrast": {"type": "choice", "choice": "without_contrast", "probabilities": {"without_contrast": 0.9}},
        "admission": {"type": "noul", "noul": 0.91}, "shock_red": {"type": "noul", "noul": 0.02},
        "shock_orange": {"type": "noul", "noul": 0.8}, "ecg": {"type": "noul", "noul": 0.95},
        "iv_access": {"type": "noul", "noul": 0.9}, "blood": {"type": "noul", "noul": 0.93},
        "monitoring": {"type": "noul", "noul": 0.4}, "img_ct": {"type": "noul", "noul": 0.98}}}
_or = {"llm": {"model": "klein", "base_url": "https://openrouter.ai/api/v1"}, "visite_rules": "Schockraum ORANGE bei SpO2 unter 90 %."}
_d = visite.triage(_or, "Sturz auf den Kopf unter Apixaban.", request=_fake_jev)
_v = _jev.view(_d)
check("Jev: eine Anfrage an /systemone mit Fall, Hausregeln und allen Fragen",
      _sent["path"] == "/systemone" and _sent["body"]["model"] == _jev.MODEL and "hausregeln" in _sent["body"]["state"]
      and "Apixaban" in _sent["body"]["state"]["fall"]["anonymisierte_eingabe"] and set(_sent["body"]["questions"]) == set(_jev.QUESTIONS)
      and _sent["body"]["questions"]["ecg"]["instructions"].endswith(_jev.RULE_HINT), str(_sent.get("path")))
check("Jev: Notaufnahme, Fallführung, Bett, Schockraum", _v["place"] == "Notaufnahme" and _v["specialty"].startswith("Unfallchirurgie")
      and _v["bed"] and _v["shock"] == ("ORANGE", 0.8), str(_v))
check("Jev: Maßnahmen mit Laborprofil und CT ohne Kontrastmittel", ("Labor", 0.93, "Basis 2") in _v["measures"]
      and ("CT", 0.98, "ohne KM") in _v["imaging"] and ("Monitoring", 0.4, "") in _v["measures"], str(_v["measures"]))
check("Jev: Text zum Kopieren", "Versorgungspfad: Notaufnahme (97 %)" in _jev.export(_d) and "Bett suchen in: Unfallchirurgie" in _jev.export(_d)
      and "12-Kanal-EKG: 95 %" in _jev.export(_d), _jev.export(_d))
_p = dict(_d, choice=dict(_d["choice"], placement={"choice": "urgent_care_practice", "p": 0.9}))
check("Jev: Notdienstpraxis braucht weder Abteilung noch Bett", _jev.view(_p)["place"].startswith("Notdienstpraxis")
      and not _jev.view(_p)["bed"] and not _jev.view(_p)["specialty"])
try:
    visite.triage({"llm": {"model": "x", "base_url": "http://localhost:11434/v1"}}, "Fall", request=_fake_jev)
    check("Jev: nur über OpenRouter", False)
except llm.LlmError:
    check("Jev: nur über OpenRouter", True)
try:
    _jev.ask(_or["llm"], "Fall", request=lambda *a: {"answers": {}})
    check("Jev: leere Antwort ist ein Fehler", False)
except llm.LlmError:
    check("Jev: leere Antwort ist ein Fehler", True)
check("Visite: Arztbrief bei OpenRouter mit Gemini 3.1 Pro, sonst mit dem LLM-Modell, eigene Angabe gewinnt",
      visite.writer(_or)["model"] == visite.WRITER and visite.writer({"llm": {"model": "llama", "base_url": "http://localhost:11434/v1"}})["model"] == "llama"
      and visite.writer(dict(_or, visite_model="mein/modell"))["model"] == "mein/modell" and visite.writer(_or)["timeout"] >= 180)
check("Visite: keine englische Zusammenfassung mehr in der Anweisung", "case_summary_en" not in visite.PROMPT and "ENGLISCH" not in visite.PROMPT)
# echte Wörter, die für einen Fachbegriff stehen: nur im klinischen Satz ersetzen
_base = dict(config.DEFAULTS)
check("Disney im klinischen Satz wird Dyspnoe", "mit Dyspnoe mit dem Rettungsdienst" in engine.postprocess(
      "95-jährige Patientin mit bekanntem Vorhofflimmern stellt sich vor mit Disney mit dem Rettungsdienst.", _base)
      and engine.postprocess("Keine Disney, kein Fieber.", _base).startswith("Keine Dyspnoe"))
check("Disney bleibt Disney, wo es gemeint ist", all("Dyspnoe" not in engine.postprocess(s, _base) for s in (
      "Wir waren am Wochenende im Disneyland.", "Die Kinder schauen Disney Plus.", "Disney hat gute Zahlen gemeldet.",
      "Die Patientin schaut gern Disney Filme.")))
with tempfile.TemporaryDirectory() as tmp:
    _s = visite.Store(pathlib.Path(tmp) / "v.sqlite")
    _id = _s.save(None, "Zimmer 4", "Sturz")
    _s.save(_id, "Zimmer 4", "Sturz, cCT", {"documentation": {"befund": "ok"}})
    _s.save(_id, "Zimmer 4a", "Sturz, cCT geplant")
    _s.rename(_id, " Zimmer 4a ")
    check("Visite: Fall bleibt mit Ergebnis gespeichert", _s.get(_id) == ("Zimmer 4a", "Sturz, cCT geplant", {"documentation": {"befund": "ok"}}), str(_s.get(_id)))
    check("Visite: Fallliste und Suche", len(_s.rows()) == 1 and len(_s.rows(query="cCT")) == 1 and not _s.rows(query="Lunge") and not _s.rows(True))
    check("Visite: endgültig löschen geht nur aus dem Papierkorb", _s.purge(_id) == 0 and len(_s.rows()) == 1)
    _s.trash(_id)
    check("Visite: Papierkorb", not _s.rows() and len(_s.rows(True)) == 1)
    _s.trash(_id, False)
    check("Visite: wiederherstellen", len(_s.rows()) == 1 and not _s.rows(True))
    _s.trash(_id)
    check("Visite: Papierkorb leeren", _s.purge() == 1 and _s.get(_id) is None)
    _s.db.close()
if sys.platform == "win32":
    # Tasten per Druck festlegen: der Haken meldet die Kombination, statt sie auszuwerten
    from diktat import winio as _w
    _hk = _w.Hotkey({"dictate": ["ctrl", "win"]}, "space", {}, *[lambda *a: _got.append("ausgelöst")] * 5)
    _got = []
    _hk.grab(_got.append)
    _dn, _up = _w.KEYDOWN[0], _w.KEYUP[0]
    _eat = [_hk._grab(_dn, 0xA2), _hk._grab(_dn, 0x5B), _hk._grab(_up, 0xA2)]
    check("Tasten: Kombination wird erst gemeldet, wenn alle Tasten los sind", _got == [] and all(_eat))
    _hk._grab(_up, 0x5B)
    check("Tasten: Strg + Win gemeldet, Umschalttasten zuerst, Lauschen beendet", _got == [["ctrl", "win"]] and _hk.capture is None, str(_got))
    _hk.grab(_got.append); _hk._grab(_dn, 0x76); _hk._grab(_dn, 0xA0); _hk._grab(_up, 0x76); _hk._grab(_up, 0xA0)
    check("Tasten: Umschalt + F7", _got[-1] == ["shift", "f7"], str(_got))
    _hk.grab(_got.append); _hk._grab(_dn, 0x1B)
    check("Tasten: Esc bricht ab", _got[-1] is None and _hk.capture is None)
    _hk.grab(_got.append); _hk._grab(_dn, 0x2E)
    check("Tasten: Entf leert", _got[-1] == [] and "ausgelöst" not in _got)
    check("Tasten: Anzeige und Rückweg", _w.parse_keys("Strg + Win") == ["ctrl", "win"] and _w.parse_keys("Umschalt + F7") == ["shift", "f7"]
          and _w.parse_keys("Leertaste") == ["space"])
    # Aktualisieren und Entfernen: mit einem nachgebauten Programmordner, ohne die App zu starten
    import time as _time
    import zipfile as _zip
    from diktat import pflege
    _base = pathlib.Path(tempfile.mkdtemp())
    _base = _base / "Oberärzte" / "Özel & Co"          # Umlaute, Leerzeichen und & im Pfad wie auf Kliniklaufwerken
    _prog = _base / "LocalScribe v2"
    (_prog / "modelle" / "m").mkdir(parents=True)
    (_prog / "modelle" / "stimme").mkdir()
    (_prog / "modelle" / "stimme" / "g").write_text("alt")
    (_prog / "modelle" / "m" / "gewichte").write_text("alt")
    (_prog / "LocalScribe.exe").write_text("alt")
    (_prog / "daten").mkdir()
    (_prog / "daten" / "config.json").write_text("{}")
    check("Pflege: Ordner ist änderbar", pflege.blocked(_prog) == "")
    _script = pflege.remove(_prog, False)
    for _ in range(100):
        if not _script.exists():
            break
        _time.sleep(0.2)
    check("Pflege: Entfernen löscht den Programmordner", not _prog.exists())
# Online-Update: nur geänderte Dateien kommen aus dem Paket, der Rest aus dem Programmordner
import os as _os
import zipfile as _zip2
from diktat import pflege as _pf
check("Update: 1.10.0 ist neuer als 1.9.3", _pf.number("v1.10.0") > _pf.number("1.9.3") and _pf.number("1.0.0") == (1, 0, 0))
_ub = pathlib.Path(tempfile.mkdtemp())
_have = _ub / "LocalScribe"
(_have / "_internal" / "qt").mkdir(parents=True)
_same = _os.urandom(300_000)
(_have / "_internal" / "qt" / "gross.dll").write_bytes(_same)
(_have / "_internal" / "weg.pyd").write_bytes(b"gibt es in der neuen Fassung nicht mehr")
(_have / "LocalScribe.exe").write_bytes(b"alt" * 1000)
(_have / "LIESMICH.txt").write_bytes(b"gleich")
_zipped = _ub / "paket.zip"
with _zip2.ZipFile(_zipped, "w", _zip2.ZIP_DEFLATED) as _z:
    _z.writestr("LocalScribe/LIESMICH.txt", b"gleich")
    _z.writestr("LocalScribe/_internal/qt/gross.dll", _same)
    _z.writestr("LocalScribe/LocalScribe.exe", b"neu" * 1000)
    _z.writestr("LocalScribe/_internal/dazu.dll", b"neue Datei")


class _Local(_pf.Remote):
    """Liest die Ausschnitte aus einer Datei statt aus dem Netz und zählt mit."""
    def hold(self, start, end):
        start, end = max(0, start), min(self.size, end)
        if start >= self.start and end <= self.start + len(self.data):
            return
        with open(self.url, "rb") as f:
            f.seek(start)
            self.start, self.data = start, f.read(end - start)
        self.loaded += len(self.data)


from diktat import __version__ as _own, ort as _ort
_next = ".".join(str(n) for n in (_pf.number(_own)[0] + 1, 0, 0))
with _zip2.ZipFile(_zipped, "a", _zip2.ZIP_DEFLATED) as _z:
    _z.writestr("LocalScribe/fassung.txt", _next)
    _z.writestr("LocalScribe/NEUES.txt", _pf.plain(f"## LocalScribe {_next}\n\n- **Neu.** Erster Punkt,\n  zweite Zeile.\n- Zweiter\n\n"
                                                    f"## LocalScribe {_own}\n\n- alt\n"))
    _z.writestr("LocalScribe/modelle/m/gewichte", b"gehoert nicht ins Update")
_src = _Local(str(_zipped), _zipped.stat().st_size)
check("Update: Änderungen aus dem Paket gelesen", _pf.remote_notes({"version": _next}, _Local(str(_zipped), _zipped.stat().st_size))
      == [(_next, "- Neu. Erster Punkt, zweite Zeile.\n- Zweiter")],
      _pf.remote_notes({"version": _next}, _Local(str(_zipped), _zipped.stat().st_size)))
_steps = []
check("Update: vorher zeigt nichts auf eine neue Fassung", _ort.chosen(_have, _own) is None)
_ver, _bytes, _count = _pf.fetch({}, _have, progress=lambda d, n: _steps.append((d, n)), source=_src, base=_have)
_built = _have / "fassungen" / _next
check("Update: neue Fassung vollständig im eigenen Ordner", _ver == _next and (_built / "LocalScribe.exe").read_bytes() == b"neu" * 1000
      and (_built / "_internal" / "qt" / "gross.dll").read_bytes() == _same
      and (_built / "_internal" / "dazu.dll").read_bytes() == b"neue Datei"
      and (_built / "LIESMICH.txt").read_bytes() == b"gleich" and not (_built / "_internal" / "weg.pyd").exists()
      and not (_built / "modelle").exists())
check("Update: nur die geänderten Dateien geladen", _count == 4 and _bytes < 6000, (_count, _bytes))
check("Update: Fortschritt endet bei 100 %", _steps and _steps[-1][0] == _steps[-1][1], _steps)
check("Update: laufende Fassung unberührt", (_have / "LocalScribe.exe").read_bytes() == b"alt" * 1000
      and (_have / "_internal" / "weg.pyd").exists())
check("Update: aktuell.txt zeigt auf die neue Fassung", _ort.chosen(_have, _own) == (_next, _built)
      and (_have / "aktuell.txt").read_text() == _next)
check("Update: Programmordner bleibt derselbe", _ort.root_of(_built) == _have and _ort.root_of(_have) == _have)
check("Update: noch einmal dasselbe lädt nichts", _pf.fetch({}, _have, source=_Local(str(_zipped), _zipped.stat().st_size), base=_have)[1:] == (0, 0))
# Zweite, neuere Fassung aus einer ZIP-Datei; die ältere verschwindet erst, wenn niemand mehr daraus arbeitet
_next2 = ".".join(str(n) for n in (_pf.number(_own)[0] + 1, 0, 1))
_zip3 = _ub / f"LocalScribe-{_next2}-windows.zip"
with _zip2.ZipFile(_zip3, "w") as _z:
    _z.writestr("LocalScribe/LocalScribe.exe", b"neuer")
    _z.writestr("LocalScribe/modelle/x", b"modell")
check("Update aus ZIP: Nummer aus dem Dateinamen, Modelle bleiben draußen", _pf.unpack(_zip3, _have) == _next2
      and (_have / "fassungen" / _next2 / "LocalScribe.exe").read_bytes() == b"neuer"
      and not (_have / "fassungen" / _next2 / "modelle").exists() and _ort.chosen(_have, _own)[0] == _next2)
(_have / "fassungen" / "halb").mkdir()
_busy = open(_built / "LocalScribe.exe", "rb") if sys.platform == "win32" else None
if _busy:
    check("Aufräumen: benutzte Fassung bleibt", _pf.tidy(_have) == [] and (_built / "LocalScribe.exe").exists())
    _busy.close()
check("Aufräumen: freie ältere Fassung verschwindet, aktuelle bleibt", _pf.tidy(_have) == [_next] and not _built.exists()
      and (_have / "fassungen" / _next2 / "LocalScribe.exe").exists() and (_have / "fassungen" / "halb").exists())
(_have / "aktuell.txt").write_text("Unsinn")
check("Update: unbrauchbare aktuell.txt heißt eigene Fassung", _ort.chosen(_have, _own) is None)
(_have / "aktuell.txt").write_text(_own)
check("Update: gleiche Nummer heißt eigene Fassung", _ort.chosen(_have, _own) is None)
try:
    _old = _ub / "LocalScribe-0.0.1-windows.zip"
    with _zip2.ZipFile(_old, "w") as _z:
        _z.writestr("LocalScribe/LocalScribe.exe", b"uralt")
    _pf.unpack(_old, _have)
    check("Update: ältere Fassung wird abgelehnt", False)
except RuntimeError:
    check("Update: ältere Fassung wird abgelehnt", not (_have / "fassungen" / "0.0.1").exists())
(_ub / "kaputt.zip").write_bytes(b"kein zip" * 100)
try:
    _pf.fetch({}, _have, source=_Local(str(_ub / "kaputt.zip"), 800), base=_have)
    check("Update: kaputtes Paket wird abgelehnt", False)
except RuntimeError:
    check("Update: kaputtes Paket wird abgelehnt", True)
try:
    _pf.unpack(pathlib.Path(__file__), _have)
    check("Update: falsche Datei wird abgelehnt", False)
except RuntimeError:
    check("Update: falsche Datei wird abgelehnt", True)
check("Was ist neu: Zeilenenden von Windows stören nicht", _pf.sections("LocalScribe 9.1.0\r\n\r\n- a\r\n  b\r\n- c\r\n\r\nLocalScribe 9.0.0\r\n\r\n- alt\r\n", "9.0.0")
      == [("9.1.0", "- a b\n- c")], _pf.sections("LocalScribe 9.1.0\r\n\r\n- a\r\n", "9.0.0"))
_n = _pf.notes()
check("Was ist neu: Änderungen der laufenden Fassung lesbar", _n and _n[0][0] == _own and "**" not in _n[0][1], [v for v, _ in _n[:1]])
# Modellordner: der eingestellte Ordner wird gefunden, ohne Netz
_shared = pathlib.Path(tempfile.mkdtemp())
(_shared / "fremd--modell--abcdefabcdef").mkdir()
(_shared / "fremd--modell--abcdefabcdef" / modelle._mark(["x.onnx"])).write_text("")
modelle.extra = str(_shared)
check("Modellordner aus den Einstellungen wird durchsucht",
      modelle.find("fremd/modell", "abcdefabcdef0000", ["x.onnx"]) == str(_shared / "fremd--modell--abcdefabcdef"))
modelle.extra = ""
# ---- 1.3.0: Einstellungen sichern und zurückholen, neue Aufträge (in einem eigenen Ordner, nie im echten) ----
_real = (config.DIR, config.FILE)
config.DIR = pathlib.Path(tempfile.mkdtemp(prefix="diktat_sich_"))
config.FILE = config.DIR / "config.json"
try:
    config.FILE.write_text(json.dumps({"config_version": 3, "hotkey_hold": ["ctrl", "win"], "vocabulary": ["RIVA"],
                                       "llm": {"model": "mein-modell"},
                                       "prompts": [{"name": "Arztbrief", "hotkey": [], "text": "mein eigener"}]}), encoding="utf-8")
    _c = config.load()
    _names = [p["name"] for p in _c["prompts"]]
    check("Aufträge: neue kommen einmal dazu, der eigene bleibt", _names == ["Arztbrief", "Zusammenfassung", "Meeting-Protokoll"]
          and _c["prompts"][0]["text"] == "mein eigener" and _c["config_version"] == 4, _names)
    _c["prompts"] = _c["prompts"][:1]
    config.save(_c)
    check("Aufträge: gelöschte kommen nicht wieder", [p["name"] for p in config.load()["prompts"]] == ["Arztbrief"])
    check("Aufträge: neue Installation hat alle sechs", len(config.DEFAULTS["prompts"]) == 6)
    _b = config.backup("vor-9.9.9")
    check("Sicherung: Kopie mit Inhalt im Datenordner", _b is not None and _b.parent == config.DIR / config.BACKUPS
          and json.loads(_b.read_text(encoding="utf-8"))["vocabulary"] == ["RIVA"])
    _out = config.DIR / "weg.json"
    config.export(_out)
    _c["vocabulary"] = []
    _c["llm"]["model"] = ""
    config.save(_c)
    _back = config.restore(_out)
    check("Zurückholen: Wortschatz und Server sind wieder da", _back["vocabulary"] == ["RIVA"] and _back["llm"]["model"] == "mein-modell"
          and json.loads(config.FILE.read_text(encoding="utf-8"))["vocabulary"] == ["RIVA"])
    check("Zurückholen: der Stand davor wurde gesichert",
          any(json.loads(f.read_text(encoding="utf-8"))["vocabulary"] == [] for f in (config.DIR / config.BACKUPS).glob("*.json")))
    for _bad in (pathlib.Path(__file__), _b.parent / "fehlt.json"):
        try:
            config.restore(_bad)
            check("Zurückholen: fremde Datei wird abgelehnt", False)
        except ValueError:
            check("Zurückholen: fremde Datei wird abgelehnt", json.loads(config.FILE.read_text(encoding="utf-8"))["vocabulary"] == ["RIVA"])
    (config.DIR / "kein.json").write_text('{"irgendwas": 1}', encoding="utf-8")
    try:
        config.restore(config.DIR / "kein.json")
        check("Zurückholen: JSON ohne Einstellungen wird abgelehnt", False)
    except ValueError:
        check("Zurückholen: JSON ohne Einstellungen wird abgelehnt", True)
    for _i in range(13):
        (config.DIR / config.BACKUPS / f"einstellungen-2000-01-{_i + 1:02d}-000000.json").write_text("{}", encoding="utf-8")
    config.backup("x")
    check("Sicherung: es bleiben zehn", len(list((config.DIR / config.BACKUPS).glob("*.json"))) == 10)
finally:
    config.DIR, config.FILE = _real
print("FEHLER:" if failed else "ALLES OK", failed or "")
sys.exit(1 if failed else 0)
