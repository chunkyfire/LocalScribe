"""Windows-Anbindung: globales Tastenkürzel, Einfügen, Autostart, aktives Fenster."""
import ctypes
import logging
import os
import subprocess
import sys
import threading
import time
import winreg
from pathlib import Path

from pynput import keyboard

log = logging.getLogger("diktat")
user32 = ctypes.windll.user32

VK = {"ctrl": (0xA2, 0xA3, 0x11), "win": (0x5B, 0x5C), "alt": (0xA4, 0xA5, 0x12),
      "shift": (0xA0, 0xA1, 0x10), "space": (0x20,), "esc": (0x1B,), "tab": (0x09,),
      "capslock": (0x14,), "pause": (0x13,), "insert": (0x2D,), "menu": (0x5D,)}
for _i in range(1, 25):
    VK[f"f{_i}"] = (0x6F + _i,)
for _c in "abcdefghijklmnopqrstuvwxyz0123456789":
    VK[_c] = (ord(_c.upper()),)
NAME = {vk: name for name, vks in VK.items() for vk in vks}

IDLE, ARMED, HOLD, LOCKED = "idle", "armed", "hold", "locked"
MOUSE = (0x01, 0x02, 0x04)   # linke, rechte, mittlere Maustaste
MODS = {"ctrl", "win", "alt", "shift"}
KEYDOWN, KEYUP = (0x100, 0x104), (0x101, 0x105)
INJECTED = 0x10


def is_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


