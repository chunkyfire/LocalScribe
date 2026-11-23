## LocalScribe 2.0.0

- **Eine Liste „Anbieter“.** Unter Einstellungen, LLM, stehen OpenRouter, Noirdoc, IONOS, STACKIT, Ollama und LM Studio
  jetzt in einer einzigen Liste; darunter eigene Anbieter und „Eigene Adresse …“. Die zweite Liste „Server“ und
  „Speichern als …“ gibt es nicht mehr: Wählen, Schlüssel einfügen, speichern. Jeder Anbieter behält seinen Schlüssel.
- **Prompts heißen wieder Prompts** und haben einen eigenen Reiter in den Einstellungen. Je Prompt drei Haken: Knopf
  auf der Seite Aufnahme, in der Auswahlliste „Meine Prompts“, als Menüpunkt links angepinnt.
- **Seite Aufnahme:** Hinter den Knöpfen steht die Auswahlliste „Meine Prompts“. Darunter die Zeile „Eigener Prompt“:
  kurz hinschreiben, was aus dem Text werden soll, und „Ausführen“. Das Zeichen links daneben formuliert die kurze
  Eingabe zu einem vollständigen Prompt aus, passend zum Transkript; der Text bleibt änderbar. „In die Sammlung“
  merkt ihn.
- **Angepinnte Prompts** stehen als eigene Menüpunkte links. Dort aufnehmen, und nach dem Stopp schreibt LocalScribe
  das Ergebnis von selbst. Verlauf, Übergabe und Wortschatz lassen sich aus der Leiste nehmen (Einstellungen, Prompts).
- **Neue Aufnahme, neuer Fall:** Der Knopf steht jetzt neben der Überschrift, auch in den Listen.
- **Löschen ohne Umweg.** In „Gespeichert“ und „Fälle“ öffnet ein Klick; beim Überfahren stehen rechts ein Stift
  (umbenennen) und ein X (in den Papierkorb). Im Papierkorb entsprechend zurückholen und endgültig löschen.
- **Übergabe mit dem Bereich Pflege.** Neben Notaufnahme, Normalstation und Intensivstation gibt es Pflege: ein Knopf
  schreibt aus Text und Ablage den Pflegebericht. Ersteinschätzung, Sicherheitsnetz und Rückfragen gibt es dort nicht.
- **Weniger Text auf den Seiten.** Erklärtexte stehen nicht mehr unter den Überschriften und in den Karten, sondern
  beim Überfahren eines kleinen i daneben.
- Behoben: Das Mausrad über einem Auswahlfeld verstellte unbemerkt dessen Wert, zum Beispiel das Modell, wenn man die
  Seite rollte. Auswahlfelder reagieren jetzt nicht mehr auf das Rad; die Seite rollt weiter.
- Behoben: In den Listen „Gespeichert“ und „Fälle“ erschien bei langen Texten ein heller Rollbalken am unteren Rand.

## LocalScribe 1.8.1

- **Noirdoc als Anbieter.** Unter Einstellungen, LLM, steht in der Liste „Server“ jetzt Noirdoc (`api.noirdoc.de`,
  Verarbeitung in der EU). Wählen, Schlüssel einfügen, speichern: LocalScribe legt den Anbieter mit eigenem Schlüssel
  an und zeigt gleich, ob der Schlüssel gilt. Modelle der zwei Unteranbieter ohne Verschwiegenheitsverpflichtung
  bietet LocalScribe dort nicht an. Die Maskierung bei Noirdoc ist ab Werk aus; der Schutz von LocalScribe ersetzt
  Namen, Daten und Nummern wie bei jedem Server außerhalb. Die Bedingungen von Noirdoc schließen klinische Zwecke aus.
- **Modell wählen statt eintippen.** Bei OpenRouter und Noirdoc steht oben eine kurze Liste; die Vorgabe ist
  Gemini 4 Hydrogen mit wenig Nachdenken. „Modelle abrufen“ setzt darunter alles, was der Server meldet. Über „+“
  kommt ein eigener Modellname dazu, „Entfernen“ nimmt ihn wieder heraus. Wer schon ein Modell eingestellt hat,
  behält es.
- Gemessen an sechs erfundenen Diktaten (Visite, Pflegebericht): Gemini 4 Hydrogen braucht 5 bis 14 Sekunden je
  Auftrag, Gemini 3.1 Flash Lite 1 bis 4. Die **Fachkorrektur** hängt an jedem Diktat und nimmt deshalb bei
  OpenRouter und Noirdoc immer das schnelle Modell, egal was oben gewählt ist.
- Der Zusatz `@low` hinter einem Modellnamen (wenig Nachdenken) gilt jetzt bei jedem Server, nicht nur bei
  OpenRouter. Kennt ein Server die Angabe nicht, geht die Anfrage ohne sie hinaus.
- Behoben: Wer in der Liste „Server“ einen anderen Anbieter wählte, schickte beim Abrufen der Modelle den
  gespeicherten Schlüssel des bisherigen Anbieters mit, und „Speichern“ überschrieb dessen Eintrag. Jetzt bleibt
  jeder Schlüssel bei seinem Anbieter; ein Wechsel holt dessen Modell und Schlüssel zurück.
- Behoben: Auf der Seite LLM waren im üblichen Fenster die Knöpfe am rechten Rand abgeschnitten.

## LocalScribe 1.8.0

- **Seite Aufnahme neu gestaltet.** Im leeren Zustand stehen eine große Zeitanzeige, eine Wellenform und ein breiter
  Knopf „Aufnahme starten“. Das Mikrofon ist gezeichnet und sitzt mittig; der schiefe Punkt ist weg. Die Reiter
  stehen rechts neben der Überschrift. Wird das Fenster klein oder liegt oben ein Band, werden Zeit und Wellenform
  kleiner: Nichts überlappt, nichts wird abgeschnitten.
- **Laufende Aufnahme:** Über dem Text läuft die Zeit, daneben der Pegel der Stimme, das Neueste rechts in Lime. Der
  Knopf heißt „Stopp“ und ist orange, danach „Schreibt …“, bis der Rest geschrieben ist. Die Übergabe sieht gleich aus.
- **Zeichen vor den Menüpunkten.** Überschriften und Zeit stehen in der Schrift Space Grotesk; sie liegt bei.
- **Kein doppelter Download.** Startet LocalScribe aus einem zweiten Programmordner desselben Windows-Kontos, benutzt
  es die Modelle, die der erste schon hat (Sprachmodell, Sprechertrennung, Namenserkennung). Jeder Programmordner
  merkt seinen Modellordner dafür im Datenordner vor (`modellorte.txt`).
