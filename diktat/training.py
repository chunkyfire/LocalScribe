"""Stimmtraining: vorgegebene Sätze vorlesen, die App lernt daraus.

Der gelesene Satz ist bekannt. Was die Erkennung stattdessen schreibt, wird Wort für Wort daneben
gelegt. Ein falsch erkanntes Wort kommt ins persönliche Wörterbuch, wenn es dem richtigen ähnlich
klingt und selbst kein echtes Wort ist. So kann das Training nie dafür sorgen, dass später ein
richtig erkanntes Alltagswort ersetzt wird.
"""
import difflib
import json
import re
from pathlib import Path

from . import fach

FILE = Path(__file__).with_name("lesetexte.json")
TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß]+|\d+")
SOUND = 0.55            # so ähnlich müssen sich Gehörtes und Gemeintes im Lautschlüssel mindestens sein
_material = None


def material() -> dict:
    """Thema -> Liste von Sätzen."""
    global _material
    if _material is None:
        _material = json.loads(FILE.read_text(encoding="utf-8"))
    return _material


def _real(word: str) -> bool:
    """Gibt es das Wort (Alltagswort, Fachbegriff, geschütztes Wort)?"""
    low = word.lower()
    terms, protected = fach.load()[0], fach.load()[1]
    return len(low) < 4 or low in terms or low in protected or low in fach.near()[0]


def learn(expected: str, heard: str):
    """Vergleicht Soll und Gehörtes. Gibt (gelesen, gelernt, offen) zurück.

    gelesen: Wurde erkennbar dieser Satz gelesen?
    gelernt: Liste (falsch, richtig) fürs Wörterbuch.
    offen:   Liste (gehört, gemeint), die nicht gelernt werden kann, weil das Gehörte ein echtes Wort ist.
    """
    exp, got = TOKEN.findall(expected), TOKEN.findall(heard)
    a, b = [w.lower() for w in exp], [w.lower() for w in got]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    same = sum(i2 - i1 for tag, i1, i2, _, _ in sm.get_opcodes() if tag == "equal")
    if not got or same < 0.4 * len(exp):
        return False, [], []
    learned, open_ = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "replace":
            continue
        for right, wrong in _pairs(exp[i1:i2], got[j1:j2]):
            if len(right) < 4 or right.isdigit() or any(c.isdigit() for c in wrong) or wrong.lower() == right.lower():
                continue
            ratio = _sound(wrong, right)
            if ratio < SOUND:
                continue
            parts = wrong.split()
            if all(_real(w) for w in parts) and not (len(parts) > 1 and ratio >= 0.8):
                open_.append((wrong, right))      # echtes Wort: nicht lernbar (ein Wortpaar, das fast gleich klingt, schon)
            else:
                learned.append((wrong, right))
    return True, learned, open_


def _sound(wrong: str, right: str) -> float:
    return difflib.SequenceMatcher(None, fach.key(wrong.replace(" ", "").lower()), fach.key(right.lower())).ratio()


def _pairs(exp, got):
    """Ordnet innerhalb einer abweichenden Stelle jedem Sollwort ein bis drei gehörte Wörter zu
    (das Modell trennt Zusammensetzungen gern), sodass es insgesamt am besten klingt."""
    n, m = len(exp), len(got)
    if n * m > 400:
        return []
    INF, SKIP = 1e9, 0.6
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            c = cost[i][j]
            if c >= INF:
                continue
            if i < n and c + SKIP < cost[i + 1][j]:
                cost[i + 1][j], back[i + 1][j] = c + SKIP, (i, j, None)
            if j < m and c + SKIP < cost[i][j + 1]:
                cost[i][j + 1], back[i][j + 1] = c + SKIP, (i, j, None)
            if i < n:
                for k in (1, 2, 3):
                    if j + k <= m:
                        wrong = " ".join(got[j:j + k])
                        step = 1.0 - _sound(wrong, exp[i])
                        if c + step < cost[i + 1][j + k]:
                            cost[i + 1][j + k], back[i + 1][j + k] = c + step, (i, j, (exp[i], wrong))
    out, i, j = [], n, m
    while back[i][j] is not None:
        pi, pj, pair = back[i][j]
        if pair:
            out.append(pair)
        i, j = pi, pj
    return out[::-1]
