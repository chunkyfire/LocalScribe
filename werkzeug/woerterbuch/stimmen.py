"""Weitere Stimmen für das Basiswörterbuch: eine lange Aufnahme mit vielen Begriffen auswerten.

    python stimmen.py <Ordner> <Tondatei> <Begriffe, durch Komma getrennt>

Die Aufnahme enthält pro Begriff den Satz „Im Befund steht X, weil X wichtig ist.“ (z. B. von
ElevenLabs gesprochen). Das Ergebnis wird an gehoert.jsonl angehängt; bauen.py liest es von dort.
"""
import difflib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
import numpy as np

from diktat import config, engine

work, audio_path, terms = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3].split(",")
t = engine.Transcriber(dict(config.DEFAULTS))
t.load()
_, blocks = engine.decode_file(audio_path)
audio = np.concatenate(list(blocks))
text = " ".join(t.model.recognize(c, sample_rate=engine.RATE) for c in engine.split_long(audio))
(work / (pathlib.Path(audio_path).stem + ".txt")).write_text(text, encoding="utf-8")
found = re.findall(r"steht\s+(.+?)[,.]?\s+weil\s+(.+?)\s+wichtig", text, flags=re.IGNORECASE)
p = n = 0
with open(work / "gehoert.jsonl", "a", encoding="utf-8") as f:
    for g1, g2 in found:
        best, at = 0.0, None
        for i in range(p, min(p + 4, len(terms))):
            r = max(difflib.SequenceMatcher(None, g.lower().replace(" ", ""), terms[i].lower()).ratio() for g in (g1, g2))
            if r > best:
                best, at = r, i
        if at is None or best < 0.5:
            continue
        f.write(json.dumps({"t": terms[at], "h": f"Im Befund steht {g1}, weil {g2} wichtig ist."}, ensure_ascii=False) + "\n")
        p, n = at + 1, n + 1
exact = sum(1 for g1, g2 in found for x in (g1, g2) if x in terms)
print(f"{len(audio) / engine.RATE:.0f} s Ton, {len(found)} Sätze erkannt, {n} von {len(terms)} Begriffen zugeordnet, "
      f"{exact} von {2 * len(found)} Nennungen exakt richtig", flush=True)
