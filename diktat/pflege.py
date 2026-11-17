"""Aktualisieren und Entfernen ohne Installationsprogramm und ohne Adminrechte.

Ein laufendes Programm kann seinen eigenen Ordner weder ersetzen noch löschen. LocalScribe legt deshalb ein kleines
Skript in den Temp-Ordner, beendet sich, und das Skript erledigt den Rest, sobald die Dateien frei sind. Einstellungen,
Verlauf und Sprachmodelle im Benutzerkonto bleiben bei einem Update unberührt.
"""
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
import zlib
from pathlib import Path

from . import __version__, config

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


RELEASES = "https://github.com/chunkyfire/LocalScribe/releases"
GAP = 64 * 1024        # liegen zwei geänderte Dateien im Paket so nah beieinander, kommen sie in einer Anfrage


def number(version: str) -> tuple:
    """„v1.2.10“ → (1, 2, 10), damit 1.2.10 neuer ist als 1.2.9."""
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3])


def _open(url, start=None, end=None, timeout=20):
    headers = {"User-Agent": f"LocalScribe/{__version__}", "Accept": "application/octet-stream, application/json"}
    if start is not None:
        headers["Range"] = f"bytes={start}-{end - 1}"
    request = urllib.request.Request(url, headers=headers)
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as e:
        # Windows-Zertifikatsspeicher unvollständig oder Kliniknetz mit eigener Stammstelle: wie beim Laden der
        # Modelle noch einmal mit der mitgelieferten Liste von certifi.
        if not isinstance(getattr(e, "reason", None), ssl.SSLError):
            raise
        try:
            import certifi
        except ImportError:
            raise e from None
        return urllib.request.urlopen(request, timeout=timeout,
                                      context=ssl.create_default_context(cafile=certifi.where()))


def latest() -> dict:
    """Neueste veröffentlichte Fassung bei GitHub: {"version", "url", "size", "newer"}.

    Die einzige Stelle, an der LocalScribe von sich aus nach einer neuen Fassung fragt, und nur auf Klick."""
    try:
        with _open(RELEASES + "/latest") as r:            # leitet auf …/releases/tag/v1.2.3 um
            version = r.geturl().rstrip("/").rsplit("/", 1)[-1].lstrip("v")
        if not re.fullmatch(r"\d+(\.\d+)+", version):
            raise ValueError("keine Fassung gefunden")
        url = f"{RELEASES}/download/v{version}/LocalScribe-{version}-windows.zip"
        with _open(url, 0, 1) as r:                         # ein Byte: nennt die Größe des Pakets
            size = int(r.headers.get("Content-Range", "/0").rsplit("/", 1)[-1])
    except (OSError, ValueError) as e:
        reason = getattr(e, "reason", e)
        raise RuntimeError(f"Dieser Rechner erreicht GitHub nicht ({reason}). Das ist in Kliniknetzen häufig so. Dann die "
                           "ZIP-Datei an einem anderen Rechner laden und hier über „Aus ZIP-Datei aktualisieren“ "
                           "auswählen.") from e
    if not size:
        raise RuntimeError("Bei GitHub liegt gerade kein Paket der neuesten Fassung.")
    return {"version": version, "url": url, "size": size, "newer": number(version) > number(__version__)}


class Remote:
    """Eine ZIP-Datei auf einem Server, gelesen in Ausschnitten (HTTP Range). So holt ein Update nur die Dateien,
    die sich geändert haben, und nicht das ganze Paket."""

    def __init__(self, url, size):
        self.url, self.size, self.pos, self.loaded = url, size, 0, 0
        self.start, self.data = 0, b""

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def hold(self, start, end):
        """Diesen Ausschnitt in einer Anfrage holen und bereithalten."""
        start, end = max(0, start), min(self.size, end)
        if start >= self.start and end <= self.start + len(self.data):
            return
        with _open(self.url, start, end, timeout=60) as r:
            if r.status != 206:
                raise RuntimeError("Der Server liefert keine Ausschnitte. Bitte die ZIP-Datei laden und über "
                                   "„Aus ZIP-Datei aktualisieren“ auswählen.")
            data = r.read()
        if len(data) != end - start:
            raise RuntimeError("Der Download wurde unterbrochen.")
        self.start, self.data, self.loaded = start, data, self.loaded + len(data)

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        if self.pos < self.start or self.pos + n > self.start + len(self.data):
            self.hold(self.pos, self.pos + max(n, GAP))
        at = self.pos - self.start
        self.pos += n
        return self.data[at:at + n]


