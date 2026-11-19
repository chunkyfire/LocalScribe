"""Stimmtraining: vorgegebene Sätze vorlesen oder Aufnahmen mit Transkript einlesen, die App lernt daraus.

Der gelesene Satz ist bekannt. Was die Erkennung stattdessen schreibt, wird Wort für Wort daneben
gelegt. Ein falsch erkanntes Wort kommt ins persönliche Wörterbuch, wenn es dem richtigen ähnlich
klingt und selbst kein echtes Wort ist. So kann das Training nie dafür sorgen, dass später ein
richtig erkanntes Alltagswort ersetzt wird.
"""
import difflib
import json
import re
from pathlib import Path

from . import fach

FILE = Path(__file__).with_name("lesetexte.json")
TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß]+|\d+")
SOUND = 0.55            # so ähnlich müssen sich Gehörtes und Gemeintes im Lautschlüssel mindestens sein
BASE = "Grundstock"     # Sätze für alle Fachrichtungen: Zahlen, Einheiten, Dosierungen, häufige Wendungen
WPM = 117               # so viele Wörter liest man mit Fachbegriffen etwa in einer Minute
_data = None


def _load() -> dict:
    """lesetexte.json: {"fach": Fachrichtung -> Übungssätze (geordnet), "pruef": Fachrichtung -> Prüfsätze,
    "alt": früheres Thema -> Sätze}. Gebaut von werkzeug/lesetexte/bauen.py."""
    global _data
    if _data is None:
        _data = json.loads(FILE.read_text(encoding="utf-8"))
    return _data


def fields() -> list:
    """Fachrichtungen mit neuen Sätzen, ohne den Grundstock."""
    return [name for name in _load()["fach"] if name != BASE]


def topics() -> list:
    """Frühere Themen, für die es noch keine neue Fachrichtung gibt."""
    return list(_load()["alt"])


def sentences(name: str = BASE) -> list:
    """Übungssätze in Lesereihenfolge: bei einer Fachrichtung erst der Grundstock, dann das Fach."""
    data = _load()
    if name in data["alt"]:
        return list(data["alt"][name])
    base = list(data["fach"][BASE])
    return base + list(data["fach"][name]) if name in data["fach"] and name != BASE else base


def held_out(name: str = BASE) -> list:
    """Prüfsätze zum Messen: kommen im Training nie vor. Grundstock plus Fachrichtung."""
    data = _load()
    base = list(data["pruef"].get(BASE, []))
    return base + list(data["pruef"].get(name, [])) if name != BASE else base


def minutes(items) -> float:
    return sum(len(plain(s)) for s in items) / WPM


def material() -> dict:
    """Name -> Sätze, für alles, was sich auswählen lässt."""
    return {name: sentences(name) for name in [BASE] + fields() + topics()}


# ---- Vergleichen: Soll in Sprechform (einhundertsechzig zu fünfundneunzig), Erkanntes in Schreibform (160/95) ----
_ONES = {"null": 0, "ein": 1, "eins": 1, "zwei": 2, "zwo": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8,
         "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12, "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15, "sechzehn": 16,
         "siebzehn": 17, "achtzehn": 18, "neunzehn": 19}
_TENS = {"zwanzig": 20, "dreißig": 30, "vierzig": 40, "fünfzig": 50, "sechzig": 60, "siebzig": 70, "achtzig": 80, "neunzig": 90}
_SHORT = {"milligramm": "mg", "mikrogramm": "µg", "microgramm": "µg", "mcg": "µg", "ug": "µg", "nanogramm": "ng", "pikogramm": "pg",
          "kilogramm": "kg", "gramm": "g", "milliliter": "ml", "mikroliter": "µl", "deziliter": "dl", "liter": "l",
          "millimol": "mmol", "mikromol": "µmol", "prozent": "%", "einheiten": "ie", "einheit": "ie", "minute": "min",
          "minuten": "min", "sekunden": "s", "sekunde": "s", "millisekunden": "ms", "stunden": "h", "stunde": "h",
          "zentimeter": "cm", "millimeter": "mm", "millibar": "mbar", "joule": "j", "intravenös": "iv", "subkutan": "sc",
          "intramuskulär": "im", "celsius": "c", "elektrokardiogramm": "ekg", "computertomografie": "ct"}


