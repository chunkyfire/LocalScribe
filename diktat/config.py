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

GERMAN = ("de",)              # Modelle, bei denen die deutsche Nachbearbeitung gilt

# Sprachmodelle zur Auswahl. Die Fassung ist festgeschrieben: Es wird nie stillschweigend eine andere geladen.
MODELS = {
    "de": {"label": "Deutsch (Parakeet, auf Deutsch nachtrainiert)",
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
    "multi": {"label": "Mehrsprachig (Parakeet v3, 25 europäische Sprachen)",
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
    "speakers": True,             # Sprecher trennen bei Aufnahme und Datei (bei nur einer Stimme bleibt der Text, wie er ist)
    "update_check": False,        # einmal am Tag still bei GitHub nach einer neueren Fassung fragen; ab Werk nur auf Klick
    "profile_name": "",           # gewähltes Profil am Programmordner (profile\\<Name>); leer = die Daten dieses Rechners
    "training_keep": True,        # Stimmtraining: vorgelesene (erfundene) Sätze als Ton aufheben, für ein Nachtraining
    "field": "",                  # Fachrichtung für die Sätze im Stimmtraining; leer = Grundstock
    "training_scores": [],        # Messungen mit Prüfsätzen: Zeitpunkt, Fachrichtung, Wortfehler, Trainingsminuten
    "live_preview": True,         # Aufnahme: laufende Äußerung schon beim Sprechen vorläufig anzeigen
    "model_dir": "",              # eigener Ordner mit Sprachmodellen (z. B. ein gemeinsames Netzlaufwerk); leer = keiner
    "handover_frame": "zna",      # Übergabe: zuletzt gewählter Rahmen (zna, station, its); gilt für den nächsten Fall
    "visite_prompt": "",          # Visite & Übergabe: eigene Anweisung an das Sprachmodell; leer = die mitgelieferte
    "visite_model": "",           # Modell für den Arztbrief; leer = visite.WRITER bei OpenRouter, sonst das LLM-Modell
    "visite_jev": "",             # Jev-Modell für die Ersteinschätzung; leer = ~typesafe/jev-latest
    "seen_version": "",           # zuletzt gesehene Fassung: Nach einem Update zeigt das Fenster einmal, was neu ist
    "visite_rules": "",           # Hausregeln (Schockraum, Labor, Zuständigkeiten), die Jev mitbekommt; leer = keine
    "training_done": [],          # Stimmtraining: schon gelesene Sätze
    "phone": {"enabled": False, "port": 8765, "token": ""},   # Handy als Mikrofon (Webseite im eigenen Netz)
    "config_version": 7,
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
            if int(stored.get("config_version") or 1) < 6:
                # 1.5.0: Sprecher trennen ist ab Werk an (einmal umstellen, bleibt abschaltbar). Das zweite deutsche
                # Sprachmodell (Canary) gibt es nicht mehr: seit der neuen Nachbearbeitung nicht genauer, aber langsamer.
                cfg["speakers"] = True
                if cfg.get("model_choice") == "genau":
                    cfg["model_choice"] = "de"
                cfg["config_version"] = 6
            if int(stored.get("config_version") or 1) < 7:
                # 1.6.0: Wer das Stimmtraining nutzt, will, dass die Stimme lernt: Die vorgelesenen (erfundenen) Sätze
                # werden ohne eigenen Haken aufgehoben.
                cfg["training_keep"] = True
                cfg["config_version"] = 7
            cfg.pop("model", None)
            cfg.pop("model_revision", None)
        except Exception:
            logging.exception("config.json ist nicht lesbar, nutze Standardwerte")
    global ACTIVE, OFFLINE, _base
    name, ACTIVE, OFFLINE, _base = str(cfg.get("profile_name") or ""), "", False, {}
    if name and profile_root() is not None:      # gewähltes Profil: seine persönlichen Einstellungen gelten
        fresh = _profile_load(name)
        if fresh is None:
            cfg["profile_name"] = ""             # das Profil gibt es nicht mehr: zurück zu den Daten dieses Rechners
        else:
            ACTIVE = name
            cfg.update(fresh)
    save(cfg)  # neue Schlüssel in die Datei nachtragen
    return cfg


def _whole() -> dict:
    """Was gerade gilt, als ein Stück: config.json, bei gewähltem Profil mit dessen persönlichen Einstellungen."""
    data = _read(FILE) or {}
    if ACTIVE:
        data.update(copy.deepcopy((_read(_copy_file(ACTIVE)) or {}).get("data") or _base))
    return data


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _read(path):
    """Inhalt einer JSON-Datei oder None (fehlt, nicht erreichbar, beschädigt)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save(cfg: dict) -> None:
    """Einstellungen schreiben. Ist ein Profil gewählt, gehen die persönlichen Teile dorthin; in config.json bleibt
    dafür stehen, was vorher zu diesem Rechner gehörte („Dieser Rechner“ bleibt, wie es war)."""
    DIR.mkdir(parents=True, exist_ok=True)
    if not ACTIVE:
        return _write(FILE, cfg)
    own = _read(FILE) or {}
    out = {k: v for k, v in cfg.items() if k not in PERSONAL}
    out.update({k: own[k] for k in PERSONAL if k in own})
    _write(FILE, out)
    _profile_save(cfg)


# ---- Profile: mehrere Personen an einem Programmordner (oft ein Netzlaufwerk, viele Rechner) ----
# Ein Profil ist ein Ordner profile\<Name> neben dem Programm: profil.json mit den persönlichen Einstellungen und
# training\ mit den Stimmaufnahmen. Kein Passwort, keine Rollen: Wer den Programmordner starten darf, kann jedes
# Profil wählen. Verlauf, Fälle, Protokoll und Schlüssel bleiben im Windows-Konto des Rechners.
PROFILES = "profile"
PROFILE_FILE = "profil.json"
COPIES = "profil-kopie"       # letzte Kopie je Profil auf diesem Rechner, falls der Programmordner gerade fehlt
PERSONAL = ("dictionary", "snippets", "vocabulary", "learned", "corrections", "commands", "prompts",
            "spoken_punctuation", "base_dictionary", "learn_terms", "sounds",
            "hotkey_hold", "hotkey_lock", "hotkey_paste_last", "hotkey_target", "hotkey_next_field",
            "field", "training_done", "training_scores", "handover_frame", "visite_prompt")
ACTIVE = ""                   # Name des gewählten Profils; leer = die Daten dieses Rechners
OFFLINE = False               # Profilordner gerade nicht erreichbar: Es gilt die Kopie von diesem Rechner
PROFILE_ROOT = None           # nur für Tests: fester Ordner statt „profile“ neben dem Programm
_base = {}                    # Stand des Profils beim letzten Lesen oder Schreiben, zum Zusammenführen
_probe = {}                   # Ordner -> lässt sich dort schreiben? (einmal je Lauf geprüft)


class _Gone:
    """Markiert „diesen Eintrag gibt es nicht“ beim Zusammenführen."""
    def __deepcopy__(self, memo):
        return self


_GONE = _Gone()


def profile_root():
    """Ordner mit den Profilen neben dem Programm; None, wenn die App aus dem Quelltext läuft."""
    if PROFILE_ROOT is not None:
        return Path(PROFILE_ROOT)
    from . import ort
    root = ort.root()
    return root / PROFILES if root else None


def _remote(path) -> bool:
    """Liegt der Ordner auf einem Netzlaufwerk (Freigabe eines Servers oder verbundener Laufwerksbuchstabe)?"""
    text = str(path)
    if text.startswith("\\\\"):
        return True
    try:
        import ctypes
        return ctypes.windll.kernel32.GetDriveTypeW(text[:3]) == 4      # DRIVE_REMOTE
    except Exception:
        return False


def _writable(folder: Path) -> bool:
    key = str(folder)
    if key not in _probe:
        try:
            probe = folder / ".schreibtest"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            _probe[key] = True
        except OSError:
            _probe[key] = False
    return _probe[key]


def profiles_on() -> bool:
    """Bietet das Fenster Profile an? Ja, wenn es den Ordner „profile“ neben dem Programm gibt, oder wenn das Programm
    auf einem Netzlaufwerk liegt, in das sich schreiben lässt: Dann legt das erste Profil den Ordner an."""
    root = profile_root()
    if root is None:
        return False
    try:
        if root.is_dir():
            return True
        return _remote(root.parent) and _writable(root.parent)
    except OSError:
        return False


def profiles_enable() -> None:
    """Profile an einem Programmordner einschalten, der nicht auf einem Netzlaufwerk liegt (legt den Ordner an)."""
    root = profile_root()
    if root is None:
        raise ValueError("Profile gibt es nur im installierten Programm.")
    root.mkdir(parents=True, exist_ok=True)


def profile_names() -> list:
    root = profile_root()
    try:
        return sorted((p.name for p in root.iterdir() if (p / PROFILE_FILE).is_file()), key=str.lower)
    except (OSError, AttributeError):
        return []


def clean_name(name: str) -> str:
    """Name eines Profils als Ordnername: ohne Zeichen, die Windows nicht erlaubt, höchstens 40 Zeichen."""
    import re
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", str(name)).strip(" .")[:40].strip(" .")
    return "" if name.upper() in ("CON", "PRN", "AUX", "NUL") or name.startswith("_") else name


def _personal(cfg: dict) -> dict:
    return {k: copy.deepcopy(cfg[k]) for k in PERSONAL if k in cfg}


def _merge(base, mine, theirs):
    """Drei Stände zusammenführen: Was nur eine Seite geändert hat, gilt; haben beide geändert, wird Eintrag für
    Eintrag weitergeschaut, und im echten Konflikt gewinnt dieser Rechner."""
    if mine == base:
        return copy.deepcopy(theirs)
    if theirs == base or mine == theirs:
        return copy.deepcopy(mine)
    if isinstance(mine, dict) and isinstance(theirs, dict):
        b = base if isinstance(base, dict) else {}
        out = {}
        for k in list(mine) + [k for k in theirs if k not in mine]:
            v = _merge(b.get(k, _GONE), mine.get(k, _GONE), theirs.get(k, _GONE))
            if v is not _GONE:
                out[k] = v
        return out
    if isinstance(mine, list) and isinstance(theirs, list):
        b = base if isinstance(base, list) else []
        named = lambda rows: all(isinstance(r, dict) and r.get("name") for r in rows)
        if mine and theirs and named(mine) and named(theirs) and named(b):   # Aufträge: nach Namen, nicht nach Platz
            merged = _merge({r["name"]: r for r in b}, {r["name"]: r for r in mine}, {r["name"]: r for r in theirs})
            return list(merged.values())
        out = [x for x in mine if not (x in b and x not in theirs)]          # was die andere Seite gestrichen hat, geht
        out += [x for x in theirs if x not in mine and x not in b]            # was die andere Seite ergänzt hat, kommt
        return copy.deepcopy(out)
    return copy.deepcopy(mine)


def _copy_file(name: str) -> Path:
    return DIR / COPIES / f"{name}.json"


def _profile_load(name: str):
    """Persönliche Einstellungen eines Profils lesen. Ist der Programmordner nicht erreichbar, gilt die Kopie von
    diesem Rechner (OFFLINE). Gibt None zurück, wenn es das Profil nicht mehr gibt."""
    global OFFLINE, _base
    root = profile_root()
    copy_file = _copy_file(name)
    kept = _read(copy_file) or {}
    try:
        reachable = root is not None and root.is_dir()
    except OSError:
        reachable = False
    if not reachable:
        if not kept:
            return None
        OFFLINE, _base = True, copy.deepcopy(kept.get("base") or {})
        return copy.deepcopy(kept.get("data") or {})
    theirs = _read(root / name / PROFILE_FILE)
    if theirs is None:
        return None
    theirs = {k: theirs[k] for k in PERSONAL if k in theirs}
    OFFLINE = False
    if kept.get("pending"):                 # hier wurde ohne Programmordner weitergearbeitet: jetzt zusammenführen
        base, mine = kept.get("base") or {}, kept.get("data") or {}
        merged = {k: _merge(base.get(k, _GONE), mine.get(k, _GONE), theirs.get(k, _GONE)) for k in PERSONAL}
        theirs = {k: v for k, v in merged.items() if v is not _GONE}
        try:
            _write(root / name / PROFILE_FILE, theirs)
        except OSError:
            OFFLINE = True
    _base = copy.deepcopy(theirs)
    try:
        _write(copy_file, {"pending": OFFLINE, "base": _base, "data": theirs})
    except OSError:
        pass
    if not OFFLINE:
        voice_sync(name)
    return copy.deepcopy(theirs)


def _profile_save(cfg: dict) -> None:
    """Persönliche Einstellungen ins Profil schreiben und dabei übernehmen, was ein anderer Rechner inzwischen
    beigetragen hat. Ist der Programmordner nicht erreichbar, bleibt alles in der Kopie auf diesem Rechner."""
    global OFFLINE, _base
    mine = _personal(cfg)
    merged = mine
    path = profile_root() / ACTIVE / PROFILE_FILE
    try:
        if not path.parent.is_dir():
            raise OSError("Profilordner nicht erreichbar")
        theirs = _read(path)
        if theirs is not None:
            merged = {k: v for k, v in ((k, _merge(_base.get(k, _GONE), mine.get(k, _GONE), theirs.get(k, _GONE)))
                                        for k in PERSONAL) if v is not _GONE}
        _write(path, merged)
        OFFLINE = False
        _base = copy.deepcopy(merged)
        for k, v in merged.items():
            if v != mine.get(k):
                cfg[k] = copy.deepcopy(v)        # was ein anderer Rechner inzwischen ergänzt hat
    except OSError:
        OFFLINE = True
    try:
        _write(_copy_file(ACTIVE), {"pending": OFFLINE, "base": _base, "data": merged})
    except OSError:
        pass


def profile_create(name: str, cfg=None) -> str:
    """Legt profile\\<Name> an. cfg: Einstellungen, deren persönlicher Teil mitgeht; ohne cfg die Werkseinstellung."""
    name = clean_name(name)
    if not name:
        raise ValueError("Bitte einen Namen eingeben (ohne Sonderzeichen wie / : * ?).")
    root = profile_root()
    if root is None:
        raise ValueError("Profile gibt es nur im installierten Programm.")
    if name.lower() in (n.lower() for n in profile_names()):
        raise ValueError(f"Das Profil „{name}“ gibt es schon.")
    try:
        _write(root / name / PROFILE_FILE, _personal(cfg if cfg is not None else DEFAULTS))
    except OSError as e:
        raise ValueError(f"Der Programmordner lässt sich nicht beschreiben ({e}).") from e
    return name


def profile_use(cfg: dict, name: str) -> None:
    """Auf ein Profil wechseln (leer = die Daten dieses Rechners): erst den jetzigen Stand sichern, dann die
    persönlichen Einstellungen in cfg tauschen. Der Rechner merkt sich die Wahl für dieses Windows-Konto."""
    global ACTIVE, OFFLINE, _base
    save(cfg)
    if name:
        fresh = _profile_load(name)
        if fresh is None:
            raise ValueError(f"Das Profil „{name}“ ist nicht erreichbar.")
    else:
        own = _read(FILE) or {}
        fresh, OFFLINE, _base = {k: own[k] for k in PERSONAL if k in own}, False, {}
    ACTIVE = name
    cfg["profile_name"] = name
    for k in PERSONAL:
        cfg[k] = copy.deepcopy(fresh[k] if k in fresh else DEFAULTS[k])
    save(cfg)


def voice_dir(name=None) -> Path:
    """Ordner der Stimmaufnahmen: im gewählten Profil, sonst im Datenordner dieses Rechners. Ist der Programmordner
    gerade nicht erreichbar, sammelt die App auf diesem Rechner und legt die Aufnahmen später ins Profil."""
    name = ACTIVE if name is None else name
    if not name:
        return DIR / VOICE
    if OFFLINE or profile_root() is None:
        return DIR / COPIES / name / VOICE
    return profile_root() / name / VOICE


def voice_sync(name: str) -> int:
    """Aufnahmen, die ohne Programmordner auf diesem Rechner gesammelt wurden, ins Profil legen."""
    here, there, moved = DIR / COPIES / name / VOICE, profile_root() / name / VOICE, 0
    try:
        for index in sorted(here.rglob("index.jsonl")) if here.is_dir() else []:
            target = there / index.parent.relative_to(here)
            target.mkdir(parents=True, exist_ok=True)
            lines = []
            for line in index.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                    audio = Path(row["audio"]).name
                except (ValueError, KeyError, TypeError):
                    continue
                source = index.parent / audio
                if not source.is_file():
                    continue
                stem, n = Path(audio).stem, 1
                while (target / audio).exists():                 # derselbe Name ist im Profil schon vergeben
                    if (target / audio).read_bytes() == source.read_bytes():
                        break
                    n += 1
                    audio = f"{stem}-{n}.wav"
                else:
                    shutil.copyfile(source, target / audio)
                    lines.append(json.dumps(dict(row, audio=audio), ensure_ascii=False))
            if lines:
                with open(target / "index.jsonl", "a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                moved += len(lines)
        if here.is_dir():
            shutil.rmtree(here, ignore_errors=True)
    except OSError:
        pass
    return moved


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
        if ACTIVE:
            _write(target, _whole())             # mit dem, was im gewählten Profil steht
        else:
            shutil.copyfile(FILE, target)
        for old in sorted(folder.glob("einstellungen-*.json"))[:-10]:
            old.unlink()
        return target
    except OSError:
        logging.exception("Sicherung der Einstellungen fehlgeschlagen")
        return None


PROFILE = ".lsprofil"          # Profil: Einstellungen und Stimmaufnahmen in einer Datei (ein ZIP)
SETTINGS = "einstellungen.json"
VOICE = "training"


def export(path) -> int:
    """Einstellungen an einen frei gewählten Ort schreiben. Endet der Name auf .lsprofil, kommen die Stimmaufnahmen des
    Stimmtrainings (Übungs- und Prüfsätze) mit in die Datei. Gibt die Zahl der Aufnahmen zurück. API-Schlüssel sind nie dabei."""
    text = json.dumps(_whole(), indent=2, ensure_ascii=False)
    if not str(path).lower().endswith(PROFILE):
        Path(path).write_text(text, encoding="utf-8")
        return 0
    import zipfile
    count, voice = 0, voice_dir()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(SETTINGS, text)
        for f in sorted(voice.rglob("*")) if voice.is_dir() else []:
            if f.is_file() and f.suffix in (".wav", ".jsonl"):
                z.write(f, f"{VOICE}/{f.relative_to(voice).as_posix()}")
                count += f.suffix == ".wav"
    return count


def _voice_in(z) -> int:
    """Stimmaufnahmen aus einem Profil dazulegen: Vorhandene Dateien bleiben, das Verzeichnis wird ergänzt."""
    count = 0
    names = [n for n in z.namelist() if n.startswith(VOICE + "/") and ".." not in n and not n.endswith("/")]
    for name in (n for n in names if n.endswith(".jsonl")):
        folder = voice_dir() / Path(name).parent.relative_to(VOICE)
        folder.mkdir(parents=True, exist_ok=True)
        new = []
        for line in z.read(name).decode("utf-8", "replace").splitlines():
            try:
                audio = Path(json.loads(line)["audio"]).name
            except (ValueError, KeyError, TypeError):
                continue
            source = f"{Path(name).parent.as_posix()}/{audio}"
            if source in names and not (folder / audio).exists():
                (folder / audio).write_bytes(z.read(source))
                new.append(line)
        if new:
            with open(folder / Path(name).name, "a", encoding="utf-8") as f:
                f.write("\n".join(new) + "\n")
            count += len(new)
    return count


def restore(path) -> dict:
    """Einstellungen (oder ein Profil mit Stimmaufnahmen) aus einer gesicherten Datei zurückholen. Die bisherigen
    Einstellungen werden vorher gesichert; vorhandene Stimmaufnahmen bleiben und werden ergänzt."""
    import zipfile
    profile = None
    try:
        if zipfile.is_zipfile(path):
            profile = zipfile.ZipFile(path)
            stored = json.loads(profile.read(SETTINGS).decode("utf-8-sig"))
        else:
            stored = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, KeyError) as e:
        raise ValueError(f"Die Datei lässt sich nicht lesen ({e}).") from e
    if not isinstance(stored, dict) or not ({"hotkey_hold", "dictionary", "llm"} & set(stored)):
        raise ValueError("Das ist keine Einstellungsdatei von LocalScribe.")
    backup("vor-zurueckholen")
    active, own = ACTIVE, _read(FILE) or {}
    on_disk = dict(stored)
    on_disk["profile_name"] = active             # eine gesicherte Datei wählt kein Profil; das gewählte bleibt
    if active:                                   # die persönlichen Teile gehen ins gewählte Profil, nicht in „Dieser Rechner“
        on_disk = {k: v for k, v in on_disk.items() if k not in PERSONAL}
        on_disk.update({k: own[k] for k in PERSONAL if k in own})
    _write(FILE, on_disk)
    cfg = load()
    if active and ACTIVE == active:
        cfg.update({k: copy.deepcopy(stored[k]) for k in PERSONAL if k in stored})
        save(cfg)
    if profile is not None:
        with profile:
            cfg["_voice"] = _voice_in(profile)        # nur für die Meldung, wird nicht gespeichert
    return cfg


def prompt_by_name(cfg: dict, name: str):
    for p in cfg.get("prompts") or []:
        if p.get("name") == name:
            return p
    return None
