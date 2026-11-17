"""Aktualisieren und Entfernen ohne Installationsprogramm und ohne Adminrechte.

Ein Update ersetzt nichts: Die neue Fassung kommt in einen eigenen Ordner (fassungen\\<Nummer>), danach nennt
aktuell.txt ihre Nummer. Die LocalScribe.exe im Programmordner startet beim nächsten Mal diese Fassung (siehe ort.py).
Wer gerade diktiert, arbeitet mit seiner Fassung weiter, auch auf anderen Rechnern am selben Laufwerk. Ältere Ordner
verschwinden, sobald niemand mehr daraus arbeitet. Einstellungen, Verlauf und Sprachmodelle bleiben unberührt.

Nur das Entfernen braucht noch ein kleines Skript im Temp-Ordner: Ein laufendes Programm kann seinen eigenen Ordner
nicht löschen.
"""
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
import zlib
from pathlib import Path

from . import __version__, config, ort
from .ort import EXE, number

VERSION_FILE = "fassung.txt"           # im Paket: die Nummer der Fassung
NOTES = "NEUES.txt"                    # im Paket: was sich mit jeder Fassung geändert hat
# Die Skripte enthalten nur ASCII; alle Pfade kommen als Umgebungsvariablen (LS_…). In einer Batchdatei selbst
# gehen Umlaute je nach Codepage kaputt („Oberärzte“ wurde zu „OberÃ¤rzte“, der Ordner nicht gefunden).
HEAD = "@echo off\r\n"
WAIT = "ping -n 2 127.0.0.1 >nul\r\n"   # eine Sekunde; „timeout“ verweigert ohne Konsole den Dienst


def program():
    """Der Programmordner; None, wenn LocalScribe aus dem Quelltext läuft (dann gibt es nichts zu aktualisieren)."""
    return ort.root()


def readonly(prog: Path) -> str:
    """Leer, wenn dieses Konto im Programmordner neue Fassungen anlegen darf; sonst der Grund in einem Satz."""
    try:
        (prog / ort.VERSIONS).mkdir(exist_ok=True)
        probe = prog / ort.VERSIONS / f".schreibtest-{os.getpid()}"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return ""
    except OSError as e:
        return (f"Diese Installation wird zentral gepflegt: In {prog} darf dieses Konto nichts anlegen "
                f"({e.strerror or e}). Aktualisieren kann, wer dort schreiben darf. LocalScribe übernimmt die neue "
                "Fassung dann auf jedem Rechner beim nächsten Start von selbst.")


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


def _slot(prog: Path, version: str) -> Path:
    """Ordner für eine neue Fassung. Umbenannt wird nichts: Manche Laufwerke erlauben das Anlegen, aber nicht das
    Umbenennen. Vollständig ist der Ordner erst mit der Markierung, die _finish zuletzt schreibt."""
    reason = readonly(prog)
    if reason:
        raise RuntimeError(reason)
    if not re.fullmatch(r"\d+(\.\d+){1,2}", version):
        raise RuntimeError("Dem Paket fehlt die Nummer der Fassung.")
    if number(version) <= number(__version__):
        raise RuntimeError(f"Das Paket enthält die Fassung {version}; hier läuft schon {__version__}.")
    folder = prog / ort.VERSIONS / version
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _finish(prog: Path, folder: Path, version: str):
    if not (folder / EXE).is_file():
        raise RuntimeError("Im Paket fehlt LocalScribe.exe.")
    (folder / ort.DONE).write_text(version, encoding="utf-8")
    current = prog / ort.CURRENT
    try:
        part = current.with_name(current.name + f".{os.getpid()}")
        part.write_text(version, encoding="utf-8")
        os.replace(part, current)
    except OSError:
        current.write_text(version, encoding="utf-8")       # Laufwerk ohne Umbenennen: direkt schreiben


def complete(prog: Path, version: str) -> bool:
    folder = prog / ort.VERSIONS / version
    return (folder / ort.DONE).is_file() and (folder / EXE).is_file()


