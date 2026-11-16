"""Schutz vor dem Versand an ein Sprachmodell außerhalb des Rechners.

Bevor Text zu einem Server im Internet geht (OpenRouter, IONOS …), ersetzt LocalScribe auf diesem Rechner alles,
was eine Person erkennbar macht, durch Platzhalter: Namen, Geburts- und andere Daten, Telefonnummern,
E-Mail-Adressen, Anschriften, lange Nummern (Fall-, Versicherten-, Kontonummern). Der Server sieht
„[NAME_1] kam am [DATUM_1]“; die Antwort wird hier wieder zurückübersetzt. Fehlt in der Antwort ein Platzhalter,
gilt sie als unbrauchbar.

Zwei Stufen:
  1. Regeln (immer): Muster für Daten, Nummern, Kontaktdaten, Anschriften und Namen hinter Anrede oder Titel.
  2. Ein Erkennungsmodell für Namen, Orte und Einrichtungen ohne solche Hinweise (GLiNER multi PII, 293 MB,
     läuft auf der CPU, wird beim ersten Einschalten geladen). Ohne das Modell rutscht ein Name ohne Anrede
     („Meier kam heute Nacht“) durch.

Medizinische Fachbegriffe bleiben stehen, auch wenn sie wie Namen aussehen (Parkinson, Crohn, Hodgkin).
Kein Verfahren findet alles: Das ist eine Schutzschicht, kein Beweis der Anonymität.
"""
import logging
import os
import re

import numpy as np

from . import fach

log = logging.getLogger("diktat")
REPO = "greg-gajda/gliner_multi_pii-v1-onnx-q8-emb4"       # Apache-2.0, mDeBERTa-v3, 8-Bit-Gewichte
REVISION = "6f0fb72527ee7b344a9a0071dd10a90f93d45e2e"
FILES = ["model_q8_emb4.onnx", "tokenizer.json", "gliner_config.json"]
LABELS = ["person", "address", "location", "organization", "date of birth", "phone number", "email"]
KIND = {"person": "NAME", "address": "ORT", "location": "ORT", "organization": "ORT",
        "date of birth": "DATUM", "phone number": "KONTAKT", "email": "KONTAKT"}
THRESHOLD = {"person": 0.3, "address": 0.4, "location": 0.5, "organization": 0.6}
MAX_WORDS = 250          # das Modell wertet höchstens 384 Wörter je Durchgang aus
WIDTH = 12

MONTH = "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
STRONG = r"Herrn?|Frau|Hr\.|Fr\.|Dr\.(?:\s?med\.)?|Prof\.|Professor(?:in)?|Doktor|Familie|Schwester|Pfleger"
WEAK = (r"Kollegen?|Kollegin|Patient(?:in)?|Oberarzt|Oberärztin|Chefarzt|Chefärztin|Hausarzt|Hausärztin|Ehemann|Ehefrau|"
        r"Tochter|Sohn|Mutter|Vater|Betreuer(?:in)?")
