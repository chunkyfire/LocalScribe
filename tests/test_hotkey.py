"""Tastenlogik mit simulierten Tastenereignissen prüfen (ohne echten Hook)."""
import pathlib
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from diktat import winio

down = set()
winio.is_down = lambda vk: vk in down
ev = []
failed = 0


class L:  # Listener-Attrappe
    def suppress_event(self):
        raise RuntimeError("suppress")


def make(holds, taps=None):
    h = winio.Hotkey(holds, "space", taps or {}, lambda i: ev.append("start:" + i), lambda: ev.append("stop"),
                     lambda: ev.append("cancel"), lambda: ev.append("lock"), lambda i: ev.append("tap:" + i))
    h.listener = L()
    return h


def key(h, vk, isdown, inj=False):
    r = h._handle(0x100 if isdown else 0x101, NS(vkCode=vk, flags=0x10 if inj else 0))
    (down.add if isdown else down.discard)(vk)
    return r


def run(h, name, seq, expect, sw=None):
    global failed
    ev.clear(); down.clear(); h.held.clear(); h.swallowed.clear(); h.state = "idle"
    res = [key(h, *s) for s in seq]
    ok = ev == expect and (sw is None or res == sw)
    failed += not ok
    print("OK  " if ok else "FAIL", name, "" if ok else (ev, res))


CTRL, WIN, SHIFT, SPACE, ESC, A, V, F7, F8 = 0xA2, 0x5B, 0xA0, 0x20, 0x1B, 0x41, 0x56, 0x76, 0x77
S = "start:dictate"

h = make({"dictate": ["ctrl", "win"]})
run(h, "Strg+Win halten", [(CTRL, 1), (WIN, 1), (WIN, 1), (WIN, 0), (CTRL, 0)], [S, "stop"])
run(h, "andere Reihenfolge", [(WIN, 1), (CTRL, 1), (CTRL, 0), (WIN, 0)], [S, "stop"])
run(h, "Strg+Win+A bricht ab", [(CTRL, 1), (WIN, 1), (A, 1), (A, 0), (WIN, 0), (CTRL, 0)], [S, "cancel"])
run(h, "Strg+A+Win startet nicht", [(CTRL, 1), (A, 1), (WIN, 1), (WIN, 0), (A, 0), (CTRL, 0)], [])
run(h, "Freihand", [(CTRL, 1), (WIN, 1), (SPACE, 1), (SPACE, 0), (WIN, 0), (CTRL, 0), (A, 1), (A, 0),
                    (CTRL, 1), (WIN, 1), (WIN, 0), (CTRL, 0)], [S, "lock", "stop"],
    [False, False, True, True] + [False] * 8)
run(h, "Freihand, Esc bricht ab", [(CTRL, 1), (WIN, 1), (SPACE, 1), (SPACE, 0), (WIN, 0), (CTRL, 0), (ESC, 1), (ESC, 0)],
    [S, "lock", "cancel"])
run(h, "Esc beim Halten", [(CTRL, 1), (WIN, 1), (ESC, 1), (ESC, 0), (WIN, 0), (CTRL, 0)], [S, "cancel"])
run(h, "eingespeistes Strg+V ignoriert", [(CTRL, 1, True), (V, 1, True), (V, 0, True), (CTRL, 0, True)], [])
ev.clear(); down.clear(); h.held.clear(); h.state = "idle"
key(h, WIN, 1); key(h, 0x4C, 1); down.clear()  # Win+L: Sperrbildschirm schluckt das Loslassen
key(h, CTRL, 1); key(h, WIN, 1); key(h, WIN, 0); key(h, CTRL, 0)
ok = ev == [S, "stop"]; failed += not ok
print("OK  " if ok else "FAIL", "nach Win+L wieder nutzbar")

h = make({"dictate": ["f7"], "prompt:Glätten": ["f8"]}, {"paste_last": ["shift", "f7"]})
run(h, "F7 halten (Taste wird geschluckt)", [(F7, 1), (F7, 1), (F7, 1), (F7, 0)], [S, "stop"], [True] * 4)
run(h, "F7 Freihand", [(F7, 1), (SPACE, 1), (SPACE, 0), (F7, 0), (A, 1), (A, 0), (F7, 1), (F7, 0)],
    [S, "lock", "stop"], [True, True, True, True, False, False, True, True])
run(h, "F7 + A bricht ab, F7 bleibt geschluckt", [(F7, 1), (A, 1), (F7, 1), (A, 0), (F7, 0)], [S, "cancel"],
    [True, False, True, False, True])
run(h, "Strg+F7 startet nicht", [(CTRL, 1), (F7, 1), (F7, 0), (CTRL, 0)], [], [False] * 4)
run(h, "F8 startet den Prompt", [(F8, 1), (F8, 0)], ["start:prompt:Glätten", "stop"], [True, True])
run(h, "F8 während F7 bricht ab", [(F7, 1), (F8, 1), (F8, 0), (F7, 0)], [S, "cancel"])
run(h, "Umschalt+F7 fügt letzten Text ein", [(SHIFT, 1), (F7, 1), (F7, 1), (F7, 0), (SHIFT, 0)], ["tap:paste_last"],
    [False, True, True, True, False])
ok = winio.parse_keys("Strg + Win") == ["ctrl", "win"] and winio.parse_keys("f8") == ["f8"] \
    and winio.parse_keys("") == [] and winio.parse_keys("ctrl+quatsch") is None
failed += not ok
print("OK  " if ok else "FAIL", "Tasten einlesen")

# ---- eine einzelne Modifikatortaste (Strg) als Halte-Taste: startet erst nach kurzem Halten
import time

MOUSE_LEFT = 0x01


def timed(name, steps, expect):
    """steps: (Taste, gedrückt) oder Zahl = Sekunden warten oder "klick"."""
    global failed
    h = make({"dictate": ["ctrl"]}, {"paste_last": ["shift", "f7"]})
    h.delay = 0.08
    ev.clear(); down.clear()
    for s in steps:
        if isinstance(s, (int, float)):
            time.sleep(s)
        elif s == "klick":
            down.add(MOUSE_LEFT)
        else:
            key(h, *s)
    time.sleep(0.1)
    ok = ev == expect
    failed += not ok
    print("OK  " if ok else "FAIL", name, "" if ok else ev)
    h.state = "idle"


timed("Strg halten startet nach der Wartezeit", [(CTRL, 1), 0.25, (CTRL, 0)], [S, "stop"])
timed("Strg kurz antippen startet nichts", [(CTRL, 1), 0.02, (CTRL, 0), 0.2], [])
timed("Strg+C bleibt Kopieren", [(CTRL, 1), 0.02, (A, 1), (A, 0), 0.2, (CTRL, 0)], [])
timed("Strg+Klick startet nichts", [(CTRL, 1), 0.02, "klick", 0.2, (CTRL, 0)], [])
timed("Taste während der Aufnahme bricht ab", [(CTRL, 1), 0.25, (A, 1), (A, 0), (CTRL, 0)], [S, "cancel"])
timed("Mausklick während der Aufnahme bricht ab", [(CTRL, 1), 0.25, "klick", 0.1, (CTRL, 0)], [S, "cancel"])
timed("Strg + Leertaste: Freihand", [(CTRL, 1), 0.25, (SPACE, 1), (SPACE, 0), (CTRL, 0), 0.05, (CTRL, 1), (CTRL, 0)],
      [S, "lock", "stop"])
sys.exit(1 if failed else 0)
