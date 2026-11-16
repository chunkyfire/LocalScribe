# /// script
# requires-python = ">=3.11.9,<3.12"
# dependencies = ["nemo_toolkit[asr]", "torch", "numba-cuda[cu12]", "huggingface_hub", "soundfile", "pyarrow", "onnx", "onnxscript", "av", "onnxruntime"]
# ///
"""Den Schreibteil von primeline-Parakeet (Decoder und Joint) mit künstlich gesprochenen Diktatsätzen nachtrainieren.

    python trainieren.py <Datenordner mit liste.jsonl> <Arbeitsordner> [Schritte] [Lernrate] [--torchloss] [--repo=<HF-Datensatz>]

Mit --repo (für einen Lauf auf Hugging Face Jobs) kommen die Daten als daten.tar aus dem Datensatz, und das Ergebnis
(decoder_joint als ONNX und als Gewichte, Bericht) wird dorthin unter <Arbeitsordner-Name>/ hochgeladen.

Der Hörteil (Encoder, 600 Mio. Gewichte) bleibt unverändert: Er wird nicht auf die künstlichen Stimmen hin verbogen,
und LocalScribe braucht danach nur eine neue kleine Datei (decoder_joint, 72 MB). Echte Aufnahmen (MLS Deutsch) mit
den Texten, die das Ausgangsmodell selbst dazu schreibt, laufen als Anker mit, damit es sein bisheriges Verhalten
(Satzzeichen, Zahlen, Alltagssprache) behält. Am Ende: Wortfehlerrate vorher und nachher auf zurückgehaltenen Sätzen.
"""
import difflib, io, json, os, pathlib, random, re, sys, time
if os.name == "nt":                          # Windows: die CUDA-Bibliotheken der Verlustfunktion laden, bevor PyTorch seine älteren Fassungen lädt
    import ctypes, glob
    for pat in ("nvidia/nvjitlink/bin/*.dll", "nvidia/cuda_nvcc/nvvm/bin/*.dll"):
        for f in glob.glob(os.path.join(sys.prefix, "Lib", "site-packages", pat)):
            ctypes.WinDLL(f)
import soundfile as sf, torch
from huggingface_hub import hf_hub_download
from omegaconf import OmegaConf, open_dict

data, work = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
steps = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
lr = float(sys.argv[4]) if len(sys.argv) > 4 else 5e-5
work.mkdir(parents=True, exist_ok=True)
REPO = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--repo=")), None)
if REPO and not (data / "liste.jsonl").exists():
    import tarfile
    data.mkdir(parents=True, exist_ok=True)
    with tarfile.open(hf_hub_download(REPO, "daten.tar", repo_type="dataset")) as tar:
        tar.extractall(data)
    print("Daten entpackt:", len(list((data / "audio").iterdir())), "Dateien", flush=True)
report = {}
random.seed(0)
torch.set_float32_matmul_precision("high")

def words(t):
    return re.sub(r"[^\wäöüß ]+", " ", t.lower().replace("-", " ")).split()

def errors(ref, hyp):
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i, a in enumerate(r, 1):
        p, d[0] = d[0], i
        for j, b in enumerate(h, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (a != b))
    return d[-1], len(r)

def wer(rows, hyps):
    e = n = 0
    for r, h in zip(rows, hyps):
        a, b = errors(r["text"], h); e += a; n += b
    return 100 * e / max(n, 1)

NUMBERS = set("null ein eine einen eins zwei drei vier fünf sechs sieben acht neun zehn elf zwölf zwanzig dreißig vierzig fünfzig sechzig siebzig achtzig neunzig "
              "hundert tausend komma prozent grad milligramm mikrogramm gramm kilogramm milliliter liter deziliter millimeter zentimeter meter quadratmeter "
              "millimol mikromol nanogramm pikogramm einheiten stunde stunden minute minuten sekunden tage tagen wochen monate jahre mal pro zu".split())

def plain(w):
    """Ein gewöhnliches Wort: nur Buchstaben, keine Zahl und keine Einheit (die schreibt das Modell in eigener Form)."""
    k = re.sub(r"[^\wäöüß]", "", w.lower())
    return bool(k) and k.isalpha() and k not in NUMBERS and not re.search(r"(zehn|zig|hundert|tausend)$", k)

