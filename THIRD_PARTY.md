# Bausteine anderer und ihre Lizenzen

LocalScribe selbst steht unter der GPL-3.0-or-later (siehe `LICENSE`).

| Baustein | Wofür | Lizenz | In der ZIP-Datei? |
|---|---|---|---|
| [primeline/parakeet-primeline](https://huggingface.co/primeline/parakeet-primeline) (primeline; Basis: NVIDIA parakeet-tdt-0.6b-v3) | Spracherkennung | CC-BY-4.0 | nein, wird beim ersten Start geladen |
| [OpenVoiceOS/primeline-parakeet-onnx](https://huggingface.co/OpenVoiceOS/primeline-parakeet-onnx) | ONNX-Fassung des Modells | CC-BY-4.0 | nein |
| [Release modell-primeline-1](https://github.com/chunkyfire/LocalScribe/releases/tag/modell-primeline-1) | dieselben Gewichte, von LocalScribe schonender auf 8 Bit gekürzt (verändert: nur die Matrizen des Encoders gekürzt) | CC-BY-4.0 | nein, wird beim ersten Start geladen |
| [istupakov/parakeet-tdt-0.6b-v3-onnx](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx) (NVIDIA parakeet-tdt-0.6b-v3) | mehrsprachige Spracherkennung, wahlweise | CC-BY-4.0 | nein, wird bei Auswahl geladen |
| [istupakov/canary-1b-v2-onnx](https://huggingface.co/istupakov/canary-1b-v2-onnx) (NVIDIA canary-1b-v2) | genaueres deutsches Modell, wahlweise | CC-BY-4.0 | nein, wird bei Auswahl geladen |
| [Wikidata](https://www.wikidata.org/) | Fachbegriffe im medizinischen Basiswörterbuch | CC0 | ja (`diktat/basiswoerterbuch.json`) |
| [ICD-10-GM, Alphabetisches Verzeichnis](https://www.bfarm.de/DE/Kodiersysteme/Klassifikationen/ICD/ICD-10-GM/_node.html) (BfArM) | Fachbegriffe im Fachlexikon | Nutzungsbedingungen des BfArM | ja, als Wortliste (`diktat/fachlexikon.json`) |
| [Wespeaker/wespeaker-voxceleb-resnet34-LM](https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM) (WeSpeaker, trainiert auf VoxCeleb) | Stimmabdrücke für „Sprecher trennen“ | CC-BY-4.0 | nein, wird beim ersten Einschalten geladen |
| [Silero VAD](https://github.com/snakers4/silero-vad) | erkennt Sprechpausen | MIT | ja (`diktat/silero_vad.onnx`) |
| [onnx-asr](https://github.com/istupakov/onnx-asr) | führt das Sprachmodell aus | MIT | ja |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | Rechenkern | MIT | ja |
| [PySide6 / Qt](https://www.qt.io/) | Oberfläche | LGPL-3.0 | ja |
| [PyAV](https://github.com/PyAV-Org/PyAV) mit FFmpeg | liest Audio- und Videodateien | BSD-3-Clause, FFmpeg in den fertigen Paketen GPL-3.0 | ja |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) mit PortAudio | Mikrofon | MIT | ja |
| [pynput](https://github.com/moses-palmer/pynput) | Tastenkürzel, Einfügen | LGPL-3.0 | ja |
| [keyring](https://github.com/jaraco/keyring) | API-Schlüssel in der Windows-Anmeldeinformationsverwaltung | MIT | ja |
| [huggingface_hub](https://github.com/huggingface/huggingface_hub) | lädt das Modell | Apache-2.0 | ja |
| [certifi](https://github.com/certifi/python-certifi) | Zertifikatsliste für den Modell-Download | MPL-2.0 | ja |
| [tokenizers](https://github.com/huggingface/tokenizers) | zerlegt Text für die Namenserkennung | Apache-2.0 | ja |
| [GLiNER multi PII](https://huggingface.co/greg-gajda/gliner_multi_pii-v1-onnx-q8-emb4) (urchade/gliner_multi_pii-v1, mDeBERTa-v3) | erkennt Namen, Orte und Einrichtungen vor dem Versand an ein Sprachmodell | Apache-2.0 | nein, wird auf Knopfdruck geladen (293 MB) |
| [cryptography](https://cryptography.io/) | erzeugt das Zertifikat für „Handy als Mikrofon“ | Apache-2.0 oder BSD-3-Clause | ja |
| [Segno](https://github.com/heuer/segno) | zeichnet den QR-Code | BSD-3-Clause | ja |
| [NumPy](https://numpy.org/) | Rechnen mit Audiodaten | BSD-3-Clause | ja |
| [Python](https://www.python.org/) | Laufzeit | PSF-2.0 | ja |

Die GPL für LocalScribe folgt aus dem mitgelieferten FFmpeg: Wer die ZIP-Datei weitergibt, gibt
ein GPL-Werk weiter. Der vollständige Quelltext liegt in diesem Repository.
