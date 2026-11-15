"""Zeigt die rohe Antwort des Sprachmodells auf ein Diktat: python korrektur_roh.py <app.jsonl> <Modell> [Name]"""
import json
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
from diktat import engine, fach, korrektor

for line in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(line)
    if len(sys.argv) > 3 and r["name"] != sys.argv[3]:
        continue
    text = engine.tidy(fach.correct(engine.apply_base(r["hyp"])))
    found = korrektor.suspects(text)[:korrektor.MAX_WORDS]
    body = {"model": sys.argv[2], "stream": False, "format": "json", "options": {"temperature": 0},
            "messages": [{"role": "system", "content": korrektor.SYSTEM},
                         {"role": "user", "content": f"Text: {text.strip()}\nVerdächtig: {json.dumps(found, ensure_ascii=False)}"}]}
    t = time.time()
    req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        d = json.load(resp)
    print(json.dumps({"name": r["name"], "s": round(time.time() - t, 1), "verdaechtig": found, "antwort": d["message"]["content"],
                      "tokens": d.get("eval_count")}, ensure_ascii=False), flush=True)
