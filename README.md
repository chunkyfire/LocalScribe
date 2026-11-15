# LocalScribe

Lokales Diktieren per Tastenkürzel für Windows: Taste halten, sprechen, loslassen – der Text
landet im gerade aktiven Textfeld. Die Spracherkennung läuft vollständig auf dem eigenen Rechner
(primeline-Parakeet, 600 Mio. Parameter, int8-ONNX, nur CPU, rund 850 MB Arbeitsspeicher).
In den Einstellungen stehen zwei weitere Modelle zur Wahl: ein genaueres, langsameres deutsches
(NVIDIA Canary 1B v2) und ein mehrsprachiges (NVIDIA Parakeet v3, 25 europäische Sprachen).

**Handbuch mit Bildern:** [docs/LocalScribe-Handbuch.pdf](docs/LocalScribe-Handbuch.pdf) – Installieren, Starten, Diktieren und alle Funktionen auf neun Seiten.

## Installieren (ohne Adminrechte)

1. Unter **Releases** die Datei `LocalScribe-…-windows.zip` herunterladen. Die Prüfsumme steht
   daneben in `SHA256SUMS.txt`.
2. Entpacken, zum Beispiel nach `Dokumente\LocalScribe`.
3. `LocalScribe.exe` starten. Meldet Windows „Der Computer wurde geschützt“: **Weitere Informationen →
   Trotzdem ausführen** (die Datei ist nicht signiert).
4. Beim ersten Start lädt die App einmalig das Sprachmodell (910 MB). Ein Balken im Fenster, in der
   Statusleiste am unteren Bildschirmrand und im Infobereich zeigt, wie weit der Download ist; erst wenn er
   voll ist, lässt sich diktieren. Das Modell bleibt danach dauerhaft unter
   `%LOCALAPPDATA%\LocalScribe\modelle` liegen (ohne Adminrechte beschreibbar) und wird nie erneut geladen.
   Ab dann arbeitet die App ohne Internet.
   Rechner ohne Internet: den Ordner `modelle` von einem anderen Rechner neben `LocalScribe.exe` kopieren.
5. Verknüpfungen für Desktop und Startmenü: im Fenster unter **Einstellungen**.

Deinstallieren: Ordner löschen, dazu `%LOCALAPPDATA%\LocalScribe` (Einstellungen, Verlauf, Sprachmodelle).
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
  Der Text läuft live mit: Nach jeder Sprechpause erscheint, was gerade gesagt wurde.
- **Datei** – Audio- oder Videodatei hineinziehen (MP3, M4A, WAV, FLAC, OGG, MP4 …).
- **Sprecher trennen** (Häkchen bei Aufnahme und Datei) – für Gespräche: Der Text bekommt Zeilen
  „Sprecher 1: …“, „Sprecher 2: …“. Läuft auf der CPU dieses Rechners; beim ersten Einschalten wird einmalig
  ein Stimmmodell geladen (26 MB). Siehe „Sprecher trennen“ unten.
- **Wörterbuch** – falsch Erkanntes automatisch ersetzen. Mit **Wort einsprechen** lernt die App
  dazu: richtige Schreibweise eintippen, Knopf halten, Wort sprechen. Was die Erkennung daraus
  macht, wird künftig ersetzt. Übernommen wird nur, was dem richtigen Wort ähnlich ist.
  Mitgeliefert ist ein **medizinisches Basiswörterbuch** (abschaltbar): Fehlschreibungen von rund
  5 900 Wirkstoffen, Diagnosen, anatomischen und klinischen Begriffen. Siehe unten.
- **Stimmtraining** – 152 medizinische Sätze aus zehn Themen zum Vorlesen. Die App vergleicht, was sie
  verstanden hat, mit dem Satz und trägt deine Aussprache falsch erkannter Fachbegriffe ins Wörterbuch ein.
  Freiwillig; je mehr Sätze, desto besser. Siehe „Stimmtraining“ unten.
- **Textbausteine** – gesprochenes Stichwort → hinterlegter Text.
- **KI-Nachbearbeitung** – Server-Adresse, API-Schlüssel, Modell und eigene Prompts.
  Spricht jede OpenAI-kompatible Schnittstelle (Ollama, LM Studio, vLLM, eigener Anbieter).
  Der API-Schlüssel liegt in der Windows-Anmeldeinformationsverwaltung, nicht in einer Datei.
  Ist der Server nicht erreichbar, wird der unbearbeitete Text eingefügt.
- **Einstellungen** – Tasten, Mikrofon, Töne, Autostart, Aufbewahrung, Verknüpfungen.

