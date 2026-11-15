"""Aufnahme, Spracherkennung und Textnachbearbeitung."""
import collections
import json
import logging
import re
import time

import numpy as np
import sounddevice as sd
from pathlib import Path

from . import config, fach

from .vad import FRAME, Vad

log = logging.getLogger("diktat")
RATE = 16000
# Was die Messungen an diesem Modell ergeben haben (tests/langzeit):
# 1. Ab etwa 23 s Länge verliert es Text (22,7 s vollständig, 24,2 s nur noch die Hälfte, 35 s leer).
# 2. Enthält ein Stück eine Sprechpause, lässt es danach oder davor öfter ganze Satzteile weg –
#    bei 10 bis 18 s langen Stücken fehlten in einer Stunde Diktat rund 8 % der Wörter.
# Deshalb bekommt das Modell immer nur eine zusammenhängende Äußerung: Geschnitten wird an jeder
# Sprechpause ab MIN_PAUSE, und kein Stück wird länger als MAX_LEN.
MIN_PAUSE, MAX_LEN, PAD = 0.3, 12.0, 0.2
GAP = "[Stelle nicht erkannt]"


def input_devices() -> list[str]:
    """Namen der Eingabegeräte der Standard-Audioschnittstelle (ohne Dubletten)."""
    try:
        host = sd.default.hostapi
        names = []
        for d in sd.query_devices():
            if d["max_input_channels"] > 0 and d["hostapi"] == host and d["name"] not in names:
                names.append(d["name"])
        return names
    except Exception:
        log.exception("Geräteliste nicht lesbar")
        return []


def _device_index(name):
    if not name:
        return None
    host = sd.default.hostapi
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and d["hostapi"] == host and d["name"] == name:
            return i
    log.warning("Mikrofon %r nicht gefunden, nutze Standardgerät", name)
    return None


class Recorder:
    def __init__(self):
        self.device_name = None
        self.level = 0.0
        self._frames = []
        self._stream = None
        self._rate = RATE

    def start(self):
        self.stop()
        self._frames = []
        self.level = 0.0
        dev = _device_index(self.device_name)
        try:
            self._open(dev, RATE)
        except Exception:
            # Gerät kann kein 16 kHz: in Geräterate aufnehmen, später umrechnen
            rate = int(sd.query_devices(dev, "input")["default_samplerate"])
            self._open(dev, rate)

    def _open(self, dev, rate):
        self._rate = rate
        self._stream = sd.InputStream(samplerate=rate, channels=1, dtype="float32",
                                      device=dev, blocksize=0, callback=self._callback)
        self._stream.start()

    def _callback(self, indata, frames, t, status):
        mono = indata[:, 0].copy()
        self._frames.append(mono)
        self.level = float(np.sqrt(np.mean(mono * mono))) if len(mono) else 0.0

    def stop(self) -> np.ndarray:
        s, self._stream = self._stream, None
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                log.exception("Audiostream ließ sich nicht sauber schließen")
        self.level = 0.0
        if not self._frames:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(self._frames)
        self._frames = []
        if self._rate != RATE and len(audio):
            n = int(len(audio) * RATE / self._rate)
            audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
        return audio


