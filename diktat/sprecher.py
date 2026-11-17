"""Sprecher unterscheiden, lokal auf der CPU.

Zwei kleine ONNX-Modelle arbeiten zusammen, wie in der Pipeline von pyannote.audio 3.1, aber ohne PyTorch:
  1. Segmentierung (pyannote segmentation-3.0, MIT, 6 MB, liegt der App bei): hört in Fenstern von zehn Sekunden,
     wer wann spricht, auch wenn Sprecher ohne Pause wechseln oder kurz gleichzeitig reden. Sie kennt je Fenster
     bis zu drei Stimmen, weiß aber nicht, wer das über die Fenster hinweg ist.
  2. Stimmabdruck (WeSpeaker ResNet34, CC-BY-4.0, 26 MB; im Komplettpaket, sonst einmalig geladen): Jede Stimme
     eines Fensters bekommt je drei Sekunden, die sie allein spricht, einen Abdruck. Ähnliche Abdrücke werden über
     alle Fenster zu Sprechern gruppiert. Die kurzen Abschnitte fangen Wechsel zwischen ähnlichen Stimmen auf, die
     die Segmentierung überhört.
Daraus entsteht eine Zeitleiste „wer spricht wann“ in Schritten von 17 ms. Jedes erkannte Wort bekommt den Sprecher,
der zu seinem Zeitpunkt spricht; der Wechsel kann also mitten in einer Äußerung liegen.

Grenzen: Reden zwei gleichzeitig, bekommt das Wort einen der beiden. Wer insgesamt nur wenige Sekunden spricht
(unter drei Sekunden oder unter zwei Prozent der Redezeit), wird dem ähnlichsten Sprecher zugeschlagen.
"""
import logging
from pathlib import Path

import numpy as np

log = logging.getLogger("diktat")
REPO, REVISION = "Wespeaker/wespeaker-voxceleb-resnet34-LM", "f0c48c298fd835726c27956a5d617bad7115627e"
FILE = "voxceleb_resnet34_LM.onnx"
SEGMENTER = Path(__file__).with_name("segmentierung.onnx")
RATE = 16000
WINDOW, HOP = 10 * RATE, 5 * RATE       # Fenster der Segmentierung und Abstand zwischen zwei Fenstern
SHIFT, FIELD = 270, 991                 # Schritt und Breite eines Ausgabe-Rahmens der Segmentierung in Samples
SETS = [(), (0,), (1,), (2,), (0, 1), (0, 2), (1, 2)]     # Klassen der Segmentierung: wer von drei Stimmen spricht
PART = int(3.0 * RATE / SHIFT)   # Rahmen je Abschnitt, für den eine Stimme einen eigenen Abdruck bekommt (3 s)
MIN_VOICE = 0.6          # so viele Sekunden muss eine Stimme im Fenster allein sprechen, damit sie einen Abdruck bekommt
SAME = 0.42              # ab dieser Ähnlichkeit (Kosinus) gelten zwei Gruppen als derselbe Sprecher
SOLO_SECONDS = 3.0       # wer insgesamt kürzer allein spricht, gilt nicht als eigener Sprecher …
SOLO_SHARE = 0.02        # … und auch nicht, wer weniger als diesen Anteil der gesamten Redezeit hat (sonst werden
                         # aus Rauschen und Lachen in langen Aufnahmen zusätzliche Sprecher)
MAX_SPEAKERS = 8
_mel = None


