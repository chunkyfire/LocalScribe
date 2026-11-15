"""Eigene Diktate auswerten: Wortfehlerrate gegen den Solltext, für die App und für fremde Modellausgaben.

    python eigene.py <bench.json mit {"gt": {Name: Text}, "modelle": {Name: {Modell: Text}}}> <app.jsonl> [...]

Der Solltext ist geschrieben, das Diktat gesprochen; vor dem Vergleich wird beides angeglichen
(Z.n. = Zustand nach, mg/m² = mg pro Quadratmeter, Zahlwörter = Ziffern, Listennummern entfallen).
"""
import json
import pathlib
import re
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
from diktat import engine, fach

NUM = {"null": 0, "eins": 1, "ein": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8,
       "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12, "zwanzig": 20, "dreißig": 30, "vierzig": 40, "fünfzig": 50,
       "sechzig": 60, "siebzig": 70, "achtzig": 80, "neunzig": 90, "hundert": 100}
SUBS = [(r"(?m)^\s*\d+\.\s+", " "), (r"z\.\s?n\.", "zustand nach"), (r"\bi\.\s?v\.?", "iv"), (r"mg/m²", "mg pro quadratmeter"),
        (r"ml/min", "ml pro minute"), (r"%", " prozent "), (r"\bhf\b", "herzfrequenz"), (r"milligramm", "mg"), (r"milliliter", "ml"),
        (r"(\d)-(\d)-(\d+)", r"\1 \2 \3"), (r"(\d),(\d)", r"\1komma\2"), (r"\biii\b", "3"), (r"\bii\b", "2"), (r"spo\s?2", "spo2"),
        (r"-", " ")]


def norm(text):
    t = text.lower()
    for a, b in SUBS:
        t = re.sub(a, b, t)
    out = []
    for w in re.findall(r"[a-zäöüß0-9]+", t):
        m = re.fullmatch(r"(\w+?)und(zwanzig|dreißig|vierzig|fünfzig|sechzig|siebzig|achtzig|neunzig)", w)
        if m and m.group(1) in NUM:
            w = str(NUM[m.group(1)] + NUM[m.group(2)])
        elif w in NUM and w != "ein":
            w = str(NUM[w])
        out.append(w)
    return out


def errors(ref, hyp):
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


bench = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
gt = {k: norm(v) for k, v in bench["gt"].items()}
table = {}
for name, models in bench["modelle"].items():
    for model, text in models.items():
        key = re.sub(r"\s*[\d,.]+\s*s$", "", model).strip()
        table.setdefault(key, {})[name] = errors(gt[name], norm(text))
for path in sys.argv[2:]:
    label = "LocalScribe " + pathlib.Path(path).stem
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        if r["name"] in gt:
            table.setdefault(label + " roh", {})[r["name"]] = errors(gt[r["name"]], norm(r["hyp"]))
            table.setdefault(label + " mit Nachbearbeitung", {})[r["name"]] = errors(gt[r["name"]], norm(fach.correct(engine.apply_base(r["hyp"]))))
names = list(gt)
total = sum(len(gt[n]) for n in names)
print(f"{'':52s}" + "".join(f"{n[:10]:>11s}" for n in names) + "     gesamt")
for model, row in sorted(table.items(), key=lambda kv: sum(kv[1].get(n, len(gt[n])) for n in names)):
    cells = "".join(f"{100 * row[n] / len(gt[n]):10.1f}%" if n in row else f"{'–':>11s}" for n in names)
    full = all(n in row for n in names)
    print(f"{model[:52]:52s}{cells}" + (f"{100 * sum(row.values()) / total:10.1f}%" if full else f"{'unvollst.':>11s}"))
