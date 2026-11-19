"""Einstellungen und Daten liegen unter %LOCALAPPDATA%\\LocalScribe, also je Windows-Konto.

Ausnahme: Liegt neben LocalScribe.exe ein Ordner „daten“, liegt alles dort. So hat jede Person, die das Programm in
ihrem eigenen Ordner hält, ihre eigenen Einstellungen, ihren Verlauf und ihren gelernten Wortschatz, auch auf einem
Windows-Konto, das sich mehrere teilen.

Bewusst nicht unter %APPDATA% (Roaming): Dort würden Verlauf und Aufnahmen in Firmennetzen
mit dem Benutzerprofil auf einen Server wandern.
"""
import copy
import json
import logging
import os
import shutil
import time
from pathlib import Path

APP = "LocalScribe"
PORTABLE = "daten"       # Ordner neben LocalScribe.exe: gibt es ihn, liegen dort alle eigenen Daten

def _dir() -> Path:
    """Der erste Ordner, in den sich schreiben lässt: „daten“ neben dem Programm, wenn es ihn gibt, sonst das
    eigene Windows-Konto. Von sich aus legt die App nie Daten in den Programmordner: Der liegt oft auf einem
    Netzlaufwerk, das sich mehrere teilen, und dort hätten Verlauf und Protokoll ungefragt nichts zu suchen."""
    import sys
    import tempfile
    from . import ort
    own = ort.root() / PORTABLE if ort.root() else None
    places = [own] if own is not None and own.is_dir() else []
    places += [Path(base) / APP for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA"),
                                             str(Path.home()), tempfile.gettempdir()) if base]
    for path in places:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".schreibtest"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            return path
        except OSError:
            continue
    return Path(tempfile.gettempdir()) / APP


DIR = _dir()
RECORDINGS = "aufnahmen"
FILE = DIR / "config.json"
LOG = DIR / "diktat.log"
DB = DIR / "verlauf.sqlite"
ICON = DIR / "diktat.ico"

GERMAN = ("de", "genau")      # Modelle, bei denen die deutsche Nachbearbeitung gilt

# Sprachmodelle zur Auswahl. Die Fassung ist festgeschrieben: Es wird nie stillschweigend eine andere geladen.
MODELS = {
    "de": {"label": "Deutsch (primeline-Parakeet)",
           "repo": "OpenVoiceOS/primeline-parakeet-onnx", "revision": "411093fba73540a11c451841a8e7922c13b0fb00",
           # Dieselben Gewichte, schonender auf 8 Bit gekürzt (werkzeug/modell/kuerzen.py): so genau wie die
           # vollen 2,5 GB, so schnell wie bisher. Dateiname: [Größe, SHA-256].
           "release": {"name": "primeline-parakeet-kanal8-1",
                       "url": "https://github.com/chunkyfire/LocalScribe/releases/download/modell-primeline-1/",
                       "files": {
                           "config.json": [121, "db59e29a3c1fde6a081bf04965e72bba26cd65be1aee65b064360df8aef468e5"],
                           "vocab.txt": [93939, "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d"],
                           "decoder_joint-model.int8.onnx": [72520894, "e713d02c73176e629de49948f755a8e855b4850d4341124088d69adcfbc833c1"],
                           "encoder-model.int8.onnx": [881780860, "d3183080403232b0db42ba461ec4dc917996811fe689de42492747dc723a10d2"]}}},
    "genau": {"label": "Deutsch, genauer und langsamer (NVIDIA Canary 1B v2)", "type": "nemo-canary-1b-v2", "language": "de",
              "repo": "istupakov/canary-1b-v2-onnx", "revision": "5ebc1520cef7b6b318b3526ad17adbfe00bc1bfc"},
    "multi": {"label": "Mehrsprachig: 25 europäische Sprachen (NVIDIA Parakeet v3)",
              "repo": "istupakov/parakeet-tdt-0.6b-v3-onnx", "revision": "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce"},
}

SUMMARY = ("Fasse den Text zusammen und erfinde nichts. Geht es um eine Patientin oder einen Patienten (Anamnese, Visite, "
           "Fallbesprechung), schreibe eine knappe klinische Dokumentation mit den Abschnitten Anlass, Anamnese, Befunde, "
           "Beurteilung und Vorgehen; Abschnitte, zu denen nichts gesagt wurde, weglassen. Sonst fünf bis acht Sätze, das "
           "Wichtigste zuerst.")
