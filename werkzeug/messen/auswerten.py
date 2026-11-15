"""Wortfehlerrate auf echten Aufnahmen, vor und nach der Nachbearbeitung.

    python auswerten.py <multimed_*.jsonl> [...]

Vergleicht: Rohtext des Modells, mit Basiswörterbuch, mit Basiswörterbuch und Lautschlüssel.
Zählt außerdem jede Ersetzung als richtig (steht so im Soll) oder falsch (Original stand im Soll).
"""
import json
import pathlib
import re
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
from diktat import engine, fach

TOK = re.compile(r"[a-zäöüß0-9]+")


def norm(text):
    return TOK.findall(text.lower())


def errors(ref, hyp):
    """Levenshtein über Wörter."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def steps(text):
    yield "roh", text
    a = engine.apply_base(text)
    yield "+ Basiswörterbuch", a
    b = fach.correct(a, fuzzy=False)
    yield "+ Lautschlüssel, ß", b
    yield "+ ein Laut daneben", fach.correct(a)
    yield "+ Schreibweisen", engine.tidy(fach.correct(a))


terms = set(fach.load()[0])
for path in sys.argv[1:]:
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    rows = [r for r in rows if not r["hyp"].startswith("!") and r["ref"].strip()]
    n = sum(len(norm(r["ref"])) for r in rows)
    print(f"\n{pathlib.Path(path).name}: {len(rows)} Aufnahmen, {sum(r['sec'] for r in rows) / 60:.0f} min, {n} Wörter")
    tot, good, bad, neutral, ex = {}, {}, {}, {}, {}
    fach_n = fach_ok = {}
    hits = {}
    for r in rows:
        ref = norm(r["ref"])
        refset = set(ref)
        last = None
        for name, text in steps(r["hyp"]):
            hyp = norm(text)
            tot[name] = tot.get(name, 0) + errors(ref, hyp)
            # Fachbegriffe des Solls, die im Ist richtig stehen
            want = [w for w in ref if w in terms]
            h = hits.setdefault(name, [0, 0])
            h[0] += sum(1 for w in want if w in set(hyp))
            h[1] += len(want)
            if last is not None:
                for a, b in zip(norm(last), hyp):
                    if a != b:
                        if b in refset:
                            good[name] = good.get(name, 0) + 1
                        elif a in refset:
                            bad[name] = bad.get(name, 0) + 1
                            ex.setdefault(name, []).append(f"{a}→{b}")
                        else:
                            neutral[name] = neutral.get(name, 0) + 1
                            ex.setdefault(name + " offen", []).append(f"{a}→{b}")
            last = text
    for name in tot:
        print(f"  {name:20s} WER {100 * tot[name] / n:5.2f} %   Fachbegriffe richtig {hits[name][0]}/{hits[name][1]}"
              f"   Ersetzungen: richtig {good.get(name, 0)}, falsch {bad.get(name, 0)}, offen {neutral.get(name, 0)}")
    for k, v in ex.items():
        print("   ", k, ":", "; ".join(v[:40]))