_UNITS = set(_SHORT.values())


def _below_thousand(word: str):
    total = 0
    if "hundert" in word:
        left, word = word.split("hundert", 1)
        if left and (left not in _ONES or _ONES[left] > 19):        # auch zwölfhundert
            return None
        total = 100 * (_ONES[left] if left else 1)
        if not word:
            return total
    if word in _ONES:
        return total + _ONES[word]
    if word in _TENS:
        return total + _TENS[word]
    m = re.fullmatch(r"([a-zäöüß]+?)und([a-zäöüß]+)", word)
    if m and _ONES.get(m.group(1), 99) < 10 and m.group(2) in _TENS:
        return total + _ONES[m.group(1)] + _TENS[m.group(2)]
    return None


def number(word: str):
    """Zahlwort -> Zahl, sonst None: einhundertsechzig, zweitausendvierhundert, fünfundneunzig. „ein“ allein bleibt Wort."""
    word = word.lower()
    if word == "ein" or not re.search(r"null|ein|zw|drei|vier|fünf|sech|sieb|acht|neun|zehn|elf|hundert|tausend", word):
        return None
    total = 0
    if "tausend" in word:
        left, word = word.split("tausend", 1)
        k = _below_thousand(left) if left else 1
        if k is None:
            return None
        total = 1000 * k
        if not word:
            return total
    rest = _below_thousand(word)
    return None if rest is None else total + rest


def plain(text: str) -> list:
    """Text als vergleichbare Wortfolge: klein, Zahlwörter als Ziffern, Einheiten in Kurzform, Schema 1-0-1 als 1 0 1."""
    t = text.lower().replace("−", "-").replace("\u00a0", " ")
    for a, b in ((r"(\d)\.(\d{3})\b", r"\1\2"), (r"°\s?c\b", " grad c "), (r"°", " grad "), (r"%", " % "),
                 (r"(?<=\d)\s?[-/]\s?(?=\d)", " "), (r"(\d) zu (?=\d)", r"\1 "), (r"/", " pro "), (r"i\.\s?v\.?", "iv"),
                 (r"i\.\s?e\.?", "ie"), (r"s\.\s?c\.?", "sc"), (r"i\.\s?m\.?", "im"), (r"-", " ")):
        t = re.sub(a, b, t)
    out = []
    for w in re.findall(r"\d+(?:,\d+)?|[a-zäöüßµ]+|%", t):
        n = None if w[0].isdigit() else number(w)
        w = str(n) if n is not None else _SHORT.get(w, w)
        if w == "komma" and out and out[-1].isdigit():
            out[-1] += ","                       # null Komma drei -> 0,3
        elif out and out[-1].endswith(",") and w.isdigit():
            out[-1] += w
        elif out and re.fullmatch(r"\d+,\d+", out[-1]) and w.isdigit() and len(w) == 1 and n is not None:
            out[-1] += w                         # sieben Komma zwei sechs -> 7,26
        else:
            if w in _UNITS and out and out[-1] in ("ein", "eine", "einen", "einem", "einer"):
                out[-1] = "1"                    # ein Milligramm -> 1 mg
            out.append(w)
    out = [w.rstrip(",") for w in out]
    return [w for i, w in enumerate(out)         # 160 zu 95 -> 160 95
            if not (w == "zu" and 0 < i < len(out) - 1 and out[i - 1][0].isdigit() and out[i + 1][0].isdigit())]


