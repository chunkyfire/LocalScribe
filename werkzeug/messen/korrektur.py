"""Fachkorrektur messen: python korrektur.py <app.jsonl> <Ausgabe.jsonl> <Modell> [cpu]

Nimmt die Erkennung aus dateien.py, wendet Wörterbuch und Lautschlüssel an und danach die
Fachkorrektur über Ollama. Mit „cpu“ rechnet Ollama ohne Grafikkarte.
"""
import json
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
from diktat import engine, fach, korrektor

src, out, model = sys.argv[1], sys.argv[2], sys.argv[3]
cpu = len(sys.argv) > 4 and sys.argv[4] == "cpu"


def ask(system, user):
    body = {"model": model, "stream": False, "format": "json", "options": {"temperature": 0, **({"num_gpu": 0} if cpu else {})},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request("http://localhost:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["message"]["content"]


ask("Antworte mit {}", "{}")      # Modell laden
with open(out, "w", encoding="utf-8") as f:
    for line in open(src, encoding="utf-8"):
        r = json.loads(line)
        text = engine.tidy(fach.correct(engine.apply_base(engine.LEADING.sub("", r["hyp"].strip()))))
        start = time.time()
        fixed, changes = korrektor.correct(text, {}, ask)
        r.update(hyp=fixed, vorher=text, korrektur_s=round(time.time() - start, 1), ersetzt=changes, verdaechtig=korrektor.suspects(text))
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(r["name"], r["korrektur_s"], "s", changes, flush=True)
