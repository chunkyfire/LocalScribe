# Wie gut ist die Nachbearbeitung? Messungen vom 15.11.2026

Modell: primeline-Parakeet (int8, CPU). Nachbearbeitung: Basiswörterbuch (bekannte Fehlschreibungen),
Lautschlüssel gegen 39 461 Fachbegriffe, ß-Reparatur, ein Laut daneben.

| Test | Wortfehlerrate roh | danach | Fachbegriffe richtig roh | danach | Ersetzungen richtig / falsch |
|---|---|---|---|---|---|
| 395 Arztbrief-Sätze (GraSCCo), Windows-Stimme, 44 min | 12,38 % | 11,14 % | 536/653 | 561/653 | 60 / 2 |
| 221 echte Aufnahmen (MultiMed deutsch, Testteil), 46 min | 13,06 % | 12,42 % | 306/349 | 311/349 | 40 / 0 |
| mehrsprachiges Modell, dieselben 395 Sätze | 12,62 % | 12,3 % | 540/653 | 552/653 | – |

Einzelbegriffe (Satz „Im Befund steht X, weil X wichtig ist“): von 11 856 Nennungen richtig 5 315 roh,
7 076 allein über den Klang, 9 367 mit der Liste bekannter Fehlschreibungen. Diese Liste stammt aus
denselben Aufnahmen; der Wert ist deshalb eine Obergrenze. ElevenLabs-Stimme, 37 Begriffe: 52 von 74
roh, 65 von 74 danach.

Ersetzungen in korrekt geschriebenem Text: MultiMed (79.357 Wörter) 4. GraSCCo (30.872 Wörter) 50.
Die Liste steht unten; es sind fast nur ß-Schreibungen und echte Tippfehler der Vorlage (Tropponin. Paracetmol).

## Echte Diktate (fünf Aufnahmen eines Arztes, 4 Minuten)

Wortfehlerrate nach Angleichen von Schreib- und Sprechform (`eigene.py`):

| Modell | roh | mit Nachbearbeitung |
|---|---|---|
| primeline-Parakeet (Standard) | 27,7 % | 23,3 % |
| NVIDIA Canary 1B v2 int8 | 23,8 % | 20,6 % |
| Whisper large-v3-turbo German, ONNX q4, über onnx-asr | 20,9 % | 20,1 % |
| Whisper large-v3-turbo German, extern gemessen | 17,7 % | – |

Die ONNX-q4-Fassung von Whisper ließ im Tumorboard-Diktat sämtliche Dosierungen weg und ist deshalb
nicht eingebaut. Canary lässt nichts weg. Einige Wörterbucheinträge stammen aus diesen Diktaten.

## Fassung 0.8: Schreibweisen und Kernbegriffe

Dieselben fünf Diktate, dieselbe Erkennung, neue Nachbearbeitung (`python werkzeug\messen\eigene.py`):

| Modell | roh | 0.7 | 0.8 |
|---|---|---|---|
| primeline-Parakeet (Standard) | 27,7 % | 23,3 % | 18,0 % |
| NVIDIA Canary 1B v2 int8 | 23,8 % | 20,6 % | 18,7 % |

Was dazukam: Einnahmeschema („40 mg100“ → „40 mg 1-0-0“), „RR140“, „0090 Grad“, „Hertz, Frequenz“,
„Patientin reduziertem“, englischer Einwurf am Diktatanfang, eingeschobener Vokal in langen Fachwörtern
(Moxonoidin), 330 weitere Kernbegriffe. Diese Regeln sind an genau diesen Diktaten entstanden; die Zahl ist
deshalb das günstigste Bild. Die beiden unabhängigen Prüfsätze oben ändern sich kaum (MultiMed 12,42 %,
GraSCCo-Sätze 11,14 → 11,09 %, weiterhin eine falsche Ersetzung). Das Standardmodell liegt damit auf diesen
Diktaten gleichauf mit dem langsameren Canary und mit Whisper large-v3-turbo (17,7 %).