def merge(ref, hyp, allowed=None):
    """Den Text des Ausgangsmodells behalten (Zahlen, Einheiten, Satzzeichen in seiner Form) und nur falsch gehörte Wörter
    durch die richtigen ersetzen. allowed: nur Wörter aus dieser Menge einsetzen (für fremde Transkripte)."""
    key = lambda w: re.sub(r"[^\wäöüß]", "", w.lower())
    r, h = ref.split(), hyp.split()
    rk, hk = [key(w) for w in r], [key(w) for w in h]
    ok = lambda w: plain(w) and (allowed is None or key(w) in allowed)
    def take(hw, rw):                        # richtiges Wort, Satzzeichen vom Modell
        if allowed is None:
            return rw                         # eigener Text: Wort samt Satzzeichen stimmt
        tail = re.search(r"[^\wäöüß]*$", hw).group(0) if hw else re.search(r"[^\wäöüß]*$", rw).group(0)
        core = re.sub(r"[^\wäöüß]+$", "", rw)
        if allowed is not None and core.islower() and hw[:1].isupper():
            core = core[:1].upper() + core[1:]
        return core + tail
    out, fixed = [], 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, hk, rk, autojunk=False).get_opcodes():
        if tag == "equal":
            out += h[i1:i2]
        elif tag == "replace" and i2 - i1 == j2 - j1:
            for i, j in zip(range(i1, i2), range(j1, j2)):
                if plain(h[i]) and ok(r[j]):
                    out.append(take(h[i], r[j])); fixed += 1
                else:
                    out.append(h[i])
        elif tag == "replace" and all(plain(w) for w in h[i1:i2]) and all(ok(w) for w in r[j1:j2]) and allowed is None:
            out += [take("", w) for w in r[j1:j2 - 1]] + [take(h[i2 - 1], r[j2 - 1])]; fixed += 1
        elif tag == "insert" and allowed is None and all(plain(w) for w in r[j1:j2]):
            out += r[j1:j2]; fixed += 1       # das Modell hat gewöhnliche Wörter ausgelassen
        elif tag == "delete" and allowed is None and all(plain(w) for w in h[i1:i2]):
            fixed += 1                        # das Modell hat Wörter dazuerfunden
        else:
            out += h[i1:i2]
    return " ".join(out), fixed

import nemo.collections.asr as nemo_asr
try:
    import lightning.pytorch as pl
except ImportError:
    import pytorch_lightning as pl

print("Lade Ausgangsmodell …", flush=True)
model = nemo_asr.models.ASRModel.restore_from(hf_hub_download("primeline/parakeet-primeline", "2_95_WER.nemo"), map_location="cuda")
print(type(model).__name__, "| Verlust:", model.cfg.loss.get("loss_name"), "| Gewichte Decoder+Joint:",
      round(sum(p.numel() for m in (model.decoder, model.joint) for p in m.parameters()) / 1e6, 1), "Mio.", "| Joint:", {k: model.cfg.joint.get(k) for k in ("fuse_loss_wer", "fused_batch_size")}, flush=True)

def hear(paths, batch=24):
    out = model.transcribe([str(p) for p in paths], batch_size=batch, verbose=False, num_workers=0)
    if isinstance(out, tuple):
        out = out[0]
    return [getattr(o, "text", o) for o in out]

# ---- künstliche Sätze: vom Ausgangsmodell anhören lassen, Unverständliches aussortieren ----
syn = [json.loads(l) for l in open(data / "liste.jsonl", encoding="utf-8")]
NEURO = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--neuro=")), 0)
if NEURO:                                   # künstlich gesprochene Neurologie-Sätze (NeurologyAI/neuro-parakeet-food, MIT, Chatterbox-Stimmen)
    import pyarrow.parquet as pq
    (data / "neuro").mkdir(exist_ok=True)
    got, k = 0, 0
    while got < NEURO and k < 14:
        pf = pq.ParquetFile(hf_hub_download("NeurologyAI/neuro-parakeet-food", f"data/train-{k:05d}-of-00014.parquet", repo_type="dataset")); k += 1
        for batch in pf.iter_batches(batch_size=64, columns=["audio", "text", "duration"]):
            for r in batch.to_pylist():
                if not 1.5 <= r["duration"] <= 16 or len(r["text"].split()) < 3:
                    continue
                name = f"neuro/n{got:05d}.wav"; (data / name).write_bytes(r["audio"]["bytes"])
                syn.append({"audio": name, "text": r["text"], "stimme": "chatterbox-neuro", "sec": round(r["duration"], 2)}); got += 1
                if got >= NEURO:
                    break
            if got >= NEURO:
                break
    print("Neurologie-Sätze dazu:", got, flush=True)
cache = work / f"vorher_{len(syn)}.json"
if cache.exists():
    before = json.load(open(cache, encoding="utf-8"))