- **Die Namenserkennung lädt von selbst.** Ist ein Server außerhalb des Rechners eingestellt, der Schutz an und die
  Namenserkennung fehlt (kleines Paket), lädt LocalScribe sie nach dem Start einmal (293 MB); der Stand steht unten
  links. Ein Auftrag, der in dieser Zeit geklickt wird, wartet und startet danach von selbst, statt mit einer
  Fehlermeldung zu enden. Die Regel bleibt: Ohne Namenserkennung geht nichts an einen Server außerhalb.
- Behoben: Nach einer Aufnahme stand auf der Seite Aufnahme „dann Auswerten“, obwohl es diesen Knopf dort nicht gibt.

## LocalScribe 1.7.1

- **Seite Aufnahme: vier Aufträge für die Klinik.** Unter dem Transkript stehen jetzt **Visite**, **Meeting-Protokoll**,
  **Arztbrief** und **Pflegebericht**, in dieser Reihenfolge. Glätten und Zusammenfassung stehen dort nicht mehr. Als
  Aufträge bleiben beide erhalten (Glätten behält die Taste F8) und lassen sich unter Einstellungen, LLM, wieder
  ankreuzen. Wer seine Auswahl schon selbst geändert hatte, behält sie und bekommt die zwei neuen dazu.
- **Visite** schreibt aus dem Gesagten einen Visiteneintrag nach dem SOAP-Schema: Subjektiv (was die Patientin oder
  der Patient schildert), Objektiv (Befund und Werte), Beurteilung (wie gesagt), Plan (Anordnungen als Liste).
- **Pflegebericht** schreibt einen Eintrag für den Verlaufsbericht der Pflege: je Vorgang Beobachtung, Maßnahme,
  Wirkung und Weitergabe, sachlich und ohne Wertung, Aussagen wörtlich in Anführungszeichen. Routine ohne
  Besonderheit und Floskeln wie „o. B.“ fallen weg. Bei Sturz, Wunde, Schmerz, Fixierung oder Medikationsfehler
  steht am Ende, welches Blatt zusätzlich auszufüllen ist. Pflegediagnosen, Ziele und Maßnahmen schlägt der Auftrag
  nicht vor: Die Einschätzung bleibt bei der Pflegefachperson.
- Beide übernehmen nur, was gesagt wurde, und kennzeichnen mögliche Hörfehler bei Arzneimitteln, Zahlen und
  Einheiten mit `[unklar: …]`, statt sie stillschweigend zu ändern. Die Ergebnisse sind Entwürfe und vor jeder
  Verwendung zu prüfen.
- Messprotokoll: Zeit vom Ende des Diktats bis zum Text für 5 bis 60 Sekunden Ton (`werkzeug/messen/latenz.py`).

## LocalScribe 1.7.0

- **Profile für mehrere Personen an einem Programmordner.** Liegt LocalScribe auf einem Netzlaufwerk, steht unten
  links im Fenster, wer diktiert: „Dieser Rechner“ oder ein Profil. Ein Klick wählt ein Profil oder legt eines an.
  Ein Profil enthält Wörterbuch, Wortschatz, Textbausteine, Aufträge, Tasten und das Stimmtraining mit seinen
  Aufnahmen. Es liegt im Programmordner unter `profile\<Name>` und folgt der Person an jeden Rechner, der LocalScribe
  von dort startet; der Rechner rechnet weiter selbst. Die Wahl merkt sich jeder Rechner je Windows-Konto: Am eigenen
  Konto wählt man einmal, an einem Stationskonto wechselt man mit einem Klick, auch über das Symbol neben der Uhr.
  Für einen einzelnen Rechner lässt sich das unter Einstellungen einschalten; sonst sieht man davon nichts.
- **Was auf dem Rechner bleibt:** Verlauf, Fälle, Protokoll, Mikrofon, Server und Schlüssel. Profile haben kein
  Passwort: Wer den Programmordner starten darf, kann jedes Profil wählen.
- **Programmordner nicht erreichbar:** LocalScribe arbeitet mit der letzten Kopie auf dem Rechner weiter und führt
  Änderungen und Aufnahmen zusammen, sobald der Ordner wieder da ist. Nutzen zwei Rechner gleichzeitig dasselbe
  Profil, bleiben die Ergänzungen beider erhalten.
- „Profil sichern“ und „Profil zurückholen“ gelten für das gewählte Profil.

## LocalScribe 1.6.1

- **Update unten links im Fenster.** Dort steht jetzt die laufende Fassung. Ein Klick fragt bei GitHub nach einer
  neueren. Gibt es eine, steht dort „Update“ mit der Nummer: Ein Klick lädt nur die geänderten Dateien und richtet
  die neue Fassung neben der laufenden ein, danach steht dort „Neu starten“. Hat jemand an einem anderen Rechner
  am selben Ordner aktualisiert, erscheint „Neu starten“ von selbst. Der Weg über Einstellungen bleibt; dort steht
  weiter, was neu ist.
- **Tägliche Nachfrage, wenn gewünscht.** Neu in den Einstellungen: „Einmal am Tag von selbst nach Updates fragen“.
  Ab Werk aus: Ohne diesen Schalter fragt die App wie bisher nur auf Klick im Netz nach.
- Werkzeug für das Nachtraining auf die eigene Stimme (`werkzeug/training/stimme.py`, `stimme_messen.py`): liest
  die Aufnahmen des Stimmtrainings, trainiert auf der eigenen Grafikkarte nur den kleinen Schreibteil des
  Sprachmodells und misst mit den Prüfsätzen, was 5, 10, 20, 40 Minuten bringen. Noch nicht Teil der App; der
  Probelauf mit einer künstlichen Stimme steht im Messprotokoll.

## LocalScribe 1.6.0

- **Stimmtraining mit neuen Sätzen und Fachrichtung.** Die Übungssätze sind neu geschrieben. Zuerst kommt ein
  **Grundstock** für alle (etwa 9 Minuten: Zahlen, Einheiten, Dosierungen, Vitalwerte, häufige Arzneimittel und
  Wendungen), danach die gewählte **Fachrichtung** mit jeweils gut 30 Minuten: **Notfallmedizin** und **Innere Medizin
  und Nephrologie**; weitere Fächer folgen. Jede Fachrichtung enthält Sätze, wie Ärztinnen und Ärzte sie diktieren
  oder übergeben, Sätze aus dem Gespräch mit Patientinnen und Patienten und Sätze aus der Organisation. Die
  Reihenfolge ist so gewählt, dass jeder nächste Satz möglichst viele neue Laute und Fachwörter bringt: Auch fünf
  Minuten lohnen sich. Die Fachrichtung merkt sich die App.
