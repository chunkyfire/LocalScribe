"""Die erzeugten Sätze von freien künstlichen Stimmen (Piper) sprechen lassen: 16 kHz FLAC und eine Liste.

    python sprechen.py <texte.jsonl> <Zielordner> [Prozesse]
"""
import json, pathlib, random, sys
from multiprocessing import Pool

VOICES = [("thorsten/high/de_DE-thorsten-high", 34), ("thorsten/medium/de_DE-thorsten-medium", 10), ("thorsten_emotional/medium/de_DE-thorsten_emotional-medium", 14),
          ("kerstin/low/de_DE-kerstin-low", 11), ("ramona/low/de_DE-ramona-low", 11), ("karlsson/low/de_DE-karlsson-low", 10), ("pavoque/low/de_DE-pavoque-low", 10)]
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
_loaded = {}

def voice(key):
    if key not in _loaded:
        from huggingface_hub import hf_hub_download
        from piper import PiperVoice
        files = [hf_hub_download("rhasspy/piper-voices", f"de/de_DE/{key}.{ext}") for ext in ("onnx", "onnx.json")]
        _loaded[key] = PiperVoice.load(files[0], config_path=files[1])
    return _loaded[key]

def speak(job):
    i, text = job
    import numpy as np, soundfile as sf
    from math import gcd
    from piper.config import SynthesisConfig
    from scipy.signal import resample_poly
    target = out / "audio" / f"s{i:05d}.flac"
    rnd = random.Random(i)
    key = rnd.choices([v for v, _ in VOICES], [w for _, w in VOICES])[0]
    if target.exists():
        return i, key, sf.info(str(target)).duration
    try:
        v = voice(key)
        n = v.config.num_speakers or 1
        cfg = SynthesisConfig(speaker_id=rnd.randrange(n) if n > 1 else None, length_scale=rnd.uniform(0.88, 1.15), noise_scale=rnd.uniform(0.5, 0.75), noise_w_scale=rnd.uniform(0.6, 0.9))
        pcm = b"".join(c.audio_int16_bytes for c in v.synthesize(text, cfg))
        a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        sr = v.config.sample_rate
        if sr != 16000:
            g = gcd(16000, sr)
            a = resample_poly(a, 16000 // g, sr // g)
        a = np.concatenate([np.zeros(rnd.randrange(800, 4000), np.float32), a, np.zeros(rnd.randrange(800, 4000), np.float32)])
        sf.write(str(target), np.clip(a, -1, 1), 16000, subtype="PCM_16")
        return i, key, len(a) / 16000
    except Exception as e:
        return i, key, "FEHLER " + repr(e)[:150]

if __name__ == "__main__":
    (out / "audio").mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in open(src, encoding="utf-8")]
    for key, _ in VOICES:
        voice(key)                                   # einmal laden, damit die Prozesse nicht gleichzeitig herunterladen
    total = 0.0
    with Pool(int(sys.argv[3]) if len(sys.argv) > 3 else 8) as pool, open(out / "liste.jsonl", "w", encoding="utf-8") as f:
        for n, (i, key, sec) in enumerate(pool.imap(speak, [(i, r["text"]) for i, r in enumerate(rows)], chunksize=8)):
            if isinstance(sec, str):
                print(i, sec, flush=True)
                continue
            total += sec
            f.write(json.dumps({"audio": f"audio/s{i:05d}.flac", "text": rows[i]["text"], "stimme": key.split("/")[-1], "sec": round(sec, 2)}, ensure_ascii=False) + "\n")
            if n % 200 == 0:
                print(n, "von", len(rows), "|", round(total / 60), "min Ton", flush=True)
    print("FERTIG", round(total / 3600, 2), "Stunden Ton")
