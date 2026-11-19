"""Die nachtrainierten Schreibteile aus stimme.py über den Weg der App messen: 8-Bit-Hörteil, Dekodieren mit
Wortschatz, Nachbearbeitung. Läuft auf der CPU in der Umgebung der App.

    python stimme_messen.py <training-Ordner von LocalScribe> <Arbeitsordner von stimme.py> [--bench=<Ordner>]

Gemessen werden die Prüfsätze (dieselbe Stimme, Sätze, die nie im Training waren). Mit --bench zusätzlich freie
Diktate: <Ordner>/bench.json mit {"gt": {Name: Solltext}} und <Ordner>/bench/*.wav; ausgewertet wie in
werkzeug/messen/eigene.py. Ausgegeben werden nur Zahlen, keine Texte.
"""
import gc, json, os, pathlib, shutil, sys, time, wave

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
from diktat import config, engine, modelle, training

src, work = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
bench_dir = next((pathlib.Path(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--bench=")), None)
found = modelle.find_release(config.MODELS["de"]["release"])
if not found:
    sys.exit("Das deutsche Sprachmodell liegt noch nicht auf diesem Rechner (LocalScribe einmal starten).")
base = pathlib.Path(found)
index = src / training.TESTS / "index.jsonl"
test = [json.loads(l) for l in open(index, encoding="utf-8") if l.strip()]
test = [r for r in test if (index.parent / r["audio"]).exists()]


def audio(p):
    w = wave.open(str(p)); a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    if w.getnchannels() > 1:
        a = a.reshape(-1, w.getnchannels()).mean(axis=1)
    assert w.getframerate() == 16000, w.getframerate()
    return a


bench = json.loads((bench_dir / "bench.json").read_text(encoding="utf-8")) if bench_dir else None
names = {k.lower().replace("ä", "ae").replace("ü", "ue").replace("ö", "oe"): k for k in bench["gt"]} if bench else {}
stages = [("vorher", base / "decoder_joint-model.int8.onnx")]
for d in sorted((p for p in work.glob("m*") if (p / "decoder_joint-model.onnx").exists()), key=lambda p: float(p.name[1:])):
    stages.append((d.name[1:] + " min", d / "decoder_joint-model.onnx"))
rows, files = [], []
for label, decoder in stages:
    folder = work / "modell" / label.replace(" ", "")
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("config.json", "vocab.txt"):
        shutil.copy(base / name, folder / name)
    enc = folder / "encoder-model.int8.onnx"
    if not enc.exists():
        try:
            os.link(base / enc.name, enc)            # derselbe Hörteil, ohne ihn zu kopieren
        except OSError:
            shutil.copy(base / enc.name, enc)
    shutil.copy(decoder, folder / "decoder_joint-model.int8.onnx")
    config.MODELS["de"]["path"] = str(folder)
    cfg = dict(config.DEFAULTS)                      # Werkseinstellung: Kernliste im Wortschatz, kein persönliches Wörterbuch
    t = engine.Transcriber(cfg); t.load()
    raw = post = n = 0; took = 0.0
    for r in test:
        s = time.time(); hyp = t.transcribe(audio(index.parent / r["audio"])); took += time.time() - s
        e, w = training.score(r["text"], hyp); raw += e; n += w
        post += training.score(r["text"], engine.postprocess(hyp, cfg))[0]
    row = {"stufe": label, "pruef_roh": 100 * raw / max(n, 1), "pruef": 100 * post / max(n, 1), "woerter": n, "s_je_satz": took / max(len(test), 1)}
    if bench:
        out = work / f"stimme_{label.replace(' ', '')}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            for p in sorted((bench_dir / "bench").glob("*.wav")):
                name = next((v for k, v in names.items() if k.startswith(p.stem[:4]) or p.stem.startswith(k[:4])), p.stem)
                f.write(json.dumps({"name": name, "hyp": t.transcribe(audio(p))}, ensure_ascii=False) + "\n")
        files.append(str(out))
    rows.append(row)
    print(f"{label:>8s}: Prüfsätze roh {row['pruef_roh']:.2f} %, mit Nachbearbeitung {row['pruef']:.2f} % ({n} Wörter), {row['s_je_satz']:.2f} s je Satz", flush=True)
    del t; gc.collect()
json.dump(rows, open(work / "messung.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if bench:
    import subprocess
    out = subprocess.run([sys.executable, str(ROOT / "werkzeug" / "messen" / "eigene.py"), str(bench_dir / "bench.json")] + files,
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    print("\nFreie Diktate (Wortfehler, wie in eigene.py):")
    for line in out.splitlines():
        if "stimme_" in line or line.strip().endswith("gesamt"):
            print(line)
shutil.rmtree(work / "modell", ignore_errors=True)
print("FERTIG", flush=True)