def _root_in(z: zipfile.ZipFile) -> str:
    roots = {n.split("/")[0] for n in z.namelist() if n.count("/") == 1 and n.endswith("/" + EXE)}
    if len(roots) != 1:
        raise RuntimeError("Das ist kein LocalScribe-Paket: In der ZIP-Datei fehlt LocalScribe.exe.")
    return roots.pop() + "/"


def _version_in(z: zipfile.ZipFile, root: str, name: str = "") -> str:
    try:
        return z.read(root + VERSION_FILE).decode("utf-8").strip()
    except KeyError:
        found = re.search(r"LocalScribe-(\d+\.\d+\.\d+)", name)
        return found.group(1) if found else ""


def unpack(archive, prog: Path) -> str:
    """ZIP einer LocalScribe-Fassung als neue Fassung einrichten. Gibt ihre Nummer zurück.

    Sprachmodelle aus einem Komplettpaket bleiben außen vor: Die liegen schon im Programmordner oder im Konto."""
    try:
        z = zipfile.ZipFile(archive)
    except (OSError, zipfile.BadZipFile) as e:
        raise RuntimeError(f"Die Datei lässt sich nicht als ZIP öffnen ({e}).") from e
    with z:
        root = _root_in(z)
        version = _version_in(z, root, Path(str(archive)).name)
        if complete(prog, version):
            _finish(prog, prog / ort.VERSIONS / version, version)
            return version
        folder = _slot(prog, version)
        try:
            for item in z.infolist():
                rel = item.filename[len(root):]
                if not item.filename.startswith(root) or item.is_dir() or rel.startswith("modelle/"):
                    continue
                target = folder / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(item) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
        except (OSError, zipfile.BadZipFile) as e:
            raise RuntimeError(f"Entpacken fehlgeschlagen ({getattr(e, 'strerror', None) or e}). Ist genug Platz "
                               "im Ordner? Die laufende Fassung ist unverändert.") from e
        _finish(prog, folder, version)
    return version


RELEASES = "https://github.com/chunkyfire/LocalScribe/releases"
GAP = 64 * 1024        # liegen zwei geänderte Dateien im Paket so nah beieinander, kommen sie in einer Anfrage


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


def fetch(info: dict, prog: Path, progress=None, source=None, base=None):
    """Neue Fassung einrichten und dafür nur laden, was sich geändert hat. Gibt (Nummer, geladene Bytes, Zahl der
    geladenen Dateien) zurück.

    Das Inhaltsverzeichnis des Pakets nennt für jede Datei Größe und Prüfsumme. Was in der laufenden Fassung (base)
    schon genau so liegt, wird von dort kopiert; nur der Rest kommt aus dem Netz. progress(geladen, gesamt) meldet
    den Stand."""
    base = Path(base or ort.here() or prog)
    remote = source or Remote(info["url"], info["size"])
    try:
        z = zipfile.ZipFile(remote)
        root = _root_in(z)
        version = _version_in(z, root, info.get("url", "")) or info.get("version", "")
        if complete(prog, version):
            _finish(prog, prog / ort.VERSIONS / version, version)
            return version, 0, 0
        new = _slot(prog, version)
        files = sorted((i for i in z.infolist() if i.filename.startswith(root) and not i.is_dir()),
                       key=lambda i: i.header_offset)
        ends = [i.header_offset for i in files[1:]] + [z.start_dir]
        todo = []                                        # (Eintrag, Ende seiner Daten im Paket)
        for item, end in zip(files, ends):
            rel = item.filename[len(root):]
            if rel.startswith("modelle/"):
                continue
            have, target = base / rel, new / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file() and target.stat().st_size == item.file_size and _crc(target) == item.CRC:
                continue                                 # liegt schon da (abgebrochenes Update)
            if have.is_file() and have.stat().st_size == item.file_size and _crc(have) == item.CRC:
                shutil.copyfile(have, target)
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
        _finish(prog, new, version)
        return version, getattr(remote, "loaded", total), len(todo)
    except (OSError, zipfile.BadZipFile, urllib.error.URLError) as e:
        raise RuntimeError(f"Das Update ließ sich nicht laden ({getattr(e, 'reason', None) or e}). Die laufende "
                           "Fassung ist unverändert. Später noch einmal versuchen oder die ZIP-Datei von Hand "
                           "laden.") from e


