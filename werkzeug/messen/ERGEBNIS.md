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

## Whisper gegen Parakeet auf der CPU

Whisper large-v3-turbo, deutsch nachtrainiert, mit faster-whisper ohne Grafikkarte (`werkzeug\messen\whisper.py`),
dieselben fünf Diktate, dieselbe Nachbearbeitung, derselbe Rechner (i7-13700KF):

| Modell | roh | mit Nachbearbeitung | Tempo | 38 s Diktat brauchen |
|---|---|---|---|---|
| Whisper turbo deutsch, int8 | 18,0 % | 16,0 % | 4,2-fach | 10,5 s |
| Whisper turbo deutsch, volle Gewichte | 17,5 % | 15,3 % | 2,4-fach | 17,9 s |
| Parakeet, Fassung ab 0.9 | 21,8 % | 14,3 % | 12,6-fach | 3 s |

Whisper ist roh genauer, weil es Zahlen und Einheiten von sich aus sauberer schreibt. Nach der Nachbearbeitung
liegt Parakeet vorn und ist dreimal so schnell; auf einem langsameren Klinikrechner wird der Abstand in
Sekunden größer.

Unabhängige Gegenprobe mit Fachsprache: die 395 vorgelesenen Arztbrief-Sätze (GraSCCo, synthetische Stimme, neu
erzeugt und mit der Fassung ab 0.9 erkannt). Roh 12,38 → 11,70 %, mit Nachbearbeitung 11,09 → 10,54 %,
Fachbegriffe richtig 566 → 581 von 659. An diesen Sätzen wurde nichts angepasst.

## Nachtrainierte Medizin-Modelle: gemessen, schlechter

Beide öffentlich verfügbaren deutschen Medizin-Parakeets, selbst nach ONNX gebracht (`werkzeug/modell/umwandeln.py`),
an denselben fünf Diktaten, volle Gewichte:

| Modell | roh | mit Nachbearbeitung | Auffällig |
|---|---|---|---|
| johannhartmann/parakeet_de_med | 22,8 % | 20,6 % | schreibt Zahlen aus, „Yeah“, „Mm-hmm“ |
| Mediform/parakeet-medical-de | 33,3 % | 30,8 % | lässt ganze Passagen weg (Medikationsliste, Dosierungen) |
| primeline-Parakeet | 21,8 % | 15,0 % | |

## Wort-Boosting beim Dekodieren: gemessen, nicht eingebaut

Ein früher Versuch (`boost.py`, inzwischen entfernt und durch `diktat/beam.py` ersetzt) gab beim Dekodieren Wortstücken einen Zuschlag, die das entstehende Wort zum Anfang
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

## Fachkorrektur ab 0.9.1: strengerer Türsteher

Nach der Messung oben verschärft: Der Vorschlag muss selbst im Fachlexikon stehen, mit demselben Laut beginnen
und im Lautschlüssel zu 72 % übereinstimmen. Mit dem neuen Erkennungsmodell und Llama 3.1 8B (lokal, RTX 4070 Ti,
2,6 bis 3,9 s je Diktat): drei Ersetzungen, alle richtig (Settimplantation → Stentimplantation, inhaltiger →
inhalativer, Retroximab → Rituximab), keine falsche; 14,3 → 13,8 % Wortfehler. Zwei falsche Vorschläge des Modells
(Hydralacin → Hydrochlorothiazid, gürtelförmiger → keilförmiger) hält der Türsteher auf. Ab Werk aus, weil der
Schritt ohne Grafikkarte zu lange dauert; mit einem stärkeren Modell hinter einer Schnittstelle noch nicht gemessen.

## Was kommerzielle Dienste tun

Nach den öffentlichen Angaben mehrerer Anbieter ärztlicher Spracherkennung: nachtrainierte Erkennungsmodelle
(in einem Fall ein Parakeet-Modell, nachtrainiert auf rund 1 500 Stunden klinischer Aufnahmen), ein Vokabular für
eigene Schreibweisen, automatische Satzzeichen, Sprechertrennung, teils eine Zertifizierung als Medizinprodukt.

