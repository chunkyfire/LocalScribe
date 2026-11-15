"""Sprache-oder-nicht pro 32 ms mit Silero VAD (MIT-Lizenz, https://github.com/snakers4/silero-vad).

Das kleine Netz (2 MB, liegt der App bei) erkennt Sprache am Klang, nicht an der Lautstärke.
Damit bleiben Sprechpausen auch dann erkennbar, wenn es im Raum laut ist.
"""
import threading
from pathlib import Path

import numpy as np

FRAME = 512          # Samples pro Rahmen bei 16 kHz (32 ms)
CONTEXT = 64
MODEL = Path(__file__).with_name("silero_vad.onnx")


_session = None
_lock = threading.Lock()


def session():
    """Das Netz wird einmal geladen und von allen Vad-Objekten geteilt (run() ist threadsicher)."""
    global _session
    with _lock:
        if _session is None:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            opts.log_severity_level = 3
            _session = ort.InferenceSession(str(MODEL), sess_options=opts, providers=["CPUExecutionProvider"])
    return _session


class Vad:
    def __init__(self):
        self.session = session()
        self.rate = np.array(16000, dtype=np.int64)
        self.reset()

    def reset(self):
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, CONTEXT), dtype=np.float32)

    def __call__(self, frame: np.ndarray) -> float:
        """Wahrscheinlichkeit für Sprache in einem Rahmen von genau FRAME Samples."""
        x = np.concatenate([self.context, frame.reshape(1, FRAME).astype(np.float32, copy=False)], axis=1)
        out, self.state = self.session.run(None, {"input": x, "state": self.state, "sr": self.rate})
        self.context = x[:, -CONTEXT:]
        return float(out[0, 0])
