"""Baut diktat/basiswoerterbuch.json: Fehlschreibung -> richtiger Fachbegriff.

    python bauen.py <Ordner mit begriffe.txt, alle_woerter.txt, gehoert.jsonl> <index.aff/.dic deutsch> <englisch>

Zwei Quellen für Fehlschreibungen:
  1. gehört:  was das Sprachmodell aus dem vorgelesenen Begriff tatsächlich gemacht hat (gehoert.jsonl)
  2. Regeln:  übliche Lautverwechslungen (ph/f, c/k/z, y/i, th/t, Doppelkonsonanten …)

Trennschärfe: Eine Fehlschreibung wird nur aufgenommen, wenn sie
  - kein Wort ist (Hunspell deutsch und englisch, Worthäufigkeitslisten in acht Sprachen),
  - kein anderer Fachbegriff und kein Wort aus einem Fachnamen ist,
  - nur zu genau einem Begriff passt und ihm ähnlich genug ist.
Braucht: pip install spylls wordfreq
"""
import collections
import difflib
import json
import pathlib
import re
import sys

from spylls.hunspell import Dictionary
from wordfreq import zipf_frequency

work = pathlib.Path(sys.argv[1])
HUN = [Dictionary.from_files(p) for p in sys.argv[2:4]]
OUT = pathlib.Path(__file__).resolve().parent.parent.parent / "diktat" / "basiswoerterbuch.json"
LANGS = ("de", "en", "fr", "es", "it", "nl", "pl", "tr")
CARRIER = {"im", "befund", "steht", "weil", "wichtig", "ist"}
WORD = re.compile(r"[A-Za-zÄÖÜäöüß]+")

terms = dict(line.split("\t") for line in (work / "begriffe.txt").read_text(encoding="utf-8").splitlines() if line)
lexicon = {t.lower() for t in terms} | {w.lower() for w in (work / "alle_woerter.txt").read_text(encoding="utf-8").split()}
_known = {}


def is_word(w: str) -> bool:
    """Gibt es diese Schreibweise? Dann darf sie nie ersetzt werden."""
    w = w.lower()
    if w not in _known:
        _known[w] = (w in lexicon or any(zipf_frequency(w, lang) > 0 for lang in LANGS)
                     or any(d.lookup(x) for d in HUN for x in (w, w.capitalize())))
    return _known[w]


def spelling(w):
    """c, k und z sind in der Fachsprache austauschbar (Karzinom/Carcinom, Zystitis/Cystitis)."""
    w = re.sub(r"c(?=[eiäy])", "z", w.replace(" ", ""))
    return re.sub(r"c(?!h)", "k", w)


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------- 1. gehört
def heard_variants():
    found = collections.defaultdict(set)
    path = work / "gehoert.jsonl"
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        term, text = row["t"], row["h"]
        if text.startswith("!"):
            continue
        low = term.lower()
        words = [w.lower() for w in WORD.findall(text)]
        need = 0.74 if len(low) >= 8 else 0.8
        for size in (1, 2):
            for i in range(len(words) - size + 1):
                window = words[i:i + size]
                if CARRIER & set(window):
                    continue
                cand = " ".join(window)
                if cand.replace(" ", "") == low and size == 2:
                    pass                                   # nur auseinandergeschrieben
                elif ratio(cand.replace(" ", ""), low) < need:
                    continue
                if cand == low:
                    continue
                joined = cand.replace(" ", "")
                if not 0.8 <= len(joined) / len(low) <= 1.25:
                    continue                               # abgeschnittene Wörter (Fibrat für Bezafibrat) sind eigene Wörter
                if size == 2 and joined != low and ratio(joined, low) < need + 0.06:
                    continue
                if size == 1 and is_word(cand):
                    continue
                if size == 2 and all(is_word(w) for w in window) and cand.replace(" ", "") != low:
                    continue                               # zwei echte Wörter: könnte so gemeint sein
                if size == 2 and any(len(w) < 3 for w in window):
                    continue
                found[cand].add(term)
    return found


