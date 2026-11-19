# /// script
# requires-python = ">=3.11.9,<3.12"
# dependencies = ["nemo_toolkit[asr]", "torch", "numba-cuda[cu12]", "huggingface_hub", "soundfile", "pyarrow", "onnx", "onnxscript", "av", "onnxruntime"]
# ///
"""Den Schreibteil des deutschen Parakeet (Decoder und Joint) auf EINE Stimme nachtrainieren, mit Lernkurve:
Was bringen 5, 10, 20, 40 Minuten Vorlesen?

    python stimme.py <training-Ordner von LocalScribe> <Arbeitsordner> [--minuten=5,10,20,40] [--epochen=10] [--lr=3e-5]
                     [--anker=1.0] [--torchloss]

Eingabe ist der Ordner, den das Stimmtraining der App anlegt: index.jsonl und WAV-Dateien (Übungssätze), darunter
pruef/ mit den Prüfsätzen, die nie ins Training gehen. Alles läuft auf diesem Rechner (Grafikkarte); nichts wird
hochgeladen. Der Hörteil (Encoder) bleibt unverändert, LocalScribe müsste nur eine kleine Datei tauschen.

Zieltext eines Übungssatzes ist, was das Ausgangsmodell selbst hört (seine Schreibweise für Zahlen, Einheiten und
Satzzeichen bleibt), nur falsch gehörte Wörter werden durch die richtigen ersetzt. Sätze, in denen das Modell eine
Zahl anders hört, als sie dasteht, gehen nicht ins Training: Eine falsche Zahl soll nie gelernt werden.
Echte Aufnahmen anderer Stimmen (MLS Deutsch, MultiMed) mit den Texten des Ausgangsmodells laufen als Anker mit,
damit es sein bisheriges Verhalten behält (--anker: Anteil je Übungssatz, 0 = ohne).

Ergebnis: <Arbeitsordner>/kurve.json und je Stufe m<Minuten>/decoder_joint-model.onnx. Gemessen wird danach mit
stimme_messen.py über den Weg der App (8-Bit-Hörteil, Wortschatz, Nachbearbeitung).
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

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from diktat import training as T             # Soll und Gehörtes gleich schreiben (Zahlwörter, Einheiten), wie „Messen“ in der App


def arg(name, default):
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{name}=")), default)


src, work = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
MINUTES = [float(x) for x in arg("minuten", "5,10,20,40").split(",")]
EPOCHS, LR, ANCHOR = int(arg("epochen", "10")), float(arg("lr", "3e-5")), float(arg("anker", "1.0"))
BS = 8
print("Aufruf:", " ".join(sys.argv[3:]) or "(Vorgaben)", "| Minuten", MINUTES, "| Epochen", EPOCHS, "| Lernrate", LR, "| Anker", ANCHOR, flush=True)
work.mkdir(parents=True, exist_ok=True)
random.seed(0)
torch.set_float32_matmul_precision("high")


def rows_of(folder):
    p = folder / "index.jsonl"
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if p.exists() else []
    return [dict(r, audio=str(folder / r["audio"])) for r in rows if (folder / r["audio"]).exists() and 1.0 <= r["sec"] <= 24]


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


def wer(rows, hyps, key="text"):
    e = n = 0
    for r, h in zip(rows, hyps):
        a, b = errors(r[key], h); e += a; n += b
    return 100 * e / max(n, 1)


def score(ref, hyp):
    """(Fehler, Wörter) wie „Messen“ in der App; das Modell schreibt ss für ß, das zählt nicht als Fehler."""
    r, h = ([w.replace("ß", "ss") for w in T.plain(x)] for x in (ref, hyp))
    return min(T.errors(r, h), len(r)), len(r)


def read_wer(rows, hyps):
    """Wortfehler auf vorgelesenen Sätzen: Zahlwörter und Ziffern, Einheiten lang und kurz zählen als gleich."""
    e = n = 0
    for r, h in zip(rows, hyps):
        a, b = score(r["text"], h); e += a; n += b
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


UNITS = set(T._SHORT) | set(T._SHORT.values())


def kkey(w):
    """Vergleichsschlüssel eines Worts: klein, ohne Satzzeichen, ß wie ss, Zahlwort als Zahl, Einheit in Kurzform."""
    low = re.sub(r"[^\wäöüµ%]", "", w.lower().replace("ß", "ss"))
    n = T.number(low) if low.isalpha() else None
    return str(n) if n is not None else T._SHORT.get(low, low)


def common(w):
    """Ein gewöhnliches Wort, das berichtigt werden darf (keine Zahl, keine Einheit)."""
    low = re.sub(r"[^\wäöüßµ]", "", w.lower())
    return plain(w) and low not in UNITS and T.number(low) is None


def written(text):
    """Den Satz in Sprechform so zerlegen, dass er sich Wort für Wort neben den Text des Modells legen lässt:
    [Schlüssel, Wort wie im Satz, gewöhnlich?]; „elf Komma zwei“ wird ein Eintrag mit dem Schlüssel 112."""
    out = []
    for w in text.split():
        low = re.sub(r"[^\wäöüßµ%]", "", w.lower())
        n = T.number(low) if low.isalpha() else None
        if low == "komma" and out and out[-1][3] == "zahl":
            out[-1][3] = "komma"; out[-1][1] += " " + w; continue
        if n is not None and out and out[-1][3] == "komma":
            out[-1][0] += str(n); out[-1][3] = "nachkomma"; out[-1][1] += " " + w; continue
        if n is not None and n < 10 and out and out[-1][3] == "nachkomma":
            out[-1][0] += str(n); out[-1][1] += " " + w; continue          # sieben Komma zwei sechs
        out.append([kkey(w), w, common(w), "zahl" if n is not None else ""])
    return out


def target(ref, hyp):
    """Zieltext für einen vorgelesenen Satz: der Text des Ausgangsmodells (Zahlen, Einheiten, Satzzeichen, ss in
    seiner Form), nur falsch gehörte gewöhnliche Wörter kommen aus dem Satz. Gibt (Zieltext, berichtigte Stellen)."""
    R, h = written(ref), hyp.split()
    for r in R:
        r[1] = r[1].replace("ß", "ss")                                    # das Modell schreibt ss; die App macht daraus wieder ß
    out, fixed = [], 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [kkey(w) for w in h], [r[0] for r in R], autojunk=False).get_opcodes():
        ref_ok = all(R[j][2] for j in range(j1, j2))
        if tag == "equal":
            out += h[i1:i2]
        elif tag == "replace" and i2 - i1 == j2 - j1:
            for i, j in zip(range(i1, i2), range(j1, j2)):
                long_unit = re.sub(r"[^\wäöüßµ]", "", R[j][1].lower()) in T._SHORT and len(h[i]) > 4 and h[i].strip(".,;:").isalpha() \
                    and difflib.SequenceMatcher(None, h[i].lower(), R[j][1].lower()).ratio() > 0.7
                if (common(h[i]) and R[j][2]) or long_unit:               # auch: Einheit ausgeschrieben, aber verhört (Decilliter)
                    out.append(R[j][1]); fixed += 1
                else:
                    out.append(h[i])
        elif tag == "replace" and ref_ok and all(common(w) for w in h[i1:i2]):
            out += [R[j][1] for j in range(j1, j2)]; fixed += 1
        elif tag == "insert" and ref_ok:
            out += [R[j][1] for j in range(j1, j2)]; fixed += 1           # das Modell hat gewöhnliche Wörter ausgelassen
        elif tag == "delete" and all(common(w) for w in h[i1:i2]):
            fixed += 1                                                    # das Modell hat Wörter dazuerfunden
        else:
            out += h[i1:i2]
    return " ".join(out), fixed


if "--probe" in sys.argv:                    # nur die Zieltexte prüfen: python stimme.py - - --probe
    for ref, hyp in (("Körpergröße einhundertachtundsiebzig Zentimeter, Körpergewicht dreiundneunzig Kilogramm, Body-Mass-Index neunundzwanzig Komma vier.",
                      "Kapergrösse 178 cm, Kappergewicht 93 kg, Odi Massendex 29,4."),
                     ("Hämoglobin elf Komma zwei Gramm pro Deziliter, Leukozyten neuntausendsechshundert pro Mikroliter.",
                      "Hämoglobin 11,2 g pro Decilliter Leukozyten 9600 pro Mikroliter."),
                     ("Die Fortbildung beginnt im großen Besprechungsraum, regelmäßig um fünfzehn Uhr.",
                      "Die Fortbildung beginnt im grossen Besprechungsraum, regelmässig um 15 Uhr."),
                     ("Kalium fünf Komma acht, Kreatinin zwei Komma drei Milligramm pro Deziliter.", "Kalium 5,9, Kreatinin 2,3 mg/dl."),
                     ("Blutdruck einhundertfünfunddreißig zu fünfundachtzig, Herzfrequenz zweiundsiebzig pro Minute.",
                      "Blutdruck 135 zu 85 Hz Frequenz 72 pro Minute.")):
        z, f = target(ref, hyp)
        print("SOLL", ref); print("HÖRT", hyp); print("ZIEL", z, "|", f, "berichtigt | Rest", score(ref, z)[0]); print()
    sys.exit()

train, test = rows_of(src), rows_of(src / T.TESTS)
print(f"Übungssätze: {len(train)} ({sum(r['sec'] for r in train) / 60:.1f} min) | Prüfsätze: {len(test)} ({sum(r['sec'] for r in test) / 60:.1f} min)", flush=True)
if not train or not test:
    sys.exit("Es fehlen Übungssätze oder Prüfsätze (im Stimmtraining vorlesen und „Messen …“).")

import nemo.collections.asr as nemo_asr
try:
    import lightning.pytorch as pl
except ImportError:
    import pytorch_lightning as pl

print("Lade Ausgangsmodell …", flush=True)
model = nemo_asr.models.ASRModel.restore_from(hf_hub_download("primeline/parakeet-primeline", "2_95_WER.nemo"), map_location="cuda")


def hear(paths, batch=16):
    out = model.transcribe([str(p) for p in paths], batch_size=batch, verbose=False, num_workers=0)
    if isinstance(out, tuple):
        out = out[0]
    return [getattr(o, "text", o) for o in out]


# ---- vorher: was hört das Ausgangsmodell bei dieser Stimme? ----
t = time.time()
before_train, before_test = hear([r["audio"] for r in train]), hear([r["audio"] for r in test])
print(f"Angehört in {time.time() - t:.0f} s | Wortfehler vorher: Übungssätze {read_wer(train, before_train):.1f} %, Prüfsätze {read_wer(test, before_test):.1f} %", flush=True)
unclear = wrong_number = fixed_total = 0
passed = 0.0
for r, h in zip(train, before_train):
    r["bis"] = passed = passed + r["sec"]                       # so viele Sekunden waren mit diesem Satz gelesen
    e, n = score(r["text"], h)
    r["vorher"], r["ziel"], r["ok"] = h, "", False
    if e / max(n, 1) > 0.5:
        unclear += 1; continue                                    # passt nicht zum Satz (verlesen, abgebrochen)
    r["ziel"], f = target(r["text"], h)
    if score(r["text"], r["ziel"])[0]:
        wrong_number += 1; continue                               # Zahl oder Einheit anders gehört: nicht lernen
    r["ok"] = True; fixed_total += f
usable = [r for r in train if r["ok"]]
print(f"Brauchbar: {len(usable)} von {len(train)} (unverständlich {unclear}, Zahl oder Einheit weicht ab {wrong_number}); berichtigte Stellen {fixed_total}", flush=True)
for r in [r for r in train if r["ziel"] and not r["ok"]][:4] + [r for r in usable if r["ziel"] != r["vorher"]][:4]:
    print("  SOLL", r["text"][:110]); print("  HÖRT", r["vorher"][:110]); print("  ZIEL", r["ziel"][:110], "" if r["ok"] else "(nicht gelernt)")

# ---- Anker: echte Aufnahmen anderer Stimmen mit den Texten des Ausgangsmodells ----
anchor_dir = pathlib.Path(arg("ankerordner", str(work.parent / "anker"))); anchor_list = anchor_dir / "anker.json"
if ANCHOR <= 0:
    anchor = []
elif anchor_list.exists():
    anchor = json.load(open(anchor_list, encoding="utf-8"))
else:
    import pyarrow.parquet as pq
    anchor_dir.mkdir(parents=True, exist_ok=True)
    pf = pq.ParquetFile(hf_hub_download("facebook/multilingual_librispeech", "german/dev-00000-of-00001.parquet", repo_type="dataset"))
    paths, gold = [], {}
    for batch in pf.iter_batches(batch_size=64, columns=["audio"]):
        for row in batch.to_pylist():
            a, sr = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
            if sr != 16000 or not 4 <= len(a) / sr <= 12:
                continue
            p = anchor_dir / f"a{len(paths):04d}.flac"; sf.write(str(p), a, sr); paths.append((p, len(a) / sr))
            if len(paths) >= 900:
                break
        if len(paths) >= 900:
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
            rs = av.AudioResampler(format="s16", layout="mono", rate=16000)
            out = [o.to_ndarray().reshape(-1) for f in c.decode(audio=0) for o in rs.resample(f)]
            out += [o.to_ndarray().reshape(-1) for o in rs.resample(None)]
            c.close()
            a = np.concatenate(out).astype(np.float32) / 32768
            if not 3 <= len(a) / 16000 <= 14:
                continue
            p = anchor_dir / f"m{more:04d}.flac"; sf.write(str(p), a, 16000); paths.append((p, len(a) / 16000)); gold[str(p)] = row[text_col]; more += 1
            if more >= 600:
                break
        print("MultiMed-Anker:", more, flush=True)
    except Exception as e:
        print("MultiMed nicht nutzbar:", repr(e)[:200], flush=True)
    texts = hear([p for p, _ in paths])
    try:
        lex = json.load(open(ROOT / "diktat" / "fachlexikon.json", encoding="utf-8"))
        allowed = {w.lower() for w in lex.get("begriffe", []) + lex.get("kern", [])}
    except Exception as e:
        allowed = set(); print("Lexikon fehlt:", repr(e)[:100], flush=True)
    anchor = []
    for (p, s), tx in zip(paths, texts):
        if len(tx.split()) < 3:
            continue
        g = gold.get(str(p))
        if g and allowed:
            e, n = errors(g, tx)
            if e / max(n, 1) > 0.5:
                continue                      # Transkript und Aufnahme passen nicht zusammen
            tx, _ = merge(g, tx, allowed)
        anchor.append({"audio": str(p), "sec": round(s, 2), "text": tx})
    json.dump(anchor, open(anchor_list, "w", encoding="utf-8"), ensure_ascii=False)
print("Anker:", len(anchor), "echte Aufnahmen,", round(sum(a["sec"] for a in anchor) / 60), "min", flush=True)
random.Random(1).shuffle(anchor)
anchor_held, anchor_train = anchor[:120], anchor[120:]
before_anchor = [a["text"] for a in anchor_held]                 # Soll ist der Text des Ausgangsmodells


def manifest(name, rows):
    p = work / name
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"audio_filepath": r["audio"], "duration": r["sec"], "text": r.get("ziel") or r["text"]}, ensure_ascii=False) + "\n")
    return str(p)


# ---- nur Decoder und Joint lernen ----
model.encoder.freeze()
for p in model.preprocessor.parameters():
    p.requires_grad = False
_train = model.train
def train_mode(mode=True):                   # der Hörteil bleibt auch während des Trainings im Auswertungsmodus
    out = _train(mode); model.encoder.eval(); model.preprocessor.eval(); return out
model.train = train_mode
if getattr(model, "spec_augmentation", None) is not None:
    model.spec_augmentation = None
if "--torchloss" in sys.argv:               # Verlustfunktion in reinem PyTorch: langsamer, braucht aber keine CUDA-Zusatzbibliotheken
    from nemo.collections.asr.losses.rnnt import RNNTLoss
    kw = dict(OmegaConf.to_container(model.cfg.loss.tdt_kwargs))
    model.loss = RNNTLoss(num_classes=model.joint.num_classes_with_blank - 1 - model.joint.num_extra_outputs, loss_name="tdt_pytorch",
                          loss_kwargs=dict(durations=kw["durations"], sigma=kw.get("sigma", 0.0)), reduction=model.cfg.get("rnnt_reduction", "mean_batch"))
    model.joint.set_loss(model.loss)
base = {"decoder": {k: v.detach().cpu().clone() for k, v in model.decoder.state_dict().items()},
        "joint": {k: v.detach().cpu().clone() for k, v in model.joint.state_dict().items()}}
val_m = manifest("val.json", usable[:8])     # wird nicht ausgewertet (limit_val_batches=0), NeMo verlangt die Angabe


class Tick(pl.Callback):
    def __init__(self):
        self.t = time.time()
    def on_train_batch_end(self, trainer, module, outputs, batch, idx):
        if trainer.global_step % 50 == 0:
            loss = outputs["loss"].item() if isinstance(outputs, dict) else float(outputs)
            print("   Schritt", trainer.global_step, "Verlust", round(loss, 3), "|", round(time.time() - self.t), "s", flush=True)


curve = [{"minuten": 0, "saetze": 0, "pruef": read_wer(test, before_test), "anker_abweichung": 0.0, "hyp": before_test}]
for minutes in MINUTES:
    part = [r for r in usable if r["bis"] <= minutes * 60 + 1]
    if not part or (len(curve) > 1 and len(part) == curve[-1]["saetze"]):
        print(f"{minutes:g} min: nicht mehr Material als in der Stufe davor, übersprungen", flush=True)
        continue
    model.decoder.load_state_dict(base["decoder"]); model.joint.load_state_dict(base["joint"])
    for m in (model.decoder, model.joint):
        for p in m.parameters():
            p.requires_grad = True
    rnd = random.Random(0)
    extra = rnd.sample(anchor_train, min(len(anchor_train), max(60, int(ANCHOR * len(part))))) if anchor_train else []
    rows = part + extra; rnd.shuffle(rows)
    steps = max(40, EPOCHS * -(-len(rows) // BS))
    model.setup_training_data(OmegaConf.create(dict(manifest_filepath=manifest("train.json", rows), sample_rate=16000, batch_size=BS, shuffle=True, num_workers=0,
                                                    pin_memory=True, max_duration=24, min_duration=0.5, is_tarred=False, use_lhotse=False)))
    model.setup_multiple_validation_data(OmegaConf.create(dict(manifest_filepath=val_m, sample_rate=16000, batch_size=BS, shuffle=False, num_workers=0, use_lhotse=False)))
    optim = OmegaConf.create(dict(name="adamw", lr=LR, betas=[0.9, 0.98], weight_decay=1e-3,
                                  sched=dict(name="CosineAnnealing", warmup_steps=max(5, steps // 10), min_lr=LR / 20, max_steps=steps)))
    with open_dict(model.cfg):
        model.cfg.optim = optim                 # auch dort, wo Lightning beim Start nachsieht
    model.setup_optimization(optim)
    trainer = pl.Trainer(accelerator="gpu", devices=1, max_steps=steps, precision=32, gradient_clip_val=1.0, log_every_n_steps=25,
                         enable_checkpointing=False, logger=False, num_sanity_val_steps=0, limit_val_batches=0, enable_progress_bar=False)
    model.set_trainer(trainer)
    trainer.callbacks.append(Tick())
    t = time.time()
    print(f"{minutes:g} min: {len(part)} Übungssätze ({sum(r['sec'] for r in part) / 60:.1f} min) + {len(extra)} Anker, {steps} Schritte", flush=True)
    trainer.fit(model)
    took = time.time() - t
    model.eval().cuda()
    after = hear([r["audio"] for r in test])
    dev = wer(anchor_held, hear([a["audio"] for a in anchor_held])) if anchor_held else 0.0
    out = work / f"m{minutes:g}"; out.mkdir(exist_ok=True)
    torch.save({"decoder": model.decoder.state_dict(), "joint": model.joint.state_dict()}, out / "decoder_joint.pt")
    curve.append({"minuten": minutes, "saetze": len(part), "anker": len(extra), "schritte": steps, "sekunden": round(took),
                  "pruef": read_wer(test, after), "anker_abweichung": dev, "hyp": after})
    print(f"   Prüfsätze {curve[0]['pruef']:.2f} % -> {curve[-1]['pruef']:.2f} % | andere Stimmen weichen ab um {dev:.2f} % | Training {took:.0f} s", flush=True)
json.dump({"pruefsaetze": [r["text"] for r in test], "kurve": curve, "epochen": EPOCHS, "lernrate": LR, "anker": ANCHOR},
          open(work / "kurve.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- zum Schluss: jede Stufe als ONNX-Datei für die App (der Export friert die Gewichte ein, deshalb erst jetzt) ----
for c in curve[1:]:
    out = work / f"m{c['minuten']:g}"
    state = torch.load(out / "decoder_joint.pt", map_location="cuda")
    model.decoder.load_state_dict(state["decoder"]); model.joint.load_state_dict(state["joint"])
    model.eval().cuda()
    target = out / "decoder_joint-model.onnx"
    try:
        with torch.no_grad():
            model.get_export_subnet("decoder_joint")._export(str(target))
    except Exception as e:                     # ältere NeMo-Fassung: alles exportieren und den Hörteil wieder löschen
        print("Einzel-Export ging nicht (", repr(e)[:160], "), exportiere das ganze Modell", flush=True)
        raw = out / "roh"; raw.mkdir(exist_ok=True)
        with torch.no_grad():
            model.export(str(raw / "model.onnx"))
        os.replace(raw / "decoder_joint-model.onnx", target)
        import shutil
        shutil.rmtree(raw, ignore_errors=True)
    print("EXPORT", out.name, round(target.stat().st_size / 1e6), "MB", flush=True)
print("KURVE", " | ".join(f"{c['minuten']:g} min: {c['pruef']:.2f} %" for c in curve), flush=True)
print("FERTIG", flush=True)
