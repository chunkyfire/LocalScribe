"""Der Wortschatz für das Dekodieren (beam.py): Kernbegriffe, eigene Begriffe und gelernte Fachwörter.

Das Wörterbuch hilft beim Dekodieren nur, wenn es die Wörter enthält, die man wirklich diktiert; ein riesiges
allgemeines Lexikon schadet (werkzeug/messen/ERGEBNIS.md). Deshalb sammelt LocalScribe aus dem mitgelieferten
Lexikon genau die Fachwörter heraus, die in den eigenen Diktaten und in eigenen Texten (Briefe, Befunde)
vorkommen. Gemerkt werden einzelne Wörter aus dem Lexikon, nie Sätze, und nichts, was nicht im Lexikon steht:
Namen von Patienten können so nicht in die Liste geraten. Alles bleibt in der Einstellungsdatei auf diesem Rechner.
"""
import json
import logging
import re
import zipfile
from pathlib import Path

from . import fach

log = logging.getLogger("diktat")
LIMIT = 4000        # mehr gelernte Wörter bringen nichts mehr und kosten Genauigkeit
MIN = 5
WORDS = re.compile(r"[A-Za-zÄÖÜäöüßéèáàç]{%d,}" % MIN)
_lex = None


def lexicon() -> dict:
    """Alle Fachwörter der App: klein geschrieben -> richtige Schreibweise."""
    global _lex
    if _lex is None:
        _lex = dict(fach.load()[0])
        try:
            base = json.loads(Path(__file__).with_name("basiswoerterbuch.json").read_text(encoding="utf-8"))
            for term in base:
                if WORDS.fullmatch(term):
                    _lex.setdefault(term.lower(), term)
        except Exception:
            log.exception("Basiswörterbuch nicht lesbar")
        for term in fach._kern:
            _lex.setdefault(term.lower(), term)
    return _lex


def from_text(text: str) -> list:
    """Fachwörter aus dem Lexikon, die im Text vorkommen (in der Schreibweise des Lexikons, ohne Doppelte)."""
    lex, out, seen = lexicon(), [], set()
    for word in WORDS.findall(text or ""):
        low = word.lower()
        if low in lex and low not in seen:
            seen.add(low)
            out.append(lex[low])
    return out


def read(path) -> str:
    """Text aus einer Datei: .docx, .odt, sonst als Textdatei (.txt, .md, .rtf, .html)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".docx", ".odt"):
        inner = "word/document.xml" if suffix == ".docx" else "content.xml"
        with zipfile.ZipFile(path) as z:
            xml = z.read(inner).decode("utf-8", "replace")
        return re.sub(r"<[^>]+>", " ", xml)
    if suffix == ".pdf":
        from pypdf import PdfReader             # nur wenn vorhanden; sonst meldet der Aufrufer die Datei als nicht lesbar
        return " ".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    data = path.read_bytes()
    for enc in ("utf-8", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def grow(cfg: dict, text: str) -> int:
    """Fachwörter aus einem Text in die gelernte Liste aufnehmen. Gibt die Zahl der neuen Wörter zurück."""
    if not cfg.get("learn_terms", True):
        return 0
    learned = cfg.setdefault("learned", [])
    fach.load()
    have = {t.lower() for t in learned} | {t.lower() for t in fach._kern}
    new = [t for t in from_text(text) if t.lower() not in have]
    if new:
        learned.extend(new)
        del learned[:-LIMIT]                    # die ältesten fallen heraus
    return len(new)


def learn_files(cfg: dict, paths) -> tuple:
    """Eigene Texte einlesen. Gibt (neue Wörter, nicht lesbare Dateien) zurück."""
    added, failed = 0, []
    for path in paths:
        try:
            added += grow(dict(cfg, learn_terms=True, learned=cfg.setdefault("learned", [])), read(path))
        except Exception as e:
            log.warning("Text %s nicht lesbar: %s", Path(path).name, e)
            failed.append(Path(path).name)
    return added, failed


def terms(cfg: dict) -> list:
    """Alles, was beim Dekodieren einen Bonus bekommt."""
    fach.load()
    return sorted(fach._kern) + list(cfg.get("vocabulary") or []) + list(cfg.get("learned") or [])
