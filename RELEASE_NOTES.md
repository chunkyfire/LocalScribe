## LocalScribe 0.7.0

- **Strg + Win ist die Standardtaste.** Strg allein hat bei längerem Halten gestört; wer sie unverändert
  hatte, wird umgestellt.
- **Drittes Sprachmodell: „Deutsch, genauer und langsamer“** (NVIDIA Canary 1B v2). An fünf echten ärztlichen
  Diktaten 20,6 % Wortfehler statt 23,3 % mit dem Standardmodell, bei etwa doppelter Rechenzeit.
- Einwürfe wie „Hey!“ oder „Hello.“, die das Modell aus einem Atemzug macht, werden verworfen.
- Wörterbuch um Fehlschreibungen aus echten Diktaten ergänzt.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.
