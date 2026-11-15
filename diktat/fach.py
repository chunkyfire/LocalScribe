"""Fachbegriffe am Klang erkennen.

Das Sprachmodell schreibt Fachwörter oft so, wie sie klingen: „Tachükardie“, „Flegmone“,
„Kolezüstitis“. Der Lautschlüssel bildet solche Schreibweisen und den richtigen Begriff auf
dieselbe Form ab. Ersetzt wird ein Wort nur, wenn
  - es selbst kein bekanntes Wort ist (geschützte Wörter und alle Begriffe bleiben unberührt),
  - sein Lautschlüssel zu genau einem Fachbegriff gehört.
Beugungsformen (Pankreatitiden) haben einen anderen Schlüssel und bleiben, wie sie sind.
"""
import difflib
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


def _cs(low: str) -> int:
    return len(re.findall(r"c(?!h|k)", low))


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
        # ein Laut zu viel: Klopfschmerz ist nicht Kopfschmerz. Nur ein eingeschobener Vokal
        # in einem langen Wort gilt als verhört (Moxonoidin).
        if len(b) < NEAR:
            return False
        return any(a[i] in VOWELS and a[:i] + a[i + 1:] == b for i in range(1, len(a) - 2))
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


WIDE = 8         # ab dieser Schlüssellänge sucht die weite Suche (Trimbo, Trossiba, Pempolyzomap)
RATIO = 0.85     # so ähnlich müssen die Lautschlüssel mindestens sein
_wide = None


def _compound(low, known):
    """Aus zwei echten Wörtern zusammengesetzt (Hautturgor, Mundspatel): ein richtiges Wort, das nur in keiner Liste steht."""
    for i in range(4, len(low) - 3):
        a, b = low[:i], low[i:]
        if (a in known or a.rstrip("s") in known) and (b in known or b.capitalize() in known):
            return True
    return False


# Wortstämme von Wirkstoffnamen (als Lautschlüssel): Wer so endet und kein bekanntes Wort ist, ist ein Medikament.
STEMS = ("map", "nip", "pril", "sartan", "statin", "olol", "prazol", "konazol", "floksazin", "zilin", "mizin", "ziklin",
         "gliptin", "gliflozin", "glutit", "parin", "ksaban", "gatran", "tidin", "dipin", "zepam", "zolam", "tropium", "terol",
         "sonit", "setron", "lukast", "triptan", "siklofir", "dronat", "tiazit", "semit", "profen", "koksip", "fibrat",
         "mustin", "rubizin", "platin", "taksel", "zept", "presin", "relin", "metason", "oksetin", "pramin", "triptilin",
         "peridon", "kainamit", "zetam", "fosfamit", "trekzat", "limus", "sporin", "penem", "bactam", "baktam")
LOOSE = 0.7      # so ähnlich müssen Wirkstoffnamen mit gleichem Stamm mindestens klingen


def wide(low: str):
    """Kein echtes Wort, klingt aber deutlich nach genau einem Fachbegriff: Lymphardenopathie -> Lymphadenopathie.

    Strenger als ein Laut daneben, weil mehr abweichen darf: das gehörte Wort steht in keiner Wortliste,
    der Anfang stimmt, die Abweichung liegt nicht nur am Wortende (Beugung) und kein zweiter Begriff ist ähnlich nah.
    Wirkstoffnamen erkennt man am Stamm (-mab, -sartan); dort genügt eine geringere Ähnlichkeit, verglichen wird
    nur mit Wirkstoffen desselben Stamms (Pempolyzomap -> Pembrolizumab).
    """
    global _wide
    known = near()[0]
    k = key(low)
    if low in known:
        return None
    stem = next((s for s in STEMS if k.endswith(s) and len(k) >= len(s) + 4), None)
    if not stem and (len(k) < WIDE or _compound(low, known)):
        return None
    keys = load()[2]
    if _wide is None:
        _wide = {}
        for c in keys:
            if len(c) >= WIDE - 1:
                _wide.setdefault(c[0], []).append(c)
    need = LOOSE if stem else RATIO
    best, second, term = 0.0, 0.0, None
    for c in _wide.get(k[0], ()):
        if abs(len(c) - len(k)) > 2 or (stem and not c.endswith(stem)) or (not stem and c[:2] != k[:2]):
            continue
        m = difflib.SequenceMatcher(None, k, c, autojunk=False)
        if m.real_quick_ratio() < need or m.quick_ratio() < need:
            continue
        r = m.ratio()
        if r < need:
            continue
        if not stem:
            same = 0
            while same < min(len(k), len(c)) and k[same] == c[same]:
                same += 1
            if same >= min(len(k), len(c)) - 2:
                continue        # nur das Ende weicht ab: Beugungsform oder anderes Grundwort
        if r > best:
            if keys[c] != term:
                second = best
            best, term = r, keys[c]
        elif keys[c] != term and r > second:
            second = r
    return term if term and best - second >= 0.05 else None


