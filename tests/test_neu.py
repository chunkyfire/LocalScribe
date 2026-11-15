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
print("FEHLER:" if failed else "ALLES OK", failed or "")
sys.exit(1 if failed else 0)
