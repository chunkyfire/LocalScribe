"""Fachkorrektur mit einem kleinen Sprachmodell – mit Türsteher.

Das Sprachmodell sieht den Text und eine Liste der Wörter, die die App nicht kennt (weder
Alltagswort noch Fachbegriff). Es schlägt vor, was gemeint war. Übernommen wird ein Vorschlag nur,
wenn er
  - selbst ein bekanntes Wort oder ein Fachbegriff ist,
  - ähnlich klingt wie das Gehörte,
  - keine Zahl verändert.
Alles andere bleibt, wie es erkannt wurde. Das Sprachmodell kann also nichts umformulieren,
nichts hinzufügen und nichts weglassen.

In der App ab 0.9.1 als Option auf der Seite KI-Nachbearbeitung, ab Werk aus. Gemessen mit Llama 3.1 8B lokal:
drei richtige Ersetzungen, keine falsche, 14,3 -> 13,8 % Wortfehler, rund drei Sekunden je Diktat auf einer
Grafikkarte (werkzeug/messen/ERGEBNIS.md).
"""
import difflib
import json
import logging
import re

from . import fach, llm

log = logging.getLogger("diktat")
SYSTEM = ("Du korrigierst Hörfehler der Spracherkennung in deutschen ärztlichen Diktaten. Die Erkennung verhört "
          "sich bei Fachbegriffen, Medikamenten und Abkürzungen und schreibt ähnlich klingende Wörter, manchmal "
          "auch mehrere Wörter statt eines: \"Tor Asemid\" statt \"Torasemid\", \"Markomar\" statt \"Marcumar\", "
          "\"Kollitis\" statt \"Kolitis\", \"Ehe ka ge\" statt \"EKG\". Du bekommst den Text und eine Liste von "
          "Wörtern, die in keinem Wörterbuch stehen. Antworte nur mit einem JSON-Objekt: Schlüssel ist die falsch "
          "erkannte Stelle genau wie im Text (ein Wort oder wenige aufeinanderfolgende Wörter), Wert ist das "
          "gemeinte Wort in richtiger medizinischer Schreibweise. Prüfe jedes Wort der Liste und außerdem jedes "
          "andere Wort, das im medizinischen Zusammenhang keinen Sinn ergibt. Nimm nur Stellen auf, bei denen du "
          "sicher bist, was gemeint ist. Schreibe keine Abkürzungen aus, formuliere nichts um, ergänze nichts, "
          "ändere keine Zahlen. Wenn nichts zu korrigieren ist, antworte mit {}.")
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


VOWELS = set("aeiouäöüy")
ENDINGS = ("es", "en", "er", "em", "e", "s", "n")


def accept(heard: str, proposed) -> bool:
    """Der Türsteher. Das Sprachmodell schlägt vor, übernommen wird nur, was klingt wie das Gehörte:

    - Steht an der Stelle ein Wort, das es nicht gibt, darf es durch ein bekanntes Wort oder einen Fachbegriff
      ersetzt werden, wenn die Lautschlüssel zu drei Vierteln übereinstimmen (Hahnstau -> Harnstau).
    - Mehrere echte Wörter dürfen zu einem Fachbegriff werden, wenn sie zusammen fast genauso klingen
      (Atem Note -> Atemnot).
    - Ein einzelnes echtes Wort weicht nur einem Begriff der medizinischen Kernliste (Kabel -> Cave),
      nie einer bloßen Beugungsform.
    Zahlen bleiben immer unberührt, Fachbegriffe werden nie ersetzt, länger als doppelt so lang wird nichts.
    """
    if not isinstance(proposed, str) or not proposed.strip() or proposed.strip().lower() == heard.lower():
        return False
    proposed = proposed.strip()
    if re.search(r"\d", proposed + heard) or len(proposed) > 2 * len(heard) + 4:
        return False
    terms, protected = fach.load()[0], fach.load()[1]
    known = fach.near()[0]
    heard_words, words = fach.WORD.findall(heard), fach.WORD.findall(proposed)
    if not heard_words or not words or len(heard_words) > 4 or len(words) > 2:
        return False
    if len(heard_words) == 1 and heard_words[0].lower() in terms:
        return False                # Fachbegriffe bleiben

    def exists(w):
        low = w.lower()
        return low in known or low in terms or low in protected or fach._compound(low, known)

    def valid(w):
        low = w.lower()
        if low in terms or low in known or low in core() or w in SHORT or fach._compound(low, known):
            return True
        return any(low.endswith(e) and len(low) - len(e) >= 5 and (low[:-len(e)] in terms or low[:-len(e)] in known)
                   for e in ENDINGS)               # gebeugte Form eines bekannten Worts

    a, b = fach.key("".join(heard_words).lower()), fach.key("".join(words).lower())
    if not a or not b:
        return False
    ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    if a[0] != b[0] and not (a[0] in VOWELS and b[0] in VOWELS) and ratio < 0.9:
        return False                # Hörfehler behalten den Anlaut (gürtelförmig ist nicht keilförmig)
    medical = all(w.lower() in terms or w.lower() in core() or w in SHORT for w in words)
    if any(len(w) >= 4 and not exists(w) for w in heard_words):
        return ratio >= (0.7 if medical else 0.75 if all(valid(w) for w in words) else 0.93)
    if len(heard_words) > 1:
        return medical and len(words) == 1 and ratio >= 0.9
    if min(len(a), len(b)) >= 5 and (a[:-2] == b[:-2] or a.startswith(b) or b.startswith(a)):
        return False                # nur die Endung anders: Beugungsform, kein Hörfehler
    return ratio >= 0.65 and all(w.lower() in core() or w in SHORT for w in words)


