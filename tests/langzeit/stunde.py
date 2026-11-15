"""Langzeittest: eine Stunde Diktat durch die echte Verarbeitungskette schicken und zählen, was fehlt.

Aufruf:  python stunde.py <Arbeitsordner> [Minuten]
Voraussetzung: saetze.txt und s0001.wav … im Arbeitsordner (siehe saetze.py und tts.ps1).

Ablauf
  1. Sätze mit zufälligen Pausen (auch ganz ohne Pause und mit langen Denkpausen) zu einer Aufnahme
     zusammensetzen, leises Raumrauschen dazu.
  2. Vergleichstext: jeden Satz einzeln erkennen (kurz, also ohne Schnittstellen).
  3. Datei-Weg:    die ganze Aufnahme als Datei transkribieren.
  4. Aufnahme-Weg: dieselbe Aufnahme als Mikrofon-Blöcke einspeisen (schneller als Echtzeit).
  5. Absturz-Weg:  Aufnahme mittendrin abbrechen und aus der Sicherungsdatei wiederherstellen.
  6. Wort für Wort gegen den Vergleichstext halten.
"""
import difflib
import json
import os
import pathlib
import queue
import re
import sys
import threading
import time
import wave

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent.parent))
import numpy as np
from PySide6 import QtWidgets
from PySide6.QtCore import QTimer

from diktat import config, engine
from diktat.longform import LongJob

work = pathlib.Path(sys.argv[1])
minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
RATE = 16000
out = open(work / "bericht.txt", "a", encoding="utf-8")


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    out.write(line + "\n")
    out.flush()


def tokens(text):
    return re.findall(r"[a-zäöüß0-9]+", text.lower())


# ---------- 1. Aufnahme zusammensetzen
sentences = (work / "saetze.txt").read_text(encoding="utf-8").splitlines()
rng = np.random.default_rng(7)
parts, spans, pos, used = [], [], 0, 0
for i, _ in enumerate(sentences, 1):
    with wave.open(str(work / f"s{i:04d}.wav")) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768 * 0.35
    # Stille am Anfang und Ende der Sprachausgabe abschneiden, damit „ohne Pause“ wirklich ohne Pause ist
    loud = np.flatnonzero(np.abs(a) > 0.004)
    a = a[max(0, loud[0] - 160): loud[-1] + 160]
    r = rng.random()
    if r < 0.15:
        gap = rng.uniform(0.0, 0.04)        # durchgesprochen
    elif r < 0.75:
        gap = rng.uniform(0.2, 0.7)
    elif r < 0.95:
        gap = rng.uniform(0.8, 2.0)
    else:
        gap = rng.uniform(3.0, 8.0)         # Denkpause
    if i in (150, 400):
        gap = 45.0 if i == 150 else 180.0   # Telefon klingelt, Patient wird umgelagert
    parts += [a, np.zeros(int(gap * RATE), np.float32)]
    spans.append((pos, pos + len(a)))
    pos += len(a) + int(gap * RATE)
    used = i
    if pos >= minutes * 60 * RATE:
        break
audio = np.concatenate(parts)
audio += (rng.standard_normal(len(audio)) * 0.0008).astype(np.float32)   # Raumrauschen
say(f"== Aufnahme: {len(audio) / RATE / 60:.1f} Minuten, {used} Sätze, "
    f"{sum(len(tokens(s)) for s in sentences[:used])} Wörter im Vorlesetext")
wav_path = work / "stunde.wav"
with wave.open(str(wav_path), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
    w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())

t = engine.Transcriber(dict(config.DEFAULTS))
t.load()

# ---------- 2. Vergleichstext (Satz für Satz, zwischengespeichert)
base_file = work / "vergleich.json"
base = json.loads(base_file.read_text(encoding="utf-8")) if base_file.exists() else {}
start = time.time()
for i in range(1, used + 1):
    if str(i) not in base:
        s, e = spans[i - 1]
        base[str(i)] = t.model.recognize(audio[s:e], sample_rate=RATE)
        if i % 100 == 0:
            base_file.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
base_file.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
ref, ref_sentence = [], []
for i in range(1, used + 1):
    tk = tokens(base[str(i)])
    ref += tk
    ref_sentence += [i] * len(tk)
empty = [i for i in range(1, used + 1) if not tokens(base[str(i)])]
say(f"== Vergleichstext: {len(ref)} Wörter ({time.time() - start:.0f} s), leere Sätze: {empty}")