- **Warum neu:** Ein Teil der bisherigen Sätze deckte sich mit den Diktaten, an denen die Erkennung gemessen wird.
  Die neuen Sätze sind von allen Messungen getrennt. Die früheren Themen bleiben für Fächer ohne neue Sätze
  wählbar, ohne die zwölf Sätze, die sich überschnitten.
- **Messen, was das Vorlesen bringt.** „Messen …“ liest 40 Prüfsätze vor, die im Training nie vorkommen, und zeigt
  deine Wortfehlerquote. Einmal vor dem Training, später wieder: Die Zeile „Messungen“ zeigt den Verlauf.
- **Der Ton der Übungssätze wird ohne Haken aufgehoben** (nur diese erfundenen Sätze, nie Diktate), damit das
  Sprachmodell später auf die eigene Stimme nachtrainiert werden kann. „Alle löschen“ entfernt sie.
- **Profil sichern.** Unter Einstellungen schreibt „Profil sichern …“ Wörterbuch, gelernten Wortschatz,
  Textbausteine, Aufträge, Tasten, Server und die Stimmaufnahmen in eine Datei (`.lsprofil`); „Profil zurückholen …“
  liest sie an diesem oder einem anderen Rechner wieder ein. Nur die Einstellungen als JSON gehen weiter. Updates
  fassen das Profil nicht an.
- Behoben: „Aus Datei zurückholen“ übernahm die Einstellungen seit 1.3.0 erst nach einem Neustart und zeigte keine
  Bestätigung.
- Behoben: Übungssätze mit vielen Zahlen wurden manchmal als „passt nicht zum Satz“ abgelehnt, weil die Erkennung
  Ziffern schreibt und der Satz Zahlwörter enthält.

## LocalScribe 1.5.0

- **Übergabe in drei Rahmen: Notaufnahme, Station, Intensiv.** Oben rechts wählbar; Notaufnahme ist die Vorgabe, die
  letzte Wahl gilt für den nächsten Fall. Jeder Rahmen stellt Jev eigene Fragen und gibt dem Sprachmodell einen eigenen
  Auftrag:
  - **Station:** Tages-Check statt Ersteinschätzung. Droht eine Verschlechterung, ist eine Entlassung in 48 Stunden
    realistisch, Sepsis-Screening; darunter „heute prüfen“: Laborkontrolle, Antibiotika, Medikation,
    Thromboseprophylaxe, Zugänge und Katheter, Mobilisation, Delir und Sturz, Sozialdienst, Konsil, Therapieziel.
    Das Sprachmodell schreibt einen Visiteneintrag (Verlauf, Befund, Beurteilung, Procedere, Diagnosen, Medikation
    mit dem, was heute geändert wurde).
  - **Intensiv:** Droht eine Eskalation, verlegbar in 24 Stunden, Aufwach- und Atemversuch, Extubation absehbar;
    „heute prüfen“: Sedierung, Antiinfektiva, Nierenersatz, Negativbilanz, Ernährung, Thromboseprophylaxe,
    Ulkusprophylaxe, Katheter, Frühmobilisation, Delir-Screening, Therapieziel und Angehörige. Das Sprachmodell
    schreibt eine Übergabe nach Organsystemen mit Tageszielen und statt der Patienteninfo einen Text für Angehörige.
  - Sicherheitsnetz und Rückfragen richten sich nach dem Rahmen: auf Station nach Medikation, Entlassung und
    Verschlechterung, auf Intensiv nach Dosen, Raten, Vorzeichen und Tagesroutine.
- **Hörfehler werden gemeldet statt übernommen.** Alle drei Aufträge weisen das Sprachmodell an, verhörte Arzneimittel,
  Dosen, Einheiten und fehlende Vorzeichen im Sicherheitsnetz zu nennen und nicht stillschweigend zu korrigieren.
- **Arztbrief dreimal so schnell.** Bei OpenRouter schreibt jetzt Gemini 3.8 Flash mit wenig Nachdenken: rund 15
  statt 45 Sekunden, in der Messung mit denselben gemeldeten Hörfehlern wie bisher Gemini 3.1 Pro. Unter
  Einstellungen, LLM, „Modell für Brief und Übergabe“ stehen Standard, Gründlich (Gemini 3.1 Pro) und Schnell
  (Gemini 3.6 Flash) zur Wahl; ein eigener Modellname geht weiter. Neu: Der Zusatz `@low` hinter einem Modellnamen
  lässt ein denkendes Modell bei OpenRouter weniger nachdenken.
- **Rat zum Modell je Anbieter.** Unter der Server-Adresse steht, welches Modell sich dort bewährt hat (OpenRouter,
  IONOS, STACKIT, eigener Rechner). STACKIT AI Model Serving ist als Anbieter vorbelegt.
- **Sprachmodell: nur noch Deutsch und Mehrsprachig.** Das zweite deutsche Modell („genauer und langsamer“) ist
  entfernt: Seit der neuen Nachbearbeitung war es auf den eigenen Diktaten nicht mehr genauer (18,7 % gegenüber
  18,0 % Wortfehler), aber etwa halb so schnell. Wer es gewählt hatte, steht jetzt auf Deutsch.
- **Sprecher trennen ist ab Werk an** (Aufnahme, Datei, Übergabe). Bei nur einer Stimme bleibt der Text, wie er ist.
  Das Häkchen schaltet es ab. Fehlt das Stimmmodell (26 MB), wird es beim ersten Öffnen der Seite geholt.
- Beim „Neu erzeugen“ zeigen die Blöcke den Wartetext statt der alten Fassung.

## LocalScribe 1.4.0

- **Übergabe ist wieder ein eigener Menüpunkt** (vorher „Visite & Übergabe“ als Auftrag auf der Seite Aufnahme), jetzt
  mit einer **Ablage** für den Fall. Jede beantwortete Rückfrage und jeder Text, den du mit „Zur Ablage legen“
  beiseitelegst, ist ein Eintrag; ein Klick zeigt, ändert oder entfernt ihn. Ausgewertet wird immer alles zusammen.
- **Rückfragen direkt beantworten.** Unter jeder Rückfrage des Modells steht ein Feld: Antwort eintragen, „Ablegen“.
  Der Knopf „Auswerten“ heißt danach „Neu erzeugen“ und berücksichtigt Antworten und neue Einträge.
- **Aufnahme aufgeräumt.** Leer zeigt die Seite nur einen großen Aufnahmeknopf und „Datei laden“. Nach der Aufnahme
  steht das gespeicherte Transkript da, darunter drei Aufträge: Glätten, Zusammenfassung, Meeting-Protokoll. Welche
  Aufträge dort stehen, bestimmt ein Haken je Auftrag unter Einstellungen, LLM.
