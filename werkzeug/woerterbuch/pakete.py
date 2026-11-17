"""Fachgebiets-Pakete für den Wortschatz erzeugen: je Fachgebiet die Wörter, die in Arztbriefen wirklich fallen.

    python pakete.py <Ausgabe.json>

Fragt das in LocalScribe eingestellte Sprachmodell (KI-Nachbearbeitung) nach Begriffslisten; es gehen nur diese
Fragen hinaus, keine Diktate. Ergebnis: {Fachgebiet: [Begriffe]}; Auswahl und Zuschnitt macht pakete_bauen.py.
"""
import concurrent.futures as cf
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
from diktat import config, llm

FACH = ["Notaufnahme und Akutmedizin", "Allgemeine Innere Medizin", "Kardiologie", "Nephrologie und Dialyse",
        "Gastroenterologie und Hepatologie", "Pneumologie", "Neurologie", "Neurochirurgie", "Radiologie",
        "Unfallchirurgie und Orthopädie", "Allgemein- und Viszeralchirurgie", "Gefäß- und Herzchirurgie",
        "Hämatologie und Onkologie", "Endokrinologie und Diabetologie", "Infektiologie und Mikrobiologie",
        "Intensivmedizin und Anästhesie", "Urologie", "Gynäkologie und Geburtshilfe", "Pädiatrie", "Psychiatrie",
        "Dermatologie", "HNO", "Augenheilkunde", "Geriatrie und Palliativmedizin", "Rheumatologie", "Labormedizin"]
ART = ["Diagnosen, Syndrome und Befundbegriffe", "Wirkstoffe und in Deutschland gängige Handelsnamen",
       "Untersuchungen, Eingriffe, Operationen, Geräte und Materialien",
       "Anatomie, Laborwerte, Scores, Klassifikationen und Eponyme"]
SYSTEM = ("Du bist ein erfahrener deutscher Facharzt und kennst die Sprache deutscher Arztbriefe genau. "
          "Antworte nur mit einem JSON-Objekt {\"begriffe\": [...]}.")
cfg = config.load()["llm"]
WORD = re.compile(r"[A-Za-zÄÖÜäöüßé][A-Za-zÄÖÜäöüßé\-]{3,}")


def ask(fach, art):
    user = (f"Fachgebiet: {fach}. Nenne 180 einzelne Wörter aus dem Bereich „{art}“, die in deutschen Arztbriefen, "
            "Befunden und Diktaten dieses Fachgebiets häufig vorkommen. Nur einzelne Wörter in der üblichen deutschen "
            "Schreibweise (zusammengesetzte Wörter als ein Wort), keine Erklärungen, keine Abkürzungen aus Großbuchstaben, "
            "keine Allerweltswörter. Bevorzuge Wörter, die eine Spracherkennung leicht verhört.")
    for _ in range(3):
        try:
            data = json.loads(llm.chat(cfg, SYSTEM, user, json_mode=True))
            words = [w.strip() for w in data.get("begriffe", []) if isinstance(w, str) and WORD.fullmatch(w.strip())]
            if len(words) >= 40:
                return fach, words
        except Exception as e:
            err = e
    print("fehlgeschlagen:", fach, art, flush=True)
    return fach, []


out = {}
with cf.ThreadPoolExecutor(6) as pool:
    for fach, words in pool.map(lambda p: ask(*p), [(f, a) for f in FACH for a in ART]):
        have = out.setdefault(fach, [])
        seen = {w.lower() for w in have}
        have += [w for w in dict.fromkeys(words) if w.lower() not in seen]
        print(fach, len(have), flush=True)
pathlib.Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
print("FERTIG", sum(len(v) for v in out.values()), "Begriffe,", len({w.lower() for v in out.values() for w in v}), "verschiedene")