def enabled(cfg: dict) -> bool:
    l = cfg.get("llm") or {}
    return bool(cfg.get("llm_fix") and (l.get("model") or "").strip() and (l.get("base_url") or "").strip())


WAIT = 6.0               # länger wartet ein Diktat nicht auf die Fachkorrektur; dann bleibt der Text, wie er ist
PIECE = 110             # Wörter je Anfrage: längere Texte gehen in Stücken an das Sprachmodell, gleichzeitig


def _pieces(text: str):
    """Text an Satzenden in Stücke von höchstens PIECE Wörtern teilen; zusammengesetzt ergeben sie wieder den Text."""
    parts, cur, n = [], "", 0
    for sentence in re.findall(r"[^.!?\n]*[.!?\n]+\s*|[^.!?\n]+$", text):
        words = len(sentence.split())
        if cur and n + words > PIECE:
            parts.append(cur)
            cur, n = "", 0
        cur, n = cur + sentence, n + words
    return parts + [cur] if cur else parts


def _one(text: str, ask, shield, memory=()):
    visible = shield.hide(text) if shield else text
    found = suspects(visible)[:MAX_WORDS]
    low = visible.lower()
    mine = {h: m for h, m in memory if h.lower() in low}            # nur, was in diesem Text vorkommt
    hint = (f"\nFrühere Berichtigungen dieses Nutzers (erkannt -> gemeint), nur anwenden, wenn es hier passt: "
            f"{json.dumps(mine, ensure_ascii=False)}") if mine else ""
    try:
        raw = ask(SYSTEM, f"Text: {visible.strip()}\nNicht im Wörterbuch: {json.dumps(found, ensure_ascii=False)}{hint}")
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        answer = json.loads(m.group()) if m else {}
    except Exception as e:
        log.warning("Fachkorrektur fehlgeschlagen: %s", e)
        return text, []
    done = []
    for heard, proposed in answer.items():
        edge = r"(?<![A-Za-zÄÖÜäöüß])" + re.escape(heard) + r"(?![A-Za-zÄÖÜäöüß])" if isinstance(heard, str) else ""
        if not edge or "[" in heard or not re.search(edge, text):
            continue                # die Stelle muss im Text stehen; Platzhalter des Schutzes sind tabu
        own = isinstance(proposed, str) and mine.get(heard, "").lower() == proposed.strip().lower() != ""
        if own or accept(heard, proposed):      # was der Nutzer selbst einmal berichtigt hat, braucht keinen Türsteher
            proposed = proposed.strip()
            text = re.sub(edge, lambda m: proposed, text)
            done.append((heard, proposed))
    return text, done


def correct(text: str, cfg_llm: dict, ask=None, memory=None):
    """Gibt (Text, Liste der Ersetzungen) zurück. ask(system, user) -> Antworttext; Standard: der eingestellte Server.

    memory: eigene Berichtigungen des Nutzers [(erkannt, gemeint)], die ein Wörterbuch nicht abbilden kann, weil
    das Erkannte selbst ein richtiges Wort ist (Kabel -> Cave). Das Sprachmodell entscheidet am Zusammenhang.

    Geht der Text zu einem Server außerhalb des Rechners, sieht dieser nur die geschützte Fassung (schutz.py):
    Namen, Daten und Nummern sind durch Platzhalter ersetzt. Ersetzt wird im Originaltext.
    """
    from . import schutz
    if ask is None and schutz.blocked(cfg_llm):
        log.warning("Fachkorrektur übersprungen: %s", schutz.MISSING)
        return text, []
    shield = schutz.Mask(lenient=True) if ask is None and schutz.needed(cfg_llm) else None
    if ask is None:
        cfg_llm = llm.quick(cfg_llm)             # hängt an jedem Diktat: das schnelle Modell des Anbieters
        cfg_llm = dict(cfg_llm, timeout=min(float(cfg_llm.get("timeout") or 30), WAIT))
        def ask(system, user):
            return llm.chat(cfg_llm, system, user, json_mode=True)
    memory = [(h, m) for h, m in (memory or []) if isinstance(h, str) and isinstance(m, str)]
    parts = _pieces(text)
    if len(parts) <= 1:
        return _one(text, ask, shield, memory)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(4, len(parts))) as pool:
        results = list(pool.map(lambda p: _one(p, ask, shield, memory), parts))
    return "".join(r[0] for r in results), [c for r in results for c in r[1]]
