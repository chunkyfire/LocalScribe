"""Sprachmodelle: einmal laden, dann für immer behalten.

Gesucht wird in dieser Reihenfolge, und nur wenn nirgends etwas liegt, wird heruntergeladen:
  1. Ordner „modelle“ neben dem Programm (so lässt sich LocalScribe samt Modell auf einen Rechner
     ohne Internet kopieren),
  2. der in den Einstellungen angegebene Modellordner (ein gemeinsamer Ort für viele Programmordner),
  3. Ordner „modelle“ eine Ebene über dem Programmordner (dasselbe ganz ohne Einstellung: mehrere
     Programmordner nebeneinander teilen sich ein „modelle“),
  4. der Datenordner (hierhin wird heruntergeladen; ohne Adminrechte beschreibbar),
  5. der allgemeine Hugging-Face-Zwischenspeicher (frühere Fassungen haben dort abgelegt).
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
extra = ""               # Modellordner aus den Einstellungen (cfg["model_dir"]); setzt die App beim Laden


def folder() -> Path:
    return config.DIR / "modelle"


def _name(repo: str, revision: str) -> str:
    return repo.replace("/", "--") + "--" + revision[:12]


def _mark(patterns) -> str:
    """Name der Fertig-Markierung. Hängt an den Dateimustern: Wer dasselbe Modell in anderer Rechengenauigkeit
    lädt, bekommt eine eigene Markierung, damit ein halber Ordner nie als vollständig gilt."""
    import hashlib
    return MARK + "-" + hashlib.md5("|".join(sorted(patterns)).encode()).hexdigest()[:8]


def _beside() -> Path:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    return base / "modelle"


def places():
    """Alle Ordner, in denen fertige Modelle liegen können, in Suchreihenfolge."""
    beside = _beside()
    out = [beside]
    if extra:
        out.append(Path(extra))
    if getattr(sys, "frozen", False):
        out.append(beside.parent.parent / "modelle")
    out.append(folder())
    return out


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
    for base in places():
        path = base / _name(repo, revision)
        if (path / _mark(patterns)).exists():
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
    (target / _mark(patterns)).write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
    if progress:
        progress(total, total)
    return str(target)


def find_release(release: dict):
    """Pfad eines schon geladenen Modells aus einem GitHub-Release oder None."""
    for base in places():
        path = base / release["name"]
        if (path / MARK).exists():
            return str(path)
    return None


def _open(request):
    """Verbindung öffnen. Erst mit den Zertifikaten von Windows (nötig hinter Klinik-Proxys, die den Verkehr
    aufbrechen), bei einem Zertifikatsfehler noch einmal mit der mitgelieferten Liste von certifi."""
    import ssl
    import urllib.error
    import urllib.request
    try:
        return urllib.request.urlopen(request, timeout=60)
    except urllib.error.URLError as e:
        if not isinstance(getattr(e, "reason", None), ssl.SSLError):
            raise
        try:
            import certifi
        except ImportError:
            raise e from None
        return urllib.request.urlopen(request, timeout=60, context=ssl.create_default_context(cafile=certifi.where()))


def fetch_release(release: dict, progress=None) -> str:
    """Modell aus einem GitHub-Release laden: {"name", "url", "files": {Dateiname: [Größe, sha256]}}.

    Jede Datei wird in eine .teil-Datei geschrieben, nach einem Abbruch dort fortgesetzt, gegen ihre
    Prüfsumme geprüft und erst dann umbenannt. progress(geladene_bytes, gesamt_bytes).
    """
    import hashlib
    import urllib.request
    path = find_release(release)
    if path:
        return path
    target = folder() / release["name"]
    target.mkdir(parents=True, exist_ok=True)
    total = sum(size for size, _ in release["files"].values())
    done = 0
    log.info("Modell %s wird nach %s heruntergeladen", release["name"], target)
    for name, (size, digest) in release["files"].items():
        final, part = target / name, target / (name + ".teil")
        if final.exists() and final.stat().st_size == size:
            done += size
            continue
        have = part.stat().st_size if part.exists() else 0
        if have > size:
            part.unlink()
            have = 0
        request = urllib.request.Request(release["url"] + name, headers={"User-Agent": "LocalScribe"})
        if have:
            request.add_header("Range", f"bytes={have}-")
        try:
            with _open(request) as response:
                if have and response.status != 206:      # Server setzt nicht fort: von vorn
                    have = 0
                with open(part, "ab" if have else "wb") as f:
                    got = have
                    while True:
                        block = response.read(1 << 20)
                        if not block:
                            break
                        f.write(block)
                        got += len(block)
                        if progress:
                            progress(done + got, total)
        except Exception as e:
            raise RuntimeError(f"Das Sprachmodell ließ sich nicht herunterladen ({e}). Bitte Internetverbindung "
                               "prüfen; beim nächsten Start geht es an derselben Stelle weiter.") from e
        h = hashlib.sha256()
        with open(part, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        if part.stat().st_size != size or h.hexdigest() != digest:
            part.unlink()
            raise RuntimeError(f"Die Datei {name} ist beschädigt angekommen und wurde verworfen. Bitte neu starten.")
        part.replace(final)
        done += size
    (target / MARK).write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
    if progress:
        progress(total, total)
    return str(target)
