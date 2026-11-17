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
# Die Skripte enthalten nur ASCII; alle Pfade kommen als Umgebungsvariablen (LS_…). In einer Batchdatei selbst
# gehen Umlaute je nach Codepage kaputt („Oberärzte“ wurde zu „OberÃ¤rzte“, der Ordner nicht gefunden).
HEAD = "@echo off\r\n"
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


def _run(script: str, **paths) -> Path:
    """Skript in den Temp-Ordner schreiben und unsichtbar starten (läuft weiter, wenn die App endet).

    Nur CREATE_NO_WINDOW: Das gibt dem Skript eine versteckte Konsole, die auch seine Hilfsprogramme benutzen.
    Mit DETACHED_PROCESS hätte es gar keine, und jedes „ping“ der Warteschleife öffnete ein eigenes Fenster."""
    assert script.isascii(), "Pfade gehören in die Umgebung, nicht ins Skript"
    fd, name = tempfile.mkstemp(suffix=".cmd", prefix="localscribe-")
    with os.fdopen(fd, "w", encoding="ascii", newline="") as f:
        f.write(script)
    env = dict(os.environ, **{key: str(value) for key, value in paths.items()})
    subprocess.Popen(["cmd.exe", "/c", name], cwd=tempfile.gettempdir(), env=env, close_fds=True,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
    Für ein Update genügt deshalb das kleine Paket. Ein Ordner „daten“ (eigene Daten im Programmordner) zieht mit."""
    old = prog.with_name(prog.name + ".alt")
    launch = 'start "" "%LS_PROG%\\%LS_EXE%"\r\n' if start else ""
    return _run(HEAD + f'''set N=0
:warten
ren "%LS_PROG%" "%LS_OLDNAME%" 2>nul && goto frei
set /a N+=1
if %N% geq 60 goto fehler
{WAIT}goto warten
:frei
if not exist "%LS_NEW%\\modelle" mkdir "%LS_NEW%\\modelle"
for /d %%D in ("%LS_OLD%\\modelle\\*") do if not exist "%LS_NEW%\\modelle\\%%~nxD" move "%%D" "%LS_NEW%\\modelle\\" >nul
if exist "%LS_OLD%\\%LS_DATA%" move "%LS_OLD%\\%LS_DATA%" "%LS_NEW%\\%LS_DATA%" >nul
ren "%LS_NEW%" "%LS_NAME%"
{launch}rmdir /s /q "%LS_OLD%"
goto ende
:fehler
rmdir /s /q "%LS_NEW%"
echo x> "%LS_FAILED%"
{launch}:ende
del "%~f0"
'''.replace("\n", "\r\n").replace("\r\r\n", "\r\n"),
                LS_PROG=prog, LS_NEW=new, LS_OLD=old, LS_OLDNAME=old.name, LS_NAME=prog.name, LS_EXE=EXE,
                LS_DATA=config.PORTABLE, LS_FAILED=config.DIR / FAILED)


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
rmdir /s /q "%LS_PROG%" 2>nul
if not exist "%LS_PROG%" goto frei
set /a N+=1
if %N% geq 60 goto frei
{WAIT}goto warten
:frei
'''
    if data:
        lines += 'rmdir /s /q "%LS_DIR%"\n'
    lines += 'del "%~f0"\n'
    return _run(lines.replace("\n", "\r\n").replace("\r\r\n", "\r\n"), LS_PROG=prog or "", LS_DIR=config.DIR)
