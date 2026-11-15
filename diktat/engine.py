"""Aufnahme, Spracherkennung und Textnachbearbeitung."""
import logging
import re
import time

import numpy as np
import sounddevice as sd

RATE = 16000
# Das Modell verliert ab etwa 23 s Länge Text (gemessen: 22,7 s vollständig, 24,2 s nur noch die
# Hälfte, 35 s leer). Deshalb wird alles in Stücke von 10 bis 18 s geschnitten, jeweils an der
# leisesten Stelle zwischen Sekunde 10 und 18.
TARGET, SEARCH = 10.0, 8.0
log = logging.getLogger("diktat")


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


def quiet_cut(audio: np.ndarray, target=TARGET, search=SEARCH) -> int:
    """Index der leisesten Stelle zwischen target und target+search Sekunden."""
    lo, hi = int(target * RATE), int((target + search) * RATE)
    win = int(0.05 * RATE)
    seg = audio[lo:hi]
    n = len(seg) // win
    rms = np.sqrt(np.mean(seg[: n * win].reshape(n, win) ** 2, axis=1))
    # über 0,3 s glätten, damit eine echte Pause gewinnt
    rms = np.convolve(rms, np.ones(6) / 6, mode="same")
    return lo + int(np.argmin(rms)) * win + win // 2


def split_long(audio: np.ndarray, target=TARGET, search=SEARCH) -> list[np.ndarray]:
    """Aufnahmen über 18 s an Sprechpausen teilen (siehe TARGET)."""
    chunks = []
    while len(audio) > (target + search) * RATE:
        cut = quiet_cut(audio, target, search)
        chunks.append(audio[:cut])
        audio = audio[cut:]
    chunks.append(audio)
    return chunks


def stream_chunks(blocks, target=TARGET, search=SEARCH):
    """Aus einem Strom von Audioblöcken (float32, 16 kHz) Stücke von 10 bis 18 s schneiden,
    jeweils an einer Sprechpause. Hält nie mehr als ein Stück im Speicher."""
    parts, n = [], 0
    limit = int((target + search) * RATE)
    for block in blocks:
        if block is None or not len(block):
            continue
        parts.append(block)
        n += len(block)
        while n > limit:
            buf = np.concatenate(parts)
            cut = quiet_cut(buf, target, search)
            yield buf[:cut]
            parts, n = [buf[cut:]], len(buf) - cut
    if n:
        yield np.concatenate(parts)


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

    def load(self, notify=None):
        import onnx_asr
        import onnxruntime as ort

        cfg = self.cfg
        so = ort.SessionOptions()
        if cfg.get("threads"):
            so.intra_op_num_threads = int(cfg["threads"])
        kw = dict(quantization=cfg.get("quantization") or None,
                  providers=[cfg.get("provider") or "CPUExecutionProvider"], sess_options=so)
        t = time.time()
        from huggingface_hub import snapshot_download
        q = cfg.get("quantization")
        files = ["config.json", "vocab.txt", f"*-model.{q}.onnx*" if q else "*-model.onnx*"]
        try:
            # schon geladen? Dann ohne Netzwerk starten.
            path = snapshot_download(cfg["model"], allow_patterns=files, local_files_only=True)
        except Exception:
            log.info("Modell nicht im lokalen Cache, lade %s herunter", cfg["model"])
            if notify:
                notify("Sprachmodell wird einmalig heruntergeladen (650 MB) …")
            path = snapshot_download(cfg["model"], allow_patterns=files)
        model = onnx_asr.load_model("nemo-conformer-tdt", path, **kw)
        model.recognize(np.zeros(RATE, dtype=np.float32), sample_rate=RATE)  # aufwärmen
        self.model = model
        log.info("Modell bereit nach %.1f s", time.time() - t)

    def transcribe_stream(self, blocks, on_part=None, cancelled=lambda: False) -> str:
        """Beliebig langen Audiostrom stückweise erkennen.

        on_part(bisheriger_text, sekunden_fertig) wird nach jedem Stück aufgerufen.
        """
        texts, done = [], 0.0
        for chunk in stream_chunks(blocks):
            if cancelled():
                break
            done += len(chunk) / RATE
            if len(chunk) >= 0.2 * RATE and float(np.abs(chunk).max()) >= 0.004:
                text = (self.model.recognize(chunk, sample_rate=RATE) or "").strip()
                if text:
                    texts.append(text)
            if on_part:
                on_part(join_parts(texts), done)
        return join_parts(texts)

    def transcribe(self, audio: np.ndarray) -> str:
        parts = []
        for chunk in split_long(audio):
            if len(chunk) < 0.1 * RATE:
                continue
            text = self.model.recognize(chunk, sample_rate=RATE)
            if text and text.strip():
                parts.append(text.strip())
        return " ".join(parts)


def _phrase(key: str) -> str:
    return r"(?<!\w)" + r"\s+".join(re.escape(w) for w in key.split()) + r"(?!\w)"


def postprocess(text: str, cfg: dict) -> str:
    text = text.strip()
    if not text:
        return ""
    for wrong, right in (cfg.get("dictionary") or {}).items():
        text = re.sub(_phrase(wrong), lambda m, r=right: r, text, flags=re.IGNORECASE)
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