def _crc(path: Path) -> int:
    crc = 0
    with open(path, "rb") as f:
        while block := f.read(1 << 20):
            crc = zlib.crc32(block, crc)
    return crc


def fetch(info: dict, prog: Path, progress=None, source=None):
    """Neue Fassung neben dem Programmordner aufbauen und dafür nur laden, was sich geändert hat.

    Das Inhaltsverzeichnis des Pakets nennt für jede Datei Größe und Prüfsumme. Was im Programmordner schon genau so
    liegt, wird von dort kopiert; nur der Rest kommt aus dem Netz. Gibt (Ordner der neuen Fassung, geladene Bytes,
    Zahl der geladenen Dateien) zurück. progress(geladen, gesamt) meldet den Stand."""
    reason = blocked(prog)
    if reason:
        raise RuntimeError(reason + " Entpacke die neue Fassung stattdessen von Hand in einen neuen Ordner.")
    remote = source or Remote(info["url"], info["size"])
    new = prog.with_name(prog.name + ".neu")
    shutil.rmtree(new, ignore_errors=True)
    try:
        z = zipfile.ZipFile(remote)
        roots = {n.split("/")[0] for n in z.namelist() if n.count("/") == 1 and n.endswith("/" + EXE)}
        if len(roots) != 1:
            raise RuntimeError("Das Paket bei GitHub ist kein LocalScribe-Paket.")
        root = roots.pop() + "/"
        files = sorted((i for i in z.infolist() if i.filename.startswith(root) and not i.is_dir()),
                       key=lambda i: i.header_offset)
        ends = [i.header_offset for i in files[1:]] + [z.start_dir]
        todo = []                                        # (Eintrag, Ende seiner Daten im Paket)
        for item, end in zip(files, ends):
            rel = item.filename[len(root):]
            have, target = prog / rel, new / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if have.is_file() and have.stat().st_size == item.file_size and _crc(have) == item.CRC:
                shutil.copy2(have, target)
            else:
                todo.append((item, end))
        total = sum(end - item.header_offset for item, end in todo)
        done, i = 0, 0
        while i < len(todo):                             # benachbarte Dateien in einer Anfrage
            j = i
            while j + 1 < len(todo) and todo[j + 1][0].header_offset - todo[j][1] <= GAP \
                    and todo[j + 1][1] - todo[i][0].header_offset <= 64 << 20:
                j += 1
            remote.hold(todo[i][0].header_offset, todo[j][1])
            for item, end in todo[i:j + 1]:
                with z.open(item) as src, open(new / item.filename[len(root):], "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)          # prüft dabei die Prüfsumme der Datei
                done += end - item.header_offset
                if progress:
                    progress(done, total)
            i = j + 1
        if not (new / EXE).is_file():
            raise RuntimeError("Im Paket fehlt LocalScribe.exe.")
        return new, getattr(remote, "loaded", total), len(todo)
    except (OSError, zipfile.BadZipFile, urllib.error.URLError) as e:
        shutil.rmtree(new, ignore_errors=True)
        raise RuntimeError(f"Das Update ließ sich nicht laden ({getattr(e, 'reason', None) or e}). Nichts wurde "
                           "verändert. Später noch einmal versuchen oder die ZIP-Datei von Hand laden.") from e
    except RuntimeError:
        shutil.rmtree(new, ignore_errors=True)
        raise


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