Von den verbleibenden 74 Fehlern (412 Wörter) sind etwa ein Drittel Zählweise (Zusammenschreibung, „IE“
gegen „Einheiten“, „2x5“, Meier/Meyer, ein „äh“ in der Vorlage), ein Drittel Hörfehler bei Fachwörtern, die
das Stimmtraining für diesen Sprecher lernen kann (Riba, Golb, Trimbo, Hydralacin, Semitendinosuszähne),
und ein Drittel grobe Verhörer, bei denen ein echtes Wort dasteht (Set statt Stent, Kabel statt Cave,
Zuschauer statt Zustand).

## Lokales Sprachmodell als Korrektor: gemessen, nicht eingebaut

`diktat/korrektor.py` lässt ein Sprachmodell Ersetzungen vorschlagen und übernimmt nur, was ein Türsteher
durchlässt (Vorschlag ist ein bekanntes Wort oder Kernbegriff, klingt wie das Gehörte, ändert keine Zahl,
ist keine Beugungsform). Gemessen über Ollama auf einer RTX 4070 Ti (`werkzeug\messen\korrektur.py`):

| Modell | Zeit je Diktat | übernommen | davon richtig |
|---|---|---|---|
| Gemma 3 4B | 2,9 bis 3,6 s | 1 | 1 (Riba → RIVA) |
| Llama 3.1 8B | 3,2 bis 4,4 s | 4 | 1 bis 2 |

Die rohen Vorschläge sind überwiegend falsch („Nachstemi“ → „Nestgitter“, „Erdjobschema“ → „ERGO-Schema“,
„Oberbauchschmerz“ → „Obere Bauchschmerz“). Ohne Grafikkarte dauert derselbe Schritt ein Vielfaches. Für
„Text in wenigen Sekunden, auf der CPU“ taugt das nicht; die groben Verhörer brauchen ein stärkeres Modell
(geplanter Cloud-Modus) oder ein nachtrainiertes Erkennungsmodell.

## Fassung 0.9: Das Kürzen auf 8 Bit war der größte Fehler

Dieselben fünf Diktate, immer primeline-Parakeet, nur die Rechengenauigkeit des Encoders unterscheidet sich
(`werkzeug/modell/kuerzen.py`, `werkzeug\messen\dateien.py`):

| Fassung | Größe | roh | mit Nachbearbeitung | Tempo (i7-13700KF) |
|---|---|---|---|---|
| verbreitete int8-Fassung (bis 0.8) | 654 MB | 27,7 % | 18,0 % | 11,6-fach |
| volle Gewichte | 2,5 GB | 21,8 % | 15,0 % | 13,2-fach |
| nur Matrizen auf 8 Bit | 880 MB | 21,8 % | 15,8 % | 13,7-fach |
| nur Matrizen auf 8 Bit, je Kanal eigene Skala (ab 0.9) | 882 MB | 21,8 % | 14,3 % | 12,6-fach |

Das ist keine an den Diktaten gewonnene Regel, sondern dasselbe Modell mit weniger Rundungsfehlern. An den
221 unabhängigen MultiMed-Aufnahmen: roh 13,06 → 12,94 %, mit Nachbearbeitung 12,42 → 12,27 %. Die Unterschiede
zwischen den drei guten Fassungen (14,3 bis 15,8 %) liegen bei 412 Wörtern im Bereich einzelner Wörter.

## Nachtrainierte Medizin-Modelle: gemessen, schlechter

Beide öffentlich verfügbaren deutschen Medizin-Parakeets, selbst nach ONNX gebracht (`werkzeug/modell/umwandeln.py`),
an denselben fünf Diktaten, volle Gewichte:

| Modell | roh | mit Nachbearbeitung | Auffällig |
|---|---|---|---|
| johannhartmann/parakeet_de_med | 22,8 % | 20,6 % | schreibt Zahlen aus, „Yeah“, „Mm-hmm“ |
| Mediform/parakeet-medical-de | 33,3 % | 30,8 % | lässt ganze Passagen weg (Medikationsliste, Dosierungen) |
| primeline-Parakeet | 21,8 % | 15,0 % | |