class Hotkey:
    """Globale Tastenkürzel.

    holds: {id: Tasten}  Halten = aufnehmen. Halten + Sperrtaste = Freihand.
                         Esc oder eine fremde Taste = abbrechen.
    taps:  {id: Tasten}  einmal drücken = Aktion.
    Die Callbacks laufen im Hook-Thread und müssen sofort zurückkehren.

    Besteht ein Halte-Kürzel nur aus einer Modifikatortaste (Strg allein), beginnt die Aufnahme
    erst nach `delay` Sekunden. Strg+C, Strg+Klick oder AltGr lösen so nichts aus: Jede andere
    Taste und jeder Mausklick in dieser Zeit lässt die Taste ihre gewohnte Arbeit tun.
    """

    def __init__(self, holds, lock, taps, on_start, on_stop, on_cancel, on_lock, on_tap, delay=0.3):
        self.holds = {i: {c.lower() for c in keys} for i, keys in holds.items() if keys}
        self.taps = {i: {c.lower() for c in keys} for i, keys in taps.items() if keys}
        self.lock = (lock or "").lower() or None
        self.on_start, self.on_stop, self.on_cancel = on_start, on_stop, on_cancel
        self.on_lock, self.on_tap = on_lock, on_tap
        self.delay = delay
        self.armed = 0           # Zähler: macht überholte Zeitgeber unwirksam
        self.state = IDLE
        self.combo = set()       # Tasten des gerade aktiven Halte-Kürzels
        self.held = set()        # gedrückte virtuelle Tasten
        self.swallowed = set()   # Tasten, deren Druck wir verschluckt haben
        self.capture = None      # Einstellungen: nächste Tastenkombination hierhin melden statt auswerten
        self.seen = []
        self.listener = keyboard.Listener(win32_event_filter=self._filter)

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()

    def reset(self):
        self.state = IDLE

    def grab(self, callback):
        """Die nächste gedrückte Tastenkombination an callback(Liste der Tasten) melden, statt sie auszuwerten.
        Esc meldet None (abbrechen), Entf oder Rücktaste eine leere Liste (Kürzel leeren). grab(None) beendet das."""
        self.seen = []
        self.capture = callback

    def _grab(self, msg, vk) -> bool:
        name = NAME.get(vk)
        if msg in KEYDOWN:
            self.held.add(vk)
            self.swallowed.add(vk)
            done = None
            if not self.seen and name == "esc":
                done = (None,)
            elif not self.seen and vk in (0x08, 0x2E):
                done = ([],)
            elif name and name not in self.seen:
                self.seen.append(name)
            if done:
                callback, self.capture = self.capture, None
                callback(*done)
        elif msg in KEYUP:
            self.held.discard(vk)
            self.swallowed.discard(vk)
            if self.seen and not any(NAME.get(k) in self.seen for k in self.held):
                keys = [k for k in self.seen if k in MODS] + [k for k in self.seen if k not in MODS]
                callback, self.capture, self.seen, self.state = self.capture, None, [], IDLE
                callback(keys)
        return True

    def _solo(self) -> bool:
        return len(self.combo) == 1 and self.combo <= MODS

    def _wait(self, ident, token):
        """Läuft neben dem Hook: startet die Aufnahme nach der Wartezeit, bricht bei Mausklick ab."""
        end = time.time() + self.delay
        while self.armed == token and self.state in (ARMED, HOLD):
            if any(is_down(b) for b in MOUSE):
                was, self.state = self.state, IDLE
                if was == HOLD:
                    self.on_cancel()
                return
            if self.state == ARMED and time.time() >= end:
                self.state = HOLD
                self.on_start(ident)
            elif self.state == HOLD and not any(is_down(vk) for k in self.combo for vk in VK[k]):
                self.state = IDLE     # Loslassen verpasst (Sperrbildschirm, Wettlauf mit dem Hook)
                self.on_stop()
                return
            time.sleep(0.02)

    def _names(self):
        return {NAME.get(vk, f"vk{vk}") for vk in self.held}

    def _filter(self, msg, data):
        swallow = False
        try:
            swallow = self._handle(msg, data)
        except Exception:
            log.exception("Fehler im Tastatur-Hook")
        if swallow:
            self.listener.suppress_event()
        return True

    def _handle(self, msg, data) -> bool:
        if data.flags & INJECTED:
            return False
        vk = data.vkCode
        if self.capture:
            return self._grab(msg, vk)
        name = NAME.get(vk, f"vk{vk}")
        if msg in KEYDOWN:
            # verpasste Loslass-Ereignisse (Sperrbildschirm, UAC) bereinigen
            self.held = {k for k in self.held if is_down(k)}
            first = vk not in self.held
            self.held.add(vk)
            if self._down(name, first, vk):
                self.swallowed.add(vk)
                return True
        elif msg in KEYUP:
            self.held.discard(vk)
            if self.state == ARMED and name in self.combo:
                self.state = IDLE
            elif self.state == HOLD and name in self.combo:
                self.state = IDLE
                self.on_stop()
            if vk in self.swallowed:
                self.swallowed.discard(vk)
                return True
        return False

    def _down(self, name, first, vk) -> bool:
        """True = Tastendruck nicht an Windows weitergeben."""
        # Kürzel-Tasten, die keine Modifikatoren sind (z. B. F7), schlucken wir selbst
        if self.state == ARMED:
            if name in self.combo:
                return False          # Tastenwiederholung der gehaltenen Taste
            self.state = IDLE         # andere Taste: gewöhnliches Kürzel wie Strg+C, kein Diktat
        if self.state == IDLE:
            if first:
                names = self._names()
                for ident, combo in self.taps.items():
                    if name in combo and names == combo:
                        self.on_tap(ident)
                        return name not in MODS
                for ident, combo in self.holds.items():
                    if name in combo and names == combo:
                        self.combo = combo
                        if self._solo() and self.delay > 0:
                            self.state = ARMED
                            self.armed += 1
                            threading.Thread(target=self._wait, args=(ident, self.armed), daemon=True).start()
                            return False
                        self.state = HOLD
                        self.on_start(ident)
                        return name not in MODS
            return vk in self.swallowed  # Wiederholungen einer geschluckten Taste
        own = name in self.combo and name not in MODS
        if self.state == HOLD:
            if name == self.lock:
                if first:
                    self.state = LOCKED
                    self.on_lock()
                return True
            if name not in self.combo and first:
                self.state = IDLE
                self.on_cancel()
                return False
            return own
        if self.state == LOCKED:
            if name == "esc":
                self.state = IDLE
                self.on_cancel()
                return True
            if name == self.lock:
                return True
            if first and name in self.combo and self.combo <= self._names():
                self.state = IDLE
                self.on_stop()
            return own
        return False


def parse_keys(text: str):
    """"strg+win" -> ["ctrl", "win"]; None bei unbekannter Taste."""
    alias = {"strg": "ctrl", "control": "ctrl", "windows": "win", "umschalt": "shift",
             "leertaste": "space", "leer": "space", "escape": "esc"}
    keys = []
    for part in text.replace(" ", "").lower().split("+"):
        if not part:
            continue
        part = alias.get(part, part)
        if part not in VK:
            return None
        if part not in keys:
            keys.append(part)
    return keys