- **Zusammenfassung** schreibt bei einem Patientengespräch eine knappe klinische Dokumentation (Anlass, Anamnese,
  Befunde, Beurteilung, Vorgehen), sonst fünf bis acht Sätze. **Meeting-Protokoll** ist auf Besprechungen zugeschnitten.
  Wer die beiden Texte nicht geändert hat, bekommt die neuen.
- **Wörterbuch: eine Liste statt zwei.** Das Feld „Meine Begriffe“ ist weg. Wer nur die richtige Schreibweise kennt,
  klickt „Hinzufügen“ und füllt nur die rechte Spalte aus; links steht dann „(am Klang)“. Vorhandene Begriffe stehen
  als solche Zeilen in der Liste.
- **Stimmtraining kompakter:** Vorlesen, aus eigenem Material lernen (Aufnahmen mit Transkript, eigene Texte),
  Haken für das Nachtraining.
- Fälle aus 1.3.0 liegen unter Übergabe, „Fälle“. Die Seite Aufnahme führt ab jetzt eine eigene Liste.
- Behoben: Ergebnisblöcke konnten in kleinen Fenstern zusammengedrückt werden.

## LocalScribe 1.3.0

- **Vier Menüpunkte statt acht.** Verlauf, Aufnahme, Wortschatz, Einstellungen. Wörterbuch, Stimmtraining und
  Textbausteine sind Reiter unter „Wortschatz“. „Aufnahme“ und „Datei“ sind eine Seite: aufnehmen oder über „Datei …“
  eine Audio- oder Videodatei laden. „Visite & Übergabe“ ist keine eigene Seite mehr, sondern ein Auftrag.
- **Aufträge unter dem Text.** Nach der Aufnahme stehen unter dem Text die Aufträge als Knöpfe: Arztbrief,
  Zusammenfassung, Meeting-Protokoll, Stichpunkte, E-Mail, Glätten, Visite & Übergabe und alle eigenen Prompts aus den
  Einstellungen. Ein Klick, das Ergebnis erscheint darunter als Block mit „Kopieren“. Mehrere Aufträge nacheinander
  gehen; alles wird mit dem Text unter „Gespeichert“ abgelegt. Drei Aufträge sind neu (Arztbrief, Zusammenfassung,
  Meeting-Protokoll) und werden bei vorhandenen Einstellungen einmal ergänzt.
- **Einstellungen gehen nicht mehr verloren.** Vor jedem Wechsel der Fassung legt LocalScribe eine Kopie der
  Einstellungen im Datenordner ab (Ordner `sicherung`, die letzten zehn). Unter Einstellungen gibt es „In Datei
  sichern“ und „Aus Datei zurückholen“, etwa für einen anderen Rechner. API-Schlüssel stehen nicht in der Datei; sie
  liegen im Schlüsselspeicher von Windows.
- **Neues Erscheinungsbild.** Halb durchsichtige Karten vor einem dunklen Grund mit weichen Lichtflecken, rundere
  Formen, Reiter als Pillen. Das Fenster selbst bleibt undurchsichtig, damit es auf jedem Windows gleich aussieht.
- Nicht fertig transkribierte Aufnahmen bietet jetzt die Seite Aufnahme zum Nachholen an.

## LocalScribe 1.2.1

- **„Was ist neu“ vor dem Update zeigte nichts an.** Unter Windows gebaute Pakete haben andere Zeilenenden; daran
  scheiterte das Lesen der Änderungen aus dem Paket. Behoben auf beiden Seiten: beim Lesen und beim Bauen.
- Zugleich das erste Update auf dem neuen Weg: von 1.2.0 aus lädt LocalScribe nur die geänderten Dateien, richtet 1.2.1
  neben der laufenden Fassung ein und startet sie beim nächsten Mal.

## LocalScribe 1.2.0

- **Updates, während LocalScribe läuft, auch für viele Rechner an einem Ordner.** Ein Update ersetzt nichts mehr. Die
  neue Fassung kommt in einen eigenen Ordner (`fassungen\<Nummer>`), die Datei `aktuell.txt` nennt ihre Nummer, und
  `LocalScribe.exe` startet beim nächsten Mal diese Fassung. Niemand muss LocalScribe dafür beenden: nicht am eigenen
  Rechner und nicht an den anderen, wenn der Ordner auf einem gemeinsamen Laufwerk liegt. Jeder Rechner übernimmt die
  neue Fassung bei seinem nächsten Start. Bis dahin steht im Fenster eine schmale Leiste mit „Jetzt neu starten“;
  nichts springt auf. Ältere Fassungen räumt LocalScribe weg, sobald niemand mehr daraus arbeitet.
- **Was ist neu.** Vor dem Update zeigt „Was ist neu in …“ die Änderungen der neuen Fassung, gelesen aus dem Paket.
  Nach dem Update weist das Fenster einmal darauf hin. Jederzeit: Einstellungen, ganz unten, „Was ist neu“. Im
  Programmordner liegt dasselbe als `NEUES.txt`.
- **Zentral gepflegt.** Wer im Programmordner nichts anlegen darf, sieht das beim Suchen nach Updates und bekommt die
  neue Fassung, sobald jemand mit Schreibrecht sie eingerichtet hat.
- **Einmalig zu beachten:** Das Update von 1.1.1 oder älter auf 1.2.0 läuft noch auf dem alten Weg (LocalScribe
  beendet sich und tauscht den Ordner). Auf einem gemeinsamen Laufwerk müssen dafür einmal alle LocalScribe beenden.
  Ab 1.2.0 ist das vorbei.
- **Gemessen, nicht eingebaut.** medBERT als Schiedsrichter bringt an den fünf eigenen Diktaten 8,3 → 8,0 % und bleibt
  draußen (133 MB für einen Fehler weniger). Dasselbe Diktat in drei Geschwindigkeiten erkennen und abstimmen lassen:
  16,6 → 15,7 % an neun echten Diktaten, bei dreifacher Rechenzeit. Einzelheiten in `werkzeug/messen/ERGEBNIS.md`.

## LocalScribe 1.1.1

- **Visite & Übergabe aufgeräumt.** Die große Aufnahmekarte ist weg: oben eine schmale Leiste mit Fallbezeichnung,
  Aufnahmeknopf (zeigt beim Aufnehmen die Zeit), „Sprecher trennen“ und „Auswerten“. Der Text nimmt die ganze Breite ein
  und tritt zurück, sobald ein Ergebnis da ist. Darunter stehen Ersteinschätzung, Sicherheitsnetz und gezielte
  Rückfragen gleich breit nebeneinander, darunter der Arztbrief, daneben Kodierung und Patienteninfo. Die
  Ersteinschätzung ist kompakter: Kärtchen für Versorgungspfad, Fallführung und Bett, darunter nur, was ab 70 %
  vorgeschlagen wird; der Rest in einer Zeile. Im schmalen Fenster werden aus drei Spalten zwei.