else:
    t = time.time(); before = hear([data / r["audio"] for r in syn]); json.dump(before, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
    print("Angehört:", len(syn), "Sätze in", round(time.time() - t), "s", flush=True)
keep = []
for r, h in zip(syn, before):
    e, n = errors(r["text"], h)
    r["vorher"], r["fehler"] = h, e / max(n, 1)
    if r["fehler"] <= 0.5 and 1.0 <= r["sec"] <= 22:
        keep.append(r)
report["vorher_kunst_alle"] = wer(keep, [r["vorher"] for r in keep])
print(f"Brauchbar: {len(keep)} von {len(syn)} | Wortfehler des Ausgangsmodells darauf: {wer(keep, [r['vorher'] for r in keep]):.1f} %", flush=True)
by_voice = {}
for r in keep:
    by_voice.setdefault(r["stimme"], []).append(r)
print({k: (len(v), round(wer(v, [r["vorher"] for r in v]), 1)) for k, v in by_voice.items()}, flush=True)
n_fixed = 0
for r in keep:
    r["ziel"], f = merge(r["text"], r["vorher"]); n_fixed += f
print("Zieltexte der Kunstsätze: Text des Ausgangsmodells mit", n_fixed, "berichtigten Stellen", flush=True)
for r in keep[:6]:
    print("  SOLL", r["text"][:100]); print("  HÖRT", r["vorher"][:100]); print("  ZIEL", r["ziel"][:100])
random.shuffle(keep)
held, train_syn = keep[:300], keep[300:]

# ---- Anker: echte Aufnahmen mit den Texten des Ausgangsmodells ----
anchor_dir = work / "anker"; anchor_list = work / "anker.json"
if anchor_list.exists():
    anchor = json.load(open(anchor_list, encoding="utf-8"))
else:
    import pyarrow.parquet as pq
    anchor_dir.mkdir(exist_ok=True)
    pf = pq.ParquetFile(hf_hub_download("facebook/multilingual_librispeech", "german/dev-00000-of-00001.parquet", repo_type="dataset"))
    paths, gold = [], {}
    for batch in pf.iter_batches(batch_size=64, columns=["audio"]):
        for row in batch.to_pylist():
            a, sr = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
            if sr != 16000 or not 4 <= len(a) / sr <= 12:
                continue
            p = anchor_dir / f"a{len(paths):04d}.flac"; sf.write(str(p), a, sr); paths.append((p, len(a) / sr))
            if len(paths) >= 2500:
                break
        if len(paths) >= 2500:
            break
    try:                                    # dazu echte Medizin-Aufnahmen (MultiMed, Trainingsteil), damit Zahlen, Einheiten und Satzenden bleiben
        import av, numpy as np
        table = pq.read_table(hf_hub_download("leduckhai/MultiMed", "German/train-00000-of-00001.parquet", repo_type="dataset"))
        col = next(n for n in table.column_names if "audio" in n)
        text_col = next(n for n in table.column_names if n in ("text", "transcription", "sentence", "transcript"))
        more = 0
        for i in range(table.num_rows):
            row = table.slice(i, 1).to_pylist()[0]; cell = row[col]
            c = av.open(io.BytesIO(cell["bytes"] if isinstance(cell, dict) else cell))
            r = av.AudioResampler(format="s16", layout="mono", rate=16000)
            out = [o.to_ndarray().reshape(-1) for f in c.decode(audio=0) for o in r.resample(f)]
            out += [o.to_ndarray().reshape(-1) for o in r.resample(None)]
            c.close()
            a = np.concatenate(out).astype(np.float32) / 32768
            if not 3 <= len(a) / 16000 <= 14:
                continue
            p = anchor_dir / f"m{more:04d}.flac"; sf.write(str(p), a, 16000); paths.append((p, len(a) / 16000)); gold[str(p)] = row[text_col]; more += 1
            if more >= 1400:
                break
        print("MultiMed-Anker:", more, flush=True)
    except Exception as e:
        print("MultiMed nicht nutzbar:", repr(e)[:200], flush=True)
    texts = hear([p for p, _ in paths])
    try:
        local = pathlib.Path(__file__).resolve().parent.parent.parent / "diktat" / "fachlexikon.json"
        lex = json.load(open(local if local.exists() else hf_hub_download(REPO, "fachlexikon.json", repo_type="dataset"), encoding="utf-8"))
        allowed = {w.lower() for w in lex.get("begriffe", []) + lex.get("kern", [])}
    except Exception as e:
        allowed = set(); print("Lexikon fehlt:", repr(e)[:100], flush=True)
    anchor, n_gold = [], 0
    for (p, s), t in zip(paths, texts):
        if len(t.split()) < 3:
            continue
        g = gold.get(str(p))
        if g and allowed:
            e, n = errors(g, t)
            if e / max(n, 1) > 0.5:
                continue                      # Transkript und Aufnahme passen nicht zusammen
            t, f = merge(g, t, allowed); n_gold += f
        anchor.append({"audio": str(p), "sec": round(s, 2), "text": t})
    print("Echte Medizin-Aufnahmen: Fachwörter nach dem menschlichen Transkript berichtigt an", n_gold, "Stellen", flush=True)
    json.dump(anchor, open(anchor_list, "w", encoding="utf-8"), ensure_ascii=False)
print("Anker:", len(anchor), "echte Aufnahmen,", round(sum(a["sec"] for a in anchor) / 60), "min", flush=True)
random.shuffle(anchor)
anchor_held, anchor_train = anchor[:150], anchor[150:]

def manifest(name, rows, root=None):
    p = work / name
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"audio_filepath": str((root / r["audio"]) if root else r["audio"]), "duration": r["sec"], "text": r.get("ziel") or r["text"]}, ensure_ascii=False) + "\n")
    return str(p)