Gemeinsam ist allen: ein auf echten klinischen Aufnahmen nachtrainiertes Erkennungsmodell plus Vokabular.
LocalScribe hat das Vokabular (Wörterbuch, Lautschlüssel, Stimmtraining), aber kein nachtrainiertes Modell.
Der nächste große Schritt wäre ein deutsches medizinisches Parakeet (etwa Mediform/parakeet-medical-de) als
ONNX-Fassung oder ein eigenes Nachtraining auf eigenen Diktaten.

## Vergleich mit drei Cloud-Diensten (16.11.2026)

Die Dienste sind hier nicht namentlich genannt (A, B, C). Die Messung ist klein (fünf Diktate, ein Sprecher) und
sagt nichts über ihre Leistung im Alltag.

Fünf eigene Diktate (412 Wörter, 4 min), als 16-kHz-Datei digital in den Browser eingespielt: Die Seite bekommt
statt des Mikrofons einen Tonstrom aus der Datei, ohne Lautsprecher und Raum. Die Programme im Diktiermodus,
ohne eigenes Vokabular. Gezählt wie in `eigene.py`, für alle gleich.

| Programm | KHK | Tumorboard | OP | Übergabe | Fälle | gesamt |
|---|---|---|---|---|---|---|
| Dienst A, Diktat | 10,3 % | 10,9 % | 13,7 % | 6,2 % | 5,4 % | **8,3 %** |
| Dienst C, Rohtranskript | 11,8 % | 25,0 % | 11,8 % | 2,5 % | 4,7 % | 9,5 % |
| Dienst C, fertiger Text | 10,3 % | 17,2 % | 15,7 % | 13,6 % | 2,0 % | **9,7 %** |
| Dienst B, Diktat | 13,2 % | 12,5 % | 13,7 % | 11,1 % | 4,7 % | **9,7 %** |
| LocalScribe 0.9.7 | 11,8 % | 17,2 % | 15,7 % | 8,6 % | 2,0 % | **9,0 %** |
| LocalScribe 0.9.4 | 11,8 % | 18,8 % | 13,7 % | 9,9 % | 7,4 % | 11,2 % |
| LocalScribe 0.9.3 | | | | | | 12,6 % |

Rund fünf der Fehler je Programm stammen aus der Vorlage (dort steht „Tumorkonferenz“, gesprochen wird
„Tumorboard“; „distal“ wird nicht gesprochen), die Untergrenze liegt also bei etwa 1 %.

Was man an den Ausgaben sieht:

- Dienst C arbeitet zweistufig. Das Rohtranskript enthält dieselben Verhörer wie LocalScribe („Kabel“ für Cave,
  „Schon nach SET-Implantation“). Ein Sprachmodell macht daraus den fertigen Text, bessert vieles aus
  („Z. n. Stent-Implantation“), lässt aber auch Gesprochenes weg („im RIVA“, „Nabic“) und fügt Überschriften
  ein, die niemand diktiert hat („Diagnose:“, „Eingriff:“).
- Dienst A schreibt schon während des Sprechens fertig formatierten Text (Z.n., i.v., mg/m², 1-0-0) und trifft fast
  alle Wirkstoffnamen. Fehler: „SET-Implantation“, „linker Sprung“ statt „linkes Sprunggelenk“, „Krea“ statt Cave.
- LocalScribe verliert vor allem bei Wirkstoff- und Handelsnamen (Ondansetron, Trimbow, Tresiba, Nabic,
  Sevelamer) und bei kurzen Alltagswörtern, die nur der Zusammenhang klärt (Sehne/Szene, Bohren/Born, Cave/Kabel).
  Das Erste lösen eigene Begriffe, das Zweite nur ein Sprachmodell als Korrektor.

0.9.7 holt den Abstand zu einem Teil mit Regeln auf, die an diesen fünf Diktaten entstanden sind (kurze Handelsnamen,
zerlegte Begriffe). Auf den unabhängigen Prüfsätzen bringen dieselben Regeln 10,30 → 10,15 % und 12,00 → 11,98 %.

Dienst B bekam denselben Ton über ein virtuelles Audiokabel, Diktat per gehaltener Taste. Er trifft alle
Wirkstoffnamen bis auf zwei, kürzt von sich aus ab („AZ“, „bds.“, „KOF“) und setzt im Diktat ohne Zusatzfunktion
keine Satzzeichen. Die Testfassung hängte an drei Diktate ein Wort an; ohne diese drei Wörter wären es 9,0 %.

