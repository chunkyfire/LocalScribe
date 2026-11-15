"""Einstellungen und Daten liegen unter %LOCALAPPDATA%\\LocalScribe.

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
DIR = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())) / APP
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

DEFAULTS = {
    # Tasten gedrückt halten = aufnehmen, loslassen = einfügen
    "hotkey_hold": ["ctrl", "win"],
    # während des Haltens zusätzlich drücken = Freihand (weiterreden ohne Halten);
    # beenden mit erneutem Druck der Halte-Tasten, abbrechen mit Esc
    "hotkey_lock": "space",
    # letzten Text noch einmal einfügen (falls das falsche Fenster aktiv war)
    "hotkey_paste_last": ["shift", "f7"],
    # Sprachmodell: "de" oder "multi", siehe MODELS
    "model_choice": "de",
    # mitgeliefertes medizinisches Wörterbuch anwenden (nur mit dem deutschen Modell)
    "base_dictionary": True,
    "llm_fix": False,             # Fachkorrektur: Hörfehler bei Fachbegriffen vom Sprachmodell vorschlagen lassen
    "vocabulary": [],             # eigene Begriffe: nur die richtige Schreibweise, erkannt wird am Klang
    "mic_warm": False,            # Mikrofon dauerhaft offen halten: kein Startverzug, erste Silbe bleibt
    "speakers": False,            # Sprecher trennen bei Aufnahme und Datei
    "training_done": [],          # Stimmtraining: schon gelesene Sätze
    "training_keep": False,       # Stimmtraining: Aufnahmen mit Satz auf diesem Rechner aufheben (für ein Nachtraining)
    "config_version": 3,
    "quantization": "int8",
    "provider": "CPUExecutionProvider",
    "threads": 0,
    "microphone": None,
    "sounds": True,
    "restore_clipboard": True,
    "trailing_space": True,
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
    },
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
    ],
}


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


def prompt_by_name(cfg: dict, name: str):
    for p in cfg.get("prompts") or []:
        if p.get("name") == name:
            return p
    return None
