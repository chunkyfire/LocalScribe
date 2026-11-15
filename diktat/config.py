"""Einstellungen: %APPDATA%\\LocalScribe\\config.json (wird beim ersten Start angelegt)."""
import copy
import json
import logging
import os
from pathlib import Path

APP = "LocalScribe"
DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP
FILE = DIR / "config.json"
LOG = DIR / "diktat.log"
DB = DIR / "verlauf.sqlite"
ICON = DIR / "diktat.ico"

DEFAULTS = {
    # Tasten gedrückt halten = aufnehmen, loslassen = einfügen
    "hotkey_hold": ["f7"],
    # während des Haltens zusätzlich drücken = Freihand (weiterreden ohne Halten);
    # beenden mit erneutem Druck der Halte-Tasten, abbrechen mit Esc
    "hotkey_lock": "space",
    # letzten Text noch einmal einfügen (falls das falsche Fenster aktiv war)
    "hotkey_paste_last": ["shift", "f7"],
    "model": "OpenVoiceOS/primeline-parakeet-onnx",
    "quantization": "int8",
    "provider": "CPUExecutionProvider",
    "threads": 0,
    "microphone": None,
    "sounds": True,
    "restore_clipboard": True,
    "trailing_space": True,
    "min_seconds": 0.3,
    # Verlauf nach so vielen Tagen löschen (0 = nie)
    "history_days": 30,
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
    """Daten aus der Zeit vor der Umbenennung (Ordner „Diktat“) übernehmen."""
    old = DIR.with_name("Diktat")
    if old.is_dir() and not DIR.exists():
        try:
            old.rename(DIR)
        except OSError:
            logging.exception("Alter Datenordner nicht übernehmbar")


def load() -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    cfg = copy.deepcopy(DEFAULTS)
    if FILE.exists():
        try:
            stored = json.loads(FILE.read_text(encoding="utf-8-sig"))
            llm = {**cfg["llm"], **(stored.get("llm") or {})}
            cfg.update(stored)
            cfg["llm"] = llm
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