def _ending(low: str, term: str) -> str:
    """Die Beugung des gehörten Worts behalten: viseralen -> viszeralen, Rhapdomyosarkoms -> Rhabdomyosarkoms."""
    t = term.lower()
    if t.endswith("e") and low[-2:] in ("en", "er", "es", "em"):
        return term + low[-1]
    if low.endswith("s") and not t.endswith(("s", "e")) and len(key(low)) == len(key(t)) + 1:
        return term + "s"
    return term


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


_own = (None, {}, set())


def own(vocabulary):
    """Eigene Begriffe des Nutzers (nur die richtige Schreibweise): Lautschlüssel -> Begriff, und die Begriffe klein."""
    global _own
    stamp = tuple(vocabulary or ())
    if _own[0] != stamp:
        table, low = {}, {}
        for term in stamp:
            term = term.strip()
            if len(term) >= 4 and WORD.fullmatch(term):
                low[term.lower()] = term
                for k in alternates(term.lower()):
                    table.setdefault(k, term)
        _own = (stamp, table, low)
    return _own[1], _own[2]


def correct(text: str, fuzzy: bool = True, vocabulary=None, far: bool = True, respell: bool = True) -> str:
    terms, protected, keys, eszett = load()
    if not keys:
        return text
    own_keys, own_low = own(vocabulary)

    def cased(word, term):
        return term[0].lower() + term[1:] if word[0].islower() else term[0].upper() + term[1:]

    def fix(m):
        word = m.group()
        low = word.lower()
        if low in eszett and not (word[0].isupper() and low.startswith(NAMES)):
            return cased(word, eszett[low])     # das Modell schreibt gelegentlich ss für ß
        if low in own_low:
            return own_low[low]                 # eigener Begriff: immer in der hinterlegten Schreibweise
        if own_keys and len(low) >= 4 and low not in terms and low not in protected:
            # eigene Begriffe haben Vorrang und gelten schon ab vier Buchstaben (Riba -> RIVA)
            mine = {own_keys[k] for k in alternates(low) if k in own_keys}
            if len(mine) == 1:
                return next(iter(mine))
            if not mine and low not in near()[0]:
                # kein echtes Wort und klingt fast wie genau ein eigener Begriff (Trossiba -> Tresiba)
                k = key(low)
                close = {t for ok, t in own_keys.items() if ok[:1] == k[:1]
                         and difflib.SequenceMatcher(None, k, ok).ratio() >= 0.75}
                if len(close) == 1:
                    return next(iter(close))
        if len(low) < MIN or low in terms or low in protected:
            return word
        found = {keys[k] for k in alternates(low) if k in keys}
        if len(found) == 1:
            term = next(iter(found))
            if spelling(low) == spelling(term.lower()) and not (respell and (_cs(low) > _cs(term.lower())
                                                                             or key(low).endswith(STEMS))):
                return word             # c, k und z: nur andere Schreibweise. Eingedeutscht wird (Coronare ->
                                        # Koronare), wenn nur diese Form im Lexikon steht; umgekehrt nur bei
                                        # Wirkstoffnamen, die eine feste Schreibweise haben (Kandesartan).
            return term[0].lower() + term[1:] if word[0].islower() else term
        if not found and fuzzy:
            term = nearest(low)
            if not term and far:
                term = wide(low)
                if term:
                    term = _ending(low, term)
            if term:
                return term[0].lower() + term[1:] if word[0].islower() else term
        return word
    return WORD.sub(fix, text)
