## LocalScribe 0.9.7

- **Wortfehler an den fünf eigenen Diktaten: 9,0 %** (0.9.6: 11,2 %; Tandem 8,3 %, Heidi 9,7 %). Gleiche
  Geschwindigkeit, weiter ohne Cloud. Auf den unabhängigen Prüfsätzen 10,15 % statt 10,30 % und 11,98 % statt 12,00 %.
- **Kurze Handelsnamen und Abkürzungen**: Unbekannte kurze Wörter werden mit der Kernliste verglichen
  („Trimbo“ wird Trimbow, „Trossiba“ Tresiba, „Nabik“ Nabic, „Sdemi“ STEMI).
- **Zerlegte Begriffe**: Was die Erkennung in zwei Wörter teilt, wird wieder eines („Dosier Aerosol“,
  „Sevilla mehr“ wird Sevelamer, „Pleurer Gauss“ wird Pleuraerguss).
- Schreibweisen: „Dreißiger Regel“ wird 30er-Regel, ein abgebrochenes „Grad Celsi“ wird ergänzt.
- Ein Teil dieser Regeln ist an den fünf Diktaten entstanden; dort ist der Gewinn deshalb größer als anderswo.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.6

- **Handbuch auf dem Stand der App**: Meine Begriffe, Wirkstoffnamen, Fachkorrektur, Mikrofon offen halten, Hinweis zur
  Tonqualität, Aufnahmen im Stimmtraining und die gemessene Genauigkeit im Vergleich zu Tandem und Heidi.
- Seite Stimmtraining: Der Text am neuen Häkchen war zu lang und hat die Seite bei schmalem Fenster rechts abgeschnitten.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.5

- **Stimmtraining kann Aufnahmen aufheben** (Seite Stimmtraining, ab Werk aus): Ton und vorgelesener Satz bleiben als
  WAV mit Verzeichnis auf diesem Rechner (`%LOCALAPPDATA%\LocalScribe\training`). Das ist das Material, aus dem
  ein Nachtraining des Sprachmodells auf die eigene Stimme werden kann; die Seite zeigt die gesammelten Minuten,
  öffnet den Ordner und löscht auf Wunsch alles. Ohne Häkchen wird wie bisher nichts gespeichert.
- Wirkstoffnamen werden auch mit falschem Anlaut erkannt („Chiprofloxacin“).
- Sprechertrennung an einem deutschen Arzt-Patienten-Gespräch geprüft (zwei Stimmen, 64 Sekunden): alles richtig zugeordnet.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.4

- **Vergleich mit Tandem und Heidi gemessen**: dieselben fünf Diktate, digital eingespielt. Wortfehler: Tandem 8,3 %,
  Heidi 9,7 %, LocalScribe 11,2 % (0.9.3: 12,6 %). Beide laufen in der Cloud; Heidi korrigiert das Rohtranskript
  mit einem Sprachmodell nach.
- **Wirkstoffnamen am Wortstamm**: Wer auf -mab, -sartan, -prazol und ähnlich endet und kein bekanntes Wort ist, wird
  mit den Wirkstoffen desselben Stamms verglichen („Pempolyzomap“ wird Pembrolizumab, „Retroximab“ Rituximab).
- **Weite Lautsuche**: Unbekannte Wörter, die deutlich nach genau einem Fachbegriff klingen, werden ersetzt
  („Lymphardenopathie“), die Beugung bleibt erhalten. Auf 395 unabhängigen Sätzen elf richtige Ersetzungen, eine falsche.
- **Eingedeutschte Schreibweise**: „Coronare“ und „exacerbierte“ werden zu „Koronare“ und „exazerbierte“, wenn nur
  diese Form im Lexikon steht.
- **Hinweis zur Tonqualität**: Liefert das Mikrofon keinen Ton, ist die Aufnahme sehr leise oder übersteuert, sagt
  LocalScribe das, statt still einen leeren oder schlechten Text zu liefern.
- Ist das Windows-Standardmikrofon ein virtuelles Audiokabel, nimmt LocalScribe das erste echte Mikrofon.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.3

- **Mikrofon offen halten** (Einstellungen, ab Werk aus): Das Diktat startet ohne Verzögerung und nimmt die
  Viertelsekunde vor dem Tastendruck mit, damit die erste Silbe nicht fehlt. Außerhalb eines Diktats wird nur
  diese Viertelsekunde im Arbeitsspeicher gehalten. Windows zeigt dabei dauerhaft das Mikrofon-Symbol.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.2

- **Meine Begriffe** (Seite Wörterbuch): nur die richtige Schreibweise eintragen, durch Komma getrennt –
  Medikamente, Abkürzungen, Namen. LocalScribe erkennt am Klang, wenn die Erkennung daraus etwas Ähnliches macht
  („Riba“ wird RIVA, „Trossiba“ wird Tresiba), und schreibt den Begriff wie hinterlegt. Man muss nicht mehr
  wissen, wie das Wort falsch herauskommt. Echte Wörter bleiben unberührt.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.1

- **Fachkorrektur als Option** (Seite KI-Nachbearbeitung, ab Werk aus): Das eingestellte Sprachmodell schlägt vor,
  was bei verhörten Wörtern gemeint war. Übernommen wird nur, was selbst ein Fachbegriff ist, ähnlich klingt und
  keine Zahl ändert. Gemessen mit Llama 3.1 8B lokal: drei richtige Ersetzungen, keine falsche (14,3 → 13,8 %
  Wortfehler), rund drei Sekunden je Diktat auf einer Grafikkarte.
- Der Modell-Download kommt auch mit Zertifikatsproblemen zurecht (zweiter Versuch mit eigener Zertifikatsliste).
- Beim Beenden nimmt LocalScribe das Modell eines lokalen Ollama sofort aus dem Grafikspeicher.
- Whisper large-v3-turbo deutsch auf der CPU gemessen: 16,0 % Wortfehler bei einem Drittel der Geschwindigkeit
  (Parakeet 14,3 %).

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.0

- **Deutlich genauer bei gleicher Geschwindigkeit.** Die bisher verwendete 8-Bit-Fassung des Sprachmodells
  hat gegenüber den vollen Gewichten rund sechs Prozentpunkte Wortfehlerrate gekostet. LocalScribe lädt jetzt
  eine eigene, schonender gekürzte Fassung (910 MB statt 650 MB, einmaliger Download mit Balken): so genau wie
  die vollen 2,5 GB, so schnell wie bisher. An fünf echten ärztlichen Diktaten 14,3 % Wortfehler statt 18,0 %
  (roh 21,8 % statt 27,7 %); an 221 unabhängigen Aufnahmen 12,3 % statt 12,4 %. Wer keine Verbindung hat,
  arbeitet mit der bisherigen Fassung weiter.
- Gemessen und nicht eingebaut: zwei öffentlich verfügbare, auf Medizin nachtrainierte Parakeet-Modelle
  (schlechter bzw. mit ausgelassenen Passagen) und Wort-Boosting beim Dekodieren (kaum Wirkung). Zahlen in
  `werkzeug/messen/ERGEBNIS.md`.
- Sprechertrennung an echten Gesprächen gemessen: 89 % der Sprechzeit richtig zugeordnet bei Aufnahmen in
  normaler Tonqualität, 75 % bei Telefonaufnahmen.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

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