## Sprechertrennung an einem deutschen Arzt-Patienten-Gespräch (16.11.2026)

Ein Anamnesegespräch aus zehn Redebeiträgen (64 s, Nierenbeckenentzündung), gesprochen von zwei deutschen
Frauenstimmen von ElevenLabs, also künstlich erzeugt und ohne Durcheinanderreden. Zwei Sprecherinnen erkannt,
100 % der Sprechzeit richtig zugeordnet, 8,3 s Rechenzeit auf der CPU. Erkennungsfehler: „Ramipil“.

(Gemessen mit dem Verfahren bis 0.14; das Skript dazu gibt es nicht mehr.)

Ein echtes Gespräch mit Unterbrechungen, Nebengeräuschen und ähnlichen Stimmen ist schwerer; dazu die Werte
oben (VoxConverse 88,6 %, CallHome 75,4 %).

## Sprechertrennung mit pyannote-Segmentierung (17.11.2026, ab 0.15.0)

Anlass: In einer echten Aufnahme mit vier Personen in der Notaufnahme landeten Redebeiträge beim falschen Sprecher,
weil die Sprecher ohne Pause wechselten und das alte Verfahren je Sprechpausen-Stück genau einen Sprecher vergab.
Neu: Segmentierung (pyannote segmentation-3.0 als ONNX) in Fenstern von 10 s, Stimmabdruck (WeSpeaker) je 3 s
Alleinredezeit einer Stimme, Gruppierung, Zeitleiste, Zuordnung je Wort über dessen Zeitpunkt.

    python werkzeug\messen\gespraech.py <parquet> <Anzahl>

Anteil der Sprechzeit beim richtigen Sprecher; Sprache, die keinem Sprecher zugeordnet wurde, zählt als falsch
(das alte Verfahren wurde ohne diese Strafe gemessen, die neuen Zahlen sind also die strengeren):

| Aufnahmen | alt | neu | Sprecherzahl stimmt alt | neu |
|---|---|---|---|---|
| VoxConverse, 10 Aufnahmen (Interviews, 1 bis 17 Sprecher) | 88,6 % | 92,7 % | 5 von 10 | 8 von 10 |
| CallHome englisch, 12 Telefongespräche | 75,4 % | 81,3 % | 8 von 12 | 10 von 12 |

Varianten: ein Abdruck je Stimme und Fenster statt je 3 s: 93,9 % und 77,1 %, aber das deutsche Testgespräch aus
zwei ähnlichen Stimmen fiel zu einem Sprecher zusammen (die Segmentierung überhört dort einzelne Wechsel). Ohne die
Zwei-Prozent-Regel für Sprecher mit wenig Redezeit: 94,7 % und 80,3 %, am Telefon aber nur bei 2 von 12 die richtige
Sprecherzahl. Schwelle 0,36 statt 0,42: das deutsche Gespräch fällt zusammen. Die Varianten sind auf vorab berechneten
Abdrücken verglichen (dort 93,3 % und 80,9 % für die gewählte Fassung); die Tabelle zeigt den Lauf durch die App-Klasse.
Die Werte sind an genau diesen Aufnahmen eingestellt, also eher günstig.

Deutsches Anamnesegespräch (zwei ähnliche Frauenstimmen von ElevenLabs, zehn Redebeiträge, 55 s), Redebeiträge
ohne jede Pause aneinandergehängt, mit der Spracherkennung der App (`tests\_cem\dicht.py`): 94 % der Wörter beim
richtigen Sprecher; mit 0,15 s Pause zwischen den Beiträgen 100 %. Rechenzeit 5 s für 55 s Ton einschließlich
Spracherkennung (i7-13700KF).

Nicht gemessen: echte deutsche Gespräche mit mehr als zwei Personen, Nebengeräusche einer Notaufnahme, mehrere
Personen in unterschiedlichem Abstand zum Mikrofon.

## Fachkorrektur mit großem Sprachmodell und ein unabhängiger Prüfsatz (16.11.2026)

