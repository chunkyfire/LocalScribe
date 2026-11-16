"""Fachkorrektur über den in der App eingestellten Server messen (z. B. OpenRouter, IONOS).

    python korrektur_cloud.py <app.jsonl> <Ausgabe.jsonl> [Anzahl] [satzzeichen]

Nimmt die Erkennung aus dateien.py oder multimed.py, wendet Wörterbuch und Lautschlüssel an und danach die
Fachkorrektur mit dem Sprachmodell aus den Einstellungen (Schlüssel aus dem Windows-Schlüsselspeicher).
Schreibt je Aufnahme: Text vorher, Rohantwort des Modells, übernommene Ersetzungen, Dauer. Die Rohantwort
bleibt erhalten, damit sich der Türsteher ohne neue Anfragen nachprüfen lässt.
"""
import json
import pathlib
import sys
import time
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
from diktat import config, engine, fach, korrektor, llm

src, out = sys.argv[1], sys.argv[2]
limit = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 10 ** 9
signs = "satzzeichen" in sys.argv[3:]          # diktierte Satzzeichen umsetzen, wie mit der Einstellung der App
cfg = config.load()["llm"]
print("Server:", cfg.get("base_url"), "| Modell:", cfg.get("model"), flush=True)
rows = [json.loads(l) for l in open(src, encoding="utf-8")]
rows = [r for r in rows if not r["hyp"].startswith("!")][:limit]
total = 0.0
with open(out, "w", encoding="utf-8") as f:
    for r in rows:
        text = engine.tidy(fach.correct(engine.apply_base(engine.LEADING.sub("", r["hyp"].strip()))))
        if signs:
            text = engine.spoken(text)
        raw = {}

        def ask(system, user):
            raw["antwort"] = llm.chat(cfg, system, user, json_mode=True)
            return raw["antwort"]
        start = time.time()
        fixed, changes = korrektor.correct(text, cfg, ask)
        took = time.time() - start
        total += took
        r.update(hyp=fixed, vorher=text, roh=raw.get("antwort", ""), korrektur_s=round(took, 2), ersetzt=changes)
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        print(r.get("name", "")[:20], round(took, 2), "s", changes, flush=True)
print(f"{len(rows)} Aufnahmen, im Mittel {total / max(1, len(rows)):.2f} s je Anfrage")
