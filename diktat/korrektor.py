"""Fachkorrektur mit einem kleinen Sprachmodell – mit Türsteher.

Das Sprachmodell sieht den Text und eine Liste der Wörter, die die App nicht kennt (weder
Alltagswort noch Fachbegriff). Es schlägt vor, was gemeint war. Übernommen wird ein Vorschlag nur,
wenn er
  - selbst ein bekanntes Wort oder ein Fachbegriff ist,
  - ähnlich klingt wie das Gehörte,
  - keine Zahl verändert.
Alles andere bleibt, wie es erkannt wurde. Das Sprachmodell kann also nichts umformulieren,
nichts hinzufügen und nichts weglassen.

Stand 0.8: in der App noch nicht geschaltet. Gemessen mit lokalen Modellen (Gemma 3 4B, Llama 3.1 8B):
drei bis vier Sekunden auf einer Grafikkarte, und die Vorschläge sind zu oft falsch
(werkzeug/messen/ERGEBNIS.md). Der Türsteher ist für ein stärkeres Modell im Cloud-Modus vorgesehen.
"""
import difflib
import json
import logging
import re

from . import fach, llm

log = logging.getLogger("diktat")
SYSTEM = ("Du korrigierst Hörfehler der Spracherkennung in deutschen ärztlichen Diktaten. Die Erkennung verhört "
          "sich bei Fachbegriffen, Medikamenten und Abkürzungen und schreibt ähnlich klingende Wörter: "
          "\"Set-Implantation\" statt \"Stent-Implantation\", \"Kabel\" statt \"Cave\", \"Riba\" statt \"RIVA\", "
          "\"Retroximab\" statt \"Rituximab\". Du bekommst den Text und eine Liste von Wörtern, die in keinem "
          "Wörterbuch stehen. Antworte nur mit einem JSON-Objekt: Schlüssel ist ein falsch erkanntes Wort genau "
          "wie im Text, Wert ist das gemeinte Wort in richtiger medizinischer Schreibweise. Prüfe jedes Wort der "
          "Liste und außerdem jedes andere Wort, das im medizinischen Zusammenhang keinen Sinn ergibt. Nimm nur "
          "Wörter auf, bei denen du sicher bist, was gemeint ist. Formuliere nichts um, ergänze nichts, ändere "
          "keine Zahlen. Wenn nichts zu korrigieren ist, antworte mit {}.")
# kurze Fachwörter und Abkürzungen, die das Lexikon (ab sechs Buchstaben) nicht führt
SHORT = {"Stent", "Cave", "RIVA", "RCA", "RCX", "GOLD", "STEMI", "NSTEMI", "Sehne", "Ileus", "Lyse", "Shunt", "Ulkus", "Koma", "Tumor", "Aszites", "Ödem", "Sepsis", "Niere", "Leber", "Milz", "Lunge", "Herz"}
MAX_WORDS = 14          # mehr Verdächtige auf einmal machen die Antwort langsam


def suspects(text: str):
    """Wörter ab fünf Buchstaben, die weder Fachbegriff noch bekanntes Wort sind."""
    terms, protected = fach.load()[0], fach.load()[1]
    known = fach.near()[0]
    out = []
    for w in fach.WORD.findall(text):
        low = w.lower()
        if len(low) >= 5 and low not in terms and low not in known and low not in protected and w not in out:
            out.append(w)
    return out


_core = None


def core() -> set:
    global _core
    if _core is None:
        data = json.loads(fach.FILE.read_text(encoding="utf-8"))
        _core = {w.lower() for w in data.get("kern", [])}
    return _core


def accept(heard: str, proposed) -> bool:
    """Der Türsteher. Ein unbekanntes Wort darf durch ein bekanntes ersetzt werden, ein echtes Wort nur
    durch einen Fachbegriff. In beiden Fällen muss der Vorschlag klingen wie das Gehörte."""
    if not isinstance(proposed, str) or not proposed.strip() or proposed.strip().lower() == heard.lower():
        return False
    proposed = proposed.strip()
    if re.search(r"\d", proposed + heard) or len(proposed) > 2 * len(heard) + 4:
        return False
    terms, protected = fach.load()[0], fach.load()[1]
    known = fach.near()[0]
    words = fach.WORD.findall(proposed)
    if not words or len(words) > 2:
        return False
    medical = all(w.lower() in core() or w in SHORT for w in words)     # Kernliste: Diagnosen, Wirkstoffe, Befunde
    if not (medical or all(len(w) < 5 or w.lower() in known or w.lower() in terms for w in words)):
        return False
    heard_words = fach.WORD.findall(heard)
    real = all(w.lower() in known or w.lower() in protected or len(w) < 5 for w in heard_words)
    if any(w.lower() in terms for w in heard_words) or (real and not medical):
        return False                # Fachbegriffe bleiben; echte Wörter weichen nur einem Fachbegriff
    a, b = fach.key("".join(heard_words).lower()), fach.key("".join(words).lower())
    if min(len(a), len(b)) >= 5 and (a[:-2] == b[:-2] or a.startswith(b) or b.startswith(a)):
        return False                # nur die Endung anders: Beugungsform, kein Hörfehler
    return difflib.SequenceMatcher(None, a, b).ratio() >= (0.7 if real else 0.6)


def correct(text: str, cfg_llm: dict, ask=None):
    """Gibt (Text, Liste der Ersetzungen) zurück. ask(system, user) -> Antworttext; Standard: der eingestellte Server."""
    found = suspects(text)[:MAX_WORDS]
    if ask is None:
        def ask(system, user):
            return llm.chat(cfg_llm, system, user, json_mode=True)
    try:
        raw = ask(SYSTEM, f"Text: {text.strip()}\nNicht im Wörterbuch: {json.dumps(found, ensure_ascii=False)}")
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        answer = json.loads(m.group()) if m else {}
    except Exception as e:
        log.warning("Fachkorrektur fehlgeschlagen: %s", e)
        return text, []
    done = []
    for heard, proposed in answer.items():
        if not isinstance(heard, str) or not re.search(r"(?<![A-Za-zÄÖÜäöüß])" + re.escape(heard) + r"(?![A-Za-zÄÖÜäöüß])", text):
            continue
        if accept(heard, proposed):
            proposed = proposed.strip()
            text = re.sub(r"(?<![A-Za-zÄÖÜäöüß])" + re.escape(heard) + r"(?![A-Za-zÄÖÜäöüß])", lambda m: proposed, text)
            done.append((heard, proposed))
    return text, done