Sprachmodell: Gemini 3.1 Flash Lite über OpenRouter, eine Anfrage je Diktat (lange Texte in Stücken zu 110 Wörtern,
gleichzeitig), Median 1,1 s. Der Türsteher (`korrektor.accept`) wurde an den Arztbrief-Sätzen eingestellt; Med-Dictate
und MultiMed hat er dabei nicht gesehen.

| Prüfsatz | Umfang | roh | App | App mit Fachkorrektur |
|---|---|---|---|---|
| eigene Diktate (ein Sprecher) | 5 Diktate, 412 Wörter | 20,1 % | 9,0 % | **7,5 %** |
| Med-Dictate, Corti (fremde Sprecher, 7 Fachgebiete) | 9 Diktate, 32,6 min | 21,0 % | 16,7 % | **13,7 %** |
| Arztbrief-Sätze, vorgelesen (GraSCCo) | 395 Sätze | | 10,2 % | **8,4 %** |
| MultiMed (YouTube, Laiensprache) | 318 Aufnahmen | | 12,3 % | 12,2 % |

Zum Vergleich auf den eigenen Diktaten: Dienst A 8,3 %, Dienst B 9,7 %, Dienst C 9,7 %.

Med-Dictate (`corti.py`, `corti_auswerten.py`): neun deutsche ärztliche Diktate von Corti-Mitarbeitenden ohne
Patientendaten, mit diktierten Satzzeichen, erkannt in 151 s für 32,6 min Ton. Fachbegriffe richtig: roh 57,6 %,
App 65,0 %, mit Fachkorrektur 71,5 %. Die Stufen: Nachbearbeitung 21,0 → 18,3 %, diktierte Satzzeichen → 16,7 %,
Fachkorrektur → 13,7 %. Was bleibt, sind Verhörer des Sprachmodells bei seltenen Fachwörtern (Fiduzialpunkte,
suszeptibilitätsgewichtet), abgeschnittene Mehrzahlendungen und Schreibvarianten (okzipital/occipital), die hier
als Fehler zählen.

MultiMed: neun richtige, zwei falsche Ersetzungen (beide Schreibweisen von Eigennamen), zwölf ohne Einfluss auf das Soll.

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

## Größere Modelle als Korrektor (16.11.2026)

Gleiche Eingabe, gleiches Tor, nur das Modell getauscht (`LS_MODEL=... korrektur_cloud.py`), über OpenRouter.

| Modell | eigene Diktate | Corti DE | Wartezeit je Diktat |
|---|---|---|---|
| ohne Korrektor | 9,0 % | 16,65 % | – |
| Gemini 3.1 Flash Lite | 7,5 % | 13,72 % | 1–2 s |
| Gemini 3.5 Flash Lite | 8,0 % | 14,40 % | 1–2 s |
| Claude Haiku 5.5 | 8,7 % | 13,75 % | 6 s / 14 s |
| Gemini 3.6 Flash | 6,8 % | 13,33 % | 18 s / 25 s |

Das größte Modell holt noch 0,4 bis 0,7 Punkte, braucht dafür aber das Zehn- bis Zwanzigfache an Zeit. Was danach
übrig bleibt, ist überwiegend falsch Gehörtes, das kein Textmodell aus dem Wortlaut erraten kann. Bei 412 Wörtern
entspricht ein Wort 0,24 Punkten; Unterschiede unter einem Punkt zwischen den schnellen Modellen sind Rauschen.

## Nachtraining des Sprachmodells mit künstlichen Stimmen: sechs Läufe, kein Gewinn (16.11.2026)

Werkzeug: `werkzeug/training/` (Sätze erzeugen, mit Piper sprechen, trainieren, Start auf Hugging Face Jobs).
Ausgangsmodell primeline-Parakeet (NeMo), Prüfung an echten Aufnahmen mit der Nachbearbeitung der App.