def errors(ref: list, hyp: list) -> int:
    """Wie viele Wörter müssten ersetzt, gestrichen oder ergänzt werden (Editierabstand)."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def score(expected: str, heard: str) -> tuple:
    """(Fehler, Wörter) für einen vorgelesenen Satz."""
    ref = plain(expected)
    return min(errors(ref, plain(heard)), len(ref)), len(ref)


def _real(word: str) -> bool:
    """Gibt es das Wort (Alltagswort, Fachbegriff, geschütztes Wort)?"""
    low = word.lower()
    terms, protected = fach.load()[0], fach.load()[1]
    return len(low) < 4 or low in terms or low in protected or low in fach.near()[0]


def learn(expected: str, heard: str):
    """Vergleicht Soll und Gehörtes. Gibt (gelesen, gelernt, offen) zurück.

    gelesen: Wurde erkennbar dieser Satz gelesen?
    gelernt: Liste (falsch, richtig) fürs Wörterbuch.
    offen:   Liste (gehört, gemeint), die nicht gelernt werden kann, weil das Gehörte ein echtes Wort ist.
    """
    exp, got = TOKEN.findall(expected), TOKEN.findall(heard)
    a, b = [w.lower() for w in exp], [w.lower() for w in got]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    # Gelesen? Verglichen wird in gleicher Schreibweise, sonst fiele jeder Satz mit vielen Zahlen durch
    ref, hyp = plain(expected), plain(heard)
    same = sum(m.size for m in difflib.SequenceMatcher(None, ref, hyp, autojunk=False).get_matching_blocks())
    if not got or same < 0.4 * len(ref):
        return False, [], []
    learned, open_ = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "replace":
            continue
        for right, wrong in _pairs(exp[i1:i2], got[j1:j2]):
            if len(right) < 4 or right.isdigit() or any(c.isdigit() for c in wrong) or wrong.lower() == right.lower():
                continue
            ratio = _sound(wrong, right)
            if ratio < SOUND:
                continue
            parts = wrong.split()
            if all(_real(w) for w in parts) and not (len(parts) > 1 and ratio >= 0.8):
                open_.append((wrong, right))      # echtes Wort: nicht lernbar (ein Wortpaar, das fast gleich klingt, schon)
            else:
                learned.append((wrong, right))
    return True, learned, open_


def _sound(wrong: str, right: str) -> float:
    return difflib.SequenceMatcher(None, fach.key(wrong.replace(" ", "").lower()), fach.key(right.lower())).ratio()


def _pairs(exp, got):
    """Ordnet innerhalb einer abweichenden Stelle jedem Sollwort ein bis drei gehörte Wörter zu
    (das Modell trennt Zusammensetzungen gern), sodass es insgesamt am besten klingt."""
    n, m = len(exp), len(got)
    if n * m > 400:
        return []
    INF, SKIP = 1e9, 0.6
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            c = cost[i][j]
            if c >= INF:
                continue
            if i < n and c + SKIP < cost[i + 1][j]:
                cost[i + 1][j], back[i + 1][j] = c + SKIP, (i, j, None)
            if j < m and c + SKIP < cost[i][j + 1]:
                cost[i][j + 1], back[i][j + 1] = c + SKIP, (i, j, None)
            if i < n:
                for k in (1, 2, 3):
                    if j + k <= m:
                        wrong = " ".join(got[j:j + k])
                        step = 1.0 - _sound(wrong, exp[i])
                        if c + step < cost[i + 1][j + k]:
                            cost[i + 1][j + k], back[i + 1][j + k] = c + step, (i, j, (exp[i], wrong))
    out, i, j = [], n, m
    while back[i][j] is not None:
        pi, pj, pair = back[i][j]
        if pair:
            out.append(pair)
        i, j = pi, pj
    return out[::-1]


# ---- Aus einer Aufnahme mit Transkript lernen: Der Ton wird nur gelesen, nie gespeichert ----
TEXTS = (".txt", ".docx", ".odt", ".md", ".rtf")


def partner(audio_path):
    """Das Transkript zur Aufnahme: eine Textdatei mit gleichem Namen im selben Ordner, sonst None."""
    path = Path(audio_path)
    for suffix in TEXTS:
        other = path.with_suffix(suffix)
        if other.exists() and other != path:
            return other
    return None


def from_recording(transcriber, cfg: dict, audio_path, text: str):
    """Erkennt die Aufnahme, vergleicht mit dem Transkript und lernt: Verhörer fürs Wörterbuch, Fachwörter für den
    Wortschatz. Gibt (passt zusammen, neue Wörterbuch-Paare, neue Fachwörter) zurück. Geschrieben wird nur in cfg;
    der Ton bleibt im Arbeitsspeicher und ist danach weg."""
    import numpy as np

    from . import engine, wortschatz
    _, blocks = engine.decode_file(audio_path)
    audio = np.concatenate(list(blocks) or [np.zeros(0, dtype=np.float32)])
    heard = engine.postprocess(transcriber.transcribe(audio), {
        "dictionary": {}, "trailing_space": False, "base_dictionary": cfg.get("base_dictionary", True),
        "model_choice": cfg.get("model_choice", "de")})
    read, learned, _ = learn(text, heard)
    if not read:
        return False, [], 0
    data = dict(cfg.get("dictionary") or {})
    new = [(w, r) for w, r in dict(learned).items() if data.get(w) != r]
    data.update(new)
    cfg["dictionary"] = data
    words = wortschatz.grow(dict(cfg, learn_terms=True, learned=cfg.setdefault("learned", [])), text)
    return True, new, words


# ---- Vorgelesene Sätze aufheben: Material für ein Nachtraining auf die eigene Stimme.
# Aufgehoben werden nur die erfundenen Sätze des Stimmtrainings, nie Diktate oder eingelesene Aufnahmen. Prüfsätze
# liegen getrennt im Unterordner „pruef“, damit ein Training sie nie zu sehen bekommt.
TESTS = "pruef"


def store(test: bool = False) -> Path:
    from . import config
    return config.DIR / "training" / TESTS if test else config.DIR / "training"


def keep(audio, text: str, rate: int = 16000, test: bool = False) -> Path:
    """Eine vorgelesene Aufnahme mit ihrem Satz ablegen (WAV, 16 kHz) und im Verzeichnis index.jsonl vermerken."""
    import time
    import wave

    import numpy as np
    folder = store(test)
    folder.mkdir(parents=True, exist_ok=True)
    stem, n = time.strftime("%Y%m%d-%H%M%S"), 1
    path = folder / f"{stem}.wav"
    while path.exists():
        n += 1
        path = folder / f"{stem}-{n}.wav"
    data = (np.clip(np.asarray(audio, dtype=np.float32), -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    with open(folder / "index.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"audio": path.name, "text": text, "sec": round(len(data) / rate, 2)}, ensure_ascii=False) + "\n")
    return path


def kept(test: bool = False):
    """(Anzahl, Sekunden) der aufgehobenen Aufnahmen; test=True zählt die Prüfsätze."""
    n, sec = 0, 0.0
    try:
        for line in open(store(test) / "index.jsonl", encoding="utf-8"):
            r = json.loads(line)
            if (store(test) / r["audio"]).exists():
                n, sec = n + 1, sec + r.get("sec", 0.0)
    except (OSError, ValueError):
        pass
    return n, sec


def clear() -> int:
    """Alle aufgehobenen Aufnahmen löschen, auch die Prüfsätze. Gibt die Zahl der gelöschten Dateien zurück."""
    n = 0
    for folder in (store(True), store()):
        if folder.is_dir():
            for path in list(folder.glob("*.wav")) + [folder / "index.jsonl"]:
                try:
                    path.unlink()
                    n += path.suffix == ".wav"
                except OSError:
                    pass
    return n