# ---------------------------------------------------------------- 2. Regeln
VOWEL = "aeiouäöüy"
RULES = [  # (Muster, Ersatz)
    (r"ph", "f"), (r"th", "t"), (r"rh", "r"), (r"y", "i"), (r"y", "ü"), (r"x", "ks"), (r"qu", "kw"),
    (r"(?<=[aeiou])ck", "k"),
    (r"v", "w"), (r"v", "f"), (r"ie(?=[a-zäöü])", "i"), (r"ie$", "i"), (r"ae", "ä"), (r"oe", "ö"), (r"ä", "e"),
    (r"eu", "oi"), (r"ei", "ai"), (r"(?<=[aeiouäöü])s(?=[aeiouäöü])", "z"), (r"z(?=[aeiouäöüy])", "ts"),
    (r"ll", "l"), (r"mm", "m"), (r"nn", "n"), (r"ss", "s"), (r"tt", "t"), (r"pp", "p"), (r"rr", "r"), (r"ff", "f"),
    (rf"(?<=[{VOWEL}])l(?=[{VOWEL}])", "ll"), (rf"(?<=[{VOWEL}])t(?=[{VOWEL}])", "tt"),
    (rf"(?<=[{VOWEL}])n(?=[{VOWEL}])", "nn"), (rf"(?<=[{VOWEL}])m(?=[{VOWEL}])", "mm"),
    (r"ti(?=on)", "zi"), (r"ose$", "oze"), (r"ase$", "aze"), (r"in$", "ien"), (r"ol$", "ohl"), (r"an$", "ahn"),
    (r"oe$", "ö"), (r"oe$", "o"), (r"äe", "e"), (r"ämie$", "emie"), (r"itis$", "ietis"), (r"zy", "zü"),
]


def rule_variants(term):
    low = term.lower()
    out = set()
    if len(low) < 7:
        return out
    for pat, rep in RULES:
        hits = list(re.finditer(pat, low))
        for m in hits:                       # jede Stelle einzeln
            out.add(low[:m.start()] + rep + low[m.end():])
        if len(hits) > 1:                    # und alle Stellen zugleich
            out.add(re.sub(pat, rep, low))
    out.discard(low)
    return out


# ---------------------------------------------------------------- zusammenführen
heard = heard_variants()
variants = collections.defaultdict(set)      # Fehlschreibung -> Begriffe
source = {}
for v, ts in heard.items():
    variants[v] |= ts
    source[v] = "gehört"
for term, vs in json.loads((pathlib.Path(__file__).with_name("hand.json")).read_text(encoding="utf-8")).items():
    for v in vs:                                 # von Hand beobachtete Fehlschreibungen, gleiche Prüfung
        if not is_word(v):
            variants[v].add(term)
            source[v] = "Hand"
for term in terms:
    for v in rule_variants(term):
        if not is_word(v):
            variants[v].add(term)
            source.setdefault(v, "Regel")

result = collections.defaultdict(list)
stats = collections.Counter()
for v, ts in variants.items():
    if len(ts) != 1:
        stats["mehrdeutig"] += 1
        continue
    if v in lexicon:
        stats["ist Fachbegriff"] += 1
        continue
    if source[v] != "Hand" and len(v.replace(" ", "")) < 6:
        stats["zu kurz"] += 1                            # kurze Formen gleichen zu leicht Namen und Abkürzungen
        continue
    if spelling(v) == spelling(next(iter(ts)).lower()):
        stats["nur andere Schreibweise (c/k/z)"] += 1
        continue
    result[next(iter(ts))].append(v)
    stats[source[v]] += 1

OUT.write_text(json.dumps({t: sorted(vs) for t, vs in sorted(result.items())}, ensure_ascii=False, separators=(",", ":")),
               encoding="utf-8")
print(dict(stats), "| Begriffe mit Einträgen:", len(result), "| Datei:", OUT.stat().st_size // 1024, "KB")