- **Prompt für Visite & Übergabe im Reiter LLM.** Modell für den Arztbrief, Hausregeln für Jev und der Prompt stehen
  jetzt in den Einstellungen unter LLM, unter den übrigen Prompts.
- **Gemessen, noch nicht eingebaut: medBERT als Schiedsrichter.** Ein deutsches medizinisches Sprachmodell
  (medBERT.de, 109 Mio. Parameter) bewertet die Alternativen, die die Spracherkennung selbst für ein Wort hatte. An
  neun echten Diktaten (33 Minuten) sinkt die Wortfehlerrate damit von 15,7 % auf 15,2 %; Einzelheiten in
  `werkzeug/messen/ERGEBNIS.md`.

## LocalScribe 1.1.0

- **Visite & Übergabe neu gebaut.** Links ein Aufnahmeknopf wie auf der Seite Aufnahme, auf Wunsch mit „Sprecher
  trennen“; der Text läuft mit und lässt sich nach dem Stopp korrigieren. „Auswerten“ startet zwei Modelle
  nebeneinander. Jev (TypeSafe, über OpenRouter) gibt eine Ersteinschätzung als Wahrscheinlichkeiten: Notaufnahme oder
  Notdienstpraxis, Schockraum-Kriterien, fallführende Abteilung, Bett suchen und wo, EKG, Zugang, Labor mit Profil,
  Monitoring, Bildgebung. Gemini 3.1 Pro schreibt Arztbrief-Entwurf, Sicherheitsnetz und drei gezielte Rückfragen.
  Jeder Teil steht in einem eigenen Block mit „Kopieren“: Anamnese offen, Befund und der Rest zum Aufklappen, Kodierung
  und Patienteninfo eingeklappt. Die englische Zusammenfassung entfällt. Gemessen an einem erfundenen Fall: Jev nach
  0,4 bis 4 Sekunden, der Arztbrief nach rund 36 Sekunden. Mit einem Sprachmodell im eigenen Haus entfällt die
  Ersteinschätzung, der Arztbrief kommt dann von diesem Modell. Weiterhin ein experimenteller Modus, kein Medizinprodukt.
- **Fälle umbenennen** in der Fallliste; der Name ist die Fallbezeichnung über dem Text.
- **LLM in den Einstellungen.** Die Seite „KI-Nachbearbeitung“ ist jetzt der Reiter „LLM“ in den Einstellungen. Dort
  stehen auch das Modell für den Arztbrief und optionale Hausregeln für die Ersteinschätzung.
- **Tasten per Druck festlegen.** In ein Tastenfeld klicken, Kombination drücken, speichern. Entf leert, Esc bricht ab.
- **„Disney“ statt „Dyspnoe“.** Bei einem Sprecher schrieb das Sprachmodell „Disney“. Weil es das Wort gibt, griff die
  Klangsuche nicht. Solche echten Wörter werden jetzt im klinischen Satz ersetzt („Keine Disney, kein Fieber“ wird
  „Keine Dyspnoe“), sonst nicht („Disney Plus“ bleibt). Aufgenommen ist bisher dieses eine beobachtete Paar.

## LocalScribe 1.0.0

Erste Fassung mit der Nummer 1.0.

- **Update per Klick**: Einstellungen, ganz unten „Nach Updates suchen“. LocalScribe fragt bei GitHub nach der
  neuesten Fassung, vergleicht sie Datei für Datei mit der installierten und lädt nur, was sich geändert hat
  (von 0.15.2 auf 1.0.0: 4 Dateien, rund 12 statt 112 MB). Danach ersetzt es den Programmordner und startet neu. Von selbst fragt
  die App nie nach. Erreicht der Rechner GitHub nicht, wie oft in Kliniken, bleibt der Weg über die ZIP-Datei.
- **Vergleichswerte ohne Produktnamen**: Handbuch, Webseite und Dokumentation nennen die drei zum Vergleich gemessenen
  Cloud-Dienste nicht mehr beim Namen. Die Messung ist klein (fünf Diktate, ein Sprecher).
- Handbuch und technische Dokumentation durchgesehen. Neu darin: Lässt sich der Programmordner auf einem Netzlaufwerk
  nicht löschen, hilft ein Neustart des Rechners und sofortiges Löschen danach. So beobachtet auf einem Klinikrechner;
  welcher Prozess die Dateien dort festhielt, ist nicht geklärt.
- Was LocalScribe kann: Diktieren per Taste in jedes Textfeld, lange Aufnahmen mit Live-Text, Dateien transkribieren,
  Sprecher trennen, Wörterbuch und Stimmtraining, Textbausteine, auf Wunsch Nachbearbeitung durch ein eigenes
  Sprachmodell. Die Spracherkennung läuft auf dem eigenen Rechner, ohne Grafikkarte und ohne Adminrechte.
  Gemessen: 8,3 % Wortfehlerrate an fünf ärztlichen Diktaten eines Sprechers, 2 Sekunden für 45 Sekunden Diktat.
- Noch nicht enthalten: Nachtraining des Sprachmodells auf die eigene Stimme. Das Stimmtraining sammelt dafür auf
  Wunsch die vorgelesenen Übungssätze.

## LocalScribe 0.15.2

- **Schutz vor dem Versand nachgeprüft und verschärft**: Geht Text an ein Sprachmodell außerhalb des Rechners,
  ersetzt LocalScribe persönliche Angaben durch Platzhalter. Nachgemessen an 17 erfundenen klinischen Sätzen mit 34
  Angaben: Mit der Namenserkennung wurden alle 34 ersetzt, mit den Regeln allein nur 20. Deshalb gilt jetzt: **Fehlt
  die Namenserkennung auf dem Rechner, wird nichts gesendet.** Vorher ging der Text dann nur mit den Regeln geschützt
  hinaus. Die Namenserkennung (293 MB) liegt jetzt im Komplettpaket (rund 1,3 GB).
- Namen aus mehreren Wörtern hinter Anrede oder Titel („Frau Aylin Demirci“) ersetzen auch die Regeln jetzt ganz.
- Beenden ist endgültig: Drei Sekunden nach „Beenden“ ist der Prozess in jedem Fall weg, damit kein unsichtbarer
  Rest den Programmordner festhält.

