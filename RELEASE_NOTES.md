## LocalScribe 0.8.0

- **Download des Sprachmodells ist sichtbar.** Beim ersten Start zeigt ein Balken im Fenster, in der Leiste
  am Bildschirmrand und im Infobereich, wie weit die 650 MB sind. Das Modell liegt danach dauerhaft unter
  `%LOCALAPPDATA%\LocalScribe\modelle` (ohne Adminrechte) und wird nie erneut geladen. Für Rechner ohne
  Internet lässt sich der Ordner `modelle` neben die EXE kopieren. Wer schon ein Modell hat, lädt nichts neu.
- **Sprecher trennen.** Häkchen bei Aufnahme und Datei: Gespräche bekommen Zeilen „Sprecher 1: …“,
  „Sprecher 2: …“. Läuft auf der CPU, das Stimmmodell (26 MB) wird beim ersten Einschalten geladen.
- **Stimmtraining.** 152 medizinische Sätze zum Vorlesen; falsch erkannte Fachbegriffe kommen automatisch
  ins persönliche Wörterbuch. Echte Wörter werden nie umgelernt.
- **Weniger Fehler bei gleicher Geschwindigkeit.** Einnahmeschemata („40 mg100“ → „40 mg 1-0-0“), Blutdruck
  („RR140“), Neutral-Null-Angaben, „Patientin reduziertem“ → „Patient in reduziertem“, englische Einwürfe am
  Anfang eines Diktats, ein eingeschobener Vokal in langen Fachwörtern, 330 weitere Kernbegriffe. An fünf
  echten ärztlichen Diktaten: 18,0 % Wortfehler statt 23,3 % mit dem Standardmodell (roh 27,7 %). Die Regeln
  sind an diesen Diktaten entstanden; die beiden unabhängigen Prüfsätze bleiben gleich gut (12,4 % und 11,1 %).
- Ein lokales Sprachmodell als Fachkorrektur wurde gemessen und nicht eingebaut: zu langsam und zu oft
  falsch (`werkzeug/messen/ERGEBNIS.md`).
- Handbuch neu, mit Datenschutz und dem Abschnitt „Kein Medizinprodukt“.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.7.0

- **Strg + Win ist die Standardtaste.** Strg allein hat bei längerem Halten gestört; wer sie unverändert
  hatte, wird umgestellt.
- **Drittes Sprachmodell: „Deutsch, genauer und langsamer“** (NVIDIA Canary 1B v2). An fünf echten ärztlichen
  Diktaten 20,6 % Wortfehler statt 23,3 % mit dem Standardmodell, bei etwa doppelter Rechenzeit.
- Einwürfe wie „Hey!“ oder „Hello.“, die das Modell aus einem Atemzug macht, werden verworfen.
- Wörterbuch um Fehlschreibungen aus echten Diktaten ergänzt.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.