train_rows = [dict(r, audio=str(data / r["audio"])) for r in train_syn] + anchor_train
random.shuffle(train_rows)
train_m, val_m = manifest("train.json", train_rows), manifest("val.json", [dict(r, audio=str(data / r["audio"])) for r in held[:60]] + anchor_held[:40])  # wird nicht ausgewertet (limit_val_batches=0), NeMo verlangt die Angabe
print("Training:", len(train_rows), "Äußerungen,", round(sum(r["sec"] for r in train_rows) / 3600, 2), "h", flush=True)

# ---- nur Decoder und Joint lernen ----
FULL = "--voll" in sys.argv                  # auch den Hörteil (Encoder) mittrainieren
if not FULL:
    model.encoder.freeze()
    for p in model.preprocessor.parameters():
        p.requires_grad = False
    _train = model.train
    def train(mode=True):                   # der Hörteil bleibt auch während des Trainings im Auswertungsmodus
        out = _train(mode); model.encoder.eval(); model.preprocessor.eval(); return out
    model.train = train
    if getattr(model, "spec_augmentation", None) is not None:
        model.spec_augmentation = None
print("Trainiert wird:", "das ganze Modell" if FULL else "nur Decoder und Joint", flush=True)
bs = 4 if "--voll" in sys.argv else 8
if "--torchloss" in sys.argv:               # Verlustfunktion in reinem PyTorch: langsamer, braucht aber keine CUDA-Zusatzbibliotheken
    from nemo.collections.asr.losses.rnnt import RNNTLoss
    kw = dict(OmegaConf.to_container(model.cfg.loss.tdt_kwargs))
    model.loss = RNNTLoss(num_classes=model.joint.num_classes_with_blank - 1 - model.joint.num_extra_outputs, loss_name="tdt_pytorch",
                          loss_kwargs=dict(durations=kw["durations"], sigma=kw.get("sigma", 0.0)), reduction=model.cfg.get("rnnt_reduction", "mean_batch"))
    model.joint.set_loss(model.loss)
model.setup_training_data(OmegaConf.create(dict(manifest_filepath=train_m, sample_rate=16000, batch_size=bs, shuffle=True, num_workers=0, pin_memory=True,
                                                max_duration=16, min_duration=0.5, is_tarred=False, use_lhotse=False)))
model.setup_multiple_validation_data(OmegaConf.create(dict(manifest_filepath=val_m, sample_rate=16000, batch_size=bs, shuffle=False, num_workers=0, use_lhotse=False)))
optim = OmegaConf.create(dict(name="adamw", lr=lr, betas=[0.9, 0.98], weight_decay=1e-3,
                              sched=dict(name="CosineAnnealing", warmup_steps=100, min_lr=lr / 20, max_steps=steps)))
with open_dict(model.cfg):
    model.cfg.optim = optim                 # auch dort, wo Lightning beim Start nachsieht
model.setup_optimization(optim)
trainer = pl.Trainer(accelerator="gpu", devices=1, max_steps=steps, precision=32, gradient_clip_val=1.0, accumulate_grad_batches=2 if "--voll" in sys.argv else 1, log_every_n_steps=25,
                     enable_checkpointing=False, logger=False, num_sanity_val_steps=0, limit_val_batches=0, enable_progress_bar=False)