## LocalScribe 0.15.1

- **Ordner ließ sich nicht löschen, LocalScribe.exe tauchte wieder auf**: Ursache war eine Fassung, die im
  Hintergrund aus dem alten Ordner weiterlief. Startete man die neue aus einem anderen Ordner, ging nur das Fenster
  der alten auf. Jetzt merkt LocalScribe beim Start, dass es schon aus einem anderen Ordner läuft, nennt beide
  Ordner und beendet auf Wunsch die andere Fassung. Danach ist der alte Ordner frei.
- Autostart und vorhandene Verknüpfungen zeigen nach einem Umzug von selbst auf den Ordner, aus dem die App läuft.
  Vorher starteten sie weiter die alte Fassung.
- Unter Einstellungen, „Über LocalScribe“ steht, aus welchem Ordner die App läuft und wo ihre Daten liegen.

## LocalScribe 0.15.0

- **Sprecher trennen, neues Verfahren**: Die App erkennt Sprecherwechsel jetzt auch ohne Sprechpause. Dafür hört
  das Segmentierungsmodell von pyannote mit (6 MB, liegt der App bei, läuft auf dem Prozessor, ohne PyTorch), und
  jedes Wort wird über seinen Zeitpunkt einer Stimme zugeordnet. Bisher bekam jedes Stück zwischen zwei
  Sprechpausen genau einen Sprecher. Gemessen: 93 statt 89 % richtig zugeordnete Sprechzeit bei Interviews, 81 statt
  75 % am Telefon; die Zahl der Sprecher stimmt bei 8 statt 5 von 10 und bei 10 statt 8 von 12 Aufnahmen. Auch wer
  nur kurz spricht, kann jetzt ein eigener Sprecher sein (ab drei Sekunden und zwei Prozent der Redezeit).
- **by cemmec.ai**: Im Fenster steht, von wem LocalScribe ist; unter Einstellungen, „Über LocalScribe“ führen Verweise
  zu cemmec.ai und zu LinkedIn für Support, Rückfragen und Änderungswünsche. Auch im Handbuch und im README.

## LocalScribe 0.14.6

- **Update aus ZIP repariert**: Lag der Programmordner in einem Pfad mit Umlauten (zum Beispiel `Oberärzte`), fand
  das Tausch-Skript ihn nicht, das Update scheiterte nach einer Minute und die App startete nicht wieder. Die Pfade
  gehen jetzt unabhängig von der Codepage an das Skript.
- Beim Aktualisieren und Entfernen poppt kein schwarzes Fenster mehr auf. Vorher erschien während des Wartens jede
  Sekunde eines.
- Wer von 0.14.3 bis 0.14.5 kommt und Umlaute im Pfad hat: dieses eine Mal noch von Hand in einen neuen Ordner
  entpacken, danach funktioniert das Update aus der App.

## LocalScribe 0.14.5

- **Aufnahme mit Live-Vorschau**: Schon beim Sprechen steht der Text grau da und wächst etwa jede Sekunde mit; nach
  der Sprechpause wird daraus der gültige Text. Das Endergebnis ist dasselbe wie ohne Vorschau (gemessen), die
  Genauigkeit ändert sich nicht.
- **Eigene Fassung je Programmordner** (Einstellungen, „Daten in diesem Programmordner ablegen“): Einstellungen,
  Verlauf, Wörterbuch und Gelerntes liegen dann im Ordner `daten` neben dem Programm statt im Windows-Konto. Für
  Rechner, an denen sich mehrere ein Konto teilen.
- **Gemeinsamer Modellordner** (Einstellungen, „Modellordner“): Die Sprachmodelle müssen nicht in jedem
  Programmordner liegen. Ohne Einstellung genügt ein Ordner `modelle` neben den Programmordnern.
- Webseite, README und Handbuch zeigen vorn die Messwerte und den Download der aktuellen Version.

## LocalScribe 0.14.4

- **Sprecher trennen ohne Internet**: Das Komplettpaket bringt jetzt auch das Stimmmodell (26 MB) mit. Bisher wurde
  es beim Einschalten nachgeladen; in Netzen, die Downloads sperren, blieb die Aufnahme dadurch nach dem Stopp bei
  „Schreibe den Rest fertig“ hängen.
- Fehlt das Stimmmodell, läuft die Aufnahme sofort ohne Sprecherzeilen durch und sagt das, statt bei jeder Äußerung
  auf das Netz zu warten.
- Update aus ZIP: Modelle, die das neue Paket nicht mitbringt, werden einzeln aus der alten Fassung übernommen.

## LocalScribe 0.14.3

- **Aktualisieren aus der App**: Einstellungen, ganz unten „Aus ZIP-Datei aktualisieren“. ZIP der neuen Fassung
  auswählen, LocalScribe ersetzt den Programmordner und startet neu. Das kleine Paket genügt: Liegt das Sprachmodell
  im Programmordner, wandert es mit. Einstellungen, Verlauf und Wörterbuch bleiben.
- **Entfernen aus der App**: „LocalScribe entfernen“ löscht Verknüpfungen, Autostart und Programmordner, auf Wunsch
  auch die eigenen Daten und gespeicherten Schlüssel.
- Lässt ein Netzwerkordner das Ersetzen oder Löschen nicht zu, sagt die App das vorher, statt halb fertig zu werden.
- Handbuch und technische Dokumentation beschreiben Aktualisieren und Entfernen, auch von Hand.

## LocalScribe 0.14.2

- **Komplettpaket** `LocalScribe-…-windows-komplett.zip` (rund 1 GB): Das Sprachmodell liegt schon im Ordner, die
  App braucht kein Internet. Gedacht für Klinikrechner, deren Netz den Download des Modells sperrt. Das kleine Paket
  (rund 100 MB) gibt es weiter.
- Scheitert der Download des Sprachmodells, zeigt das Fenster jetzt den Grund im Klartext, mit den Knöpfen „Erneut
  versuchen“, „Komplettpaket herunterladen“ und „Protokoll öffnen“. Bisher stand dort nur „Modellfehler“.
- Einstellungen, Verlauf und Protokoll bleiben im eigenen Benutzerkonto (`%LOCALAPPDATA%\LocalScribe`), auch wenn
  das Programm auf einem Netzlaufwerk liegt. Lässt sich dort nicht schreiben, weicht die App selbst aus.
- Im Programmordner liegen keine Markdown-Dateien mehr: `LIESMICH.txt`, das Handbuch als PDF, Lizenzen als Text.
  Die technische Dokumentation gibt es als PDF und online.

## LocalScribe 0.14.1

