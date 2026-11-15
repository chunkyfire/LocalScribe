"""Sprachmodelle: einmal laden, dann für immer behalten.

Gesucht wird in dieser Reihenfolge, und nur wenn nirgends etwas liegt, wird heruntergeladen:
  1. Ordner „modelle“ neben dem Programm (so lässt sich LocalScribe samt Modell auf einen Rechner
     ohne Internet kopieren),
  2. %LOCALAPPDATA%\\LocalScribe\\modelle (hierhin wird heruntergeladen; ohne Adminrechte beschreibbar),
  3. der allgemeine Hugging-Face-Zwischenspeicher (frühere Fassungen haben dort abgelegt).
"""
import fnmatch
import logging
import os
import sys
import threading
import time
from pathlib import Path

from . import config

# Ohne Xet lädt huggingface_hub jede Datei Stück für Stück in den Zielordner. Nur so lässt sich der
# Fortschritt an der wachsenden Datei ablesen; mit Xet steht der Balken lange und springt dann.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

log = logging.getLogger("diktat")
MARK = ".vollstaendig"


def folder() -> Path:
    return config.DIR / "modelle"


def _name(repo: str, revision: str) -> str:
    return repo.replace("/", "--") + "--" + revision[:12]


def _beside() -> Path:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    return base / "modelle"


def _size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def find(repo: str, revision: str, patterns):
    """Pfad des vorhandenen Modells oder None. Geht nie ins Netz."""
    for base in (_beside(), folder()):
        path = base / _name(repo, revision)
        if (path / MARK).exists():
            return str(path)
    try:
        from huggingface_hub import snapshot_download
        return snapshot_download(repo, revision=revision, allow_patterns=patterns, local_files_only=True)
    except Exception:
        return None


def fetch(repo: str, revision: str, patterns, progress=None) -> str:
    """Pfad des Modells; lädt es beim ersten Mal herunter. progress(geladene_bytes, gesamt_bytes)."""
    path = find(repo, revision, patterns)
    if path:
        return path
    from huggingface_hub import HfApi, snapshot_download
    try:                                   # im Fensterprogramm gibt es keine Konsole für Fortschrittsbalken
        from huggingface_hub.utils import disable_progress_bars
        disable_progress_bars()
    except Exception:
        pass
    target = folder() / _name(repo, revision)
    target.mkdir(parents=True, exist_ok=True)
    log.info("Modell %s wird nach %s heruntergeladen", repo, target)
    total = 0
    try:
        info = HfApi().model_info(repo, revision=revision, files_metadata=True)
        total = sum(s.size or 0 for s in info.siblings
                    if any(fnmatch.fnmatch(s.rfilename, p) for p in patterns))
    except Exception as e:
        raise RuntimeError("Das Sprachmodell muss einmalig heruntergeladen werden, der Server ist aber nicht "
                           f"erreichbar. Bitte Internetverbindung prüfen und LocalScribe neu starten. ({e})") from e
    stop = threading.Event()

    def watch():
        while not stop.wait(0.4):
            if progress:
                progress(min(_size(target), total), total)
    if progress:
        progress(0, total)
        threading.Thread(target=watch, daemon=True).start()
    try:
        snapshot_download(repo, revision=revision, allow_patterns=patterns, local_dir=str(target))
    finally:
        stop.set()
    (target / MARK).write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
    if progress:
        progress(total, total)
    return str(target)