class Segmenter:
    """Zerlegt einen Audiostrom an Sprechpausen in einzelne Äußerungen.

    feed(block) nimmt beliebig große Blöcke (float32, 16 kHz) und gibt fertige Stücke als
    (audio, still) zurück, flush() den Rest. Alle Stücke zusammen ergeben wieder exakt den Eingang.

    Ob gerade gesprochen wird, entscheidet Silero VAD (siehe vad.py) am Klang, unabhängig von der
    Lautstärke – das funktioniert bei sehr leiser Sprache ebenso wie in lauter Umgebung.

    „still“ heißt: Das Stück wird nicht erkannt, weil das Modell aus reiner Stille gelegentlich
    Wörter erfindet (gemessen: „Thank you.“ bei stummgeschaltetem Mikrofon). Dafür müssen zwei
    unabhängige Prüfungen übereinstimmen: Silero hört nirgends Sprache UND der Pegel hebt sich
    nirgends vom Grundrauschen ab. Im Zweifel (Flüstern, das Silero überhört) wird erkannt.
    """
    ENTER, STAY, STILL = 0.5, 0.35, 0.2

    def __init__(self, min_pause=MIN_PAUSE, max_len=MAX_LEN, pad=PAD):
        self.vad = Vad()
        self.min_pause = max(1, int(round(min_pause * RATE / FRAME)))
        self.max_frames = int(round(max_len * RATE / FRAME))
        self.pad = int(round(pad * RATE / FRAME))
        self.rest = np.zeros(0, np.float32)
        self.cur, self.probs, self.levels = [], [], []   # Rahmen des laufenden Stücks
        self.speech = False
        self.quiet = 0           # Rahmen ohne Sprache in Folge (in einer Äußerung)
        self.onset = 0           # Rahmen mit Sprache in Folge (in der Stille)
        self.history = collections.deque(maxlen=940)     # Pegel der letzten 30 s
        self.floor = None        # Grundrauschen; steigt nur langsam, fällt sofort
        self.count = 0

    def _floor(self, rms):
        self.history.append(rms)
        self.count += 1
        if self.count >= 50 and self.count % 25 == 0:
            p10 = float(np.percentile(self.history, 10))
            self.floor = p10 if self.floor is None else min(p10, self.floor * 1.02)

    def _emit(self, out, n):
        """Die ersten n Rahmen als Stück abschließen."""
        audio = np.concatenate(self.cur[:n])
        heard = max(self.probs[:n]) >= self.STILL
        raised = self.floor is None or max(self.levels[:n]) > max(self.floor * 4.0, 1e-6)
        still = not audio.any() or (not heard and not raised)
        out.append((audio, still))
        self.cur, self.probs, self.levels = self.cur[n:], self.probs[n:], self.levels[n:]

    def feed(self, block):
        out = []
        data = np.concatenate([self.rest, block]) if len(self.rest) else block
        n = len(data) // FRAME
        self.rest = data[n * FRAME:]
        for k in range(n):
            frame = data[k * FRAME:(k + 1) * FRAME]
            rms = float(np.sqrt(np.mean(frame * frame)))
            self._floor(rms)
            p = self.vad(frame)
            self.cur.append(frame)
            self.probs.append(p)
            self.levels.append(rms)
            if self.speech:
                self.quiet = 0 if p >= self.STAY else self.quiet + 1
                if self.quiet >= self.min_pause:
                    # Pause erkannt: Äußerung samt kurzem Nachlauf abschließen
                    self._emit(out, len(self.cur) - self.quiet + min(self.pad, self.quiet))
                    self.speech, self.onset = False, 0
                    continue
            else:
                self.onset = self.onset + 1 if p >= self.ENTER else 0
                if self.onset >= 2:
                    # Sprache setzt ein: Stille abschließen, kurzer Vorlauf gehört zur Äußerung
                    keep = max(0, len(self.cur) - self.onset - self.pad)
                    if keep:
                        self._emit(out, keep)
                    self.speech, self.quiet = True, 0
                    continue
            if len(self.cur) >= self.max_frames:
                # keine Pause gefunden: dort teilen, wo in der zweiten Hälfte am wenigsten Sprache ist
                half = len(self.cur) // 2
                tail = np.array(self.probs[half:]) + np.array(self.levels[half:]) / (max(self.levels[half:]) + 1e-9) * 0.01
                self._emit(out, max(1, half + int(np.argmin(tail))))
                self.quiet = min(self.quiet, len(self.cur))
        return out

    def flush(self):
        out = []
        if len(self.rest):
            if len(self.rest) >= FRAME // 2 or not self.cur:
                frame = np.concatenate([self.rest, np.zeros(FRAME - len(self.rest), np.float32)])
                self.probs.append(self.vad(frame))
                self.levels.append(float(np.sqrt(np.mean(self.rest * self.rest))))
                self.cur.append(self.rest)
            else:
                self.cur[-1] = np.concatenate([self.cur[-1], self.rest])
            self.rest = np.zeros(0, np.float32)
        if self.cur:
            self._emit(out, len(self.cur))
        self.speech, self.quiet, self.onset = False, 0, 0
        return out


def split_long(audio: np.ndarray) -> list[np.ndarray]:
    """Fertige Aufnahme (Diktat per Taste) in einzelne Äußerungen zerlegen; reine Stille fällt weg."""
    seg = Segmenter()
    return [c for c, still in seg.feed(audio) + seg.flush() if len(c) and not still]