def pending() -> str:
    """Nummer einer eingerichteten Fassung, die neuer ist als die laufende; sonst leer."""
    prog = program()
    pick = ort.chosen(prog, __version__) if prog else None
    return pick[0] if pick else ""


def restart():
    """Die EXE im Programmordner starten; sie übergibt an die aktuelle Fassung. Der Aufrufer beendet sich danach."""
    prog = program()
    subprocess.Popen([str(prog / EXE), "--nach-update"], cwd=str(prog), close_fds=True)


def tidy(prog=None) -> list:
    """Ordner älterer Fassungen löschen, aus denen niemand mehr arbeitet. Gibt die gelöschten Nummern zurück.

    Probe ist das Umbenennen: Solange irgendwo eine LocalScribe.exe aus dem Ordner läuft, verweigert Windows das.
    Erst danach wird gelöscht; so verliert kein laufendes Programm Dateien."""
    prog = prog or program()
    if not prog or not (prog / ort.VERSIONS).is_dir():
        return []
    pick = ort.chosen(prog, "0")
    keep = number(pick[0]) if pick else ()
    mine = ort.here()
    gone = []
    for folder in (prog / ort.VERSIONS).iterdir():
        if not folder.is_dir():
            continue
        if folder.name.endswith(".weg"):
            shutil.rmtree(folder, ignore_errors=True)
            continue
        if not re.fullmatch(r"\d+(\.\d+){1,2}", folder.name) or not keep or number(folder.name) >= keep:
            continue
        if mine and folder.resolve() == mine.resolve():
            continue
        away = folder.with_name(folder.name + ".weg")
        try:
            folder.rename(away)
        except OSError:
            continue                                     # wird noch benutzt, oder das Laufwerk erlaubt es nicht
        shutil.rmtree(away, ignore_errors=True)
        gone.append(folder.name)
    return gone


def plain(markdown: str) -> str:
    """RELEASE_NOTES.md als schlichter Text: „LocalScribe 1.2.0“ als Zeile, darunter die Punkte."""
    text = re.sub(r"^##\s+", "", markdown, flags=re.M)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S)
    return text.replace("`", "")


def sections(text: str, since: str = "", upto: str = "") -> list:
    """[(Nummer, Text)] der Fassungen, die neuer sind als since und höchstens upto; neueste zuerst."""
    parts = re.split(r"^LocalScribe (\d+\.\d+\.\d+)[ \t]*$", text, flags=re.M)
    out = []
    for version, body in zip(parts[1::2], parts[2::2]):
        if (not since or number(version) > number(since)) and (not upto or number(version) <= number(upto)):
            out.append((version, re.sub(r"\s*\n[ \t]+", " ", body).strip()))
    return out


def notes(since: str = "", version: str = "") -> list:
    """Änderungen aus der eingerichteten Fassung version (sonst der laufenden), neuer als since."""
    prog = program()
    if prog is None:
        path = Path(__file__).resolve().parent.parent / "RELEASE_NOTES.md"
    elif version and version != __version__:
        path = prog / ort.VERSIONS / version / NOTES
    else:
        path = ort.here() / NOTES
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return sections(plain(text), since, version or __version__)


def remote_notes(info: dict, source=None) -> list:
    """Änderungen der Fassung bei GitHub, gelesen aus dem Paket selbst (eine kleine Datei, kein ganzer Download)."""
    try:
        z = zipfile.ZipFile(source or Remote(info["url"], info["size"]))
        return sections(z.read(_root_in(z) + NOTES).decode("utf-8"), __version__, info.get("version", ""))
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, urllib.error.URLError, UnicodeDecodeError):
        return []


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