MEETING = ("Schreibe das Protokoll einer Besprechung mit den Abschnitten Teilnehmende, Themen, Entscheidungen und Aufgaben "
           "(wer, was, bis wann). Knapp und sachlich, in ganzen Sätzen. Übernimm nur, was gesagt wurde; was nicht genannt "
           "wurde, weglassen.")
OLD_V4 = {"Zusammenfassung": "Fasse den Text in fünf bis acht Sätzen zusammen, das Wichtigste zuerst. Erfinde nichts.",
          "Meeting-Protokoll": "Schreibe ein Protokoll mit den Abschnitten Teilnehmende, Besprochenes, Entscheidungen und "
                               "Aufgaben (wer, was, bis wann). Übernimm nur, was gesagt wurde; was nicht genannt wurde, "
                               "weglassen."}
ON_RECORD = ("Glätten", "Zusammenfassung", "Meeting-Protokoll")       # ab Werk als Knopf auf der Seite Aufnahme

DEFAULTS = {
    # Tasten gedrückt halten = aufnehmen, loslassen = einfügen
    "hotkey_hold": ["ctrl", "win"],
    # während des Haltens zusätzlich drücken = Freihand (weiterreden ohne Halten);
    # beenden mit erneutem Druck der Halte-Tasten, abbrechen mit Esc
    "hotkey_lock": "space",
    # letzten Text noch einmal einfügen (falls das falsche Fenster aktiv war)
    "hotkey_paste_last": ["shift", "f7"],
    "hotkey_target": ["shift", "f9"],       # Zielfenster merken oder lösen: Diktate landen dort, egal was vorn ist
    "hotkey_next_field": ["shift", "f8"],   # nächste Sprungmarke [ ] im zuletzt eingefügten Text
    # Sprachmodell: "de" oder "multi", siehe MODELS
    "model_choice": "de",
    # mitgeliefertes medizinisches Wörterbuch anwenden (nur mit dem deutschen Modell)
    "base_dictionary": True,
    "llm_fix": False,             # Fachkorrektur: Hörfehler bei Fachbegriffen vom Sprachmodell vorschlagen lassen
    "vocabulary": [],             # eigene Begriffe: nur die richtige Schreibweise, erkannt wird am Klang
    "beam": 8,                    # Dekodieren mit so vielen Kandidaten und Wortschatz-Bonus (beam.py); 0 = einfach
    "learn_terms": True,          # Fachwörter aus den eigenen Diktaten in den Wortschatz aufnehmen (nur Lexikonwörter)
    "learned": [],                # gelernte Fachwörter (aus Diktaten und eingelesenen Texten)
    "mic_warm": False,            # Mikrofon dauerhaft offen halten: kein Startverzug, erste Silbe bleibt
    "speakers": False,            # Sprecher trennen bei Aufnahme und Datei
    "training_keep": False,       # Stimmtraining: vorgelesene (erfundene) Sätze als Ton aufheben, für ein Nachtraining
    "live_preview": True,         # Aufnahme: laufende Äußerung schon beim Sprechen vorläufig anzeigen
    "model_dir": "",              # eigener Ordner mit Sprachmodellen (z. B. ein gemeinsames Netzlaufwerk); leer = keiner
    "visite_prompt": "",          # Visite & Übergabe: eigene Anweisung an das Sprachmodell; leer = die mitgelieferte
    "visite_model": "",           # Modell für den Arztbrief; leer = Gemini 3.1 Pro bei OpenRouter, sonst das LLM-Modell
    "visite_jev": "",             # Jev-Modell für die Ersteinschätzung; leer = ~typesafe/jev-latest
    "seen_version": "",           # zuletzt gesehene Fassung: Nach einem Update zeigt das Fenster einmal, was neu ist
    "visite_rules": "",           # Hausregeln (Schockraum, Labor, Zuständigkeiten), die Jev mitbekommt; leer = keine
    "training_done": [],          # Stimmtraining: schon gelesene Sätze
    "phone": {"enabled": False, "port": 8765, "token": ""},   # Handy als Mikrofon (Webseite im eigenen Netz)
    "config_version": 5,
    "quantization": "int8",
    "provider": "CPUExecutionProvider",
    "threads": 0,
    "microphone": None,
    "sounds": True,
    "restore_clipboard": True,
    "trailing_space": True,
    "spoken_punctuation": False,  # „Punkt“, „Komma“, „Doppelpunkt“, „neue Zeile“ als Satzzeichen schreiben
    "min_seconds": 0.3,
    # Verlauf führen? Auf gemeinsam genutzten Windows-Konten ausschalten.
    "history_enabled": True,
    # Verlauf nach so vielen Tagen löschen (0 = nie). Er soll nur einen Text retten, der im
    # falschen Fenster gelandet ist; dafür reicht eine Woche.
    "history_days": 7,
    # gesprochene Befehle -> Text
    "commands": {"neue Zeile": "\n", "neuer Absatz": "\n\n"},
    # Wörterbuch: falsch erkannt -> richtig (Groß-/Kleinschreibung egal)
    "dictionary": {},
    # Textbausteine: gesprochenes Stichwort -> Text
    "snippets": {},
    # KI-Nachbearbeitung über eine OpenAI-kompatible Schnittstelle
    # (Ollama, LM Studio, vLLM oder ein Anbieter eigener Wahl).
    # Der API-Schlüssel liegt nicht hier, sondern in der Windows-Anmeldeinformationsverwaltung.
    "llm": {
        "enabled": False,
        "base_url": "http://localhost:11434/v1",
        "model": "",
        "temperature": 0.2,
        "timeout": 30,
        # Name eines Prompts, der auf jedes normale Diktat angewendet wird ("" = keiner)
        "auto_prompt": "",
        "profile": "",            # Name des gespeicherten Anbieters, zu dem der Schlüssel gehört ("" = alter Einzeleintrag)
        "protect": True,          # Namen, Daten, Nummern vor dem Versand an fremde Server durch Platzhalter ersetzen
    },
    "corrections": [],            # eigene Berichtigungen [erkannt, gemeint], die nur der Zusammenhang klärt (Kabel -> Cave)
    "llm_profiles": [],           # gespeicherte Anbieter: [{"name", "base_url", "model"}], Schlüssel im Schlüsselspeicher
    # Jeder Prompt kann eine eigene Halte-Taste bekommen: halten, sprechen, loslassen.
    "prompts": [
        {"name": "Glätten", "hotkey": ["f8"],
         "text": "Entferne Füllwörter, Versprecher und Wiederholungen. Korrigiere Grammatik und "
                 "Zeichensetzung. Ändere weder Inhalt noch Tonfall und füge nichts hinzu."},
        {"name": "E-Mail", "hotkey": [],
         "text": "Formuliere daraus eine kurze, freundliche E-Mail mit Anrede und Gruß. "
                 "Erfinde keine Inhalte."},
        {"name": "Stichpunkte", "hotkey": [],
         "text": "Fasse den Inhalt in knappen Stichpunkten zusammen, ein Gedanke pro Zeile."},
    ] + [dict(p) for p in (
        {"name": "Arztbrief", "hotkey": [],
         "text": "Schreibe aus dem Text einen Arztbrief-Entwurf mit den Abschnitten Diagnosen, Anamnese, Befund, "
                 "Verlauf und Procedere. Übernimm nur, was im Text steht, und erfinde nichts. Wozu nichts gesagt "
                 "wurde, den Abschnitt weglassen."},
        {"name": "Zusammenfassung", "hotkey": [],
         "text": SUMMARY},
        {"name": "Meeting-Protokoll", "hotkey": [],
         "text": MEETING},
    )],
}
for _p in DEFAULTS["prompts"]:
    _p["record"] = _p["name"] in ON_RECORD