| Lauf | trainiert | Daten | Kunstsätze zurückgehalten | eigene Diktate | Corti |
|---|---|---|---|---|---|
| Ausgangsmodell | – | – | – | 9,0 % | 16,65 % |
| 1 | Decoder+Joint | 4,3 h Piper, Anker MLS | 10,1 → 8,2 % | 11,4 % | 16,75 % |
| 2 | Decoder+Joint | 7,5 h Piper, Anker MLS + MultiMed | 11,4 → 10,4 % | 10,7 % | 16,39 % |
| 3 | Decoder+Joint | 11,4 h Piper mit Zahlen, berichtigte Zieltexte | 14,6 → 13,2 % | 9,7 % | 16,49 % |
| 5 | Decoder+Joint | wie 3 + 12.000 Neurologie-Sätze (Chatterbox) | 14,6 → 12,6 % | 11,2 % | 16,52 % |
| 6 | ganzes Modell | wie 5 | 14,6 → 11,1 % | 12,4 % | 16,65 % |

Lauf 4 (ganzes Modell ohne Neurologie) ging beim Export verloren (zu wenig Arbeitsspeicher).
Auf künstlichen Stimmen lernt das Modell die Fachwörter (bis 34 % weniger Fehler bei den Neurologie-Sätzen), auf
echte Stimmen überträgt sich das nicht: Corti bleibt innerhalb von 0,3 Punkten, die eigenen Diktate werden schlechter.
Was das Modell danach von sich aus richtig schreibt, fängt die Nachbearbeitung ohnehin ab; dazu kommen neue Fehler
(ausgelassene Wörter, „Thank you.“ am Ende). Keines der Modelle ist eingebaut.
Berichtigte Zieltexte (ab Lauf 3): Zieltext ist, was das Ausgangsmodell hört, nur falsch gehörte Wörter werden ersetzt;
so bleibt seine Schreibweise für Zahlen und Einheiten. Das hat die Schäden verkleinert, aber keinen Gewinn gebracht.
Offen und aussichtsreicher: Nachtraining mit echten Aufnahmen der eigenen Stimme (Stimmtraining, „Aufnahmen aufheben“).

## Dekodieren mit Wortschatz (0.12.0): eingebaut

`diktat/beam.py` dekodiert mit mehreren Kandidaten (Beam Search) und gibt Kandidaten einen Bonus, deren entstehendes
Wort auf einen Begriff aus dem Wortschatz hinausläuft; der Bonus wird abgezogen, wenn kein Begriff daraus wird.
Gemessen mit `wortschatz_corti.py` an den neun Corti-Diktaten (32,6 min, echte Stimmen), Wortfehlerrate nach der
Nachbearbeitung der App, in Klammern die Trefferquote der von Corti markierten Fachbegriffe:

| Wortschatz | einfaches Dekodieren | 8 Kandidaten mit Bonus |
|---|---|---|
| nur Kernliste der App (820 Begriffe) | 16,59 % (65,2 %) | 15,77 % (66,4 %) |
| Kernliste + Lexikonwörter aus den Transkripten, wie die App sie lernt (1.732) | – | 11,11 % (81,4 %) |
| Kernliste + von Corti markierte Begriffe aller neun Diktate (1.308) | 14,24 % (77,3 %), Begriffe nur in der Nachbearbeitung | 10,88 % (81,6 %); mit Begriffen auch in der Nachbearbeitung 10,82 % (86,5 %) |

Was nicht hilft oder schadet:

- Mehrere Kandidaten ohne Wortschatz: 16,29 % mit 4, 16,59 % mit 8. Der Gewinn kommt vom Wortschatz.
- Das ganze Lexikon (39.600 Wörter) als Wortschatz: 17,30 %. Zu viele Wortanfänge passen, der Bonus zieht gewöhnliche
  Wörter zu Lexikonwörtern („Beurteilung“ → „Verurteilung“). Mit 5.000 bzw. 15.000 fremden Lexikonwörtern zusätzlich zum
  passenden Wortschatz: 11,76 % bzw. 12,25 %. Deshalb lernt die App höchstens 4.000 Wörter und nur solche, die vorkamen.
- Das Basiswörterbuch (4.900 Begriffe) als Standard: 16,45 %, also nicht besser als die Kernliste.
- Ein Bonus für alle bekannten deutschen Wörter (782.000) als zweite Stufe: kein Gewinn.
- Ein Ausgleich je geschriebenem Wortstück gegen Auslassungen: 16,49 % bis 19,65 %, also schlechter. Stattdessen
  gilt die einfache Lesart, wenn die Suche mehr als zwei Wörter weniger liefert.
- Bonus 3 statt 2: gleich (11,01 %). 4 statt 8 Kandidaten: 11,63 %.

