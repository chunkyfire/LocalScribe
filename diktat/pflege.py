"""Aktualisieren und Entfernen ohne Installationsprogramm und ohne Adminrechte.

Ein laufendes Programm kann seinen eigenen Ordner weder ersetzen noch löschen. LocalScribe legt deshalb ein kleines
Skript in den Temp-Ordner, beendet sich, und das Skript erledigt den Rest, sobald die Dateien frei sind. Einstellungen,
Verlauf und Sprachmodelle im Benutzerkonto bleiben bei einem Update unberührt.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from . import config

EXE = "LocalScribe.exe"
FAILED = "update-fehlgeschlagen"       # legt das Skript in den Datenordner, wenn der alte Ordner nicht frei wurde
HEAD = "@echo off\r\nchcp 65001 >nul\r\n"
WAIT = "ping -n 2 127.0.0.1 >nul\r\n"   # eine Sekunde; „timeout“ verweigert ohne Konsole den Dienst


def program():
    """Ordner der gepackten App; None, wenn sie aus dem Quelltext läuft (dann gibt es nichts zu ersetzen)."""
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else None


def blocked(prog: Path) -> str:
    """Leer, wenn sich der Programmordner ersetzen und löschen lässt; sonst der Grund in einem Satz.

    Netzwerkordner erlauben oft das Anlegen, aber nicht das Löschen oder Umbenennen. Das merkt man besser vorher."""
    probe = prog.parent / f".localscribe-probe-{os.getpid()}"
    try:
        probe.mkdir()
        moved = probe.rename(probe.with_name(probe.name + "-2"))
        moved.rmdir()
        inner = prog / ".schreibtest"
        inner.write_text("", encoding="utf-8")
        inner.unlink()
        return ""
    except OSError as e:
        for left in (probe, probe.with_name(probe.name + "-2")):
            try:
                left.rmdir()
            except OSError:
                pass
        return (f"In {prog.parent} darf dieses Konto keine Ordner ändern oder löschen ({e.strerror or e}). "
                "Das ist bei Netzwerkordnern häufig so.")


def _run(script: str) -> Path:
    """Skript in den Temp-Ordner schreiben und losgelöst starten (läuft weiter, wenn die App endet)."""
    fd, name = tempfile.mkstemp(suffix=".cmd", prefix="localscribe-")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(script)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(["cmd.exe", "/c", name], cwd=tempfile.gettempdir(), creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return Path(name)


def unpack(archive, prog: Path) -> Path:
    """ZIP einer LocalScribe-Fassung neben den Programmordner entpacken. Gibt den Ordner der neuen Fassung zurück."""
    try:
        z = zipfile.ZipFile(archive)
    except (OSError, zipfile.BadZipFile) as e:
        raise RuntimeError(f"Die Datei lässt sich nicht als ZIP öffnen ({e}).") from e
    with z:
        roots = {n.split("/")[0] for n in z.namelist() if n.count("/") == 1 and n.endswith("/" + EXE)}
        if len(roots) != 1:
            raise RuntimeError("Das ist kein LocalScribe-Paket: In der ZIP-Datei fehlt LocalScribe.exe.")
        root = roots.pop()
        reason = blocked(prog)
        if reason:
            raise RuntimeError(reason + " Entpacke die neue Fassung stattdessen von Hand in einen neuen Ordner.")
        new, tmp = prog.with_name(prog.name + ".neu"), prog.with_name(prog.name + ".entpackt")
        for old in (new, tmp):
            shutil.rmtree(old, ignore_errors=True)
        try:
            z.extractall(tmp)
            (tmp / root).rename(new)
        except OSError as e:
            shutil.rmtree(new, ignore_errors=True)
            raise RuntimeError(f"Entpacken fehlgeschlagen ({e.strerror or e}). Ist genug Platz im Ordner?") from e
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return new


def swap(prog: Path, new: Path, start=True) -> Path:
    """Nach dem Beenden: alten Ordner beiseite, neuen an seine Stelle, Sprachmodell mitnehmen, neu starten.

    Modelle, die das neue Paket nicht mitbringt, wandern aus dem Ordner „modelle“ der alten Fassung in die neue:
    Für ein Update genügt deshalb das kleine Paket."""
    old = prog.with_name(prog.name + ".alt")
    launch = f'start "" "{prog / EXE}"\r\n' if start else ""
    return _run(HEAD + f'''set N=0
:warten
ren "{prog}" "{old.name}" 2>nul && goto frei
set /a N+=1
if %N% geq 60 goto fehler
{WAIT}goto warten
:frei
if not exist "{new}\\modelle" mkdir "{new}\\modelle"
for /d %%D in ("{old}\\modelle\\*") do if not exist "{new}\\modelle\\%%~nxD" move "%%D" "{new}\\modelle\\" >nul
ren "{new}" "{prog.name}"
{launch}rmdir /s /q "{old}"
goto ende
:fehler
rmdir /s /q "{new}"
echo x> "{config.DIR / FAILED}"
{launch}:ende
del "%~f0"
''')


def failed() -> bool:
    """Hat das letzte Update nicht geklappt? Die Markierung wird dabei gelöscht."""
    mark = config.DIR / FAILED
    try:
        mark.unlink()
        return True
    except OSError:
        return False


def remove(prog, data: bool) -> Path:
    """Nach dem Beenden: Programmordner löschen, auf Wunsch auch den Datenordner im Benutzerkonto."""
    lines = HEAD
    if prog:
        lines += f'''set N=0
:warten
rmdir /s /q "{prog}" 2>nul
if not exist "{prog}" goto frei
set /a N+=1
if %N% geq 60 goto frei
{WAIT}goto warten
:frei
'''
    if data:
        lines += f'rmdir /s /q "{config.DIR}"\r\n'
    return _run(lines + 'del "%~f0"\r\n')