ADDED_V4 = ("Arztbrief", "Zusammenfassung", "Meeting-Protokoll")     # kamen mit 1.3.0 dazu


def migrate() -> None:
    """Daten früherer Fassungen übernehmen (%APPDATA%\\LocalScribe, davor %APPDATA%\\Diktat)."""
    if FILE.exists() or not os.environ.get("APPDATA"):
        return
    for old in (Path(os.environ["APPDATA"]) / APP, Path(os.environ["APPDATA"]) / "Diktat"):
        if not old.is_dir() or old == DIR:
            continue
        try:
            DIR.mkdir(parents=True, exist_ok=True)
            for item in old.iterdir():
                if not (DIR / item.name).exists():
                    shutil.move(str(item), str(DIR / item.name))
            shutil.rmtree(old, ignore_errors=True)
            return
        except OSError:
            logging.exception("Alter Datenordner nicht übernehmbar")


def leftover_recordings() -> list:
    """Sicherungsdateien von Aufnahmen, die nicht zu Ende transkribiert wurden."""
    folder = DIR / RECORDINGS
    return sorted(folder.glob("*.wav")) if folder.is_dir() else []


def purge_recordings(days) -> int:
    """Liegengebliebene Tonaufnahmen nach der Aufbewahrungsfrist löschen (ohne Frist: nach 30 Tagen)."""
    limit, n = time.time() - (days or 30) * 86400, 0
    for path in leftover_recordings():
        try:
            if path.stat().st_mtime < limit:
                path.unlink()
                n += 1
        except OSError:
            logging.exception("Aufnahme %s nicht löschbar", path)
    return n