Einschränkung: Der passende Wortschatz stammt hier aus den Transkripten derselben Diktate. Das bildet ab, dass ein
Arzt seine eigenen Fachwörter immer wieder diktiert, überschätzt aber den Gewinn am ersten Tag. Rechenzeit: 32,6 min
Ton dekodieren dauert auf einem Kern gut zwei Minuten statt einer halben; der Encoder dominiert weiter.

Eigene fünf Diktate (412 Wörter, `tests/_cem/ws_eigene.py`): roh 19,7 → 15,0 % mit der Kernliste, 14,1 % mit dem aus
den Solltexten gelernten Wortschatz (99 Wörter); nach der Nachbearbeitung 9,0 → 8,3 % bzw. 8,5 %. Hier fängt die
Nachbearbeitung das meiste schon ab. Rechenzeit auf dem i7-13700KF: 28,3 s statt 19,1 s für alle fünf zusammen
(rund 45 % mehr).

### Fachgebiets-Pakete: gemessen, nicht eingebaut

`werkzeug/woerterbuch/pakete.py` lässt ein Sprachmodell für 26 Fachgebiete je rund 650 Wörter nennen, die in
Arztbriefen des Fachs häufig sind (9.800 verschiedene). Als Wortschatz an den Corti-Diktaten, ohne deren Texte zu
kennen: alle Pakete zusammen 17,04 % (schlechter als ohne), die drei passendsten Pakete je Diktat 15,84 %, das eine
passendste 15,44 %, gegenüber 15,77 % mit der Kernliste allein. Allgemeine Listen eines Fachs treffen die Wörter und
Wortformen eines einzelnen Arztes zu selten; der Gewinn (11,1 %) kommt erst mit den Wörtern aus den eigenen Texten.
Deshalb gibt es keine Pakete, sondern „Aus eigenen Texten lernen“. Die diktierten Satzzeichen-Wörter (Punkt, Komma,
Doppelpunkt …) im Wortschatz bringen 15,77 → 15,35 % und sind seitdem immer dabei.

### Geschwindigkeit (0.12.1)

`session.intra_op.allow_spinning = 0` für beide ONNX-Sitzungen. Vorher drehten die Rechen-Threads von Encoder und
Decoder nach jedem Aufruf weiter und bremsten sich im Wechsel gegenseitig. i7-13700KF, 45 s Diktat in elf Stücken:

| | Encoder | einfach dekodieren | Suche mit Wortschatz |
|---|---|---|---|
| Voreinstellung | 3,22 s | 0,75 s | 1,74 s |
| ohne Spinning | 0,94 s | 0,17 s | 0,58 s |

Nicht besser: feste Thread-Zahlen (8, 12, 16), Bindung an die schnellen Kerne, Decoder mit einem Thread, erst alle
Stücke durch den Encoder und dann dekodieren. In der Suche bleiben Wortstücke außen vor, die das Modell für um mehr
als 7 (logarithmisch) unwahrscheinlicher hält als das beste; Corti unverändert 11,08 %.

### Kleineres Modell (0.14.0): geprüft, nicht übernommen

Encoder mit 4-Bit-Matrizen (`MatMulNBits`, Blockgröße 32, aus den vollen Gewichten): 655 MB statt 841 MB. Eigene fünf
Diktate ohne Wortschatz beim Dekodieren: 10,0 % statt 9,0 % nach der Nachbearbeitung (roh 19,4 % statt 19,7 %).
Corti: 17,37 % statt 16,59 % (Fachbegriffe 63,5 % statt 65,2 %). Rechenzeit für die fünf Diktate: 12,7 s statt 7,1 s.
190 MB weniger Download wiegen das nicht auf. Die 654-MB-Fassung, die alles auf 8 Bit kürzt, war schon in 0.9 deutlich schlechter
(Tabelle oben). Kleiner ginge es nur mit einem anderen, kleineren Modell.

## medBERT als Schiedsrichter zwischen ähnlich klingenden Wörtern (17.11.2026)