def content(text):
    """Inhaltswörter (ab 4 Buchstaben) und Zahlen; der Zähler „Befund N.“ zählt nicht mit."""
    return [w for w in re.findall(r"[a-zäöüß]{4,}|\d+", text.lower()) if w != "befund"]


script = [w for s in sentences[:used] for w in content(re.sub(r"^Befund \d+\. ", "", s))]


def against_script(name, text):
    """Hält einen Text gegen das, was tatsächlich vorgelesen wurde (nur Inhaltswörter und Zahlen)."""
    got = content(text)
    lost = changed = 0
    gaps = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, script, got, autojunk=False).get_opcodes():
        if tag == "delete":
            lost += i2 - i1
            gaps.append((i2 - i1, " ".join(script[i1:i2])))
        elif tag == "replace":
            changed += i2 - i1
            if i2 - i1 >= 3:
                gaps.append((i2 - i1, " ".join(script[i1:i2]) + " -> " + " ".join(got[j1:j2])))
    say(f"-- {name} gegen den Vorlesetext: {len(script)} Inhaltswörter | fehlend {lost} | anders {changed} | "
        f"längste Lücke {max([g[0] for g in gaps], default=0)} Wörter")
    for size, words in sorted(gaps, reverse=True)[:8]:
        say(f"   {size} Wörter: {words}")
    return lost


against_script("Satz für Satz einzeln (Bestfall)", " ".join(base[str(i)] for i in range(1, used + 1)))


def compare(name, text, chunk_ends=None):
    """Hält einen Text gegen den Vergleichstext; gibt die Zahl verlorener Wörter zurück."""
    got = tokens(text)
    sm = difflib.SequenceMatcher(None, ref, got, autojunk=False)
    lost = added = changed = 0
    events = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            lost += i2 - i1
        elif tag == "insert":
            added += j2 - j1
        else:
            changed += max(i2 - i1, j2 - j1)
        near = ""
        if chunk_ends is not None:
            near = " [an Schnittstelle]" if any(abs(j1 - c) <= 2 or abs(j2 - c) <= 2 for c in chunk_ends) else " [mitten im Stück]"
        where = ref_sentence[min(i1, len(ref) - 1)]
        events.append((i2 - i1 if tag != "insert" else 0,
                       f"   Satz {where}: {tag}  soll „{' '.join(ref[i1:i2])}“  ist „{' '.join(got[j1:j2])}“{near}"))
    marks = set(int(n) for n in re.findall(r"befund (\d+)", " ".join(got)))
    ref_marks = set(int(n) for n in re.findall(r"befund (\d+)", " ".join(ref)))
    say(f"-- {name}: {len(got)} Wörter | fehlend {lost} | zusätzlich {added} | abweichend {changed} | "
        f"Satzanfänge „Befund N“ gefunden {len(marks & ref_marks)} von {len(ref_marks)}")
    missing = sorted(ref_marks - marks)
    if missing:
        say(f"   fehlende Satzanfänge: {missing[:40]}")
    for _, line in sorted(events, key=lambda e: -e[0])[:10]:
        say(line)
    return lost + changed


# ---------- 3. Datei-Weg
cuts, texts, skipped = [], [], []
orig_chunks = engine.stream_chunks


def spy(blocks, *a, **k):
    for c, still in orig_chunks(blocks, *a, **k):
        cuts.append(len(c))
        if still:
            skipped.append(len(c))
        yield c, still


engine.stream_chunks = spy
start = time.time()
seconds, blocks = engine.decode_file(wav_path)
text_file = t.transcribe_stream(blocks, lambda so_far, done: texts.append(so_far))
took = time.time() - start
lens = np.array(cuts) / RATE
ends, n = [], 0
prev = 0
for so_far in texts:               # Wortposition jeder Schnittstelle im Ergebnis
    n = len(tokens(so_far))
    ends.append(n)
say(f"== Datei-Weg: {seconds / 60:.1f} min in {took:.0f} s (Faktor {seconds / took:.0f}), {len(cuts)} Stücke, "
    f"längstes {lens.max():.1f} s, Summe der Stücke = Aufnahme: {abs(lens.sum() - len(audio) / RATE) < 0.01}, "
    f"davon als Stille übersprungen: {sum(skipped) / RATE / 60:.1f} min")
(work / "text_datei.txt").write_text(text_file, encoding="utf-8")
bad_file = compare("Datei-Weg", text_file, ends)
against_script("Datei-Weg", text_file)
engine.stream_chunks = orig_chunks

