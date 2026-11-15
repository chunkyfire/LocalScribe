## LocalScribe 0.4.0

- **Live-Transkription:** Bei langen Aufnahmen erscheint der Text nach jeder Sprechpause, nicht erst am Ende.
  Der Zwischenstand lässt sich jederzeit kopieren.
- **Sprechpausen erkennt jetzt Silero VAD** am Klang statt an der Lautstärke. Das funktioniert auch bei
  sehr leiser Sprache und in lauter Umgebung.
- **Wort einsprechen:** Im Wörterbuch die richtige Schreibweise eintippen, Knopf halten, Wort sprechen.
  Was die Erkennung daraus macht, wird künftig ersetzt.
- Verlauf wird ab Werk nach 7 Tagen gelöscht.
- Lizenz: GPL-3.0-or-later. Prüfsumme der ZIP-Datei in `SHA256SUMS.txt`.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.