Anlass: Bei einem Sprecher schrieb das Sprachmodell „Disney“ für „Dyspnoe“. Idee aus einer Rückmeldung: Ein deutsches
medizinisches Sprachmodell, das Lücken im Satz füllt (medBERT.de, `GerMedBERT/medbert-512-no-duplicates`, Apache 2.0,
109 Mio. Parameter, 436 MB), entscheidet aus dem Satzumfeld, welches von mehreren ähnlich klingenden Wörtern passt.
Bewertet wird die mittlere logarithmische Wahrscheinlichkeit der Teilstücke eines Worts, wenn alle seine Stellen
gleichzeitig verdeckt sind. Rechenzeit: rund 60 ms je Kandidat auf vier Kernen, unverkleinert.

Einzelfall: „… stellt sich vor mit [Disney|Dyspnoe] mit dem Rettungsdienst“: Dyspnoe −7,9 gegen Disney −13,2.
„Die Kinder schauen [Disney|Dyspnoe] Plus“: Disney −12,4 gegen Dyspnoe −14,7. Beide Richtungen richtig.

Messung an den neun Corti-Diktaten (echte Sprecher, 32,6 Minuten, 3451 Wörter), zwei Wege:

| Weg | Ergebnis |
|---|---|
| Nachlauf über jedes Wort, Kandidaten aus dem Fachlexikon nach Klang | mehr Schaden als Nutzen: bei Schwelle 5 werden 8 Wörter richtig korrigiert, 6 richtige zerstört, 5 falsche durch andere falsche ersetzt. Fehlt das richtige Wort unter den Kandidaten, wählt das Modell ein plausibles falsches. |
| Kandidaten aus der Strahlsuche der Spracherkennung (8 Lesarten, Unterschied in genau einem Wort, Abstand der Lesarten höchstens 2) | bei Vorsprung ab 5: 19 Wörter getauscht, 16 richtig korrigiert, 0 richtige zerstört. Bei Vorsprung ab 3: 31 getauscht, 21 richtig, 1 zerstört. |

Wortfehlerrate mit Nachbearbeitung der App, zweiter Weg:

| Schwelle | WER | Fachbegriffe |
|---|---|---|
| ohne medBERT | 15,67 % | 327/488 |
| ab 5 | 15,35 % | 327/488 |
| ab 4 | 15,28 % | 328/488 |
| ab 3 | 15,22 % | 328/488 |
| ab 2 | 15,22 % | 329/488 |

Was es bringt: Wortendungen und Fälle (Fall/falls, Keiner/Keine, Korrelationen/Korrelation), echte Wörter an falscher
Stelle (Befehl/Befall, Dora/Dura), einzelne Verschreiber (Diurrese/Diurese, epithuralen/epiduralen). Einen Teil davon
behebt die Nachbearbeitung der App schon selbst, deshalb ist der Gewinn kleiner als die Zahl der Treffer. Was es nicht
bringt: mehr erkannte Fachbegriffe (327 gegen 328 von 488); fehlt der Begriff in allen Lesarten, kann der
Schiedsrichter ihn nicht wählen.

Verkleinert auf 8 Bit (ONNX): 133 statt 529 MB, 27 statt 94 ms je Kandidat, an denselben Stellen (mit kürzerem
Satzumfeld nachgerechnet) praktisch dieselben Entscheidungen: ab Vorsprung 5 unverkleinert 13 richtig und 0 zerstört,
verkleinert 14 richtig und 0 zerstört.

Gegenprobe an den fünf eigenen Diktaten (ein Sprecher, 412 Wörter, App-Einstellung, verkleinertes Modell): ohne
medBERT 8,3 %, mit Vorsprung ab 5 8,0 % (ein Fehler weniger: „Pann“ wird „kann“), mit Vorsprung ab 3 wieder 8,3 % (ein
Treffer, ein Schaden: „Pectoris“ wird „pectorisk“). 54 Aufrufe für alle fünf Diktate, zusammen 0,4 Sekunden. Die strenge
Schwelle schadet in beiden Messungen nicht, der Gewinn ist klein.

Grenzen: neun und fünf Diktate, Schwellen an den neun gewählt, nur Unterschiede in genau einem Wort. Eingebaut ist es
nicht: Offen sind Unterschiede über mehrere Wörter, die Messung an den eigenen Diktaten und der Einbau als abschaltbare
Stufe mit einmaligem Download des Modells.

