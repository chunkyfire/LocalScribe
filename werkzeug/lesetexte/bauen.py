"""Übungssätze fürs Stimmtraining bauen: prüfen, ordnen und als diktat/lesetexte.json schreiben.

    python werkzeug/lesetexte/bauen.py

Quelle sind die Textdateien in diesem Ordner, eine je Fachrichtung, eine Zeile je Satz:
    A|…  Ärztin oder Arzt diktiert oder übergibt        P|…  Gespräch mit Patientin oder Patient
    O|…  Organisation, Telefon, Team                    T|…  Prüfsatz: wird nie im Training gezeigt, nur zum Messen
Die Sätze stehen in Sprechform (Zahlen und Einheiten als Wörter). Geordnet wird so, dass jeder nächste Satz
möglichst viele neue Laute und Fachwörter bringt: Wer nur fünf Minuten liest, hat das Wichtigste gelesen.
`alt.json` enthält die Sätze der früheren Themen, soweit noch keine neue Fachrichtung sie ersetzt.
"""
import json
import pathlib
import re
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
from diktat import fach, training                                     # noqa: E402

WPM = training.WPM
words = lambda s: re.findall(r"[A-Za-zÄÖÜäöüß]+", s)
flat = lambda s: " ".join(w.lower() for w in words(s))


def units(sentence, lexicon):
    """Was ein Satz zum Lernen beiträgt: Lautfolgen (aus dem Lautschlüssel) und Fachwörter."""
    out = set()
    for w in words(sentence):
        key = fach.key(w.lower())
        out |= {("laut", key[i:i + 3]) for i in range(max(1, len(key) - 2))}
        if len(w) > 5 and w.lower() in lexicon:
            out.add(("wort", w.lower()))
    return out


def order(groups, lexicon):
    """Je Art gierig nach neuem Beitrag je Wort ordnen, dann die Arten im Verhältnis ihrer Größe mischen."""
    ranked = {}
    for kind, sentences in groups.items():
        seen, rest, out = set(), list(sentences), []
        while rest:
            best = max(rest, key=lambda s: (sum(3 if u[0] == "wort" else 1 for u in units(s, lexicon) - seen) / len(words(s)) ** 0.5, -len(s)))
            seen |= units(best, lexicon)
            rest.remove(best)
            out.append(best)
        ranked[kind] = out
    total = sum(len(v) for v in ranked.values())
    taken, out = {k: 0 for k in ranked}, []
    for i in range(1, total + 1):
        kind = max((k for k in ranked if taken[k] < len(ranked[k])), key=lambda k: len(ranked[k]) * i / total - taken[k])
        out.append(ranked[kind][taken[kind]])
        taken[kind] += 1
    return out


def main():
    lexicon = {w.lower() for w in json.loads((ROOT / "diktat" / "fachlexikon.json").read_text(encoding="utf-8"))["begriffe"]}
    result = {"version": 2, "fach": {}, "pruef": {}, "alt": json.loads((HERE / "alt.json").read_text(encoding="utf-8"))}
    seen, problems = {}, []
    files = sorted(HERE.glob("*.txt"), key=lambda p: (p.stem != training.BASE, p.stem))
    for path in files:
        groups, tests = {}, []
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            kind, _, sentence = line.partition("|")
            sentence = sentence.strip()
            where = f"{path.name}:{n}"
            if kind not in "APOT" or not sentence:
                problems.append(f"{where}: Zeile ohne Art (A, P, O oder T)")
                continue
            count = len(words(sentence))
            if not 6 <= count <= 30:
                problems.append(f"{where}: {count} Wörter (erlaubt 6 bis 30)")
            if sentence[-1] not in ".?":
                problems.append(f"{where}: Satz endet nicht mit Punkt oder Fragezeichen")
            if re.search(r"(?<![A-Za-z])\d", sentence):
                problems.append(f"{where}: Ziffer im Satz, Zahlen bitte als Wort")
            if flat(sentence) in seen:
                problems.append(f"{where}: derselbe Satz steht schon in {seen[flat(sentence)]}")
            seen[flat(sentence)] = where
            (tests if kind == "T" else groups.setdefault(kind, [])).append(sentence)
        train = order(groups, lexicon)
        for t in tests:                       # ein Prüfsatz darf keinem Übungssatz zu ähnlich sein
            tw = set(flat(t).split())
            for s in train:
                sw = set(flat(s).split())
                if len(tw & sw) >= 0.8 * min(len(tw), len(sw)):
                    problems.append(f"{path.name}: Prüfsatz fast gleich einem Übungssatz: {t[:50]} …")
        result["fach"][path.stem.replace("_", " ")] = train
        result["pruef"][path.stem.replace("_", " ")] = tests
        n_words = sum(len(training.plain(s)) for s in train)
        print(f"{path.stem:34s} {len(train):4d} Sätze ({', '.join(f'{k} {len(v)}' for k, v in groups.items())}), "
              f"{n_words} Wörter, etwa {n_words / WPM:.0f} Minuten; {len(tests)} Prüfsätze")
    old = {flat(s) for group in result["alt"].values() for s in group}
    for key, where in seen.items():
        if key in old:
            problems.append(f"{where}: steht auch in den bisherigen Themen")
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    (ROOT / "diktat" / "lesetexte.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"bisherige Themen: {len(result['alt'])} mit {sum(len(v) for v in result['alt'].values())} Sätzen")


if __name__ == "__main__":
    main()