def load() -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    cfg = copy.deepcopy(DEFAULTS)
    if FILE.exists():
        try:
            stored = json.loads(FILE.read_text(encoding="utf-8-sig"))
            llm = {**cfg["llm"], **(stored.get("llm") or {})}
            cfg.update(stored)
            cfg["llm"] = llm
            if int(stored.get("config_version") or 1) < 3:
                # Wer eine frühere Standardtaste (F7, dann Strg allein) nie geändert hat, bekommt Strg + Win.
                if stored.get("hotkey_hold") in (["f7"], ["ctrl"]):
                    cfg["hotkey_hold"] = ["ctrl", "win"]
                cfg["config_version"] = 3
            if int(stored.get("config_version") or 1) < 4:
                # Die drei neuen Aufträge einmal nachtragen; wer einen gleichnamigen hat, behält seinen.
                names = {p.get("name") for p in cfg.get("prompts") or []}
                cfg["prompts"] = list(cfg.get("prompts") or []) + [
                    copy.deepcopy(p) for p in DEFAULTS["prompts"] if p["name"] in ADDED_V4 and p["name"] not in names]
                cfg["config_version"] = 4
            if int(stored.get("config_version") or 1) < 5:
                # 1.4.0: Welche Aufträge die Seite Aufnahme zeigt; die beiden Texte von 1.3.0 nachziehen, wenn unverändert.
                for p in cfg.get("prompts") or []:
                    p.setdefault("record", p.get("name") in ON_RECORD)
                    if p.get("text") == OLD_V4.get(p.get("name")):
                        p["text"] = {"Zusammenfassung": SUMMARY, "Meeting-Protokoll": MEETING}[p["name"]]
                cfg["config_version"] = 5
            cfg.pop("model", None)
            cfg.pop("model_revision", None)
        except Exception:
            logging.exception("config.json ist nicht lesbar, nutze Standardwerte")
    save(cfg)  # neue Schlüssel in die Datei nachtragen
    return cfg


def save(cfg: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, FILE)


BACKUPS = "sicherung"


def backup(tag: str = "") -> Path | None:
    """Kopie der Einstellungen (mit Wörterbuch, Textbausteinen, Aufträgen, Servern) im Datenordner ablegen.

    Geschieht vor jedem Versionswechsel und vor dem Zurückholen; die letzten zehn bleiben liegen. API-Schlüssel
    stehen nicht in der Datei, die liegen im Schlüsselspeicher von Windows."""
    if not FILE.exists():
        return None
    try:
        folder = DIR / BACKUPS
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"einstellungen-{time.strftime('%Y-%m-%d-%H%M%S')}{'-' + tag if tag else ''}.json"
        shutil.copyfile(FILE, target)
        for old in sorted(folder.glob("einstellungen-*.json"))[:-10]:
            old.unlink()
        return target
    except OSError:
        logging.exception("Sicherung der Einstellungen fehlgeschlagen")
        return None


def export(path) -> None:
    """Die Einstellungen als Datei an einen frei gewählten Ort schreiben."""
    shutil.copyfile(FILE, path)


def restore(path) -> dict:
    """Einstellungen aus einer gesicherten Datei zurückholen. Die bisherigen werden vorher gesichert."""
    try:
        stored = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise ValueError(f"Die Datei lässt sich nicht lesen ({e}).") from e
    if not isinstance(stored, dict) or not ({"hotkey_hold", "dictionary", "llm"} & set(stored)):
        raise ValueError("Das ist keine Einstellungsdatei von LocalScribe.")
    backup("vor-zurueckholen")
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(stored, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, FILE)
    return load()


def prompt_by_name(cfg: dict, name: str):
    for p in cfg.get("prompts") or []:
        if p.get("name") == name:
            return p
    return None
