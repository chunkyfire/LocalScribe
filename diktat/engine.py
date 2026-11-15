"""Aufnahme, Spracherkennung und Textnachbearbeitung."""
import collections
import logging
import re
import time

import numpy as np
import sounddevice as sd

log = logging.getLogger("diktat")
RATE = 16000
# Was die Messungen an diesem Modell ergeben haben (tests/langzeit):
# 1. Ab etwa 23 s Länge verliert es Text (22,7 s vollständig, 24,2 s nur noch die Hälfte, 35 s leer).
# 2. Enthält ein Stück eine Sprechpause, lässt es danach oder davor öfter ganze Satzteile weg –
#    bei 10 bis 18 s langen Stücken fehlten in einer Stunde Diktat rund 8 % der Wörter.
# Deshalb bekommt das Modell immer nur eine zusammenhängende Äußerung: Geschnitten wird an jeder
# Sprechpause ab MIN_PAUSE, und kein Stück wird länger als MAX_LEN.
MIN_PAUSE, MAX_LEN, PAD = 0.3, 12.0, 0.2
QUIET_TRUST = 0.01   # Grundrauschen darüber (lauter Raum): Stille wird nicht mehr aussortiert
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


def quiet_cut(audio: np.ndarray, target, search) -> int:
    """Index der leisesten Stelle zwischen target und target+search Sekunden."""
    lo, hi = int(target * RATE), int((target + search) * RATE)
    win = int(0.05 * RATE)
    seg = audio[lo:hi]
    n = len(seg) // win
    rms = np.sqrt(np.mean(seg[: n * win].reshape(n, win) ** 2, axis=1))
    # über 0,3 s glätten, damit eine echte Pause gewinnt
    rms = np.convolve(rms, np.ones(6) / 6, mode="same")
    return lo + int(np.argmin(rms)) * win + win // 2


class Segmenter:
    """Zerlegt einen Audiostrom an Sprechpausen in einzelne Äußerungen.

    feed(block) nimmt beliebig große Blöcke (float32, 16 kHz) und gibt fertige Stücke als
    (audio, still) zurück, flush() den Rest. Alle Stücke zusammen ergeben wieder exakt den
    Eingang. „still“ heißt: In dem Stück lag kein einziger Rahmen über dem Grundrauschen.
    Solche Stücke werden nicht erkannt, weil das Modell aus reiner Stille gelegentlich Wörter
    erfindet (gemessen: „Thank you.“ bei stummgeschaltetem Mikrofon). Ist das Grundrauschen
    ungewöhnlich hoch (über QUIET_TRUST), gilt nichts als still: Dann wird lieber alles erkannt.

    Sprache wird am Pegel relativ zum Grundrauschen erkannt; das Grundrauschen wird laufend aus
    den letzten 30 s geschätzt, eine feste Lautstärke-Schwelle gibt es nicht.
    """
    FRAME = 320  # 20 ms

    def __init__(self, min_pause=MIN_PAUSE, max_len=MAX_LEN, pad=PAD, floor=None):
        self.min_pause = int(round(min_pause * RATE / self.FRAME))
        self.max_frames = int(round(max_len * RATE / self.FRAME))
        self.pad = int(round(pad * RATE / self.FRAME))
        self.max_len = max_len
        self.fixed_floor = floor
        self.floor = floor
        self.history = collections.deque(maxlen=1500)   # 30 s Pegelwerte
        self.rest = np.zeros(0, np.float32)
        self.cur = []            # Rahmen des laufenden Stücks
        self.speech = True       # Anfang zählt als Sprache, bis das Grundrauschen bekannt ist
        self.quiet = 0           # leise Rahmen in Folge (im Sprach-Stück)
        self.onset = 0           # laute Rahmen in Folge (im Stille-Stück)
        self.loud = 0            # laute Rahmen im laufenden Stück
        self.count = 0
        self.noisy = False       # Grundrauschen über QUIET_TRUST
        self.noisy_frames = int(round(min(max_len, 8.0) * RATE / self.FRAME))

    def _loud(self, rms, inside):
        if rms < 1e-7:
            return False       # digitale Stille (stummes Mikrofon) ist nie Sprache
        if self.floor is None:
            return True
        return rms > max(self.floor * (3.0 if inside else 4.0), 1e-6)

    def _emit(self, out, frames_or_audio, loud):
        audio = frames_or_audio if isinstance(frames_or_audio, np.ndarray) else np.concatenate(frames_or_audio)
        trusted = self.floor is not None and self.floor <= QUIET_TRUST
        still = loud == 0 and (trusted or not audio.any())
        out.append((audio, still))

    def feed(self, block):
        out = []
        data = np.concatenate([self.rest, block]) if len(self.rest) else block
        n = len(data) // self.FRAME
        self.rest = data[n * self.FRAME:]
        for k in range(n):
            frame = data[k * self.FRAME:(k + 1) * self.FRAME]
            rms = float(np.sqrt(np.mean(frame * frame)))
            if self.fixed_floor is None:
                self.history.append(rms)
                self.count += 1
                if self.count >= 50 and self.count % 25 == 0:
                    self.floor = float(np.percentile(self.history, 10))
            self.cur.append(frame)
            self.noisy = self.floor is not None and self.floor > QUIET_TRUST
            if self.noisy:
                # Lauter Raum: Pausen sind am Pegel nicht mehr zu erkennen. Dann nichts aussortieren
                # und in kürzeren Abständen an der jeweils leisesten Stelle teilen.
                self.speech, self.quiet, self.loud = True, 0, self.loud + 1
                limit = self.noisy_frames
            else:
                limit = self.max_frames
            if self.noisy:
                pass
            elif self.speech:
                if self._loud(rms, True):
                    self.quiet = 0
                    self.loud += 1
                else:
                    self.quiet += 1
                if self.quiet >= self.min_pause:
                    # Pause erkannt: Äußerung samt kurzem Nachlauf abschließen
                    keep = len(self.cur) - self.quiet + self.pad
                    self._emit(out, self.cur[:keep], self.loud)
                    self.cur, self.speech, self.onset, self.loud = self.cur[keep:], False, 0, 0
                    continue
            else:
                self.onset = self.onset + 1 if self._loud(rms, False) else 0
                if self.onset >= 2:
                    # Sprache setzt ein: Stille abschließen, kurzer Vorlauf gehört zur Äußerung
                    keep = max(0, len(self.cur) - self.onset - self.pad)
                    if keep:
                        self._emit(out, self.cur[:keep], 0)
                    self.cur, self.speech, self.quiet, self.loud = self.cur[keep:], True, 0, self.onset
                    continue
            if len(self.cur) >= limit:
                # keine Pause gefunden: an der leisesten Stelle der zweiten Hälfte teilen
                audio = np.concatenate(self.cur)
                half = len(self.cur) * self.FRAME / RATE / 2
                cut = quiet_cut(audio, half, half)
                cut = max(self.FRAME, cut - cut % self.FRAME)
                self._emit(out, audio[:cut], self.loud)
                tail = audio[cut:]
                self.cur = [tail[i:i + self.FRAME] for i in range(0, len(tail), self.FRAME)]
                self.quiet = min(self.quiet, len(self.cur))
                # im Sprach-Stück vorsichtshalber weiter als Sprache werten
                self.loud = len(self.cur) if self.speech and self.loud else 0
        return out

    def flush(self):
        out = []
        parts = self.cur + ([self.rest] if len(self.rest) else [])
        if parts:
            self._emit(out, np.concatenate(parts), self.loud if self.speech else self.onset)
        self.cur, self.rest, self.quiet, self.onset, self.loud = [], np.zeros(0, np.float32), 0, 0, 0
        return out


