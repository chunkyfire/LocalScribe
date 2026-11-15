"""Ein nachtrainiertes NeMo-Parakeet (TDT 0.6B) in die ONNX-Form bringen, die LocalScribe lädt.

    python umwandeln.py <Hugging-Face-Repo> <Zielordner> <Ordner eines vorhandenen ONNX-Parakeet (für config.json)>

Braucht eine eigene Umgebung mit torch, nemo_toolkit[asr], onnx, onnxruntime (nicht die der App).
Ergebnis: encoder-model.int8.onnx, decoder_joint-model.int8.onnx, vocab.txt, config.json – dieselben
Dateien wie bei istupakov/parakeet-tdt-0.6b-v3-onnx.
"""
import pathlib
import shutil
import sys

import torch
from huggingface_hub import snapshot_download

repo, out, like = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
src = pathlib.Path(snapshot_download(repo))
import nemo.collections.asr as nemo_asr

nemo_files = list(src.glob("*.nemo"))
if nemo_files:
    model = nemo_asr.models.ASRModel.restore_from(str(nemo_files[0]), map_location="cpu")
else:
    # nur Gewichte und Konfiguration (Mediform): Modell aus der Konfiguration bauen, Gewichte einsetzen
    from omegaconf import OmegaConf, open_dict
    from safetensors.torch import load_file
    cfg = OmegaConf.load(src / "model_config.yaml")
    with open_dict(cfg):
        cfg.tokenizer.dir = str(src)
        for key in ("model_path", "vocab_path", "spe_tokenizer_vocab"):     # Verweise in ein .nemo-Archiv, das es hier nicht gibt
            cfg.tokenizer.pop(key, None)
        for key in ("train_ds", "validation_ds", "test_ds"):
            cfg.pop(key, None)
    model = nemo_asr.models.EncDecRNNTBPEModel(cfg=cfg)
    weights, own = load_file(src / "model.safetensors"), model.state_dict()
    for name, tensor in list(weights.items()):          # Gewichte im MLX-Format: Faltungen mit Kanal hinten
        if name in own and tensor.shape != own[name].shape:
            turned = tensor.permute(0, 2, 1) if tensor.dim() == 3 else tensor.permute(0, 3, 1, 2) if tensor.dim() == 4 else tensor
            if turned.shape == own[name].shape:
                weights[name] = turned.contiguous()
            else:
                print("passt nicht:", name, tuple(tensor.shape), tuple(own[name].shape))
    for name in [n for n in weights if ".lstm." in n and n.rsplit(".", 1)[-1] in ("Wx", "Wh", "bias")]:
        head, layer, kind = name.rsplit(".", 2)          # MLX nennt die LSTM-Gewichte anders
        tensor = weights.pop(name)
        if kind == "bias":
            weights[f"{head}.bias_ih_l{layer}"] = tensor
            weights[f"{head}.bias_hh_l{layer}"] = torch.zeros_like(tensor)
        else:
            weights[f"{head}.weight_{'ih' if kind == 'Wx' else 'hh'}_l{layer}"] = tensor
    missing, extra = model.load_state_dict(weights, strict=False)
    print("fehlende Gewichte:", len(missing), missing[:5], "überzählige:", len(extra), extra[:5])
model.eval()
raw = out / "roh"
raw.mkdir(exist_ok=True)
with torch.no_grad():
    model.export(str(raw / "model.onnx"))
with (out / "vocab.txt").open("wt", encoding="utf-8") as f:
    for i, token in enumerate([*model.tokenizer.vocab, "<blk>"]):
        f.write(f"{token} {i}\n")
shutil.copy(like / "config.json", out / "config.json")
from onnxruntime.quantization import QuantType, quantize_dynamic

for name in ("encoder-model", "decoder_joint-model"):
    quantize_dynamic(raw / f"{name}.onnx", out / f"{name}.int8.onnx", weight_type=QuantType.QUInt8)
    print(name, round((out / f"{name}.int8.onnx").stat().st_size / 1e6), "MB")
print("fertig:", out)