- „Visite & Übergabe“ ist als **experimenteller Modus für Benchmarking** beschriftet: Er soll Messwerte liefern, mit
  denen ein Haus entscheidet, ob sich eine eigene Entwicklung unter der Inhouse-Ausnahme (Art. 5 Abs. 5 MDR) lohnt.
- Handbuch und technische Dokumentation heben die Benchmark-Ergebnisse hervor und beschreiben, wie sich ein
  Sprachmodell im eigenen Haus anschließen lässt (Rechner mit Grafikkarte, zum Beispiel über Ollama oder LM Studio).
- Stimmtraining: Die Beschriftung sagt jetzt unmissverständlich, dass nur die angezeigten, erfundenen Übungssätze
  aufgehoben werden können, nie Diktate.

## LocalScribe 0.14.0

- **Visite & Übergabe** (neuer Bereich, aus WacheNG übernommen): Fall diktieren oder tippen, ein Sprachmodell erzeugt
  daraus einen Arztbrief-Entwurf, ein Sicherheitsnetz, drei gezielte Rückfragen, einen Kodiervorschlag und eine
  Patienteninfo, jeweils zum Kopieren. Mit „Neuer Patient“, „Fallliste“ und „Papierkorb“; jede Eingabe wird
  gesichert, Löschen führt zuerst in den Papierkorb. Die Anweisung an das Sprachmodell steht unter Einstellungen und
  ist änderbar. Liegt das Sprachmodell außerhalb des Rechners, sieht es nur die geschützte Fassung ohne Namen und
  Daten. **Nur für Forschung, Lehre und den Vergleich von Modellen; kein Medizinprodukt.**
- **Schlanker**: Der Download hat 101 statt 123 MB, entpackt 246 statt 302 MB (ungenutzte Qt-Teile für 3D, Web und
  PDF und ein ungenutzter Lader entfernt); toter Code ist gestrichen.
- **Material für ein Nachtraining**: Das Stimmtraining kann die vorgelesenen, erfundenen Sätze als Ton aufheben
  (ab Werk aus, nie Diktate). Ob ein Nachtraining auf die eigene Stimme hilft, ist noch nicht gemessen.
- Geprüft und nicht übernommen: ein kleineres Sprachmodell mit 655 MB (4 Bit). Es ist an echten Diktaten
  schlechter (10,0 % statt 9,0 %, Corti 17,4 % statt 16,6 %) und 1,8-mal langsamer.
- Handbuch mit den Abschnitten „Visite & Übergabe“ und „Wie gut und wie schnell“ (Messwerte); technische
  Dokumentation erweitert.

## LocalScribe 0.13.0

- **Aus Aufnahme mit Transkript lernen** (Seite Stimmtraining): Tondateien auswählen, das Transkript liegt als
  Textdatei mit gleichem Namen daneben oder wird im zweiten Schritt gewählt. LocalScribe erkennt die Aufnahme,
  vergleicht mit dem Transkript und lernt Verhörer fürs Wörterbuch und Fachwörter für den Wortschatz. Der Ton wird
  nur gelesen und nirgends gespeichert.
- **„Aufnahmen aufheben“ gibt es nicht mehr.** Das Stimmtraining speichert keinen Ton, auch nicht auf Wunsch.
  Liegen aus einer früheren Version noch Aufnahmen vor, zeigt die Seite sie zum Löschen an.
- „Aus eigenen Texten lernen“ und der gelernte Wortschatz stehen jetzt auf der Seite Stimmtraining; dort ist alles
  beisammen, womit die App dazulernt.
- Neu: technische Dokumentation (`docs/TECHNIK.md`) mit Aufbau, Datenablage, Netzwerkverbindungen, Verteilung ohne
  Internet und Prüfwegen. Handbuch überarbeitet.

## LocalScribe 0.12.1

- **Rund dreimal so schnell.** Encoder und Decoder des Sprachmodells haben je eigene Rechen-Threads; in der
  Voreinstellung der Laufzeitbibliothek drehten beide nach getaner Arbeit weiter und nahmen sich gegenseitig die
  Kerne weg. Abgestellt. Gemessen auf einem i7-13700KF an 45 Sekunden Diktat: Encoder 3,2 → 0,9 s, einfaches
  Dekodieren 0,75 → 0,17 s, Dekodieren mit Wortschatz 1,7 → 0,6 s. Die Erkennung ist damit trotz Wortschatz
  schneller als vorher ohne. An der Genauigkeit ändert das nichts (Corti: 11,1 %).
- Diktierte Satzzeichen (Punkt, Komma, Doppelpunkt …) stehen immer im Wortschatz und kleben seltener am Vorwort.
- Fachgebiets-Pakete als fertiger Wortschatz gemessen und verworfen (kein Gewinn, `werkzeug/messen/ERGEBNIS.md`).

## LocalScribe 0.12.0

- **Erkennung mit Wortschatz**: Beim Erkennen laufen jetzt acht Lesarten nebeneinander her, und eine Lesart, die
  auf ein Fachwort aus deinem Wortschatz hinausläuft, bekommt einen Bonus. Bisher wurde ein verhörtes Fachwort erst
  nachträglich am Klang repariert; war es in Trümmer zerlegt („Ami no fenazo“), war nichts mehr zu retten. An neun
  echten ärztlichen Diktaten (Corti Med-Dictate) sinkt die Wortfehlerrate mit passendem Wortschatz von 16,6 % auf
  11,1 %, die Trefferquote bei Fachbegriffen steigt von 65 % auf 81 %; derselbe Wortschatz nur in der
  Nachbearbeitung schafft 14,2 %. Ohne passenden Wortschatz bringt es wenig (16,6 → 15,8 %): Entscheidend ist,
  dass die Wörter drinstehen, die du wirklich diktierst.
- **Der Wortschatz wächst von selbst**: LocalScribe merkt sich, welche Fachwörter aus seinem Lexikon in deinen
  Diktaten vorkommen. Schneller geht es über Wörterbuch, „Aus eigenen Texten lernen“: eigene Briefe oder Befunde
  auswählen (docx, odt, txt, rtf, html), übernommen werden nur einzelne Fachwörter aus dem Lexikon, keine Sätze und
  keine Namen. Alles bleibt auf dem Rechner. „Meine Begriffe“ zählen wie bisher dazu.
- Kostet knapp die Hälfte mehr Rechenzeit beim Erkennen (45 Sekunden Diktat: rund 6 statt 4 Sekunden); abschaltbar mit `"beam": 0` in der Einstellungsdatei.
- Die Idee stammt aus dem Austausch mit Dr. Sándor Kónya, der dasselbe Prinzip (Beam Search mit
  Fachwörterbuch) für sein System gemessen hat; Verfahren und Messung hier sind eigenständig (`diktat/beam.py`,
  `werkzeug/messen/wortschatz_corti.py`).

