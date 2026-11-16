"""Med-Dictate (Corti) auswerten: Wortfehlerrate gegen das Wortlaut-Transkript und Trefferquote der Fachbegriffe.

    python corti_auswerten.py <corti_*.jsonl> [...]

Je Datei: Rohtext des Modells und Text nach der Nachbearbeitung der App. Enthält eine Zeile schon ein Feld
"vorher" (aus korrektur_cloud.py), gilt "hyp" als fertig korrigierter Text. Diktierte Satzzeichen stehen im
Soll als Wörter („Punkt“, „Komma“, „neuer Absatz“); beide Seiten werden gleich behandelt: Satzzeichen und diese
Befehlswörter entfallen, Zahlwörter werden Ziffern, Einheiten ausgeschrieben.
"""
import json
import pathlib
import re
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
from diktat import engine, fach

NUM = {"null": 0, "eins": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8,
       "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12, "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15, "sechzehn": 16,
       "siebzehn": 17, "achtzehn": 18, "neunzehn": 19, "zwanzig": 20, "dreißig": 30, "vierzig": 40, "fünfzig": 50,
       "sechzig": 60, "siebzig": 70, "achtzig": 80, "neunzig": 90, "hundert": 100}
TENS = "zwanzig|dreißig|vierzig|fünfzig|sechzig|siebzig|achtzig|neunzig"
SUBS = [(r"\bmg\b", "milligramm"), (r"\bml\b", "milliliter"), (r"\bcm\b", "zentimeter"), (r"\bmm\b", "millimeter"),
        (r"\bkg\b", "kilogramm"), (r"\bµg\b", "mikrogramm"), (r"%", " prozent "), (r"°", " grad "),
        (r"(\d),(\d)", r"\1 komma \2"), (r"(\d)\.(\d{3})\b", r"\1\2"), (r"z\.\s?n\.", "zustand nach"),
        (r"\bdr\.", "doktor"), (r"\bca\.", "circa"), (r"\bz\.\s?b\.", "zum beispiel"), (r"-", " ")]
COMMANDS = re.compile(r"\b(?:neuer absatz|neue zeile|doppelpunkt|punkt|komma|semikolon|fragezeichen|ausrufezeichen|"
                      r"klammer auf|klammer zu|bindestrich|schrägstrich|slash|anführungszeichen(?: auf| zu)?)\b")


ORD = {"ersten": 1, "erster": 1, "erste": 1, "dritten": 3, "dritter": 3, "dritte": 3, "siebten": 7, "siebter": 7, "siebte": 7,
       "achten": 8, "achter": 8, "achte": 8}


def number(w):
    """Deutsches Zahlwort (auch Ordnungszahl) als Zahl, sonst None: zweitausendsechsundzwanzig -> 2026."""
    if w in NUM:
        return NUM[w]
    if w in ("ein", "eine", "einen", "einem", "einer"):
        return None                                  # Artikel bleiben Wörter
    if w in ORD:
        return ORD[w]
    for end in ("sten", "ster", "stes", "ste", "ten", "ter", "tes", "te"):
        if w.endswith(end) and len(w) > len(end) + 3:
            n = number(w[:-len(end)])
            if n is not None:
                return n
    for unit, factor in (("tausend", 1000), ("hundert", 100)):
        if unit in w:
            left, right = w.split(unit, 1)
            a = 1 if left in ("", "ein") else number(left)
            b = 0 if right == "" else number(right[3:] if right.startswith("und") and factor == 1000 else right)
            return a * factor + b if a is not None and b is not None else None
    m = re.fullmatch(rf"(\w+?)und({TENS})", w)
    if m and m.group(1) in NUM or m and m.group(1) == "ein":
        return (1 if m.group(1) == "ein" else NUM[m.group(1)]) + NUM[m.group(2)]
    return None


def norm(text):
    t = text.lower()
    for a, b in SUBS:
        t = re.sub(a, b, t)
    t = COMMANDS.sub(" ", t)
    t = re.sub(r"(?<=[a-zäöüß])(?=\d)|(?<=\d)(?=[a-zäöüß])", " ", t)          # spo2 = spo 2, l4 = l 4
    out = []
    for w in re.findall(r"[a-zäöüß]+|\d+", t):
        n = number(w)
        out.append(str(n) if n is not None else w)
    return out


def errors(ref, hyp):
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def post(text):
    """Wie die App mit eingeschalteten diktierten Satzzeichen."""
    return engine.spoken(engine.tidy(fach.correct(engine.apply_base(engine.LEADING.sub("", text.strip())))))


def terms_hit(row, text):
    have = " ".join(norm(text))
    wanted = [" ".join(norm(t)) for t in row.get("begriffe") or []]
    wanted = [w for w in wanted if w]
    return sum(1 for w in wanted if w in have), len(wanted)


for path in sys.argv[1:]:
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    stages = {}
    for r in rows:
        ref = norm(r["ref"])
        variants = {"fertig": r["hyp"]} if "vorher" in r else {"roh": r["hyp"], "mit Nachbearbeitung": post(r["hyp"])}
        if "vorher" in r:
            variants = {"vor der Fachkorrektur": r["vorher"], "nach der Fachkorrektur": r["hyp"]}
        for name, text in variants.items():
            s = stages.setdefault(name, {"err": 0, "n": 0, "hit": 0, "terms": 0, "each": []})
            e = errors(ref, norm(text))
            h, n = terms_hit(r, text)
            s["err"] += e; s["n"] += len(ref); s["hit"] += h; s["terms"] += n
            s["each"].append(f"{100 * e / len(ref):.1f}")
    sec = sum(r.get("sec", 0) for r in rows)
    took = sum(r.get("s", 0) for r in rows)
    print(f"{pathlib.Path(path).name}: {len(rows)} Diktate, {sec / 60:.1f} min Ton" + (f", erkannt in {took:.0f} s" if took else ""))
    for name, s in stages.items():
        print(f"  {name:24s} WER {100 * s['err'] / s['n']:5.2f} %   Fachbegriffe {s['hit']}/{s['terms']} "
              f"({100 * s['hit'] / max(1, s['terms']):.1f} %)   je Diktat: {' '.join(s['each'])}")
