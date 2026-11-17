"""Wo das Programm liegt. Bewusst ohne weitere Importe: run.pyw fragt hier nach, bevor irgendetwas Schweres lädt.

Aufbau des Programmordners ab 1.2.0:

    LocalScribe\\LocalScribe.exe            die Fassung, die einmal entpackt wurde; sie startet immer
    LocalScribe\\aktuell.txt                Nummer der Fassung, die laufen soll
    LocalScribe\\fassungen\\1.2.1\\…         jede spätere Fassung in einem eigenen Ordner
    LocalScribe\\modelle, LocalScribe\\daten gehören allen Fassungen

Ein Update legt nur einen neuen Ordner an und ändert danach aktuell.txt. Keine Datei, die gerade jemand benutzt,
wird angefasst; deshalb geht das auch, wenn LocalScribe von einem gemeinsamen Laufwerk auf vielen Rechnern läuft.
"""
import re
import sys
from pathlib import Path

EXE = "LocalScribe.exe"
VERSIONS = "fassungen"
CURRENT = "aktuell.txt"
DONE = ".vollstaendig"


def number(version: str) -> tuple:
    """„v1.2.10“ → (1, 2, 10), damit 1.2.10 neuer ist als 1.2.9."""
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3])


def here():
    """Ordner der laufenden Fassung; None, wenn sie aus dem Quelltext läuft."""
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else None


def root_of(folder: Path) -> Path:
    """Programmordner zu einem Ordner, in dem eine LocalScribe.exe liegt."""
    folder = Path(folder)
    return folder.parent.parent if folder.parent.name.lower() == VERSIONS else folder


def root():
    """Der Programmordner, gleich welche Fassung daraus gerade läuft; None im Quelltext."""
    folder = here()
    return root_of(folder) if folder else None


def chosen(base: Path, newer_than: str):
    """Die Fassung, die laut aktuell.txt laufen soll: (Nummer, Ordner) oder None.

    Zählt nur, wenn sie neuer ist als newer_than und ihr Ordner vollständig ist. Fehlt aktuell.txt oder nennt sie
    etwas Unbrauchbares, läuft die Fassung im Programmordner selbst; so kommt man mit dem Löschen der Datei zurück."""
    try:
        version = (base / CURRENT).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not re.fullmatch(r"\d+(\.\d+){1,2}", version) or number(version) <= number(newer_than):
        return None
    folder = base / VERSIONS / version
    if (folder / DONE).is_file() and (folder / EXE).is_file():
        return version, folder
    return None


def handover(own: str):
    """Start aus dem Programmordner: Gibt es eine neuere eingerichtete Fassung, diese starten.

    Gibt True zurück, wenn übergeben wurde; der Aufrufer beendet sich dann."""
    folder = here()
    if folder is None or folder.parent.name.lower() == VERSIONS:
        return False
    pick = chosen(folder, own)
    if not pick:
        return False
    import subprocess
    try:
        subprocess.Popen([str(pick[1] / EXE)] + sys.argv[1:], cwd=str(folder), close_fds=True)
    except OSError:
        return False                      # Ordner beschädigt oder gesperrt: lieber die eigene Fassung als gar keine
    return True
