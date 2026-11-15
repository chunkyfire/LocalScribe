"""Fachbegriffe am Klang erkennen.

Das Sprachmodell schreibt Fachwörter oft so, wie sie klingen: „Tachükardie“, „Flegmone“,
„Kolezüstitis“. Der Lautschlüssel bildet solche Schreibweisen und den richtigen Begriff auf
dieselbe Form ab. Ersetzt wird ein Wort nur, wenn
  - es selbst kein bekanntes Wort ist (geschützte Wörter und alle Begriffe bleiben unberührt),
  - sein Lautschlüssel zu genau einem Fachbegriff gehört.
Beugungsformen (Pankreatitiden) haben einen anderen Schlüssel und bleiben, wie sie sind.
"""
import gzip
import json
import logging
import re
from pathlib import Path

log = logging.getLogger("diktat")
FILE = Path(__file__).with_name("fachlexikon.json")
WORD = re.compile(r"[A-Za-zÄÖÜäöüß]+")
KNOWN = Path(__file__).with_name("bekannt.txt.gz")
MIN = 6          # kürzere Wörter gleichen zu leicht Alltagswörtern und Namen
NEAR = 9         # ab dieser Schlüssellänge darf ein Laut abweichen (Stinosen, Nebennere, Pfortade)
_data = None
_near = None
_kern = set()


def key(word: str) -> str:
    """Lautschlüssel: gleiche Aussprache, gleiche Form."""
    w = word.lower().replace("ß", "ss")
    w = re.sub(r"^ch(?=[aolru])", "k", w)
    w = w.replace("sch", "$").replace("ch", "#")
    w = w.replace("ph", "f").replace("th", "t").replace("rh", "r").replace("qu", "kw").replace("x", "ks").replace("ck", "k")
    w = re.sub(r"c(?=[eiäy])", "z", w).replace("c", "k")
    w = w.replace("tz", "z").replace("ts", "z")
    w = w.replace("ae", "e").replace("ä", "e").replace("oe", "ö").replace("ue", "ü")
    w = w.replace("eu", "oi").replace("ei", "ai").replace("ey", "ai").replace("ay", "ai")
    w = w.replace("ie", "i").replace("y", "i").replace("ü", "i")
    w = w.replace("v", "f")
    w = re.sub(r"(?<=[aeioö])h(?![aeioö])", "", w)
    w = re.sub(r"(.)\1+", r"\1", w)
    return re.sub(r"g$", "k", re.sub(r"b$", "p", re.sub(r"d$", "t", w)))


def spelling(low: str) -> str:
    """c, k und z sind in der Fachsprache austauschbar (Processus/Prozessus): keine Fehlschreibung."""
    return re.sub(r"c(?!h)", "k", re.sub(r"c(?=[eiäy])", "z", low))


def alternates(low: str):
    """Der Schlüssel selbst und zwei häufige Abweichungen: w für v (Wena), z für s (Lipaze)."""
    yield key(low)
    if "w" in low:
        yield key(low.replace("w", "v"))
    if "z" in low:
        yield key(re.sub(r"(?<=[aeiouäöüy])z(?=[aeiouäöüy])", "s", low))


def _deletions(k):
    return {k[:i] + k[i + 1:] for i in range(len(k))}


VOWELS = "aeiouö"
NAMES = ("weiss", "gross", "strauss", "preuss", "heuss", "gauss", "reuss", "voss", "kress")   # Familiennamen mit ss


def _one_apart(a, b):
    """Unterscheiden sich die Schlüssel in genau einem Laut, und zwar so, wie das Modell sich verhört?

    a ist das gehörte Wort, b der Fachbegriff. Erlaubt: ein Vokal statt eines anderen (Stinosen)
    und ein im Wortinneren verschluckter Laut (Abwehspannung). Nicht erlaubt: Unterschiede am Wortende (das sind Beugungsformen),
    vertauschte Konsonanten (Schatten/Schaden) und ein s mehr oder weniger (Fugen-s).
    """
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        return len(diff) == 1 and diff[0] < len(a) - 2 and a[diff[0]] in VOWELS and b[diff[0]] in VOWELS
    if len(a) > len(b):
        return False                 # ein Laut zu viel: Klopfschmerz ist nicht Kopfschmerz
    for i in range(len(b) - 2):
        if a == b[:i] + b[i + 1:]:
            return b[i] != "s"
    return False


def near():
    """Für die unscharfe Suche: bekannte Wörter (die nie ersetzt werden) und ein Index der Schlüssel."""
    global _near
    if _near is None:
        known, index = set(), {}
        try:
            known = set(gzip.open(KNOWN, "rt", encoding="utf-8").read().split())
            for k, t in load()[2].items():
                if len(k) >= NEAR:
                    for d in _deletions(k) | {k}:
                        index.setdefault(d, set()).add(k)
        except Exception:
            log.exception("Wortliste nicht lesbar")
        _near = (known, index)
    return _near


def nearest(low: str):
    """Der einzige Fachbegriff, dessen Klang sich in genau einem Laut unterscheidet; sonst None."""
    known, index = near()
    k = key(low)
    if len(k) < NEAR or low in known:
        return None
    keys = load()[2]
    cands = {c for d in _deletions(k) | {k} for c in index.get(d, ()) if c != k and c[0] == k[0] and _one_apart(k, c)}
    found = {keys[c] for c in cands}
    return next(iter(found)) if len(found) == 1 else None


def load():
    global _data
    if _data is None:
        terms, protected, keys, eszett = {}, set(), {}, {}
        try:
            raw = json.loads(FILE.read_text(encoding="utf-8"))
            protected = set(raw["geschuetzt"])
            eszett = raw.get("eszett", {})
            for t in raw["begriffe"]:
                terms[t.lower()] = t
            # gleicher Klang, mehrere Schreibweisen (Diarrhö/Diarrhoe): die der Kernliste gilt,
            # sonst die häufigste (die Liste ist nach Häufigkeit geordnet)
            for t in raw["begriffe"]:
                keys.setdefault(key(t.lower()), t)
            for t in raw.get("kern", []):
                keys[key(t.lower())] = t
            _kern.update(raw.get("kern", []))
        except Exception:
            log.exception("Fachlexikon nicht lesbar")
        _data = (terms, protected, keys, eszett)
    return _data


def correct(text: str, fuzzy: bool = True) -> str:
    terms, protected, keys, eszett = load()
    if not keys:
        return text

    def cased(word, term):
        return term[0].lower() + term[1:] if word[0].islower() else term[0].upper() + term[1:]

    def fix(m):
        word = m.group()
        low = word.lower()
        if low in eszett and not (word[0].isupper() and low.startswith(NAMES)):
            return cased(word, eszett[low])     # das Modell schreibt gelegentlich ss für ß
        if len(low) < MIN or low in terms or low in protected:
            return word
        found = {keys[k] for k in alternates(low) if k in keys}
        if len(found) == 1:
            term = next(iter(found))
            if spelling(low) == spelling(term.lower()):
                return word
            return term[0].lower() + term[1:] if word[0].islower() else term
        if not found and fuzzy:
            term = nearest(low)
            if term:
                return term[0].lower() + term[1:] if word[0].islower() else term
        return word
    return WORD.sub(fix, text)