_kb = keyboard.Controller()
MODIFIERS = (0x11, 0x12, 0x10, 0x5B, 0x5C)


def modifiers_down() -> bool:
    return any(is_down(vk) for vk in MODIFIERS)


def send_paste():
    with _kb.pressed(keyboard.Key.ctrl):
        _kb.press("v")
        _kb.release("v")


def send_field(move: int, length: int):
    """Cursor um move Zeichen bewegen (negativ: nach links), dann length Zeichen markieren und löschen."""
    key = keyboard.Key.right if move > 0 else keyboard.Key.left
    for _ in range(abs(move)):
        _kb.press(key)
        _kb.release(key)
    if length:
        with _kb.pressed(keyboard.Key.shift):
            for _ in range(length):
                _kb.press(keyboard.Key.right)
                _kb.release(keyboard.Key.right)
        _kb.press(keyboard.Key.delete)
        _kb.release(keyboard.Key.delete)


def keep_awake(on: bool):
    """Verhindert, dass Windows während einer langen Aufnahme in den Ruhezustand geht.
    Muss aus demselben Thread ein- und ausgeschaltet werden."""
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        log.debug("Ruhezustand nicht steuerbar", exc_info=True)


def foreground() -> int:
    try:
        return int(user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


def window_title(hwnd: int) -> str:
    try:
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value
    except Exception:
        return ""


def window_alive(hwnd: int) -> bool:
    try:
        return bool(hwnd and user32.IsWindow(hwnd))
    except Exception:
        return False


def focus(hwnd: int) -> bool:
    """Fenster nach vorn holen (Zielfenster). Windows erlaubt das nur dem Vordergrundprozess; deshalb hängt sich
    der eigene Thread kurz an die Eingabe des Fensters, das gerade vorn ist."""
    try:
        if user32.GetForegroundWindow() == hwnd:
            return True
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)                      # SW_RESTORE
        me = ctypes.windll.kernel32.GetCurrentThreadId()
        front = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        joined = bool(front and front != me and user32.AttachThreadInput(me, front, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if joined:
                user32.AttachThreadInput(me, front, False)
        return user32.GetForegroundWindow() == hwnd
    except Exception:
        log.exception("Zielfenster nicht ansteuerbar")
        return False


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_app_id():
    """Eigene Taskleisten-Identität (sonst zeigt Windows das Python-Symbol)."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("cemmec.LocalScribe")
    except Exception:
        log.debug("AppUserModelID nicht setzbar", exc_info=True)


def allow_foreground():
    """Einer schon laufenden Instanz erlauben, ihr Fenster nach vorn zu holen."""
    try:
        user32.AllowSetForegroundWindow(-1)
    except Exception:
        pass


def launch_target():
    """(Programm, Argumente, Arbeitsordner) – als gebaute EXE oder aus dem Quellordner."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        return str(exe), "", str(exe.parent)
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    launcher = Path(__file__).resolve().parent.parent / "run.pyw"
    return str(pyw if pyw.exists() else exe), f'"{launcher}"', str(launcher.parent)


def _launch_command() -> str:
    exe, args, _ = launch_target()
    return " ".join(part for part in (f'"{exe}"', args, "--hidden") if part)


SHORTCUT_SCRIPT = """
$ws = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $l = $ws.CreateShortcut((Join-Path $dir 'LocalScribe.lnk'))
    $l.TargetPath = $env:DIKTAT_EXE
    $l.Arguments = $env:DIKTAT_ARGS
    $l.WorkingDirectory = $env:DIKTAT_DIR
    $l.IconLocation = $env:DIKTAT_ICON + ',0'
    $l.Description = 'LocalScribe - lokales Diktieren'
    $l.Save()
}
"""


def others(name=None):
    """Andere laufende Programme gleichen Namens in dieser Windows-Sitzung: [(Prozessnummer, Pfad der exe)].
    So findet LocalScribe eine Fassung, die aus einem anderen Ordner läuft (nach einem Update von Hand, über eine
    alte Verknüpfung oder den Autostart) und dessen Ordner festhält."""
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.OpenProcess.restype = wintypes.HANDLE
    name = (name or Path(sys.executable).name).lower()
    me, session, found = os.getpid(), wintypes.DWORD(), []
    k32.ProcessIdToSessionId(me, ctypes.byref(session))
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)          # TH32CS_SNAPPROCESS
    entry = Entry()
    entry.dwSize = ctypes.sizeof(Entry)
    more = k32.Process32FirstW(wintypes.HANDLE(snap), ctypes.byref(entry))
    while more:
        pid = entry.th32ProcessID
        if pid != me and entry.szExeFile.lower() == name:
            theirs = wintypes.DWORD()
            k32.ProcessIdToSessionId(pid, ctypes.byref(theirs))
            handle = k32.OpenProcess(0x1000, False, pid)     # PROCESS_QUERY_LIMITED_INFORMATION
            if handle and theirs.value == session.value:
                buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
                if k32.QueryFullProcessImageNameW(wintypes.HANDLE(handle), 0, buf, ctypes.byref(size)):
                    found.append((pid, buf.value))
            if handle:
                k32.CloseHandle(wintypes.HANDLE(handle))
        more = k32.Process32NextW(wintypes.HANDLE(snap), ctypes.byref(entry))
    k32.CloseHandle(wintypes.HANDLE(snap))
    return found


def end(pids, wait=8.0) -> bool:
    """Prozesse beenden und warten, bis sie weg sind (ihre Dateien sind dann wieder frei)."""
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wintypes.HANDLE
    handles = []
    for pid in pids:
        handle = k32.OpenProcess(0x100001, False, pid)       # SYNCHRONIZE | PROCESS_TERMINATE
        if handle:
            k32.TerminateProcess(wintypes.HANDLE(handle), 0)
            handles.append(handle)
    gone = True
    for handle in handles:
        gone = k32.WaitForSingleObject(wintypes.HANDLE(handle), int(wait * 1000)) == 0 and gone
        k32.CloseHandle(wintypes.HANDLE(handle))
    return gone and len(handles) == len(pids)


FOLLOW_SCRIPT = """
$ws = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $p = Join-Path $dir 'LocalScribe.lnk'
    if (Test-Path $p) {
        $l = $ws.CreateShortcut($p)
        if ($l.TargetPath -ne $env:DIKTAT_EXE) {
            $l.TargetPath = $env:DIKTAT_EXE
            $l.Arguments = $env:DIKTAT_ARGS
            $l.WorkingDirectory = $env:DIKTAT_DIR
            $l.Save()
        }
    }
}
"""


def follow():
    """Autostart und vorhandene Verknüpfungen auf den Ordner zeigen lassen, aus dem die App gerade läuft. Sonst
    startet nach einem Umzug oder Update von Hand weiter die alte Fassung und hält ihren Ordner fest."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as k:
            if winreg.QueryValueEx(k, "LocalScribe")[0] != _launch_command():
                winreg.SetValueEx(k, "LocalScribe", 0, winreg.REG_SZ, _launch_command())
    except OSError:
        pass                                  # kein Autostart eingerichtet
    exe, args, folder = launch_target()
    env = dict(os.environ, DIKTAT_EXE=exe, DIKTAT_ARGS=args, DIKTAT_DIR=folder)
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", FOLLOW_SCRIPT],
                       env=env, capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        log.exception("Verknüpfungen nicht prüfbar")


def create_shortcuts(icon: str):
    """Verknüpfungen auf dem Desktop und im Startmenü anlegen (ohne Adminrechte)."""
    exe, args, folder = launch_target()
    env = dict(os.environ, DIKTAT_EXE=exe, DIKTAT_ARGS=args, DIKTAT_DIR=folder, DIKTAT_ICON=icon)
    done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", SHORTCUT_SCRIPT],
                          env=env, capture_output=True, text=True, timeout=60,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or "PowerShell meldet einen Fehler").strip()[:200])


def remove_shortcuts():
    """Verknüpfungen auf dem Desktop und im Startmenü wieder entfernen."""
    script = ("foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) "
              "{ Remove-Item (Join-Path $d 'LocalScribe.lnk') -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                   capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)


def autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, "LocalScribe")
        return True
    except OSError:
        return False


def set_autostart(on: bool):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "LocalScribe", 0, winreg.REG_SZ, _launch_command())
        else:
            try:
                winreg.DeleteValue(k, "LocalScribe")
            except OSError:
                pass
