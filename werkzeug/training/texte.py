"""Erfundene Diktatsätze mit dichten Fachbegriffen erzeugen (für das Nachtraining mit künstlichen Stimmen).

    python texte.py <Ausgabe.jsonl> [Anzahl Stapel]

Je Stapel bekommt das Sprachmodell aus den Einstellungen ein Fachgebiet, eine Textsorte und 30 zufällige Begriffe
aus dem Fachlexikon und schreibt 40 Sätze. Keine Zahlen (das Erkennungsmodell schreibt Zahlen und Einheiten in
eigener Form, die das Training nicht verändern soll), keine Namen, keine Patientendaten.
"""
import json, pathlib, random, re, sys, threading
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
from diktat import config, llm

out, batches = pathlib.Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 80
cfg = dict(config.load()["llm"], timeout=90)
lex = json.load(open(pathlib.Path(config.__file__).with_name("fachlexikon.json"), encoding="utf-8"))
core = lex["kern"]; wide = [w for w in lex["begriffe"] if 7 <= len(w) <= 26 and w[0].isupper() and w.isalpha()]
areas = list(json.load(open(pathlib.Path(config.__file__).with_name("lesetexte.json"), encoding="utf-8")))
kinds = ["Arztbrief (Diagnosen, Epikrise, Empfehlung)", "Aufnahmebefund in der Notaufnahme", "Befund einer Bildgebung oder Funktionsdiagnostik",
         "Operations- oder Interventionsbericht", "Visite und Verlaufseintrag", "Übergabe an die Kollegin der nächsten Schicht",
         "Konsilanforderung und Konsilantwort", "Medikationsplan in Worten, ohne Dosiszahlen"]
SYSTEM = ("Du schreibst Übungssätze für ärztliche Diktate auf Deutsch. Antworte nur mit JSON: {\"saetze\": [\"...\", ...]}. Regeln: genau 40 Sätze; "
          "jeder Satz 8 bis 24 Wörter, so wie eine Ärztin oder ein Arzt in Deutschland wirklich diktiert, medizinisch stimmig; jeder Satz enthält "
          "mindestens einen der vorgegebenen Begriffe in korrekter Schreibweise, viele Sätze zwei oder drei Fachbegriffe; überhaupt keine Zahlen, "
          "weder als Ziffern noch als Zahlwörter, keine Dosierungen, keine Datumsangaben, keine Uhrzeiten; keine Personennamen, keine Orte; "
          "keine Abkürzungen mit Punkt, keine Klammern, keine Aufzählungszeichen; normale Rechtschreibung mit Satzzeichen; abwechslungsreicher Satzbau.")
BAD = re.compile(r"\d|\b(null|eins|zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|elf|zwölf|zwanzig|dreißig|vierzig|fünfzig|hundert|tausend)\b|[()\[\]/%]", re.I)
lock, seen, kept = threading.Lock(), set(), [0]

def batch(i):
    rnd = random.Random(1000 + i)
    area, kind = areas[i % len(areas)], kinds[(i // len(areas) + i) % len(kinds)]
    terms = rnd.sample(core, 12) + rnd.sample(wide, 18)
    try:
        answer = llm.chat(cfg, SYSTEM, f"Fachgebiet: {area}\nTextsorte: {kind}\nBegriffe: {', '.join(terms)}", json_mode=True)
        rows = json.loads(answer).get("saetze", [])
    except Exception as e:
        print("Stapel", i, "fehlgeschlagen:", str(e)[:120], flush=True)
        return
    with lock, open(out, "a", encoding="utf-8") as f:
        for s in rows:
            s = " ".join(str(s).split())
            if not 6 <= len(s.split()) <= 26 or BAD.search(s) or s.lower() in seen:
                continue
            seen.add(s.lower()); kept[0] += 1
            f.write(json.dumps({"text": s, "gebiet": area, "sorte": kind.split(" (")[0]}, ensure_ascii=False) + "\n")
    print("Stapel", i, area, "->", kept[0], "Sätze", flush=True)

out.write_text("", encoding="utf-8")
with ThreadPoolExecutor(4) as pool:
    list(pool.map(batch, range(batches)))
print("FERTIG", kept[0], "Sätze")