model.set_trainer(trainer)
class Tick(pl.Callback):
    def on_train_batch_end(self, trainer, module, outputs, batch, idx):
        if trainer.global_step % 20 == 0:
            loss = outputs["loss"].item() if isinstance(outputs, dict) else float(outputs)
            print("Schritt", trainer.global_step, "Verlust", round(loss, 3), "|", round(time.time() - t, 0), "s", flush=True)
trainer.callbacks.append(Tick())
t = time.time(); trainer.fit(model); print("Training:", round((time.time() - t) / 60, 1), "min", flush=True)

# ---- messen ----
model.eval().cuda()
after = hear([data / r["audio"] for r in held]); after_anchor = hear([a["audio"] for a in anchor_held])
print(f"ZURÜCKGEHALTENE KUNSTSÄTZE  vorher {wer(held, [r['vorher'] for r in held]):.2f} %  nachher {wer(held, after):.2f} %", flush=True)
for group in sorted({r["stimme"].startswith("chatterbox") for r in held}):
    part = [(r, h) for r, h in zip(held, after) if r["stimme"].startswith("chatterbox") == group]
    print("   davon", "Neurologie (Chatterbox)" if group else "eigene Sätze (Piper)", f"vorher {wer([r for r, _ in part], [r['vorher'] for r, _ in part]):.2f} %  nachher {wer([r for r, _ in part], [h for _, h in part]):.2f} %", flush=True)
print(f"ZURÜCKGEHALTENE ECHTE (Anker, Soll = Text des Ausgangsmodells)  nachher {wer(anchor_held, after_anchor):.2f} % Abweichung", flush=True)
report.update(schritte=steps, lernrate=lr, kunst_vorher=wer(held, [r["vorher"] for r in held]), kunst_nachher=wer(held, after), anker_abweichung=wer(anchor_held, after_anchor),
              beispiele=[{"soll": r["text"], "vorher": r["vorher"], "nachher": h} for r, h in zip(held, after) if r["vorher"] != h][:60])
json.dump(report, open(work / "bericht.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r, h in list(zip(held, after))[:12]:
    if r["vorher"] != h:
        print("  SOLL  ", r["text"][:110]); print("  VORHER", r["vorher"][:110]); print("  NACHHER", h[:110])
torch.save({"decoder": model.decoder.state_dict(), "joint": model.joint.state_dict()}, work / "decoder_joint.pt")
if FULL and REPO:                            # das Ergebnis sichern, bevor der speicherhungrige Export beginnt
    from huggingface_hub import HfApi
    torch.save({k: v.half() if v.is_floating_point() else v for k, v in model.state_dict().items()}, work / "modell_fp16.pt")
    HfApi().upload_file(path_or_fileobj=str(work / "bericht.json"), path_in_repo=f"{work.name}/bericht.json", repo_id=REPO, repo_type="dataset")
    HfApi().upload_file(path_or_fileobj=str(work / "modell_fp16.pt"), path_in_repo=f"{work.name}/modell_fp16.pt", repo_id=REPO, repo_type="dataset")
    print("GEWICHTE GESICHERT", flush=True)
raw = work / "onnx"; raw.mkdir(exist_ok=True)
with torch.no_grad():
    model.export(str(raw / "model.onnx"))
print("EXPORT", [p.name + " " + str(round(p.stat().st_size / 1e6)) + " MB" for p in raw.iterdir() if "decoder" in p.name], flush=True)
extra = []
if FULL:                                     # Hörteil so auf 8 Bit kürzen, wie LocalScribe ihn lädt (nur die großen Matrizen, je Kanal eigene Skala)
    from onnxruntime.quantization import QuantType, quantize_dynamic
    small = work / "encoder-model.int8.onnx"
    quantize_dynamic(raw / "encoder-model.onnx", small, weight_type=QuantType.QUInt8, op_types_to_quantize=["MatMul"], per_channel=True)
    print("ENCODER", round(small.stat().st_size / 1e6), "MB", flush=True)
    extra.append(small)
if REPO:
    from huggingface_hub import HfApi
    api = HfApi()
    for f in [work / "bericht.json"] + ([] if FULL else [work / "decoder_joint.pt"]) + [p for p in raw.iterdir() if "decoder" in p.name] + extra:
        api.upload_file(path_or_fileobj=str(f), path_in_repo=f"{work.name}/{f.name}", repo_id=REPO, repo_type="dataset")
    print("HOCHGELADEN", flush=True)
print("FERTIG", flush=True)