# häufige Nachnamen, die kein Alltagswort sind: überall geschützt
SURE = set("""Müller Schmidt Schneider Fischer Weber Meyer Wagner Becker Schulz Hoffmann Schäfer Bauer Richter Schröder
Neumann Zimmermann Krüger Hofmann Hartmann Schmitt Werner Schmitz Krause Meier Lehmann Schmid Schulze Maier Köhler
Herrmann Walter Mayer Huber Peters Scholz Möller Schubert Friedrich Günther Berger Winkler Lorenz Baumann Franke
Albrecht Schuster Ludwig Böhm Schumacher Krämer Vogt Seidel Heinrich Brandt Haas Schreiber Schulte Dietrich Ziegler
Kuhn Kühn Pohl Bergmann Voigt Arnold Wolff Pfeiffer Yilmaz Kaya Demir Öztürk Nowak Kowalski Petersen Hansen Jansen
Lindner Kramer Ernst Paul Stark Weiß Beck Roth Thomas Simon Martin""".split())
# häufige Nachnamen, die auch Alltagswörter sind: nur hinter Anrede, Titel oder Rolle
NAME = r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?"
RULES = [
    ("KONTAKT", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("KONTAKT", re.compile(r"\b(?:https?://|www\.)\S+")),
    ("NUMMER", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[\dA-Z]{4}){3,7}\b")),                       # IBAN
    ("KONTAKT", re.compile(r"(?<![\d.,])(?:\+49|0049|0)\s?\(?\d{2,5}\)?[\s/-]?\d{3,}(?:[\s-]?\d{2,}){0,3}(?![\d.,]*\d)")),
    ("DATUM", re.compile(rf"\b\d{{1,2}}\.\s?(?:\d{{1,2}}\.|(?:{MONTH}))\s?(?:\d{{4}}|\d{{2}})?(?!\d)")),
    ("DATUM", re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")),
    ("NUMMER", re.compile(r"\b[A-Z]\d{9}\b")),                                                # Versichertennummer
    ("NUMMER", re.compile(r"(?<![\d.,])\d{6,}(?![\d.,]*\d)")),                                 # Fall-, Akten-, Kontonummern
    ("ORT", re.compile(rf"\b{NAME}(?:straße|strasse|str\.|weg|platz|allee|gasse|ring|damm|ufer)\s\d+\s?[a-z]?\b")),
    ("ORT", re.compile(r"\b(?:[A-ZÄÖÜ][a-zäöüß]+\s)?(?:Straße|Weg|Platz|Allee)\s\d+\s?[a-z]?\b")),
    ("ORT", re.compile(rf"\b\d{{5}}\s{NAME}(?:\s{NAME})?")),                                   # Postleitzahl und Ort
]
CUED = re.compile(rf"\b({STRONG}|{WEAK})\s+((?:(?:Dr\.|Prof\.|med\.)\s+)*{NAME}(?:\s+{NAME}){{0,2}})")
STRONG_RX = re.compile(rf"(?:{STRONG})$")
SURE_RX = re.compile(r"\b(?:" + "|".join(sorted(SURE, key=len, reverse=True)) + r")(?:-" + NAME + r")?\b")
WORDS = re.compile(r"\w+(?:[-_]\w+)*|\S")
_session = _tok = None


# ---------- Erkennungsmodell ----------
def ready() -> bool:
    from . import modelle
    return bool(modelle.find(REPO, REVISION, FILES))


def prepare(progress=None) -> str:
    """Ordner des Erkennungsmodells; lädt es beim ersten Mal herunter (293 MB)."""
    from . import modelle
    return modelle.fetch(REPO, REVISION, FILES, progress)


def _load():
    global _session, _tok
    if _session is None:
        import onnxruntime as ort
        from tokenizers import Tokenizer
        folder = prepare()
        so = ort.SessionOptions()
        so.intra_op_num_threads = 4
        _session = ort.InferenceSession(os.path.join(folder, FILES[0]), so, providers=["CPUExecutionProvider"])
        _tok = Tokenizer.from_file(os.path.join(folder, "tokenizer.json"))
        _tok.no_truncation()
        _tok.no_padding()
    return _session, _tok


def _entities(text: str):
    """Spannen (Anfang, Ende, Etikett, Sicherheit) aus dem Erkennungsmodell."""
    session, tok = _load()
    prompt = []
    for label in LABELS:
        prompt += ["<<ENT>>", label]
    prompt.append("<<SEP>>")
    words = [(m.group(), m.start(), m.end()) for m in WORDS.finditer(text)]
    found = []
    for at in range(0, len(words), MAX_WORDS):
        part = words[at:at + MAX_WORDS]
        n = len(part)
        enc = tok.encode(prompt + [w for w, _, _ in part], is_pretokenized=True)
        ids, wid = enc.ids, enc.word_ids
        mask, prev = [], None
        for w in wid:
            mask.append(w - len(prompt) + 1 if w is not None and w != prev and w >= len(prompt) else 0)
            prev = w
        spans = np.array([[i, i + k] for i in range(n) for k in range(WIDTH)], dtype=np.int64)
        feed = {"input_ids": np.array([ids], dtype=np.int64), "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
                "words_mask": np.array([mask], dtype=np.int64), "text_lengths": np.array([[n]], dtype=np.int64),
                "span_idx": spans[None], "span_mask": (spans[:, 1] < n)[None]}
        logits = session.run(None, feed)[0][0]                       # [Wörter, Breite, Etiketten]
        probs = 1 / (1 + np.exp(-logits[:n]))
        cand = []
        for i, k, c in zip(*np.where(probs >= 0.3)):
            label = LABELS[c]
            if i + k < n and probs[i, k, c] >= THRESHOLD.get(label, 0.3):
                cand.append((float(probs[i, k, c]), int(i), int(i + k), label))
        taken = []
        for p, a, b, label in sorted(cand, reverse=True):               # sichere zuerst, keine Überschneidung
            if all(b < x or a > y for x, y in taken):
                taken.append((a, b))
                found.append((part[a][1], part[b][2], label, p))
    return found


# ---------- Regeln ----------
def _medical(span: str) -> bool:
    """Fachbegriffe, die wie Namen aussehen (Parkinson, Crohn), und Wörter ohne Großbuchstaben bleiben stehen."""
    terms = fach.load()[0]
    words = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß]+", span)]
    return bool(words) and all(w.lower() in terms or (len(w) > 3 and w.lower() in fach.near()[0] and not w[0].isupper())
                               for w in words)


def find(text: str, model: bool = True, lenient: bool = False):
    """Alle zu schützenden Stellen als (Anfang, Ende, Art), ohne Überschneidungen, von vorn nach hinten.

    lenient: für die Fachkorrektur. Deren Stoff sind gerade die Wörter, die es nicht gibt (Hahnstau, Lisenophril);
    das Erkennungsmodell hält solche Wörter gern für Orte. Orte und Einrichtungen gelten dort nur, wenn sie aus
    bekannten Wörtern bestehen, Personen nur bei hoher Sicherheit.
    """
    spans = []
    for kind, rx in RULES:
        spans += [(m.start(), m.end(), kind) for m in rx.finditer(text)]
    spans += [(m.start(), m.end(), "NAME") for m in SURE_RX.finditer(text)]
    known = fach.near()[0]
    for m in CUED.finditer(text):
        words = m.group(2).split()
        titles = [w for w in words if w.endswith(".")]
        names = [w for w in words if not w.endswith(".")]
        first = names[0] if names else ""
        if not first or first.lower() in STOP:
            continue                                        # „Herr Hat“ gibt es nicht
        if not STRONG_RX.match(m.group(1)) and not titles and first not in SURE and first.lower() in known:
            continue                                        # „Patientin Zustand nach“ – hinter einer Rolle nur echte Namen
        keep = [first]
        for w in names[1:]:                                 # weitere Namensteile, aber keine Folgewörter des Satzes
            if w.lower() in fach.load()[0] or w.lower() in STOP or (w.lower() in known and w not in SURE):
                break
            keep.append(w)
        length = len(" ".join(titles + keep))
        spans.append((m.start(2), m.start(2) + length, "NAME"))
    if model and ready():
        try:
            for a, b, label, score in _entities(text):
                span = text[a:b]
                if _medical(span) or (label != "person" and re.fullmatch(r"[A-ZÄÖÜ0-9-]{2,6}", span)):
                    continue                                # Fachbegriffe und Abkürzungen (RIVA, COPD) sind keine Orte
                if lenient:
                    words = re.findall(r"[A-Za-zÄÖÜäöüß]{4,}", span)
                    if label == "person" and score < 0.6:
                        continue
                    if label in ("address", "location", "organization") and not all(w.lower() in known for w in words):
                        continue
                spans.append((a, b, KIND[label]))
        except Exception:
            log.exception("Erkennungsmodell für Namen nicht nutzbar, es gelten nur die Regeln")
    out = []
    for a, b, kind in sorted(spans, key=lambda s: (s[0], -(s[1] - s[0]))):
        if out and a < out[-1][1]:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b, out[-1][2])       # überlappend: zusammenlegen
            continue
        out.append((a, b, kind))
    return out


