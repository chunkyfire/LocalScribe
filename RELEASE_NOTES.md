## LocalScribe 0.6.0

- **Fachbegriffe werden am Klang erkannt:** Jedes unbekannte Wort wird gegen ein Fachlexikon mit rund
  39 000 Begriffen geprüft. „Tachükardie“ wird Tachykardie, „Flegmone“ wird Phlegmone. Bekannte Wörter,
  Beugungsformen und Schreibvarianten bleiben unberührt.
- ss wird zu ß, wo es die ss-Schreibung nicht gibt (anschliessend, mässig).
- Gemessen an 395 vorgelesenen Arztbrief-Sätzen: Wortfehlerrate 12,4 % → 11,1 %, Fachbegriffe richtig
  82 % → 86 %, 60 richtige und 2 falsche Ersetzungen. Messwerkzeuge unter `werkzeug/messen/`.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.
