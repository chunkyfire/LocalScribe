"""Rohdaten für das medizinische Basiswörterbuch sammeln.

    python sammeln.py begriffe <Ordner>   Begriffe aus Wikidata (CC0) und kern.txt -> begriffe.txt, saetze.txt
    (danach tests\\langzeit\\tts.ps1 -Dir <Ordner>: jede Zeile wird von der Windows-Stimme gesprochen)
    python sammeln.py hoeren <Ordner>     jede Aufnahme erkennen -> gehoert.jsonl

Aus „was das Modell gehört hat“ baut bauen.py die Ersetzungsliste.
"""
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
import wave

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
WORD = re.compile(r"^[A-Za-zÄÖÜäöüß]{5,30}$")
SATZ = "Im Befund steht {0}, weil {0} wichtig ist."
QUERIES = {   # Wikidata-Eigenschaft -> Art
    "P267": "wirkstoff",    # ATC-Code
    "P494": "diagnose",     # ICD-10
    "P1323": "anatomie",    # Terminologia Anatomica 98
    "P486": "mesh",         # MeSH: Verfahren, Symptome, Erreger, Substanzen
}


def wikidata(prop):
    q = f'SELECT DISTINCT ?l WHERE {{ ?i wdt:{prop} ?x. ?i rdfs:label ?l. FILTER(LANG(?l)="de") }}'
    url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"User-Agent": "LocalScribe-Woerterbuch/0.5 (github.com/chunkyfire/LocalScribe)"})
    with urllib.request.urlopen(req, timeout=170) as r:
        return [b["l"]["value"] for b in json.load(r)["results"]["bindings"]]


def begriffe(work):
    terms, alle = {}, set()
    for t in (HERE / "kern.txt").read_text(encoding="utf-8").split():
        terms[t] = "kern"
    for prop, art in QUERIES.items():
        try:
            labels = wikidata(prop)
        except Exception as e:
            print(prop, "fehlgeschlagen:", e, flush=True)
            continue
        n = 0
        for label in labels:
            parts = re.split(r"[\s\-/,()]+", label)
            alle.update(p for p in parts if p)
            # Einzelwörter ganz; aus mehrteiligen Namen nur groß geschriebene Wörter (Substantive, Eigennamen)
            for p in parts:
                if WORD.match(p) and (len(parts) == 1 or p[0].isupper()) and p not in terms:
                    if art == "mesh" and len(parts) > 1:
                        continue
                    terms[p] = art
                    n += 1
        print(prop, art, len(labels), "Namen,", n, "neue Begriffe", flush=True)
    (work / "begriffe.txt").write_text("\n".join(f"{t}\t{a}" for t, a in terms.items()), encoding="utf-8")
    (work / "alle_woerter.txt").write_text("\n".join(sorted(alle)), encoding="utf-8")
    (work / "saetze.txt").write_text("\n".join(SATZ.format(t) for t in terms), encoding="utf-8")
    print(len(terms), "Begriffe", flush=True)


_model = None


def _init():
    global _model
    from diktat import config, engine
    t = engine.Transcriber(dict(config.DEFAULTS, threads=4))
    t.load()
    _model = t.model


def _hear(job):
    import numpy as np
    path, term = job
    try:
        with wave.open(path) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        return term, _model.recognize(audio, sample_rate=16000)
    except Exception as e:
        return term, "!" + str(e)


def hoeren(work):
    import multiprocessing as mp
    terms = [line.split("\t")[0] for line in (work / "begriffe.txt").read_text(encoding="utf-8").splitlines()]
    out = work / "gehoert.jsonl"
    done = sum(1 for _ in open(out, encoding="utf-8")) if out.exists() else 0
    jobs = [(str(work / f"s{i + 1:04d}.wav"), t) for i, t in enumerate(terms)][done:]
    with mp.Pool(4, initializer=_init) as pool, open(out, "a", encoding="utf-8") as f:
        for n, (term, heard) in enumerate(pool.imap(_hear, jobs, chunksize=8)):
            f.write(json.dumps({"t": term, "h": heard}, ensure_ascii=False) + "\n")
            if n % 200 == 0:
                f.flush()
    (work / "hoeren_fertig.txt").write_text("fertig", encoding="utf-8")


if __name__ == "__main__":
    {"begriffe": begriffe, "hoeren": hoeren}[sys.argv[1]](pathlib.Path(sys.argv[2]))
