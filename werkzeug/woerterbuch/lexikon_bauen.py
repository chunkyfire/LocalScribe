"""Baut diktat/fachlexikon.json: Fachbegriffe und die Wörter, die vor Ersetzung geschützt sind.

    python lexikon_bauen.py <Ordner mit begriffe.txt, alle_woerter.txt, lexikon_roh.txt> <de index> <en index>

Geschützt ist jedes bekannte Wort (Worthäufigkeitslisten deutsch und englisch, Hunspell-Stämme), dessen
Lautschlüssel mit dem eines Fachbegriffs zusammenfällt: „Lied“ wird nie zu „Lid“.
"""
import json
import pathlib
import re
import sys

from wordfreq import iter_wordlist

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import types
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
from diktat import fach

work = pathlib.Path(sys.argv[1])
WORD = re.compile(r"^[A-Za-zÄÖÜäöüß]{6,40}$")
import collections
terms, count = {}, collections.Counter()
for line in (work / "begriffe.txt").read_text(encoding="utf-8").splitlines():
    t = line.split("\t")[0]
    if WORD.match(t):
        terms.setdefault(t.lower(), t)
raw = work / "lexikon_roh.txt"
if raw.exists():
    for name in raw.read_text(encoding="utf-8").splitlines():
        parts = re.split(r"[\s\-/,()]+", name)
        for p in parts:
            # Einzelwörter ganz; aus mehrteiligen Namen nur Großgeschriebenes (Substantive, Eigennamen)
            if WORD.match(p) and (len(parts) == 1 or p[0].isupper()) and not p.isupper():
                terms.setdefault(p.lower(), p)
                count[p.lower()] += 1
# englische Namen aus Wikidata (Organomegaly) sind keine deutsche Schreibweise
kern = (pathlib.Path(__file__).with_name("kern.txt")).read_text(encoding="utf-8").split()
for t in kern:                      # die Kernliste gilt immer, auch wenn Wikidata den Begriff nicht kennt
    if WORD.match(t) and t[0].isupper():
        terms.setdefault(t.lower(), t)
kern_low = {t.lower() for t in kern}
terms = {low: t for low, t in terms.items() if low in kern_low or not re.search(r"[^aeiouäöü]y$|[^aeiou]ies$|tion[s]?$(?<=ations)|ity$|ous$|ic$", low)}
keys = {}
for low in terms:
    keys.setdefault(fach.key(low), set()).add(low)

known = set()
for lang in ("de", "en"):
    known.update(w for w in iter_wordlist(lang, "best") if len(w) >= 5)
for index in sys.argv[2:4]:
    for line in open(index + ".dic", encoding="utf-8", errors="ignore"):
        w = line.split("/")[0].strip().lower()
        if len(w) >= 5 and w.isalpha():
            known.add(w)
known.update(w.lower() for w in (work / "alle_woerter.txt").read_text(encoding="utf-8").split())
protected = sorted(w for w in known if w not in terms and any(k in keys for k in fach.alternates(w)))
out = ROOT / "diktat" / "fachlexikon.json"
# ß: Das Modell schreibt mitunter „anschliessend“. Ersetzt wird nur, wenn es die ss-Form nicht gibt.
from spylls.hunspell import Dictionary
hun = Dictionary.from_files(sys.argv[2])
eszett = {}
for w in iter_wordlist("de", "best"):
    if "ss" in w and w.isalpha() and len(w) >= 4:
        for m in re.finditer("ss", w):
            v = w[:m.start()] + "ß" + w[m.end():]
            if (hun.lookup(v) or hun.lookup(v.capitalize())) and not (hun.lookup(w) or hun.lookup(w.capitalize())):
                eszett[w] = v
                break
import gzip
with gzip.open(ROOT / "diktat" / "bekannt.txt.gz", "wt", encoding="utf-8") as f:
    f.write("\n".join(sorted(w for w in known if len(w) >= 5)))
kern = [t for t in (pathlib.Path(__file__).with_name("kern.txt")).read_text(encoding="utf-8").split() if t.lower() in terms]
out.write_text(json.dumps({"begriffe": [terms[low] for low in sorted(terms, key=lambda x: (-count[x], x))], "eszett": eszett, "kern": kern, "geschuetzt": protected}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(eszett), "ß-Wörter,", len(terms), "Begriffe,", len(protected), "geschützte Wörter,", out.stat().st_size // 1024, "KB")
