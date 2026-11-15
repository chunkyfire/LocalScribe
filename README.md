# LocalScribe

Lokales Diktieren per Tastenkürzel für Windows: Taste halten, sprechen, loslassen – der Text
landet im gerade aktiven Textfeld. Die Spracherkennung läuft vollständig auf dem eigenen Rechner
(primeline-Parakeet, 600 Mio. Parameter, int8-ONNX, nur CPU, rund 850 MB Arbeitsspeicher).

## Installieren (ohne Adminrechte)

1. Unter **Releases** die Datei `LocalScribe-…-windows.zip` herunterladen.
2. Entpacken, zum Beispiel nach `Dokumente\LocalScribe`.
3. `LocalScribe.exe` starten. Meldet Windows „Der Computer wurde geschützt“: **Weitere Informationen →
   Trotzdem ausführen** (die Datei ist nicht signiert).
4. Beim ersten Start lädt die App einmalig das Sprachmodell (650 MB). Danach arbeitet sie ohne Internet.
5. Verknüpfungen für Desktop und Startmenü: im Fenster unter **Einstellungen**.

Deinstallieren: Ordner löschen, dazu `%LOCALAPPDATA%\LocalScribe` (Einstellungen, Verlauf) und bei Bedarf
`%USERPROFILE%\.cache\huggingface` (Sprachmodell).

## Bedienung

| Aktion | Taste |
|---|---|
| Diktieren | **F7** halten, sprechen, loslassen |
| Freihand | während des Haltens **Leertaste**, dann loslassen und weiterreden; **F7** beendet |
| Abbrechen | **Esc** oder eine andere Taste während der Aufnahme |
| Letzten Text noch einmal einfügen | **Umschalt + F7** |
| Diktieren mit Prompt | Halte-Taste des Prompts, z. B. **F8** für „Glätten“ |

Gesprochene Befehle: „neue Zeile“, „neuer Absatz“. Alle Tasten lassen sich ändern.
Läuft die App schon, holt ein zweiter Start nur ihr Fenster nach vorn. Schließen des Fensters
beendet sie nicht; sie bleibt im Infobereich (Rechtsklick → Beenden).

## Das Fenster

- **Verlauf** – alle Diktate, Klick kopiert, „KI“ bearbeitet einen Eintrag nachträglich.
  Einträge werden nach 30 Tagen gelöscht (einstellbar).
- **Aufnahme** – einmal drücken startet, noch einmal drücken beendet, auch nach einer Stunde.
  Der Text entsteht schon während der Aufnahme.
- **Datei** – Audio- oder Videodatei hineinziehen (MP3, M4A, WAV, FLAC, OGG, MP4 …).
- **Wörterbuch** – falsch Erkanntes automatisch ersetzen.
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
  Er wird nach 30 Tagen gelöscht (einstellbar) und lässt sich ganz abschalten, etwa auf gemeinsam
  genutzten Windows-Konten. Gelöschte Einträge werden in der Datei überschrieben.
- **Ort.** Alles liegt unter `%LOCALAPPDATA%`, also nicht im Roaming-Profil, das in Firmennetzen
  auf einen Server wandert.
- **Zwischenablage.** Eingefügter Text wird vom Windows-Zwischenablageverlauf (Win+V) und von der
  Cloud-Zwischenablage ausgenommen.
- **Netz.** Die App geht nur beim ersten Start ins Internet, um das Sprachmodell zu laden (feste
  Fassung, Hugging Face). Danach arbeitet sie offline. Die KI-Nachbearbeitung ist ab Werk aus;
  ist dort eine Adresse außerhalb des eigenen Netzes eingetragen, zeigt die App das an.
- **Protokoll.** `diktat.log` enthält Zeiten und Zeichenzahlen, keine Inhalte.

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
    # Langzeittest (rund 25 Minuten): siehe Kopf von tests\langzeit\stunde.py

## Was gemessen ist und wo die Grenzen liegen

Langzeittest (`tests/langzeit`): eine Stunde vorgelesenes Diktat, 370 Sätze, durch die echte
Verarbeitungskette. Ergebnis und Vergleich stehen in `tests/langzeit/ERGEBNIS.md`.

- Das Modell erkennt zuverlässig nur einzelne Äußerungen. Enthält ein Stück eine Sprechpause oder
  ist es länger als etwa 23 Sekunden, lässt es Satzteile weg. Die App schneidet deshalb an jeder
  Sprechpause ab 0,3 Sekunden und nie später als nach 12 Sekunden.
- Reine Stille wird nicht erkannt, weil das Modell daraus gelegentlich Wörter erfindet.
- In sehr lauter Umgebung sind Pausen nicht mehr zu erkennen; dann sinkt die Vollständigkeit und
  die App weist darauf hin. Ein Headset hilft.
- Geprüft wurde mit einer synthetischen Stimme. Die Erkennungsgüte bei echten Stimmen, Dialekt
  und Fachvokabular ist damit nicht belegt. Jeder Text muss vor der Übernahme gegengelesen werden.
- In Fenster, die mit Adminrechten laufen, kann die App nicht einfügen.

## Herkunft

Eigener Code, eigene Gestaltung, eigene Töne. Vorbild für den Ablauf war Wispr Flow;
aus dessen Programm wurde nichts übernommen. Modell: primeline/parakeet-primeline
(CC-BY-4.0, primeline und NVIDIA), ONNX-Export OpenVoiceOS/primeline-parakeet-onnx.
