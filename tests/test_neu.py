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
rng = np.random.default_rng(1)
a, b = rng.normal(size=256), rng.normal(size=256)
voices = [v / np.linalg.norm(v) for v in (a + 0.3 * rng.normal(size=256), b + 0.3 * rng.normal(size=256),
                                          a + 0.3 * rng.normal(size=256), b + 0.3 * rng.normal(size=256))]
labels = sprecher.cluster([voices[0], voices[1], None, voices[2], voices[3]], [9, 9, 0.5, 9, 9])
check("Zwei Stimmen, kurzer Einwurf wird zugeschlagen", labels == [1, 2, 2, 1, 2], str(labels))
talk = sprecher.dialogue(["Guten Tag.", "Hallo.", "Ja.", "Wie geht es?", "Gut."], labels)
check("Gesprächstext", talk == "Sprecher 1: Guten Tag.\n\nSprecher 2: Hallo. Ja.\n\nSprecher 1: Wie geht es?\n\nSprecher 2: Gut.", talk)
check("Eine Stimme: keine Sprecherzeilen", sprecher.dialogue(["a", "b"], sprecher.cluster([voices[0], voices[2]], [9, 9])) == "")
solo = sprecher.cluster([voices[0], voices[2], voices[1]], [9, 9, 3])
check("Einzelne kurze Äußerung ist kein eigener Sprecher", solo == [1, 1, 1], str(solo))
tone = (0.1 * np.sin(2 * np.pi * 180 * np.arange(3 * 16000) / 16000)).astype(np.float32)
e = sprecher.embed(tone)
check("Stimmabdruck berechenbar", e is not None and abs(float(np.linalg.norm(e)) - 1) < 1e-3 and sprecher.embed(tone[:8000]) is None)

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

# ---- 0.9.5: Aufnahmen aus dem Stimmtraining aufheben ----
with tempfile.TemporaryDirectory() as tmp:
    old = config.DIR
    config.DIR = pathlib.Path(tmp)
    check("Ohne Aufnahmen ist der Zähler null", training.kept() == (0, 0.0))
    path = training.keep(np.sin(np.arange(32000) / 9).astype(np.float32) * 0.4, "Der Patient ist kardiopulmonal stabil.")
    training.keep(np.zeros(16000, dtype=np.float32), "Zweiter Satz.")
    import wave as _wave
    w = _wave.open(str(path))
    check("Aufnahme liegt als WAV mit 16 kHz vor", w.getframerate() == 16000 and w.getnframes() == 32000 and w.getnchannels() == 1)
    w.close()
    rows = [json.loads(l) for l in open(training.store() / "index.jsonl", encoding="utf-8")]
    check("Verzeichnis nennt Datei, Satz und Dauer", rows[0]["text"] == "Der Patient ist kardiopulmonal stabil." and rows[0]["sec"] == 2.0
          and rows[0]["audio"] == path.name, str(rows[0]))
    check("Zähler stimmt", training.kept() == (2, 3.0), str(training.kept()))
    check("Löschen entfernt alles", training.clear() == 2 and training.kept() == (0, 0.0) and not list(training.store().glob("*")))
    config.DIR = old

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
print("FEHLER:" if failed else "ALLES OK", failed or "")
sys.exit(1 if failed else 0)