## Wort-Boosting beim Dekodieren: gemessen, nicht eingebaut

`werkzeug/messen/boost.py` gibt beim Dekodieren Wortstücken einen Zuschlag, die das entstehende Wort zum Anfang
eines Kernbegriffs machen. Mit der alten int8-Fassung: eigene Diktate 20,4 → 19,4 %, die unabhängigen Aufnahmen
12,48 → 12,56 %. Ein Punkt Gewinn hier, ein Zehntel Verlust dort; mit dem genaueren Modell bleibt davon wenig.

## Sprechertrennung an echten Gesprächen

`werkzeug\messen\gespraech.py`, Datensätze mit bekannten Sprechern, Anteil der Sprechzeit beim richtigen Sprecher:

| Aufnahmen | richtig zugeordnet | Sprecherzahl stimmt |
|---|---|---|
| VoxConverse (Interviews, Diskussionen, 2 bis 6 Sprecher, normale Tonqualität), 10 Aufnahmen | 88,6 % | 5 von 10 |
| CallHome englisch (Telefon, 8 kHz, viel Durcheinanderreden), 12 Gespräche | 75,4 % | 8 von 12 |

Stimmabdrücke in kurzen Fenstern statt je Äußerung wurden versucht und waren am Telefon schlechter (die Gruppen
fallen zusammen). Ein deutsches Arzt-Patienten-Gespräch mit bekannten Sprechern gibt es öffentlich nicht.

## Was die anderen tun

- Heidi hat nach eigener Darstellung NVIDIA Parakeet V2 mit NeMo auf 1 500 Stunden klinischer Aufnahmen
  nachtrainiert, gezielt auf die Fachbegriffe, an denen das Grundmodell scheitert.
- ID (ORPHEUS) nennt eigene, am UKE trainierte Modelle, ein Vokabular für eigene Schreibweisen, das ab der
  nächsten Aufnahme gilt, automatische Satzzeichen und Sprechertrennung.
- Tandem nennt Sprach- und Textmodelle, die auf medizinische Sprache abgestimmt sind, und ist als
  Medizinprodukt der Klasse IIa zertifiziert.

Gemeinsam ist allen: ein auf echten klinischen Aufnahmen nachtrainiertes Erkennungsmodell plus Vokabular.
LocalScribe hat das Vokabular (Wörterbuch, Lautschlüssel, Stimmtraining), aber kein nachtrainiertes Modell.
Der nächste große Schritt wäre ein deutsches medizinisches Parakeet (etwa Mediform/parakeet-medical-de) als
ONNX-Fassung oder ein eigenes Nachtraining auf eigenen Diktaten.

## Was die Zahlen nicht zeigen

- Echte medizinische Diktate. Öffentliche deutsche Aufnahmen mit Transkript gibt es nicht: PoCaP
  (Erlangen) und MedASR-DE-AT (Wien) sind nicht frei, die übrigen Datensätze sind synthetisch.
  MultiMed hat echte Stimmen, besteht auf Deutsch aber vor allem aus Lehrvideos mit wenig Fachsprache.
- Die Wortfehlerrate ist streng gezählt: Zusammen- und Getrenntschreibung, Tippfehler der Vorlage und
  abgeschnittene Satzanfänge zählen als Fehler.
- Was übrig bleibt, sind grobe Verhörer und zerlegte Komposita. Dagegen hilft nur Wort-Boosting im
  Modell, Nachtraining oder ein Sprachmodell als Korrektor.

## Wiederholen

    python werkzeug\messen\multimed.py <Ordner> de test
    powershell -File tests\langzeit\tts.ps1 -Dir <Ordner mit saetze.txt>
    python werkzeug\messen\saetze.py <Ordner> de
    python werkzeug\messen\auswerten.py <Ordner>\saetze_de.jsonl