def stream_chunks(blocks, stats=None):
    """Aus einem Strom von Audioblöcken (float32, 16 kHz) einzelne Äußerungen schneiden.
    Hält nie mehr als ein Stück im Speicher. Gibt (audio, still) zurück; alle Stücke zusammen
    ergeben wieder exakt den Eingang."""
    seg = Segmenter()
    for block in blocks:
        if block is None or not len(block):
            continue
        yield from seg.feed(block)
    yield from seg.flush()


def decode_file(path):
    """Audio- oder Videodatei öffnen. Gibt (Dauer in Sekunden oder None, Blockstrom) zurück."""
    import av
    container = av.open(str(path))
    if not container.streams.audio:
        container.close()
        raise ValueError("Die Datei enthält keine Tonspur.")
    duration = float(container.duration / av.time_base) if container.duration else None

    def blocks():
        try:
            resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    yield out.to_ndarray().reshape(-1).astype(np.float32) / 32768
            for out in resampler.resample(None):
                yield out.to_ndarray().reshape(-1).astype(np.float32) / 32768
        finally:
            container.close()
    return duration, blocks()


def recover_wav(path, block=RATE):
    """Sicherungsdatei einer abgebrochenen Aufnahme lesen.

    Nach einem Absturz steht im Dateikopf die Länge null; die Tondaten dahinter sind aber da.
    Deshalb wird der Kopf (44 Bytes) übersprungen und der Rest als 16-Bit-Mono gelesen.
    """
    with open(path, "rb") as f:
        f.seek(44)
        while True:
            raw = f.read(block * 2)
            if len(raw) < 2:
                return
            yield np.frombuffer(raw[: len(raw) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768


def join_parts(texts) -> str:
    """Stücke zusammensetzen; nach rund 400 Zeichen beginnt am Satzende ein neuer Absatz."""
    out, para = "", 0
    for t in texts:
        t = t.strip()
        if not t:
            continue
        if not out:
            out, para = t, len(t)
        elif para >= 400 and out[-1] in ".!?":
            out, para = out + "\n\n" + t, len(t)
        else:
            out, para = out + " " + t, para + len(t) + 1
    return out


class Transcriber:
    def __init__(self, cfg):
        self.cfg = cfg
        self.model = None
        self.loaded = None       # Schlüssel des geladenen Modells aus config.MODELS
        self.kw = {}             # Zusatzangaben für das Modell (Sprache)

    def recognize(self, chunk: np.ndarray) -> str:
        """Ein Stück erkennen. Kurze englische Einwürfe verwirft die deutsche Erkennung: Aus einem
        Atemzug oder Räuspern vor dem ersten Wort macht das Modell gelegentlich „Hey!“ oder „Hello.“"""
        text = (self.model.recognize(chunk, sample_rate=RATE, **self.kw) or "").strip()
        if self.loaded in config.GERMAN:
            if len(chunk) < 2.5 * RATE and text.strip(" .!?,").lower() in PHANTOMS:
                return ""
            text = LEADING.sub("", text)        # „Hey! 58-jähriger Patient …“
        return text

    def load(self, progress=None):
        from . import modelle           # zuerst: stellt den Download auf sichtbaren Fortschritt ein
        import onnx_asr
        import onnxruntime as ort

        cfg = self.cfg
        so = ort.SessionOptions()
        if cfg.get("threads"):
            so.intra_op_num_threads = int(cfg["threads"])
        kw = dict(quantization=cfg.get("quantization") or None,
                  providers=[cfg.get("provider") or "CPUExecutionProvider"], sess_options=so)
        t = time.time()
        q = cfg.get("quantization")
        choice = cfg.get("model_choice") if cfg.get("model_choice") in config.MODELS else "de"
        repo, rev = config.MODELS[choice]["repo"], config.MODELS[choice]["revision"]
        try:
            ort.disable_telemetry_events()
        except Exception:
            pass
        files = ["config.json", "vocab.txt", "nemo128.onnx", f"*-model.{q}.onnx*" if q else "*-model.onnx*"]
        # liegt das Modell schon auf dem Rechner, startet die App ohne Netzwerk
        entry = config.MODELS[choice]
        if entry.get("path"):                    # Messungen mit einem Ordner
            path = entry["path"]
        elif entry.get("release") and q == "int8":
            # schonender gekürzte Fassung aus dem eigenen Release; ohne Netz oder bei Fehler die bisherige
            try:
                path = modelle.fetch_release(entry["release"], progress)
            except Exception as e:
                log.warning("Verbessertes Modell nicht ladbar (%s), nehme die bisherige Fassung", e)
                path = modelle.fetch(repo, rev, files, progress)
        else:
            path = modelle.fetch(repo, rev, files, progress)
        model = onnx_asr.load_model(config.MODELS[choice].get("type", "nemo-conformer-tdt"), path, **kw)
        self.kw = {"language": config.MODELS[choice]["language"]} if config.MODELS[choice].get("language") else {}
        model.recognize(np.zeros(RATE, dtype=np.float32), sample_rate=RATE, **self.kw)  # aufwärmen
        fach.near()                      # Fachlexikon jetzt laden, nicht erst beim ersten Diktat
        self.model = model
        self.loaded = choice
        log.info("Modell %s bereit nach %.1f s", choice, time.time() - t)

    def transcribe_stream(self, blocks, on_part=None, cancelled=lambda: False, stats=None) -> str:
        """Beliebig langen Audiostrom stückweise erkennen.

        on_part(bisheriger_text, sekunden_fertig) wird nach jedem Stück aufgerufen.
        Scheitert ein einzelnes Stück, läuft der Rest weiter; an der Stelle steht dann GAP im Text
        und stats["failed"] zählt mit – die Tonaufnahme darf in dem Fall nicht gelöscht werden.
        Es gibt bewusst keine feste Lautstärke-Schwelle: Auch sehr leise Sprache wird erkannt.
        """
        texts, done = [], 0.0
        stats = stats if stats is not None else {}
        stats.setdefault("failed", 0)
        stats.setdefault("chunks", 0)
        for chunk, still in stream_chunks(blocks, stats):
            if cancelled():
                break
            done += len(chunk) / RATE
            stats["chunks"] += 1
            if not still and len(chunk) >= 0.2 * RATE:
                try:
                    text = self.recognize(chunk)
                except Exception:
                    log.exception("Stück bei %.0f s nicht erkannt", done)
                    stats["failed"] += 1
                    text = GAP
                if text:
                    texts.append(text)
                    if "pieces" in stats:       # Sprecher trennen: Stimmabdruck je Äußerung
                        from . import sprecher
                        try:
                            voice = sprecher.embed(chunk) if text != GAP else None
                        except Exception:
                            log.exception("Stimmabdruck nicht berechenbar")
                            voice = None
                        stats["pieces"].append((text, voice, len(chunk) / RATE))
            if on_part:
                on_part(join_parts(texts), done)
        return join_parts(texts)

    def transcribe(self, audio: np.ndarray) -> str:
        parts = []
        for chunk in split_long(audio):
            if len(chunk) < 0.1 * RATE:
                continue
            text = self.recognize(chunk)
            if text:
                parts.append(text)
        return " ".join(parts)


LEADING = re.compile(r"^(?:hey|hello|hi|thank you|thanks)[!.]\s+(?=\S)", re.IGNORECASE)
_UNIT = r"(?:mg|µg|g|ml|IE|I\.E\.|Einheiten|Hub|Hübe)"
TIDY = [
    # Einnahmeschema: „40 mg100“ -> „40 mg 1-0-0“ (nur Ziffern 0 bis 2, nur direkt nach Dosis und Einheit)
    (re.compile(r"(\d\s?" + _UNIT + r")\s?([0-2])([0-2])([0-2])([0-2])?(?![\d,.]\d|\d|\s?(?:" + _UNIT + r"|%|l)\b)"),
     lambda m: m.group(1) + " " + "-".join(g for g in m.groups()[1:] if g)),
    (re.compile(r"\b(RR|HF|AF)(\d)"), r"\1 \2"),                               # „RR140“
    (re.compile(r"\b0([0-9])(\d{2,3}) Grad\b"), r"0-\1-\2 Grad"),              # Neutral-Null: „0090 Grad“
    (re.compile(r"\bHertz[, -]+[Ff]requenz"), "Herzfrequenz"),
    (re.compile(r"\bQuadrat[ -]?m2\b"), "Quadratmeter"),
    # „Patientin reduziertem Allgemeinzustand“: nach „Patientin“ kann kein Dativ auf -em stehen
    (re.compile(r"\b(Patient)in (?=[a-zäöü]+em\b)"), r"\1 in "),
]


def tidy(text: str) -> str:
    """Schreibweisen, die das Modell regelmäßig zusammenzieht (Dosierschema, Blutdruck, Gelenkmaße)."""
    for rx, repl in TIDY:
        text = rx.sub(repl, text)
    return text


def _phrase(key: str) -> str:
    # zwischen den Wörtern darf auch ein Bindestrich stehen („Set-Implantation“)
    return r"(?<!\w)" + r"[\s\-]+".join(re.escape(w) for w in key.split()) + r"(?!\w)"


PHANTOMS = {"hey", "hello", "hi", "thank you", "thanks", "bye", "okay", "oh", "yeah", "you", "so"}
BASE_FILE = Path(__file__).with_name("basiswoerterbuch.json")
_WORD = re.compile(r"[A-Za-zÄÖÜäöüß]+")
_base = None


def base_dictionary() -> dict:
    """Mitgeliefertes medizinisches Wörterbuch: Fehlschreibung (klein) -> richtige Schreibweise.

    Enthält nur Schreibweisen, die es als Wort nicht gibt (geprüft gegen deutsche und englische
    Wörterbücher und gegen die Fachbegriffe selbst). Richtig Geschriebenes wird nie angefasst.
    """
    global _base
    if _base is None:
        _base = {}
        try:
            for right, wrongs in json.loads(BASE_FILE.read_text(encoding="utf-8")).items():
                for wrong in wrongs:
                    _base[wrong] = right
        except Exception:
            log.exception("Basiswörterbuch nicht lesbar")
    return _base


def apply_base(text: str) -> str:
    """Wörter (und Paare aufeinanderfolgender Wörter) ersetzen, die im Basiswörterbuch stehen."""
    base = base_dictionary()
    if not base:
        return text
    words = list(_WORD.finditer(text))
    out, pos, i = [], 0, 0
    while i < len(words):
        m = words[i]
        right, end = None, m.end()
        if i + 1 < len(words) and text[m.end():words[i + 1].start()] in (" ", "-"):
            right = base.get(m.group().lower() + " " + words[i + 1].group().lower())
            if right:
                end, i = words[i + 1].end(), i + 1
        right = right or base.get(m.group().lower())
        if right:
            if right[0].islower() and m.group()[0].isupper():
                right = right[0].upper() + right[1:]       # Satzanfang bleibt groß
            out.append(text[pos:m.start()] + right)
            pos = end
        i += 1
    return "".join(out) + text[pos:]


def postprocess(text: str, cfg: dict) -> str:
    text = text.strip()
    if not text:
        return ""
    for wrong, right in (cfg.get("dictionary") or {}).items():
        text = re.sub(_phrase(wrong), lambda m, r=right: r, text, flags=re.IGNORECASE)
    if cfg.get("base_dictionary", True) and cfg.get("model_choice", "de") in config.GERMAN:
        # erst die bekannten Fehlschreibungen, dann alles, was wie ein Fachbegriff klingt
        text = tidy(fach.correct(apply_base(text), vocabulary=cfg.get("vocabulary")))
    for key, snippet in (cfg.get("snippets") or {}).items():
        text = re.sub(_phrase(key) + r"[.,;:!?]?", lambda m, r=snippet: r, text, flags=re.IGNORECASE)
    for key, repl in (cfg.get("commands") or {}).items():
        # "Satz. Neue Zeile. Satz" -> "Satz.\nSatz"
        text = re.sub(r"[ \t]*" + _phrase(key) + r"[.,;:!?]?[ \t]*", lambda m, r=repl: r, text, flags=re.IGNORECASE)
    # nach einem Zeilenumbruch groß weiterschreiben
    text = re.sub(r"(\n)([a-zäöü])", lambda m: m.group(1) + m.group(2).upper(), text)
    text = text.strip(" \t")
    if cfg.get("trailing_space", True) and text and not text.endswith("\n"):
        text += " "
    return text


def tone(freqs, ms=70, volume=0.12):
    """Kurzer Signalton (eigene, synthetische Töne)."""
    try:
        sr = 44100
        out = []
        for f in freqs:
            t = np.arange(int(sr * ms / 1000)) / sr
            w = np.sin(2 * np.pi * f * t) * volume
            fade = int(sr * 0.008)
            w[:fade] *= np.linspace(0, 1, fade)
            w[-fade:] *= np.linspace(1, 0, fade)
            out.append(w)
        sd.play(np.concatenate(out).astype(np.float32), sr, blocking=False)
    except Exception:
        log.debug("Ton nicht abspielbar", exc_info=True)
