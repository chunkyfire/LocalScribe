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

Deinstallieren: Ordner löschen, dazu `%APPDATA%\LocalScribe` (Einstellungen, Verlauf) und bei Bedarf
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

Dateien: `%APPDATA%\LocalScribe\` (`config.json`, `verlauf.sqlite`, `diktat.log`).

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

## Technische Hinweise

- Das Modell verliert bei Stücken über etwa 23 Sekunden Text. Die App schneidet deshalb alles
  an Sprechpausen in Stücke von 10 bis 18 Sekunden.
- In Fenster, die mit Adminrechten laufen, kann die App nicht einfügen.

## Herkunft

Eigener Code, eigene Gestaltung, eigene Töne. Vorbild für den Ablauf war Wispr Flow;
aus dessen Programm wurde nichts übernommen. Modell: primeline/parakeet-primeline
(CC-BY-4.0, primeline und NVIDIA), ONNX-Export OpenVoiceOS/primeline-parakeet-onnx.
