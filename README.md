# LocalScribe

Lokales Diktieren per Tastenkürzel für Windows: Taste halten, sprechen, loslassen – der Text
landet im gerade aktiven Textfeld. Die Spracherkennung läuft vollständig auf dem eigenen Rechner
(primeline-Parakeet, 600 Mio. Parameter, int8-ONNX, nur CPU, rund 850 MB Arbeitsspeicher).
In den Einstellungen steht daneben ein mehrsprachiges Modell zur Wahl (NVIDIA Parakeet v3, 25 europäische Sprachen).

**Download:** [aktuelle Version](https://github.com/chunkyfire/LocalScribe/releases/latest) – `…-windows-komplett.zip`
(rund 1,3 GB, alle Modelle liegen bei, kein Internet nötig) oder `…-windows.zip` (rund 100 MB, lädt das Sprachmodell
beim ersten Start).

**Wie gut und wie schnell** (Methode und Einzelwerte in [`werkzeug/messen/ERGEBNIS.md`](werkzeug/messen/ERGEBNIS.md)):

| Messung | LocalScribe | zum Vergleich |
|---|---|---|
| Wortfehlerrate, fünf ärztliche Diktate eines Sprechers (412 Wörter) | **8,3 %** | Drei Cloud-Dienste für ärztliche Dokumentation: 8,3 %, 9,7 %, 9,7 %. Lokal: Whisper Large v3 Turbo Deutsch 14,1 % |
| Wortfehlerrate, neun echte Arztdiktate (Corti Med-Dictate, 33 Minuten) | **11,1 %** mit eigenem Wortschatz, 15,4 % ohne | 16,6 % ohne Wortschatz beim Dekodieren |
| Rechenzeit für 45 Sekunden Diktat (Büro-PC, nur Prozessor) | **2 Sekunden** | |
| Sprechertrennung, richtig zugeordnete Sprechzeit | 93 % Interviews, 81 % Telefon | bisheriges Verfahren: 89 % und 75 % |

Wenige Sprecher, ruhige Umgebung; Dialekt und Lärm sind nicht gemessen.

**Von:** [cemmec.ai](https://cemmec.ai) · Dr. Cem Özel. Support, Rückfragen und Änderungswünsche:
[LinkedIn](https://www.linkedin.com/in/cem-%C3%B6zel-ab0b37113) oder ein [Issue](https://github.com/chunkyfire/LocalScribe/issues).

**Technische Dokumentation:** [online](https://chunkyfire.github.io/LocalScribe/technik.html), als [PDF](docs/LocalScribe-Technik.pdf) oder [docs/TECHNIK.md](docs/TECHNIK.md) – Aufbau, Datenablage, Netzwerkverbindungen, Verteilung.

**Handbuch mit Bildern:** [docs/LocalScribe-Handbuch.pdf](docs/LocalScribe-Handbuch.pdf) – Installieren, Starten, Diktieren, alle Funktionen und Messwerte. Online: <https://chunkyfire.github.io/LocalScribe/>

## Installieren (ohne Adminrechte)

1. Unter **Releases** eines der beiden Pakete herunterladen: `LocalScribe-…-windows-komplett.zip` (rund 1,3 GB,
   Sprachmodell und Stimmmodell liegen bei; für Klinikrechner und Rechner ohne Internet) oder `LocalScribe-…-windows.zip`
   (rund 100 MB, lädt das Sprachmodell beim ersten Start). Die Prüfsummen stehen daneben in `SHA256SUMS.txt`.
2. Entpacken, zum Beispiel nach `Dokumente\LocalScribe`.
3. `LocalScribe.exe` starten. Meldet Windows „Der Computer wurde geschützt“: **Weitere Informationen →
   Trotzdem ausführen** (die Datei ist nicht signiert).
4. Nur beim kleinen Paket: Beim ersten Start lädt die App einmalig das Sprachmodell (910 MB). Ein Balken im Fenster, in der
   Statusleiste am unteren Bildschirmrand und im Infobereich zeigt, wie weit der Download ist; erst wenn er
   voll ist, lässt sich diktieren. Das Modell bleibt danach dauerhaft unter
   `%LOCALAPPDATA%\LocalScribe\modelle` liegen (ohne Adminrechte beschreibbar) und wird nie erneut geladen.
   Ab dann arbeitet die App ohne Internet.
   Sperrt das Netz den Download, nennt das Fenster den Grund; dann das Komplettpaket nehmen.
5. Verknüpfungen für Desktop und Startmenü: im Fenster unter **Einstellungen**.

Aktualisieren: Unten links im Fenster steht die laufende Fassung. Ein Klick fragt bei GitHub nach einer neueren; gibt es eine, lädt der nächste Klick nur, was sich geändert hat, und danach steht dort „Neu starten“. Dasselbe unter **Einstellungen → Nach Updates suchen**, dort steht auch, was neu ist. Ein Update richtet die neue Fassung neben der laufenden ein, auch während LocalScribe läuft und auch auf einem gemeinsamen Laufwerk, aus dem viele Rechner arbeiten.
Erreicht der Rechner GitHub nicht: neue ZIP an einem anderen Rechner laden (das kleine Paket genügt) und unter
**Aus ZIP-Datei aktualisieren** auswählen. Entfernen: **Einstellungen → LocalScribe entfernen**; von Hand: App beenden, Ordner
löschen, dazu `%LOCALAPPDATA%\LocalScribe` (Einstellungen, Verlauf, Sprachmodelle).
Wer eine Fassung vor 0.8 benutzt hat, findet das Modell zusätzlich unter `%USERPROFILE%\.cache\huggingface`;
LocalScribe verwendet es von dort weiter und lädt nichts doppelt.

## Bedienung

| Aktion | Taste |
|---|---|
| Diktieren | **Strg + Win** halten, sprechen, loslassen |
| Freihand | während des Haltens **Leertaste**, dann loslassen und weiterreden; **Strg + Win** beendet |
| Abbrechen | **Esc** oder eine andere Taste während der Aufnahme |
| Letzten Text noch einmal einfügen | **Umschalt + F7** |
| Diktieren mit Prompt | Halte-Taste des Prompts, z. B. **F8** für „Glätten“ |

Gesprochene Befehle: „neue Zeile“, „neuer Absatz“. Alle Tasten lassen sich ändern.
Wer lieber eine einzelne Taste hat, trägt in den Einstellungen zum Beispiel `f7` ein. Eine einzelne
Modifikatortaste wie `ctrl` startet erst nach 0,3 Sekunden Halten.
Läuft die App schon, holt ein zweiter Start nur ihr Fenster nach vorn. Schließen des Fensters
beendet sie nicht; sie bleibt im Infobereich (Rechtsklick → Beenden).

## Das Fenster

- **Verlauf** – alle Diktate, Klick kopiert, „KI“ bearbeitet einen Eintrag nachträglich.
  Einträge werden nach 7 Tagen gelöscht (einstellbar).
- **Aufnahme** – einmal drücken startet, noch einmal drücken beendet, auch nach einer Stunde.
  Der Text läuft live mit: beim Sprechen grau als Vorschau, nach jeder Sprechpause als gültiger Text.
- **Datei** – Audio- oder Videodatei hineinziehen (MP3, M4A, WAV, FLAC, OGG, MP4 …).
- **Sprecher trennen** (Häkchen bei Aufnahme und Datei, ab Werk an) – für Gespräche: Der Text bekommt Zeilen
  „Sprecher 1: …“, „Sprecher 2: …“; bei nur einer Stimme bleibt er, wie er ist. Läuft auf der CPU dieses Rechners;
  einmalig wird ein Stimmmodell geladen (26 MB). Siehe „Sprecher trennen“ unten.
- **Wortschatz beim Erkennen** – die Erkennung verfolgt acht Lesarten gleichzeitig und bevorzugt die, die auf ein
  Fachwort aus deinem Wortschatz hinausläuft (Kernliste, eigene Begriffe, gelernte Wörter). LocalScribe lernt die
  Fachwörter aus deinen Diktaten mit; über **Aus eigenen Texten lernen** (Wortschatz, Reiter Stimmtraining) liest es sie aus eigenen
  Briefen und Befunden, nur einzelne Lexikonwörter, keine Sätze, keine Namen. An echten Arztdiktaten mit passendem
  Wortschatz: 16,6 → 11,1 % Wortfehler.
- **Aufnahme mit Aufträgen** – aufnehmen oder eine Datei laden; das Transkript wird gespeichert. Darunter ein Klick auf
  Visite (Eintrag nach dem SOAP-Schema), Meeting-Protokoll, Arztbrief oder Pflegebericht (Beobachtung, Maßnahme,
  Wirkung, Weitergabe; sachlich, ohne Wertung). Alle übernehmen nur, was gesagt wurde. Glätten, Zusammenfassung und
  eigene Prompts lassen sich dazuschalten. Die Erkennung läuft lokal; Aufträge gehen an das eingestellte Sprachmodell.
- **Übergabe** – eigener Bereich für Visite und Übergabe, mit einer Ablage je Fall, direkt beantwortbaren Rückfragen
  und „Neu erzeugen“.
  Drei Rahmen, oben rechts wählbar: **Notaufnahme**, **Station**, **Intensiv**.
  Jev (TypeSafe, über OpenRouter) antwortet in etwa einer halben Sekunde mit Wahrscheinlichkeiten. In der Notaufnahme
  als Ersteinschätzung: Notaufnahme oder Notdienstpraxis, Schockraum, fallführende Abteilung, Bett, EKG, Zugang, Labor,
  Bildgebung. Auf Station und Intensiv als Tages-Check: droht eine Verschlechterung oder Eskalation, ist Entlassung
  oder Verlegung realistisch, und was heute zu prüfen ist (Antibiotika, Medikation, Katheter, Prophylaxen,
  Aufwachversuch, Therapieziel …). Ein Sprachmodell schreibt je nach Rahmen Arztbrief, Visiteneintrag oder Übergabe
  nach Organsystemen, dazu Sicherheitsnetz, gezielte Rückfragen, Kodiervorschlag und Patienteninfo (auf Intensiv:
  Text für Angehörige), jeweils als eigener Block zum Auf- und Zuklappen und Kopieren; alles liegt unter „Fälle“
  (umbenennen, Papierkorb). Verhörte Arzneimittel, Dosen und fehlende Vorzeichen meldet das Sicherheitsnetz.
  Nur für Forschung, Lehre und den Vergleich von Modellen, kein Medizinprodukt. Die Anweisung ist unter Einstellungen
  änderbar.
- **Wörterbuch** – falsch Erkanntes automatisch ersetzen. Mit **Hinzufügen** und nur der rechten Spalte reicht die richtige Schreibweise
  (RIVA, Trimbow, ein Name): Was ähnlich klingt und kein echtes Wort ist, wird so geschrieben. Mit **Wort einsprechen** lernt die App
  dazu: richtige Schreibweise eintippen, Knopf halten, Wort sprechen. Was die Erkennung daraus
  macht, wird künftig ersetzt. Übernommen wird nur, was dem richtigen Wort ähnlich ist.
  Mitgeliefert ist ein **medizinisches Basiswörterbuch** (abschaltbar): Fehlschreibungen von rund
  5 900 Wirkstoffen, Diagnosen, anatomischen und klinischen Begriffen. Siehe unten.
- **Stimmtraining** – Sätze zum Vorlesen: ein Grundstock für alle (etwa 9 Minuten) und je Fachrichtung gut
  30 Minuten (bisher Notfallmedizin, Innere Medizin und Nephrologie). Die App vergleicht, was sie verstanden hat,
  mit dem Satz und trägt deine Aussprache falsch erkannter Fachbegriffe ins Wörterbuch ein. „Messen …“ zeigt mit
  eigenen Prüfsätzen, was das Vorlesen gebracht hat. Freiwillig. Siehe „Stimmtraining“ unten.
- **Textbausteine** – gesprochenes Stichwort → hinterlegter Text.
- **LLM** (Einstellungen, Reiter LLM) – Server-Adresse, API-Schlüssel, Modell und eigene Prompts für die KI-Nachbearbeitung.
  Spricht jede OpenAI-kompatible Schnittstelle (Ollama, LM Studio, vLLM, eigener Anbieter).
  Der API-Schlüssel liegt in der Windows-Anmeldeinformationsverwaltung, nicht in einer Datei.
  Ist der Server nicht erreichbar, wird der unbearbeitete Text eingefügt.
  **Fachkorrektur** (Haken, ab Werk aus): Das Sprachmodell schlägt Korrekturen für verhörte Fachbegriffe vor;
  übernommen wird nur, was selbst ein Fachbegriff ist, ähnlich klingt und keine Zahl ändert.
- **Einstellungen** – Tasten (ins Feld klicken, Kombination drücken), Mikrofon, Töne, Autostart, Aufbewahrung, Verknüpfungen.

Dateien: `%LOCALAPPDATA%\LocalScribe\` (`config.json`, `verlauf.sqlite`, `diktat.log`), also je Windows-Konto; dort
liegt auch alles Gelernte. Wer seine Daten lieber beim Programm hat (eigene Fassung je Ordner), legt sie unter
Einstellungen in den Programmordner (Ordner `daten`). Die Sprachmodelle können in einem gemeinsamen Ordner liegen
(Einstellungen, „Modellordner“, oder ein Ordner `modelle` neben den Programmordnern).

## Was mit den Daten geschieht

- **Ton.** Diktate per Taste bleiben im Arbeitsspeicher und werden nie auf die Platte geschrieben.
  Ist „Mikrofon offen halten“ eingeschaltet (ab Werk aus), bleibt das Mikrofon geöffnet; außerhalb eines Diktats
  wird nur die letzte Viertelsekunde im Arbeitsspeicher gehalten und laufend überschrieben.
  Lange Aufnahmen werden während des Sprechens in eine Sicherungsdatei geschrieben, damit bei
  einem Absturz nichts verloren ist. Diese Datei wird gelöscht, sobald der Text vollständig vorliegt.
  Bleibt sie liegen (Absturz, Fehler), bietet die App beim nächsten Öffnen das Nachholen an;
  spätestens nach der Aufbewahrungsfrist wird sie gelöscht.
- **Text.** Der Verlauf speichert Text, Zeitpunkt und Dauer – keinen Ton und keinen Fenstertitel.
  Er wird nach 7 Tagen gelöscht (einstellbar) und lässt sich ganz abschalten, etwa auf gemeinsam
  genutzten Windows-Konten. Gelöschte Einträge werden in der Datei überschrieben.
- **Ort.** Alles liegt unter `%LOCALAPPDATA%`, also nicht im Roaming-Profil, das in Firmennetzen
  auf einen Server wandert.
- **Zwischenablage.** Eingefügter Text wird vom Windows-Zwischenablageverlauf (Win+V) und von der
  Cloud-Zwischenablage ausgenommen.
- **Netz.** Die App geht nur ins Internet, um ein Modell zu laden: beim ersten Start das Sprachmodell,
  beim Wechsel des Sprachmodells und beim ersten Einschalten von „Sprecher trennen“ (jeweils feste
  Fassung, Hugging Face). Nach einer neuen Fassung fragt sie nur auf Klick (unten links im Fenster oder „Nach Updates suchen“), es sei denn, die tägliche Nachfrage ist in den Einstellungen eingeschaltet (ab Werk aus). Sonst arbeitet sie offline. Die KI-Nachbearbeitung ist ab Werk aus;
  ist dort eine Adresse außerhalb des eigenen Netzes eingetragen, zeigt die App das an.
- **Schutz vor dem Versand.** Geht Text an ein Sprachmodell außerhalb des Rechners (OpenRouter, IONOS …),
  ersetzt LocalScribe vorher auf dem Rechner Namen, Geburts- und andere Daten, Telefonnummern, E-Mail-Adressen,
  Anschriften und lange Nummern durch Platzhalter (`[NAME_1]`, `[DATUM_1]`) und übersetzt die Antwort zurück.
  Regeln finden Daten, Nummern, Kontaktdaten und Namen hinter Anrede oder Titel; die Namenserkennung (GLiNER,
  293 MB, im Komplettpaket, sonst beim ersten Bedarf von selbst geladen, läuft auf der CPU) findet Namen, Orte und Einrichtungen
  auch ohne solche Hinweise. **Fehlt die Namenserkennung, sendet LocalScribe nichts an einen fremden Server.**
  Gemessen an 17 erfundenen klinischen Sätzen mit 34 persönlichen Angaben (`werkzeug/messen/schutz.py`): Regeln
  allein ersetzen 20, mit Namenserkennung alle 34. Das ist eine kleine Stichprobe, kein Nachweis.
  Fachbegriffe wie Parkinson oder Crohn bleiben stehen. Kein Verfahren findet alles: Das ist eine Schutzschicht,
  kein Nachweis der Anonymität. Der Schutz ist für fremde Server ab Werk an und lässt sich je Anbieter abschalten.
- **Stimmabdrücke.** „Sprecher trennen“ berechnet Stimmabdrücke der Sprecher. Sie leben nur im
  Arbeitsspeicher, solange die Transkription läuft, und werden nicht gespeichert. Im Text stehen Nummern,
  keine Namen; die App erkennt niemanden wieder.
- **Protokoll.** `diktat.log` enthält Zeiten und Zeichenzahlen, keine Inhalte.

## Kein Medizinprodukt

LocalScribe schreibt auf, was gesprochen wird. Es ist ein Dokumentationswerkzeug wie ein Diktiergerät mit
Schreibkraft und trifft keine medizinische Aussage: keine Diagnose, keine Therapieempfehlung, keine
Dosisberechnung, keine Triage. Es ist kein Medizinprodukt im Sinne der Verordnung (EU) 2017/745 (MDR), hat
keine CE-Kennzeichnung und ist dafür nicht bestimmt.

- Jeder Text muss vor der Übernahme in eine Akte gegengelesen werden, besonders Wirkstoffe, Dosierungen,
  Seitenangaben und Verneinungen. Die Verantwortung für den Inhalt liegt bei der Person, die diktiert.
- Die KI-Nachbearbeitung formt Text nach deinem Prompt um (Füllwörter, Gliederung, Stil). Wer dort ein
  Sprachmodell nach Differenzialdiagnosen, Rückfragen oder Therapievorschlägen fragt, bekommt eine
  Ausgabe, die **nur für Forschung, Lehre und den Vergleich von Modellen (Benchmarking)** gedacht ist –
  nicht für Diagnostik oder Therapie eines Menschen.
- Das gilt genauso für den geplanten Cloud-Modus mit Fragen und Vorschlägen aus einem Sprachmodell.

## Aus dem Quelltext starten oder selbst bauen

    uv venv --python 3.11 .venv
    uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    .venv\Scripts\pythonw.exe run.pyw

    powershell -ExecutionPolicy Bypass -File build.ps1     # baut dist\LocalScribe-<Version>-windows.zip

Tests:

    .venv\Scripts\python.exe tests\test_hotkey.py
    .venv\Scripts\python.exe tests\test_text.py
    .venv\Scripts\python.exe tests\test_llm.py
    .venv\Scripts\python.exe tests\test_flow.py
    .venv\Scripts\python.exe tests\test_long.py
    .venv\Scripts\python.exe tests\test_live.py
    # Langzeittest (rund 25 Minuten): siehe Kopf von tests\langzeit\stunde.py

## Was gemessen ist und wo die Grenzen liegen

Langzeittest (`tests/langzeit`): eine Stunde vorgelesenes Diktat, 370 Sätze, durch die echte
Verarbeitungskette. Ergebnis und Vergleich stehen in `tests/langzeit/ERGEBNIS.md`.

- Das Modell erkennt zuverlässig nur einzelne Äußerungen. Enthält ein Stück eine Sprechpause oder
  ist es länger als etwa 23 Sekunden, lässt es Satzteile weg. Die App schneidet deshalb an jeder
  Sprechpause ab 0,3 Sekunden und nie später als nach 12 Sekunden.
- Sprechpausen erkennt Silero VAD am Klang, unabhängig von der Lautstärke.
- Reine Stille wird nicht erkannt, weil das Modell daraus gelegentlich Wörter erfindet. Dafür müssen
  zwei Prüfungen übereinstimmen (Silero hört keine Sprache, der Pegel hebt sich nicht vom
  Grundrauschen ab); im Zweifel wird erkannt.
- Der Wortschatz-Bonus beim Erkennen wirkt nur für Wörter, die im Wortschatz stehen; am ersten Tag ist das wenig
  mehr als die Kernliste. Er wächst mit den Diktaten oder sofort über „Aus eigenen Texten lernen“.
- Das Sprachmodell ist primeline-Parakeet in einer eigenen, schonender gekürzten 8-Bit-Fassung (siehe
  `werkzeug/messen/ERGEBNIS.md`).
- Gemessen ist an fünf ärztlichen Diktaten eines Sprechers (9,0 % Wortfehler, mit Fachkorrektur durch ein großes
  Sprachmodell 7,5 %; drei Cloud-Dienste für ärztliche Dokumentation 8,3 %, 9,7 % und 9,7 %), an neun fremden ärztlichen Diktaten aus Med-Dictate von
  Corti (32 Minuten, sieben Fachgebiete: 16,7 %, mit Fachkorrektur 13,7 %), an 395 vorgelesenen Arztbrief-Sätzen
  (10,2 %, mit Fachkorrektur 8,4 %) und an echten Aufnahmen aus MultiMed (12,3 %). Dialekt und laute Umgebung sind
  damit nicht belegt. Jeder Text muss vor der Übernahme gegengelesen werden.
- In Fenster, die mit Adminrechten laufen, kann die App nicht einfügen.

## Das medizinische Basiswörterbuch

`diktat/basiswoerterbuch.json` ordnet Fehlschreibungen dem richtigen Fachbegriff zu. Es wirkt nur mit
dem deutschen Modell und nach dem eigenen Wörterbuch. Entstanden ist es so (`werkzeug/woerterbuch/`):

1. Begriffe: Wirkstoffe (ATC), Diagnosen (ICD-10) und Anatomie (Terminologia Anatomica) mit deutschem
   Namen aus Wikidata (CC0), dazu eine Kernliste klinischer Begriffe und Handelsnamen.
2. Gehört: Jeder Begriff wurde von der Windows-Stimme in einem Satz vorgelesen und vom Sprachmodell
   erkannt. Was das Modell statt des Begriffs schreibt, ist eine Fehlschreibung aus erster Hand.
3. Regeln: übliche Lautverwechslungen (ph/f, y/i, th/t, Doppelkonsonanten …).
4. Trennschärfe: Aufgenommen wird nur, was kein Wort ist (Hunspell deutsch und englisch,
   Worthäufigkeitslisten in acht Sprachen), kein anderer Fachbegriff ist, sich nur in mehr als der
   c/k/z-Schreibung unterscheidet und zu genau einem Begriff passt.

Grenzen: Die Fehlschreibungen stammen von einer synthetischen Stimme, nicht von echten Sprechern.
Seltene Eigennamen, die zufällig einer Fehlschreibung gleichen, würden ersetzt.

## Fachbegriffe am Klang erkennen

Zusätzlich zur Liste bekannter Fehlschreibungen prüft die App jedes unbekannte Wort ab sechs
Buchstaben gegen ein Fachlexikon mit rund 39 000 Begriffen (ICD-10-GM, Wikidata, Kernliste). Verglichen
wird ein Lautschlüssel: „Tachükardie“, „Flegmone“ und „Kolezüstitis“ klingen wie Tachykardie,
Phlegmone und Cholezystitis und werden so geschrieben. Bekannte Wörter, Beugungsformen
(Pankreatitiden) und Schreibvarianten mit c, k oder z (Processus/Prozessus) bleiben unberührt.
Bei langen Wörtern darf ein Vokal abweichen oder ein Laut im Wortinneren fehlen (Stinosen,
Abwehspannung). Außerdem wird ss zu ß, wo es die ss-Schreibung nicht gibt (anschliessend).

Gemessen (`werkzeug/messen/`, Ergebnisse in `werkzeug/messen/ERGEBNIS.md`):

- 395 Arztbrief-Sätze aus GraSCCo (öffentlicher deutscher Klinikkorpus), vorgelesen von der
  Windows-Stimme: Wortfehlerrate 12,4 % roh, 11,1 % mit Nachbearbeitung; Fachbegriffe richtig
  82 % roh, 86 % danach; 60 richtige Ersetzungen, 2 falsche.
- 221 echte Aufnahmen aus MultiMed: Wortfehlerrate 13,1 % roh, 12,4 % danach; 40 richtige Ersetzungen,
  keine falsche.
- 5 928 einzeln vorgelesene Fachbegriffe: richtig geschrieben 45 % roh, 60 % allein über den Klang,
  79 % mit der Liste bekannter Fehlschreibungen (die aus genau diesen Aufnahmen stammt).
- 110 000 Wörter korrekt geschriebener Text (MultiMed, GraSCCo): Ersetzt wurden fast nur echte
  Tippfehler der Vorlagen.

Fünf echte Diktate eines Arztes (Arztbrief, Tumorboard, OP-Bericht, Übergabe, Fallvignetten; 4 Minuten),
Wortfehlerrate nach Angleichen von Schreib- und Sprechform:

| Modell | roh | mit Nachbearbeitung |
|---|---|---|
| primeline-Parakeet (Standard) | 27,7 % | 23,3 % |
| NVIDIA Canary 1B v2 (bis 1.4.0 als „genauer“ wählbar) | 23,8 % | 20,6 % |
| Whisper large-v3-turbo German (primeline), zum Vergleich extern gemessen | 17,7 % | – |

Einige Einträge des Wörterbuchs stammen aus genau diesen Diktaten; die Werte mit Nachbearbeitung
sind deshalb etwas zu günstig.

Die Nachbearbeitung repariert, was knapp daneben liegt. Was das Modell grob verhört
(„Aorten V Etium“), bleibt falsch; dafür bräuchte es Wort-Boosting im Modell oder Nachtraining.

Öffentliche deutsche Aufnahmen echter medizinischer Diktate mit Transkript gibt es nicht. MultiMed
(ACL 2025) ist der einzige frei zugängliche Datensatz mit echten Stimmen; sein deutscher Teil besteht
überwiegend aus Lehrvideos für Sprachprüfungen und enthält kaum Fachbegriffe.

## Fachkorrektur mit einem Sprachmodell

Unter Einstellungen, LLM, lässt sich ein Sprachmodell eintragen, das verhörte Fachwörter berichtigt
(Häkchen „Fachkorrektur“). Es sieht den Text und schlägt Ersetzungen vor; ein Türsteher in der App übernimmt nur,
was klingt wie das Gehörte:

- ein Wort, das es nicht gibt, wird ein bekanntes Wort oder ein Fachbegriff („Hahnstau“ wird Harnstau),
- mehrere Wörter werden ein Fachbegriff, wenn sie zusammen fast genauso klingen („Atem Note“ wird Atemnot),
- ein richtiges Wort weicht nur einem Begriff der medizinischen Kernliste („Kabel“ wird Cave).

Zahlen bleiben unberührt, umformuliert wird nichts. Gemessen mit Gemini Flash Lite über OpenRouter, rund eine
Sekunde je Diktat: eigene Diktate 9,0 → 7,5 %, Med-Dictate 16,7 → 13,7 %, Arztbrief-Sätze 10,2 → 8,4 %,
MultiMed 12,3 → 12,2 % (dort neun richtige, zwei falsche Ersetzungen). Mit einem kleinen lokalen Modell bringt es nichts.

**Anbieter speichern und wechseln.** Mehrere Server lassen sich unter eigenem Namen ablegen (OpenRouter, Noirdoc,
IONOS, lokal) und in der Auswahl „Anbieter“ wechseln; jeder hat seinen eigenen Schlüssel im Windows-Schlüsselspeicher.
Wer in der Liste „Server“ einen bekannten Anbieter wählt und speichert, bekommt den Eintrag von selbst.

**Modell wählen.** Bei OpenRouter und Noirdoc steht oben eine kurze Liste, die Vorgabe ist Gemini 4 Hydrogen mit wenig
Nachdenken (5 bis 14 Sekunden je Auftrag; Gemini 3.1 Flash Lite 1 bis 4). „Modelle abrufen“ ergänzt, was der Server
meldet, „+“ einen eigenen Modellnamen. Die Fachkorrektur nimmt bei beiden immer das schnelle Modell. Bei Noirdoc
fehlen die Modelle zweier Unteranbieter ohne Verschwiegenheitsverpflichtung mit Absicht.

**Aus Korrektur lernen** (Seite Wörterbuch): das letzte Diktat berichtigen. Verhörte Fachwörter kommen ins
Wörterbuch. War das Erkannte selbst ein richtiges Wort („Kabel“ statt Cave), merkt es sich die Fachkorrektur und
gibt es dem Sprachmodell als Hinweis mit; angewendet wird es nur, wo es in den Zusammenhang passt.

## Satzzeichen diktieren

Mit der Einstellung „Satzzeichen diktieren“ (ab Werk aus) werden „Punkt“, „Komma“, „Doppelpunkt“, „Semikolon“,
„Fragezeichen“, „Klammer auf/zu“, „Schrägstrich“, „neue Zeile“ und „neuer Absatz“ zu Zeichen. Hängt die Erkennung
das Befehlswort an das Wort davor („Schwindelpunkt“), wird es getrennt. „Punkt“ bleibt ein Wort hinter Artikel,
Zahl oder Bindestrich („der wichtigste Punkt“, „McBurney-Punkt“).

## Zielfenster

Umschalt + F9 merkt das Fenster, das gerade vorn ist (zum Beispiel den Arztbrief). Jedes Diktat wird danach in
dieses Fenster eingefügt, auch wenn inzwischen ein anderes Programm vorn ist: LocalScribe holt das Zielfenster
kurz nach vorn und fügt ein. Noch einmal Umschalt + F9 löst die Bindung. Der Text landet an der Stelle, an der der
Cursor in diesem Fenster zuletzt stand. Fenster, die mit höheren Rechten laufen, lassen sich von Windows aus nicht
ansteuern; dann bleibt der Text in der Zwischenablage und die App sagt das.

## Handy als Mikrofon

Für Rechner ohne gutes Mikrofon. Unter Einstellungen „Handy als Mikrofon“ ankreuzen und speichern, dann „QR-Code
zeigen“ und mit dem Telefon scannen. LocalScribe öffnet dafür einen kleinen Webserver im eigenen Netz (Port 8765,
`diktat/handy.py`). Das Telefon nimmt im Browser auf und schickt den Ton nach dem Stopp als 16-kHz-Rohton an den
Rechner. Dort läuft alles wie bei einem Diktat per Taste: erkennen, nachbearbeiten, einfügen (auch ins Zielfenster).

- Browser geben das Mikrofon nur auf verschlüsselten Seiten frei. LocalScribe erzeugt sich deshalb ein eigenes
  Zertifikat (`%LOCALAPPDATA%\LocalScribe\handy`); das Telefon warnt einmal davor, weil keine Zertifizierungsstelle
  dahinter steht.
- Der QR-Code enthält ein zufälliges Kürzel. Ohne es liefert der Server weder die Seite noch nimmt er Ton an.
- Der Ton wird nicht gespeichert und verlässt das eigene Netz nicht.
- Grenzen: Beide Geräte müssen im selben Netz sein und einander erreichen dürfen. Windows fragt beim ersten
  Einschalten nach der Firewall (privates Netz erlauben). Geprüft ist der Server mit einem nachgestellten Telefon
  am selben Rechner, nicht mit vielen Telefonmodellen.

## Stimmtraining

Auf der Seite **Stimmtraining** steht ein Satz. Knopf halten, vorlesen, loslassen. Die App legt Wort für Wort
daneben, was sie verstanden hat. Ein falsch erkanntes Wort kommt ins persönliche Wörterbuch, wenn

- es dem richtigen Wort ähnlich klingt (Lautschlüssel, mindestens 55 % Übereinstimmung) und
- es selbst kein echtes Wort ist. „Riba“ wird zu „RIVA“; „Kabel“ wird nicht zu „Cave“, weil sonst jedes
  Kabel im Diktat ersetzt würde. Solche Fälle zeigt die App an, lernt sie aber nicht.

Getrennt gehörte Zusammensetzungen werden als Paar gelernt („Set-Implantation“ → „Stentimplantation“).

**Das Material.** Unter **Fachrichtung** wählst du, was du liest. Der **Grundstock** (90 Sätze, etwa 9 Minuten)
enthält, was alle brauchen: Zahlen, Einheiten, Dosierungen, Vitalwerte, häufige Arzneimittel. Eine Fachrichtung
(**Notfallmedizin**, **Innere Medizin und Nephrologie**; weitere folgen) beginnt mit dem Grundstock und bringt
danach gut 30 Minuten eigene Sätze: wie Ärztinnen und Ärzte diktieren oder übergeben, Gespräche mit Patientinnen und
Patienten, Organisation. Die Sätze sind so geordnet, dass die ergiebigsten zuerst kommen; du kannst jederzeit
aufhören und später weitermachen. Die früheren Themen (Kardiologie, Neurologie, Chirurgie …) stehen weiter unten in
der Auswahl. Quelle: `werkzeug/lesetexte/`, eine Textdatei je Fachrichtung.

**Messen.** „Messen …“ lässt dich 40 Prüfsätze vorlesen (etwa vier Minuten), die im Training nie vorkommen, und
zeigt deine Wortfehlerquote. Einmal vor dem Training und später wieder: So siehst du, was das Vorlesen bringt.

**Der Ton der Übungssätze** wird im Datenordner aufgehoben (nur diese erfundenen Sätze, nie Diktate), damit das
Sprachmodell später auf deine Stimme nachtrainiert werden kann. „Alle löschen“ auf der Seite entfernt sie. Alles
Gelernte steht auf der Seite Wörterbuch und lässt sich dort ändern oder löschen.

**Aus Aufnahme mit Transkript lernen**: Wer Diktate mit dem fertigen Text dazu hat, wählt die Tondateien aus; das
Transkript liegt als Textdatei mit gleichem Namen daneben (`befund1.wav` und `befund1.txt` oder `.docx`). LocalScribe
erkennt die Aufnahme, vergleicht mit dem Transkript und lernt Verhörer fürs Wörterbuch und Fachwörter für den
Wortschatz. Der Ton wird nur gelesen.

**Mehrere Personen: Profile.** Liegt das Programm auf einem Netzlaufwerk, aus dem viele Rechner arbeiten, steht
unten links im Fenster, wer diktiert: „Dieser Rechner“ oder ein Profil. Ein Klick dort wählt ein Profil oder legt
eines an (auch über das Symbol neben der Uhr). Im Profil liegen Wörterbuch, Wortschatz, Textbausteine, Aufträge,
Tasten und das Stimmtraining mit seinen Aufnahmen, im Programmordner unter `profile\<Name>`; es folgt der Person an
jeden Rechner. Verlauf, Fälle, Protokoll, Mikrofon, Server und Schlüssel bleiben auf dem jeweiligen Rechner. Profile
haben kein Passwort. Fehlt das Laufwerk, arbeitet die App mit der letzten Kopie weiter und führt später zusammen.
Für einen einzelnen Rechner lässt sich das unter Einstellungen einschalten („Mehrere Personen an diesem Programm“).

**Profil sichern.** Unter Einstellungen schreibt „Profil sichern …“ Wörterbuch, Wortschatz, Textbausteine,
Aufträge, Tasten, Server und deine Stimmaufnahmen in eine Datei (`.lsprofil`). „Profil zurückholen …“ liest sie an
diesem oder einem anderen Rechner wieder ein. Nicht enthalten: Diktate, Fälle und der Schlüssel für ein
Sprachmodell-Konto. Updates fassen das Profil nicht an.

## Sprecher trennen

Für Gespräche (Anamnese, Besprechung, Interview). Zwei kleine Modelle arbeiten zusammen, wie in der Pipeline von
pyannote.audio, aber ohne PyTorch und nur auf der CPU: Das Segmentierungsmodell von pyannote (6 MB, liegt der App
bei) hört in Fenstern von zehn Sekunden, wer wann spricht, auch wenn die Sprecher ohne Pause wechseln. Für jede
Stimme entsteht ein Stimmabdruck (WeSpeaker ResNet34, 26 MB); ähnliche Abdrücke werden zu Sprechern gruppiert.
Jedes erkannte Wort bekommt den Sprecher, der zu seinem Zeitpunkt spricht. Der Wechsel kann also mitten in einer
Äußerung liegen.

Grenzen: Reden zwei gleichzeitig, bekommt das Wort einen der beiden. Wer insgesamt nur wenige Sekunden spricht,
wird dem ähnlichsten Sprecher zugeschlagen. Sehr ähnliche Stimmen können verschmelzen. Gemessen ist an englischen
Interviews und Telefongesprächen mit bekannten Sprechern, nicht an einem echten deutschen Arzt-Patienten-Gespräch.

## Lizenz und Signatur

GPL-3.0-or-later, siehe `LICENSE`. Nutzen, verändern und weitergeben ist erlaubt; wer eine veränderte
Fassung weitergibt, legt deren Quelltext ebenfalls offen. Die Lizenzen der verwendeten Bausteine
stehen in `THIRD_PARTY.md`.

Die EXE trägt keine Windows-Signatur. Zu jeder Veröffentlichung liegt die SHA-256-Prüfsumme der
ZIP-Datei in `SHA256SUMS.txt`; prüfen mit

    Get-FileHash LocalScribe-<Version>-windows.zip -Algorithm SHA256

Unter `docs/github-build.yml` liegt ein vorbereiteter GitHub-Actions-Ablauf, der die ZIP-Datei
öffentlich nachvollziehbar aus dem Quelltext baut und einen Herkunftsnachweis anhängt. Er wird
aktiv, sobald er nach `.github/workflows/build.yml` verschoben wird.

## Herkunft

Eigener Code, eigene Gestaltung, eigene Töne. Der Ablauf (Taste halten, sprechen, loslassen) ist bei
Diktier-Apps üblich; aus fremden Programmen wurde nichts übernommen. Modell: primeline/parakeet-primeline
(CC-BY-4.0, primeline und NVIDIA), ONNX-Export OpenVoiceOS/primeline-parakeet-onnx.
Sprechpausen: Silero VAD. Wer eine fertige, ausgereifte Diktier-App für alle Betriebssysteme
sucht, findet sie in [Handy](https://github.com/cjpais/Handy).
