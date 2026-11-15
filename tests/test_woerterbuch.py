"""Medizinisches Basiswörterbuch: korrigiert Fehlschreibungen, lässt Richtiges in Ruhe."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from diktat import config, engine

failed = []


def check(name, ok, extra=""):
    print("OK  " if ok else "FAIL", name, extra)
    if not ok:
        failed.append(name)


base = engine.base_dictionary()
data = json.loads(engine.BASE_FILE.read_text(encoding="utf-8"))
check("Wörterbuch geladen", len(base) > 5000, f"({len(base)} Fehlschreibungen, {len(data)} Begriffe)")
right = {t.lower() for t in data}
check("Kein richtig geschriebener Begriff steht als Fehlschreibung drin", not (right & set(base)), str(sorted(right & set(base))[:5]))

cfg = dict(config.DEFAULTS, dictionary={}, snippets={}, commands={}, trailing_space=False)
fixed = engine.postprocess("Die Lipaase ist erhöht, das Kreatinin liegt bei 1,4 mg pro Dziliter. Wir geben Metoprollol und Apiksaban.", cfg)
check("Fehlschreibungen werden korrigiert",
      fixed == "Die Lipase ist erhöht, das Kreatinin liegt bei 1,4 mg pro Deziliter. Wir geben Metoprolol und Apixaban.", fixed)

normal = ("Der Patient stellt sich mit seit drei Tagen bestehenden Oberbauchschmerzen vor. Die Lipase ist deutlich erhöht. "
          "Wir beginnen mit Metoprolol, Ramipril und Apixaban, pausieren Metformin und kontrollieren Kreatinin und Kalium. "
          "Bei Verdacht auf Pankreatitis, Cholezystitis oder Pneumonie erfolgt eine Sonografie des Abdomens. "
          "Kannst du mir bis Freitag kurz Rückmeldung geben? Dann plane ich den Termin fest ein und schicke das Protokoll. "
          "Einkaufen: Brot, Kaffee, Tomaten, Zwiebeln und etwas für das Abendessen mit Familie Schmidt aus Köln-Lindenthal. "
          "The patient presents with abdominal pain. We will start intravenous fluids and repeat the blood tests tomorrow. "
          "Karzinom, Carcinom, Zystitis, Cystitis, Sonographie, Sonografie, Glukose, Glucose, Kalzium, Calcium.")
check("Richtig geschriebener Text bleibt unverändert", engine.postprocess(normal, cfg) == normal,
      str([a for a, b in zip(engine.postprocess(normal, cfg).split(), normal.split()) if a != b]))
sound = engine.postprocess("Tachükardie, Flegmone, Kolezüstitis, Hüpokaliämie, Glomerulonefritis, Rabdomüolüse und Nefrolithiasis.", cfg)
check("Fachbegriffe werden am Klang erkannt",
      sound == "Tachykardie, Phlegmone, Cholezystitis, Hypokaliämie, Glomerulonephritis, Rhabdomyolyse und Nephrolithiasis.", sound)
keep = "Pankreatitiden, Prozessus, Processus, Lied, Wahl, Mayer, Fischer, Organomegalie, Kolitis, Colitis."
check("Beugungsformen, Schreibvarianten und Alltagswörter bleiben", engine.postprocess(keep, cfg) == keep, engine.postprocess(keep, cfg))
check("Abschaltbar", engine.postprocess("Lipaase", dict(cfg, base_dictionary=False)) == "Lipaase")
check("Gilt nicht für das mehrsprachige Modell", engine.postprocess("Lipaase", dict(cfg, model_choice="multi")) == "Lipaase")
check("Eigenes Wörterbuch hat Vorrang", engine.postprocess("Lipaase", dict(cfg, dictionary={"Lipaase": "Lipase-Wert"})) == "Lipase-Wert")
print("FEHLER:" if failed else "ALLES OK", failed or "")
sys.exit(1 if failed else 0)
