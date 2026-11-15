"""Ein ungekürztes ONNX-Parakeet schonender auf 8 Bit kürzen als die übliche Fassung.

    python kuerzen.py <Ordner mit encoder-model.onnx, decoder_joint-model.onnx, vocab.txt, config.json> <Zielordner> <Variante>

Gemessen (werkzeug/messen/ERGEBNIS.md): Die verbreitete int8-Fassung kostet gegenüber den vollen Gewichten
etwa sechs Prozentpunkte Wortfehlerrate. Varianten:
  matmul    nur die großen Matrizen (Aufmerksamkeit, Feed-Forward) kürzen, Faltungen bleiben voll
  kanal     wie matmul, aber je Ausgangskanal eigene Skala
  alles     alles kürzen (zum Vergleich)
Der kleine Decoder bleibt immer ungekürzt.
"""
import pathlib
import shutil
import sys

from onnxruntime.quantization import QuantType, quantize_dynamic

src, out, kind = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
out.mkdir(parents=True, exist_ok=True)
kw = {"matmul": dict(op_types_to_quantize=["MatMul"]),
      "kanal": dict(op_types_to_quantize=["MatMul"], per_channel=True),
      "alles": {}}[kind]
quantize_dynamic(src / "encoder-model.onnx", out / "encoder-model.int8.onnx", weight_type=QuantType.QUInt8, **kw)
shutil.copy(src / "decoder_joint-model.onnx", out / "decoder_joint-model.int8.onnx")
for name in ("vocab.txt", "config.json"):
    shutil.copy(src / name, out / name)
print(kind, round((out / "encoder-model.int8.onnx").stat().st_size / 1e6), "MB")