def noise_floor(audio: np.ndarray):
    """Grundrauschen einer fertigen Aufnahme (für kurze Diktate, bei denen sofort gesprochen wird)."""
    n = len(audio) // Segmenter.FRAME
    if n < 10:
        return None
    rms = np.sqrt(np.mean(audio[: n * Segmenter.FRAME].reshape(n, Segmenter.FRAME) ** 2, axis=1))
    return float(np.percentile(rms, 10))


def split_long(audio: np.ndarray) -> list[np.ndarray]:
    """Fertige Aufnahme (Diktat per Taste) in einzelne Äußerungen zerlegen."""
    seg = Segmenter(floor=noise_floor(audio))
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
        if stats is not None and seg.noisy:
            stats["noisy"] = True
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
        rev = cfg.get("model_revision") or None
        try:
            ort.disable_telemetry_events()
        except Exception:
            pass
        files = ["config.json", "vocab.txt", f"*-model.{q}.onnx*" if q else "*-model.onnx*"]
        try:
            # schon geladen? Dann ohne Netzwerk starten.
            path = snapshot_download(cfg["model"], revision=rev, allow_patterns=files, local_files_only=True)
        except Exception:
            log.info("Modell nicht im lokalen Cache, lade %s herunter", cfg["model"])
            if notify:
                notify("Sprachmodell wird einmalig heruntergeladen (650 MB) …")
            path = snapshot_download(cfg["model"], revision=rev, allow_patterns=files)
        model = onnx_asr.load_model("nemo-conformer-tdt", path, **kw)
        model.recognize(np.zeros(RATE, dtype=np.float32), sample_rate=RATE)  # aufwärmen
        self.model = model
        log.info("Modell bereit nach %.1f s", time.time() - t)

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
                    text = (self.model.recognize(chunk, sample_rate=RATE) or "").strip()
                except Exception:
                    log.exception("Stück bei %.0f s nicht erkannt", done)
                    stats["failed"] += 1
                    text = GAP
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
