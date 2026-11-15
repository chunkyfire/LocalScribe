"""Großes Fachlexikon aus Wikidata (CC0): deutsche Namen zu MeSH- und UMLS-Einträgen, seitenweise.

    python lexikon.py <Ordner>      -> lexikon_roh.txt (ein Name pro Zeile)
"""
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

work = pathlib.Path(sys.argv[1])
names = set()
for prop in ("P486", "P2892", "P267", "P494", "P1323", "P672", "P1694", "P7807"):
    offset = 0
    while True:
        q = (f'SELECT ?l WHERE {{ {{ SELECT ?i WHERE {{ ?i wdt:{prop} ?x }} LIMIT 20000 OFFSET {offset} }} '
             f'?i rdfs:label ?l. FILTER(LANG(?l)="de") }}')
        url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q)
        req = urllib.request.Request(url, headers={"User-Agent": "LocalScribe-Woerterbuch/0.6 (github.com/chunkyfire/LocalScribe)"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                rows = json.load(r)["results"]["bindings"]
        except Exception as e:
            print(prop, offset, "fehlgeschlagen:", str(e)[:80], flush=True)
            break
        names.update(b["l"]["value"] for b in rows)
        print(prop, offset, len(rows), "gesamt", len(names), flush=True)
        offset += 20000
        if offset > 400000 or (len(rows) == 0 and offset > 40000):
            break
        time.sleep(1)
    (work / "lexikon_roh.txt").write_text("\n".join(sorted(names)), encoding="utf-8")
print("fertig", len(names), flush=True)
