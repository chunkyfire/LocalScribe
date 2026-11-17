"""Sprecher unterscheiden, lokal auf der CPU.

Jede Äußerung (die Pausenerkennung liefert sie ohnehin) bekommt einen Stimmabdruck aus einem kleinen
ONNX-Modell (WeSpeaker ResNet34, CC-BY-4.0, 26 MB; wird beim ersten Einschalten einmalig geladen).
Ähnliche Abdrücke werden zu Sprechern gruppiert.
Grenzen: Wer wem ins Wort fällt, landet in einer gemeinsamen Äußerung; sehr kurze Einwürfe
(„ja“, „genau“) werden dem Sprecher davor oder danach zugeschlagen.
"""
import logging
import numpy as np

log = logging.getLogger("diktat")
REPO, REVISION = "Wespeaker/wespeaker-voxceleb-resnet34-LM", "f0c48c298fd835726c27956a5d617bad7115627e"
FILE = "voxceleb_resnet34_LM.onnx"
RATE = 16000
MIN_SECONDS = 1.2        # kürzere Äußerungen tragen zu wenig Stimme für einen eigenen Abdruck
SAME = 0.42              # ab dieser Ähnlichkeit (Kosinus) gelten zwei Gruppen als derselbe Sprecher
MAX_SPEAKERS = 8
SOLO_SECONDS = 8.0       # wer insgesamt kürzer spricht, gilt nicht als eigener Sprecher
_session = None
_mel = None
_missing = False         # Stimmmodell fehlt und ließ sich nicht holen: während einer Aufnahme nicht erneut versuchen


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
    """Liegt das Stimmmodell schon auf dem Rechner?"""
    from . import modelle
    return modelle.find(REPO, REVISION, [FILE]) is not None


def prepare(progress=None) -> str:
    """Pfad des Stimmmodells; lädt es beim ersten Mal herunter (26 MB)."""
    global _missing
    import os
    from . import modelle
    path = os.path.join(modelle.fetch(REPO, REVISION, [FILE], progress), FILE)
    _missing = False
    return path


def embed(audio: np.ndarray):
    """Stimmabdruck einer Äußerung (Länge 1) oder None, wenn sie zu kurz ist."""
    global _session, _missing
    if len(audio) < MIN_SECONDS * RATE or _missing:
        return None
    if _session is None:
        if not ready():
            # Nie mitten in einer Aufnahme herunterladen: In gesperrten Netzen hinge jede Äußerung über eine
            # Minute an der Zeitüberschreitung. Geladen wird beim Einschalten von „Sprecher trennen“.
            _missing = True
            log.warning("Stimmmodell fehlt auf diesem Rechner – Aufnahme läuft ohne Sprechertrennung")
            return None
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = 2
        _session = ort.InferenceSession(prepare(), so, providers=["CPUExecutionProvider"])
    feats = fbank(audio[: 20 * RATE])[None]
    out = _session.run(None, {_session.get_inputs()[0].name: feats})[0][0]
    return out / (np.linalg.norm(out) + 1e-9)


def cluster(embs, secs=None):
    """Äußerungen zu Sprechern gruppieren. embs: Liste aus Abdrücken und None. Gibt je Äußerung eine
    Sprechernummer ab 1 zurück, in der Reihenfolge des ersten Auftretens. secs: Dauer je Äußerung."""
    known = [i for i, e in enumerate(embs) if e is not None]
    labels = [0] * len(embs)
    if not known:
        return [1] * len(embs)
    groups = [[i] for i in known]
    X = np.stack([embs[i] for i in known])
    sim = X @ X.T
    pos = {i: k for k, i in enumerate(known)}
    while len(groups) > 1:
        best, pair = -1.0, None
        for a in range(len(groups)):
            ia = [pos[i] for i in groups[a]]
            for b in range(a + 1, len(groups)):
                s = sim[np.ix_(ia, [pos[i] for i in groups[b]])].mean()
                if s > best:
                    best, pair = s, (a, b)
        if best < SAME and len(groups) <= MAX_SPEAKERS:
            break
        a, b = pair
        groups[a] += groups.pop(b)
    # Eine einzelne kurze Äußerung ist kein eigener Sprecher: zur ähnlichsten größeren Gruppe
    if secs is not None and len(groups) > 1:
        big = [g for g in groups if sum(secs[i] for i in g) >= SOLO_SECONDS]
        if big:
            for g in [g for g in groups if g not in big]:
                ig = [pos[i] for i in g]
                target = max(big, key=lambda h: sim[np.ix_(ig, [pos[i] for i in h])].mean())
                target += g
            groups = big
    order = sorted(groups, key=min)
    for n, g in enumerate(order, 1):
        for i in g:
            labels[i] = n
    # kurze Äußerungen ohne eigenen Abdruck: wie die davor, sonst wie die danach
    last = 0
    for i in range(len(labels)):
        if labels[i]:
            last = labels[i]
        elif last:
            labels[i] = last
    nxt = 1
    for i in range(len(labels) - 1, -1, -1):
        if labels[i]:
            nxt = labels[i]
        else:
            labels[i] = nxt
    return labels


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