STOP = {"hat", "ist", "war", "kam", "kommt", "wurde", "wird", "und", "mit", "bei", "aus", "berichtet", "gibt", "klagt",
        "stellt", "zeigt", "heute", "gestern", "seit", "nach", "vor", "zur", "zum", "der", "die", "das"}


class Mask:
    """Übersetzt einen Text in die geschützte Fassung und Antworten wieder zurück."""

    def __init__(self, model: bool = True, lenient: bool = False):
        self.model, self.lenient, self.back, self.fwd = model, lenient, {}, {}

    def hide(self, text: str) -> str:
        out, pos = [], 0
        for a, b, kind in find(text, self.model, self.lenient):
            value = text[a:b]
            tag = self.fwd.get((kind, value))
            if not tag:
                tag = f"[{kind}_{sum(1 for k, _ in self.fwd if k == kind) + 1}]"
                self.fwd[(kind, value)] = tag
                self.back[tag] = value
            out += [text[pos:a], tag]
            pos = b
        return "".join(out) + text[pos:]

    def show(self, text: str) -> str:
        for tag, value in self.back.items():
            text = text.replace(tag, value)
        return text

    def lost(self, text: str):
        """Platzhalter, die in der Antwort fehlen (dann ist die Antwort nicht verwendbar)."""
        return [tag for tag in self.back if tag not in text]


def needed(llm_cfg: dict) -> bool:
    """Schutz gilt für jeden Server außerhalb des eigenen Rechners oder Netzes, solange er nicht abgeschaltet ist."""
    from . import llm
    return bool(llm_cfg.get("protect", True)) and not llm._is_local((llm_cfg.get("base_url") or "").strip())