## LocalScribe 0.11.1

- **Stimmtraining: fast doppelt so viel Lesematerial.** 297 statt 152 Sätze, 14 neue Themen: Endokrinologie,
  Infektiologie, Rheumatologie, Intensivmedizin, Radiologie, Urologie, Gynäkologie und Geburtshilfe, Dermatologie,
  HNO und Augenheilkunde, Psychiatrie, Pädiatrie, Geriatrie und Palliativmedizin, Labor, Anästhesie. Die Sätze sind
  erfunden und enthalten keine Patientendaten.

## LocalScribe 0.11.0

- **Handy als Mikrofon**: Einstellungen, „Handy als Mikrofon“ ankreuzen, speichern, QR-Code scannen. Das Telefon
  nimmt im Browser auf (keine App nötig) und schickt den Ton nach dem Stopp an den Rechner; erkannt und eingefügt
  wird dort wie bei jedem Diktat. Beide Geräte müssen im selben Netz sein. Die Verbindung ist verschlüsselt mit
  einem Zertifikat, das LocalScribe selbst erzeugt; das Telefon zeigt dafür einmal eine Warnung. Ohne das Kürzel
  aus dem QR-Code nimmt der Rechner nichts an. Grenzen: Windows fragt beim ersten Einschalten nach der Firewall;
  in Kliniknetzen sind Geräte oft voneinander getrennt, dann geht es nicht.

## LocalScribe 0.10.1

- **Zielfenster**: Umschalt + F9 merkt das Fenster, das gerade vorn ist. Ab dann landet jedes Diktat dort, auch
  wenn du inzwischen in einem anderen Programm liest oder klickst. Noch einmal Umschalt + F9 löst die Bindung.
  Ist das Fenster geschlossen, geht der Text wieder dorthin, wo der Cursor steht. Die Taste ist unter
  Einstellungen, Tasten änderbar.
- Messung: fünf Sprachmodelle als Fachkorrektur verglichen (`werkzeug/messen/ERGEBNIS.md`).

## LocalScribe 0.10.0

- **Schutz vor dem Versand**: Geht Text an ein Sprachmodell außerhalb des Rechners, ersetzt LocalScribe vorher
  Namen, Daten, Telefonnummern, E-Mail-Adressen, Anschriften und lange Nummern durch Platzhalter und übersetzt die
  Antwort zurück. Regeln greifen immer; eine Namenserkennung (GLiNER, 293 MB, Knopf auf der Seite
  KI-Nachbearbeitung) findet auch Namen ohne Anrede. Für fremde Server ab Werk an.
- **Anbieter speichern und wechseln**: mehrere Server mit eigenem Namen und eigenem Schlüssel (OpenRouter, IONOS,
  lokal), Auswahl auf der Seite KI-Nachbearbeitung.
- **Fachkorrektur für große Sprachmodelle**: neuer Türsteher, lange Texte gehen in Stücken gleichzeitig an den Server.
  Mit Gemini Flash Lite gemessen: eigene Diktate 9,0 → 7,5 % Wortfehler (Dienst A 8,3 %), neun fremde ärztliche
  Diktate (Med-Dictate von Corti) 16,7 → 13,7 %, Arztbrief-Sätze 10,2 → 8,4 %, rund eine Sekunde je Diktat.
- **Satzzeichen diktieren** (Einstellungen, ab Werk aus): „Punkt“, „Komma“, „Doppelpunkt“, „neue Zeile“ … werden
  zu Zeichen. Auf Med-Dictate 18,3 → 16,7 %.
- **Aus Korrektur lernen** merkt sich jetzt auch richtige Wörter an falscher Stelle („Kabel“ statt Cave) und gibt
  sie der Fachkorrektur als Hinweis mit.
- Neuer unabhängiger Prüfsatz: neun echte deutsche ärztliche Diktate mit Wortlaut-Transkript (`werkzeug/messen/corti.py`).

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.9

- **Sprungmarken in Textbausteinen**: Ein Baustein kann Marken enthalten, `[ ]`, `[Befund]` oder `___`. Nach dem
  Einfügen springt **Umschalt + F8** zur nächsten Marke und löscht sie; dort diktiert man weiter. Die Taste lässt sich
  in den Einstellungen ändern. Gerechnet wird in Zeichen ab der letzten Cursorstelle: Wer zwischendurch mit der Maus
  woanders hinklickt, bringt die Reihenfolge durcheinander. Programme, die `[ ]` beim Tippen umformatieren (der neue
  Windows-Editor), eignen sich nicht; dort `___` verwenden.
- „Normalbefunde hinzufügen“ legt zusätzlich die „Vorlage Aufnahme“ mit sechs Sprungmarken an.

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.8

- **Aus Korrektur lernen** (Seite Wörterbuch): Das letzte Diktat öffnen, die falsch erkannten Wörter berichtigen,
  auf Lernen klicken. Verhörte Fachwörter kommen ins Wörterbuch („Riba“ wird RIVA). Was selbst ein richtiges Wort
  ist („Kabel“ statt Cave), wird angezeigt, aber nicht gelernt.
- **Normalbefunde als Textbausteine** (Seite Textbausteine, Knopf „Normalbefunde hinzufügen“): zehn Formulierungen
  für unauffällige Befunde, abrufbar per Stichwort („Normalbefund Lunge“). Jeder Text lässt sich ändern oder löschen.
- Dienst B an denselben fünf Diktaten gemessen: 9,7 % Wortfehler (LocalScribe 9,0 %, Dienst A 8,3 %, Dienst C 9,7 %).

Installation: ZIP entpacken, `LocalScribe.exe` starten. Keine Adminrechte nötig. Die Datei ist nicht
signiert: Meldet Windows „Der Computer wurde geschützt“, auf **Weitere Informationen → Trotzdem ausführen**.

## LocalScribe 0.9.7

- **Wortfehler an den fünf eigenen Diktaten: 9,0 %** (0.9.6: 11,2 %; Dienst A 8,3 %, Dienst C 9,7 %). Gleiche
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
  Tonqualität, Aufnahmen im Stimmtraining und die gemessene Genauigkeit im Vergleich zu Dienst A und Dienst C.
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

- **Vergleich mit Dienst A und Dienst C gemessen**: dieselben fünf Diktate, digital eingespielt. Wortfehler: Dienst A 8,3 %,
  Dienst C 9,7 %, LocalScribe 11,2 % (0.9.3: 12,6 %). Beide laufen in der Cloud; Dienst C korrigiert das Rohtranskript
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