def _filters(n_fft=512, n_mels=80, low=20.0, high=8000.0):
    def mel(f):
        return 1127.0 * np.log(1.0 + f / 700.0)
    edges = np.linspace(mel(low), mel(high), n_mels + 2)
    freqs = mel(np.arange(n_fft // 2 + 1) * RATE / n_fft)
    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for m in range(n_mels):
        left, center, right = edges[m], edges[m + 1], edges[m + 2]
        up = (freqs - left) / (center - left)
        down = (right - freqs) / (right - center)
        fb[m] = np.maximum(0.0, np.minimum(up, down))
    return fb


def fbank(audio: np.ndarray) -> np.ndarray:
    """Mel-Filterbank wie in Kaldi (25 ms Fenster, 10 ms Schritt, 80 Bänder), mittelwertbereinigt."""
    global _mel
    if _mel is None:
        _mel = _filters()
    x = audio.astype(np.float32) * 32768.0
    n = 1 + (len(x) - 400) // 160
    idx = np.arange(400)[None, :] + 160 * np.arange(n)[:, None]
    frames = x[idx]
    frames = frames - frames.mean(axis=1, keepdims=True)
    frames = np.concatenate([frames[:, :1], frames[:, 1:] - 0.97 * frames[:, :-1]], axis=1)
    frames[:, 0] = frames[:, 0] * (1 - 0.97)
    frames = frames * (np.hanning(400) ** 0.85).astype(np.float32)
    power = np.abs(np.fft.rfft(frames, 512, axis=1)) ** 2
    feats = np.log(np.maximum(power @ _mel.T, 1.1920929e-07)).astype(np.float32)
    return feats - feats.mean(axis=0, keepdims=True)


def ready() -> bool:
    """Liegen beide Modelle auf dem Rechner?"""
    from . import modelle
    return SEGMENTER.exists() and modelle.find(REPO, REVISION, [FILE]) is not None


def prepare(progress=None) -> str:
    """Pfad des Stimmmodells; lädt es beim ersten Mal herunter (26 MB)."""
    import os
    from . import modelle
    return os.path.join(modelle.fetch(REPO, REVISION, [FILE], progress), FILE)


class Turns:
    """Hört einem Tonstrom zu und sagt am Ende, wer wann gesprochen hat.

    feed(block) nimmt den Ton stückweise (float32, 16 kHz) und behält nie mehr als ein Fenster im Speicher;
    finish() gibt (Sprecher je Rahmen, Rahmendauer in Sekunden) zurück. 0 heißt: niemand spricht."""

    def __init__(self, threads=2):
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.add_session_config_entry("session.intra_op.allow_spinning", "0")
        self.seg = ort.InferenceSession(str(SEGMENTER), so, providers=["CPUExecutionProvider"])
        self.voice = ort.InferenceSession(prepare(), so, providers=["CPUExecutionProvider"])
        self.buf = np.zeros(0, np.float32)
        self.start = 0                    # Position des Pufferanfangs im Strom, in Samples
        self.windows = []                 # je Fenster: (Position, wer-spricht-Matrix [Rahmen, 3])
        self.prints, self.seconds = [], []
        self.where = []                   # je Abdruck: (Fenster, Stimme im Fenster, erster Rahmen, letzter Rahmen)
        self.speakers = 0

    def _print(self, audio):
        feats = fbank(audio[: 20 * RATE])[None]
        out = self.voice.run(None, {self.voice.get_inputs()[0].name: feats})[0][0]
        return out / (np.linalg.norm(out) + 1e-9)

    def _window(self, x, offset):
        cls = self.seg.run(None, {self.seg.get_inputs()[0].name: x[None, None, :]})[0][0].argmax(axis=1)
        active = np.zeros((len(cls), 3), np.uint8)
        for c, members in enumerate(SETS):
            for m in members:
                active[cls == c, m] = 1
        alone = active.sum(axis=1) == 1
        for k in range(3):
            frames = np.flatnonzero((active[:, k] == 1) & alone)
            if len(frames) * SHIFT < MIN_VOICE * RATE:
                continue
            # Die Segmentierung überhört einen Wechsel zwischen ähnlichen Stimmen manchmal. Deshalb bekommt eine
            # Stimme nicht einen Abdruck fürs ganze Fenster, sondern einen je Abschnitt von rund drei Sekunden.
            parts = [frames[i:i + PART] for i in range(0, len(frames), PART)]
            if len(parts) > 1 and len(parts[-1]) < PART // 3:
                last = parts.pop()
                parts[-1] = np.concatenate([parts[-1], last])
            for part in parts:
                runs = np.split(part, np.flatnonzero(np.diff(part) > 1) + 1)
                audio = np.concatenate([x[r[0] * SHIFT: min(len(x), r[-1] * SHIFT + FIELD)] for r in runs])
                if len(audio) < 0.5 * RATE:
                    continue
                self.prints.append(self._print(audio))
                self.seconds.append(len(audio) / RATE)
                self.where.append((len(self.windows), k, int(part[0]), int(part[-1])))
        self.windows.append((offset, active))

    def feed(self, block):
        self.buf = np.concatenate([self.buf, block]) if len(self.buf) else np.asarray(block, np.float32)
        while len(self.buf) >= WINDOW:
            self._window(self.buf[:WINDOW], self.start)
            self.buf = self.buf[HOP:]
            self.start += HOP

    def _groups(self):
        """Abdrücke zu Sprechern gruppieren: immer die zwei ähnlichsten Gruppen vereinen (mittlere Ähnlichkeit aller
        Paare), bis keine zwei mehr ähnlich genug sind. Gibt je Abdruck die Nummer seiner Gruppe ab 0 zurück."""
        X = np.stack(self.prints)
        n = len(X)
        raw = X @ X.T
        sim = raw.copy()
        np.fill_diagonal(sim, -np.inf)
        size, group = np.ones(n), np.arange(n)
        while True:
            a, b = divmod(int(sim.argmax()), n)
            if not np.isfinite(sim[a, b]) or (sim[a, b] < SAME and len(set(group.tolist())) <= MAX_SPEAKERS):
                break
            sim[a, :] = (size[a] * sim[a, :] + size[b] * sim[b, :]) / (size[a] + size[b])
            sim[:, a] = sim[a, :]
            sim[a, a] = -np.inf
            sim[b, :] = sim[:, b] = -np.inf
            size[a] += size[b]
            group[group == b] = a
        secs, ids = np.array(self.seconds), sorted(set(group.tolist()))
        need = max(SOLO_SECONDS, SOLO_SHARE * secs.sum())
        big = [c for c in ids if secs[group == c].sum() >= need] or [max(ids, key=lambda c: secs[group == c].sum())]
        for c in ids:                     # wer kaum spricht, gilt nicht als eigener Sprecher: zur ähnlichsten Gruppe
            if c not in big:
                group[group == c] = max(big, key=lambda h: raw[np.ix_(group == c, group == h)].mean())
        number = {c: i for i, c in enumerate(sorted(set(group.tolist())))}
        return np.array([number[c] for c in group])

    def finish(self):
        if len(self.buf) > 0.5 * RATE or not self.windows:
            x = np.zeros(WINDOW, np.float32)
            x[: len(self.buf)] = self.buf[:WINDOW]
            self._window(x, self.start)
        total = self.start + len(self.buf)
        n = total // SHIFT + 2
        if not self.prints:
            self.speakers = 0
            return np.zeros(n, np.int16), SHIFT / RATE
        group = self._groups()
        score = np.zeros((group.max() + 1, n), np.float32)
        speech, count = np.zeros(n, np.float32), np.zeros(n, np.float32)
        for offset, active in self.windows:
            f0 = offset // SHIFT
            m = min(len(active), n - f0)
            if m > 0:
                count[f0:f0 + m] += 1
                speech[f0:f0 + m] += active[:m].max(axis=1)
        by_voice = {}
        for (w, k, first, last), g in zip(self.where, group):
            by_voice.setdefault((w, k), []).append((first, last, g))
        for (w, k), parts in by_voice.items():
            offset, active = self.windows[w]
            f0 = offset // SHIFT
            m = min(len(active), n - f0)
            if m <= 0:
                continue
            parts.sort()                 # jeder Abschnitt gilt bis zur Mitte zwischen ihm und seinem Nachbarn
            edges = [0] + [(parts[i][1] + parts[i + 1][0]) // 2 + 1 for i in range(len(parts) - 1)] + [m]
            for (_, _, g), lo, hi in zip(parts, edges, edges[1:]):
                hi = min(hi, m)
                if hi > lo:
                    score[g, f0 + lo:f0 + hi] += active[lo:hi, k]
        spoken = speech / np.maximum(count, 1) >= 0.5
        labels = np.where(score.max(axis=0) > 0, score.argmax(axis=0) + 1, 0)
        labels[~spoken] = 0
        known = np.flatnonzero(labels > 0)
        if len(known):      # Sprache ohne zugeordnete Stimme (zu kurz für einen Abdruck): wie der nächste Nachbar
            gaps = np.flatnonzero(spoken & (labels == 0))
            at = np.searchsorted(known, gaps).clip(0, len(known) - 1)
            left, right = known[(at - 1).clip(0)], known[at]
            labels[gaps] = np.where(np.abs(gaps - left) <= np.abs(right - gaps), labels[left], labels[right])
        self.speakers = len(set(labels[labels > 0].tolist()))
        return labels.astype(np.int16), SHIFT / RATE


def assign(words, labels, step):
    """Jedem Wort einen Sprecher geben. words: [(Wort, Beginn in Sekunden)], in Reihenfolge. Gibt Nummern ab 1
    zurück, in der Reihenfolge des ersten Auftretens."""
    if not words:
        return []
    raw, n = [], len(labels)
    for i, (_, t) in enumerate(words):
        end = words[i + 1][1] if i + 1 < len(words) else t + 0.4
        a = int(t / step)
        b = max(a + 1, int(min(end, t + 0.6) / step))
        span = labels[a:min(b, n)]
        span = span[span > 0]
        raw.append(int(np.bincount(span).argmax()) if len(span) else 0)
    spoken = np.flatnonzero(labels > 0)
    if not len(spoken):
        return [1] * len(words)
    for i, r in enumerate(raw):          # Wort in einer Lücke der Zeitleiste: wie die zeitlich nächste Sprache
        if not r:
            at = int(words[i][1] / step)
            k = int(np.searchsorted(spoken, at).clip(0, len(spoken) - 1))
            left, right = spoken[max(k - 1, 0)], spoken[k]
            raw[i] = int(labels[left] if abs(at - left) <= abs(right - at) else labels[right])
    raw = _tidy([w for w, _ in words], raw)
    order = {}
    return [order.setdefault(r, len(order) + 1) for r in raw]


def _tidy(texts, who):
    """Sprecherwechsel an den Satzbau anlehnen. Die Zeitleiste trifft einen Wechsel auf ein, zwei Wörter genau;
    gesprochen wird er fast immer am Satzende. Liegt ein Wechsel höchstens zwei Wörter neben einem Satzende, rückt
    er dorthin. Ein einzelnes Wort mitten im Satz eines anderen ist kein eigener Redebeitrag."""
    who, n = list(who), len(who)
    ends = [i + 1 for i, t in enumerate(texts) if t[-1:] in ".?!"]       # Positionen direkt hinter einem Satzende
    changes = [i for i in range(1, n) if who[i] != who[i - 1]]
    for i in changes:
        near = [e for e in ends if e != i and abs(e - i) <= 2 and 0 < e < n]
        if i in ends or not near:
            continue
        j = min(near, key=lambda e: abs(e - i))
        lo, hi = min(i, j), max(i, j)
        if any(c != i and lo <= c <= hi for c in changes):      # dazwischen liegt schon ein anderer Wechsel
            continue
        who[lo:hi] = [who[i - 1] if j > i else who[i]] * (hi - lo)
    for i in range(1, n - 1):            # einzelnes Wort zwischen zwei Abschnitten desselben Sprechers, kein eigener Satz
        if who[i - 1] == who[i + 1] != who[i] and texts[i][-1:] not in ".?!":
            who[i] = who[i - 1]
    return who


def dialogue(texts, labels) -> str:
    """Text mit Sprecherzeilen: aufeinanderfolgende Äußerungen desselben Sprechers bilden einen Absatz."""
    if len(set(labels)) < 2:
        return ""
    out, cur, who = [], [], None
    for t, l in zip(texts, labels):
        if l != who and cur:
            out.append(f"Sprecher {who}: " + " ".join(cur))
            cur = []
        who = l
        cur.append(t)
    if cur:
        out.append(f"Sprecher {who}: " + " ".join(cur))
    return "\n\n".join(out)
