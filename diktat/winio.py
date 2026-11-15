"""Windows-Anbindung: globales Tastenkürzel, Einfügen, Autostart, aktives Fenster."""
import ctypes
import logging
import os
import subprocess
import sys
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

IDLE, HOLD, LOCKED = "idle", "hold", "locked"
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
    """

    def __init__(self, holds, lock, taps, on_start, on_stop, on_cancel, on_lock, on_tap):
        self.holds = {i: {c.lower() for c in keys} for i, keys in holds.items() if keys}
        self.taps = {i: {c.lower() for c in keys} for i, keys in taps.items() if keys}
        self.lock = (lock or "").lower() or None
        self.on_start, self.on_stop, self.on_cancel = on_start, on_stop, on_cancel
        self.on_lock, self.on_tap = on_lock, on_tap
        self.state = IDLE
        self.combo = set()       # Tasten des gerade aktiven Halte-Kürzels
        self.held = set()        # gedrückte virtuelle Tasten
        self.swallowed = set()   # Tasten, deren Druck wir verschluckt haben
        self.listener = keyboard.Listener(win32_event_filter=self._filter)

    def start(self):
        self.listener.start()

    def stop(self):
        self.listener.stop()

    def reset(self):
        self.state = IDLE

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
            if self.state == HOLD and name in self.combo:
                self.state = IDLE
                self.on_stop()
            if vk in self.swallowed:
                self.swallowed.discard(vk)
                return True
        return False

    def _down(self, name, first, vk) -> bool:
        """True = Tastendruck nicht an Windows weitergeben."""
        # Kürzel-Tasten, die keine Modifikatoren sind (z. B. F7), schlucken wir selbst
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


def keep_awake(on: bool):
    """Verhindert, dass Windows während einer langen Aufnahme in den Ruhezustand geht.
    Muss aus demselben Thread ein- und ausgeschaltet werden."""
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        log.debug("Ruhezustand nicht steuerbar", exc_info=True)


def foreground_title() -> str:
    try:
        hwnd = user32.GetForegroundWindow()
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value
    except Exception:
        return ""


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


def create_shortcuts(icon: str):
    """Verknüpfungen auf dem Desktop und im Startmenü anlegen (ohne Adminrechte)."""
    exe, args, folder = launch_target()
    env = dict(os.environ, DIKTAT_EXE=exe, DIKTAT_ARGS=args, DIKTAT_DIR=folder, DIKTAT_ICON=icon)
    done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", SHORTCUT_SCRIPT],
                          env=env, capture_output=True, text=True, timeout=60,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or "PowerShell meldet einen Fehler").strip()[:200])


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