Dateien: `%LOCALAPPDATA%\LocalScribe\` (`config.json`, `verlauf.sqlite`, `diktat.log`).

## Was mit den Daten geschieht

- **Ton.** Diktate per Taste bleiben im Arbeitsspeicher und werden nie auf die Platte geschrieben.
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
  Fassung, Hugging Face). Danach arbeitet sie offline. Die KI-Nachbearbeitung ist ab Werk aus;
  ist dort eine Adresse außerhalb des eigenen Netzes eingetragen, zeigt die App das an.
- **Stimmabdrücke.** „Sprecher trennen“ berechnet je Äußerung einen Stimmabdruck. Er lebt nur im
  Arbeitsspeicher, solange die Transkription läuft, und wird nicht gespeichert. Im Text stehen Nummern,
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
- Echtes Wort-Boosting im Modell gibt es nicht. Das Wörterbuch korrigiert nach der Erkennung.
- Das Sprachmodell ist primeline-Parakeet in einer eigenen, schonender gekürzten 8-Bit-Fassung (siehe
  `werkzeug/messen/ERGEBNIS.md`): fünf echte ärztliche Diktate 14,3 % Wortfehler, mit der üblichen Fassung 18,0 %.
- Gemessen ist an einer synthetischen Stimme, an 221 echten Aufnahmen (MultiMed) und an fünf echten
  ärztlichen Diktaten eines Sprechers (`werkzeug/messen/ERGEBNIS.md`). Dialekt, laute Umgebung und andere
  Fachgebiete sind damit nicht belegt. Jeder Text muss vor der Übernahme gegengelesen werden.
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
| NVIDIA Canary 1B v2 („genauer“) | 23,8 % | 20,6 % |
| Whisper large-v3-turbo German (primeline), zum Vergleich extern gemessen | 17,7 % | – |

Einige Einträge des Wörterbuchs stammen aus genau diesen Diktaten; die Werte mit Nachbearbeitung
sind deshalb etwas zu günstig.

Die Nachbearbeitung repariert, was knapp daneben liegt. Was das Modell grob verhört
(„Aorten V Etium“), bleibt falsch; dafür bräuchte es Wort-Boosting im Modell oder Nachtraining.

Öffentliche deutsche Aufnahmen echter medizinischer Diktate mit Transkript gibt es nicht. MultiMed
(ACL 2025) ist der einzige frei zugängliche Datensatz mit echten Stimmen; sein deutscher Teil besteht
überwiegend aus Lehrvideos für Sprachprüfungen und enthält kaum Fachbegriffe.

## Stimmtraining

Auf der Seite **Stimmtraining** steht ein Satz. Knopf halten, vorlesen, loslassen. Die App legt Wort für Wort
daneben, was sie verstanden hat. Ein falsch erkanntes Wort kommt ins persönliche Wörterbuch, wenn

- es dem richtigen Wort ähnlich klingt (Lautschlüssel, mindestens 55 % Übereinstimmung) und
- es selbst kein echtes Wort ist. „Riba“ wird zu „RIVA“; „Kabel“ wird nicht zu „Cave“, weil sonst jedes
  Kabel im Diktat ersetzt würde. Solche Fälle zeigt die App an, lernt sie aber nicht.

Getrennt gehörte Zusammensetzungen werden als Paar gelernt („Set-Implantation“ → „Stentimplantation“).
Das Material: 152 Sätze aus Kardiologie, Pneumologie, Gastroenterologie, Nephrologie, Neurologie,
Notaufnahme, Chirurgie und Orthopädie, Onkologie und Hämatologie, Medikation, Befund und Verlauf
(`diktat/lesetexte.json`, erweiterbar). Der Ton bleibt im Arbeitsspeicher. Alles Gelernte steht auf der Seite
Wörterbuch und lässt sich dort ändern oder löschen.

## Sprecher trennen

Für Gespräche (Anamnese, Besprechung, Interview). Die Pausenerkennung zerlegt den Ton ohnehin in Äußerungen;
jede bekommt einen Stimmabdruck (WeSpeaker ResNet34, ONNX, 26 MB, läuft auf der CPU). Ähnliche Abdrücke
werden zu Sprechern gruppiert, aufeinanderfolgende Äußerungen desselben Sprechers bilden einen Absatz.

Grenzen: Fällt jemand dem anderen ohne Pause ins Wort, landen beide in einer Äußerung. Einwürfe unter
1,2 Sekunden („ja“, „genau“) tragen zu wenig Stimme und werden dem Sprecher davor zugeschlagen. Wer insgesamt
weniger als acht Sekunden spricht, gilt nicht als eigener Sprecher. Geprüft ist die Trennung an echten
Aufnahmen verschiedener Sprecher, nicht an einem echten Arzt-Patienten-Gespräch.

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

Eigener Code, eigene Gestaltung, eigene Töne. Vorbild für den Ablauf war Wispr Flow;
aus dessen Programm wurde nichts übernommen. Modell: primeline/parakeet-primeline
(CC-BY-4.0, primeline und NVIDIA), ONNX-Export OpenVoiceOS/primeline-parakeet-onnx.
Sprechpausen: Silero VAD. Wer eine fertige, ausgereifte Diktier-App für alle Betriebssysteme
sucht, findet sie in [Handy](https://github.com/cjpais/Handy).