# ---------- 4. und 5. Aufnahme-Weg und Absturz
config.DIR = work / "daten"
config.DIR.mkdir(exist_ok=True)


class Ctl:
    cfg = {"dictionary": {}, "microphone": None}
    transcriber = t


qa = QtWidgets.QApplication(sys.argv)
result = {}
job = LongJob(Ctl())
job.finished.connect(lambda text, secs, err: result.update(text=text, secs=secs, err=err))


def feed(q, upto, speed):
    """10-ms-Blöcke wie vom Mikrofon, speed-mal schneller als Echtzeit."""
    step, t0 = 160, time.time()
    for k in range(0, upto, step):
        q.put(audio[k:k + step].copy())
        if k % (RATE * 5) == 0:
            ahead = k / RATE / speed - (time.time() - t0)
            if ahead > 0:
                time.sleep(ahead)


def wait(cond, then, t0=None, limit=1500):
    t0 = t0 or time.time()
    if cond():
        return then()
    if time.time() - t0 > limit:
        say("FEHLER: Zeitüberschreitung vor", then.__name__)
        return finish(1)
    QTimer.singleShot(200, lambda: wait(cond, then, t0, limit))


def begin_recording(name):
    job._begin()
    job._queue = queue.Queue()
    (config.DIR / "aufnahmen").mkdir(exist_ok=True)
    job.wav_path = config.DIR / "aufnahmen" / name
    threading.Thread(target=job._run, args=(lambda: (None, job._mic_blocks()), job.wav_path), daemon=True).start()


def step_record():
    global rec_start
    rec_start = time.time()
    begin_recording("lauf.wav")

    def run():
        feed(job._queue, len(audio), 12)
        job.stop_recording()
    threading.Thread(target=run, daemon=True).start()
    wait(lambda: "text" in result, after_record)


def after_record():
    say(f"== Aufnahme-Weg: {result['secs'] / 60:.1f} min in {time.time() - rec_start:.0f} s eingespeist und erkannt, "
        f"Fehler: {result['err']!r}, Sicherungsdatei gelöscht: {not (config.DIR / 'aufnahmen' / 'lauf.wav').exists()}")
    (work / "text_aufnahme.txt").write_text(result["text"], encoding="utf-8")
    global bad_rec
    bad_rec = compare("Aufnahme-Weg", result["text"])
    against_script("Aufnahme-Weg", result["text"])
    say(f"   gleicher Text wie Datei-Weg: {tokens(result['text']) == tokens(text_file)}")
    step_crash()


def step_crash():
    """Absturz nach 20 Minuten: Sicherungsdatei wird nie ordentlich geschlossen."""
    upto = min(len(audio), 20 * 60 * RATE)
    path = config.DIR / "aufnahmen" / "absturz.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes((np.clip(audio[:upto], -1, 1) * 32767).astype(np.int16).tobytes())
    raw = bytearray(path.read_bytes())
    raw[4:8] = (36).to_bytes(4, "little")     # Kopf wie nach einem Absturz: Länge null
    raw[40:44] = (0).to_bytes(4, "little")
    path.write_bytes(raw)
    recover = getattr(engine, "recover_wav", None)
    if recover is None:
        say("== Absturz-Weg: keine Wiederherstellung vorhanden (engine.recover_wav fehlt)")
        try:
            secs, _ = engine.decode_file(path)
            say(f"   normale Dekodierung liest davon {secs or 0:.0f} s von {upto / RATE:.0f} s")
        except Exception as e:
            say(f"   normale Dekodierung scheitert: {e}")
        return finish(0)
    blocks = recover(path)
    text = t.transcribe_stream(blocks)
    upto_words = sum(len(tokens(base[str(i)])) for i in range(1, used + 1) if spans[i - 1][1] <= upto)
    say(f"== Absturz-Weg: aus der beschädigten Sicherungsdatei {len(tokens(text))} Wörter gerettet, "
        f"erwartet rund {upto_words}")
    part = [w for s in sentences[:sum(1 for a, b in spans[:used] if b <= upto)] for w in content(re.sub(r"^Befund \d+\. ", "", s))]
    got = content(text)
    lost = sum(i2 - i1 for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, part, got, autojunk=False).get_opcodes()
               if tag == "delete")
    say(f"   gegen den Vorlesetext: {len(part)} Inhaltswörter, fehlend {lost}")
    finish(0)


def finish(code):
    say("== ENDE")
    out.close()
    os._exit(code)


QTimer.singleShot(0, step_record)
qa.exec()
