# LocalScribe – Technische Dokumentation

Stand: Version 1.8.1. Für Betrieb, IT und alle, die den Code lesen oder prüfen wollen. Die Bedienung steht im
[Handbuch](LocalScribe-Handbuch.pdf), die Messwerte mit Methode in [`werkzeug/messen/ERGEBNIS.md`](../werkzeug/messen/ERGEBNIS.md).

## 1. Was die App ist

LocalScribe ist ein Diktierprogramm für Windows. Taste halten, sprechen, loslassen: Der Text steht dort, wo der
Cursor ist. Die Spracherkennung läuft vollständig auf dem Prozessor des Rechners; Ton verlässt den Rechner nicht.
Es gibt kein Installationsprogramm, keinen Dienst, keinen Treiber und keinen Bedarf an Adminrechten.

LocalScribe ist ein Dokumentationswerkzeug und kein Medizinprodukt im Sinne der Verordnung (EU) 2017/745. Es
stellt keine Diagnosen, gibt keine Therapieempfehlungen und trägt kein CE-Zeichen. Funktionen, die Modelle
vergleichen oder Texte von einem Sprachmodell bearbeiten lassen, dienen Forschung, Lehre und Benchmarking. Jeder
Text ist vor der Verwendung zu lesen.

Eine Ausnahme in der Sache ist der Bereich „Visite & Übergabe“ (`diktat/visite.py`), eine klinische
Entscheidungsunterstützung im Versuchsstadium: Ein Sprachmodell erzeugt aus einem Fall Hinweise auf Risiken und
gezielte Rückfragen, zieht also medizinische Schlüsse. In der Versorgung eingesetzt wäre das Software mit
medizinischer Zweckbestimmung (MDCG 2019-11, Regel 11, mindestens Klasse IIa). Der Bereich ist deshalb ein
**experimenteller Modus für Benchmarking**: Er soll Messwerte liefern, mit denen ein Haus entscheiden kann, ob sich
eine eigene Entwicklung unter der Inhouse-Ausnahme (Art. 5 Abs. 5 MDR, mit Qualitätsmanagement und Dokumentation)
lohnt. Bis dahin fließen seine Ausgaben in keine Behandlungsentscheidung. Für eine Pilotphase bietet sich als
Risikobegrenzung an, ihn nur Fachärztinnen und Fachärzten zu geben, die jede Ausgabe selbst beurteilen können.

## 2. Systemvoraussetzungen

| | |
|---|---|
| Betriebssystem | Windows 10 oder 11, 64 Bit |
| Prozessor | x86-64 mit AVX2; getestet auf Intel Core i7-13700KF |
| Arbeitsspeicher | rund 1,5 GB für die App mit geladenem Modell |
| Platte | 250 MB entpackt (Download 101 MB), dazu 910 MB Sprachmodell |
| Rechte | normale Benutzerrechte; geschrieben wird nur unter `%LOCALAPPDATA%\LocalScribe` |
| Netz | nur für den einmaligen Download des Sprachmodells; danach läuft alles ohne Netz |

## 3. Installation und Verteilung

Einzelner Rechner:

1. Auf <https://github.com/chunkyfire/LocalScribe/releases/latest> eines der beiden Pakete laden:
   `LocalScribe-<Version>-windows-komplett.zip` (rund 1,3 GB; Sprachmodell, Stimmmodell für die Sprechertrennung und
   Namenserkennung für den Schutz vor dem Versand liegen bei, kein Internet nötig) oder
   `LocalScribe-<Version>-windows.zip` (rund 100 MB, lädt das Sprachmodell beim ersten Start).
2. Entpacken (Rechtsklick, „Alle extrahieren“), zum Beispiel nach `Dokumente\LocalScribe`.
3. `LocalScribe.exe` starten. Die Datei ist nicht signiert; Windows SmartScreen fragt beim ersten Mal nach:
   „Weitere Informationen“, dann „Trotzdem ausführen“.
4. Das kleine Paket lädt beim ersten Start das Sprachmodell (910 MB) und zeigt dabei einen Fortschrittsbalken.
   Beim Komplettpaket entfällt das. Danach erscheint das Symbol neben der Uhr; steht dort „Bereit“, kann diktiert
   werden.

Klinikrechner, Rechner ohne Internet, Verteilung an viele Rechner: das Komplettpaket. Das Modell liegt dort im
Ordner `modelle` neben `LocalScribe.exe`; die App sucht es zuerst dort (`diktat/modelle.py`) und lädt dann nichts.
Der Programmordner darf auf einem Netzlaufwerk liegen und von mehreren Konten gestartet werden, er wird nur
gelesen. Er lässt sich kopieren oder per Softwareverteilung ausrollen.

Mehrere Personen, viele Programmordner: Die Modelle müssen nicht in jedem Ordner liegen. Die App sucht sie in
dieser Reihenfolge (`modelle.places`): `modelle` neben `LocalScribe.exe`; der in den Einstellungen angegebene
Modellordner (`model_dir`); `modelle` eine Ebene über dem Programmordner; der Datenordner; zuletzt die
Modellordner, die ein anderer Programmordner desselben Windows-Kontos schon benutzt hat. Jeder Programmordner trägt
den Ordner, in dem er ein Modell gefunden hat, dafür in `modellorte.txt` im Datenordner ein (höchstens acht; ein
gerade nicht erreichbarer Ordner wird zwei Minuten lang übersprungen). Ein Ordner `modelle` aus dem Komplettpaket,
einmal neben die Programmordner gelegt, versorgt also alle, die daneben das kleine Paket entpackt haben, und eine
zweite Kopie von LocalScribe lädt nichts noch einmal.

Die Namenserkennung für den Schutz vor dem Versand (293 MB) liegt im Komplettpaket bei. Fehlt sie und ist ein
Server außerhalb des Rechners mit eingeschaltetem Schutz eingestellt, lädt die App sie nach dem Start von selbst
(`app.shield_start`), sichtbar unten links; Aufträge, die darauf warten, laufen danach weiter (`hub.shield_wait`).
Bis sie da ist, geht nichts an diesen Server.

Scheitert der Download des Modells (Proxy, Firewall), zeigt das Fenster den Grund im Klartext, dazu die Knöpfe
„Erneut versuchen“, „Komplettpaket herunterladen“ und „Protokoll öffnen“.

Aktualisieren: Unten links im Fenster steht die laufende Fassung (`Hub.update_idle`); ein Klick dort oder auf
**Nach Updates suchen** (Einstellungen, ganz unten) fragt nach, der Knopf wird zu „Update <Nummer>“, lädt auf den
nächsten Klick und heißt danach „Neu starten“. Liegt eine neuere Fassung schon im Programmordner (eingerichtet an
einem anderen Rechner am selben Ordner), erscheint „Neu starten“ ohne Nachfrage im Netz (`pflege.pending`, alle
zehn Minuten). Zwei Wege in den Einstellungen. **Nach Updates suchen**: Auf Klick fragt die App bei
`github.com` nach der neuesten Fassung (`pflege.latest`, die Weiterleitung von `…/releases/latest` nennt die Nummer).
Gibt es eine neuere, liest sie das Inhaltsverzeichnis des kleinen Pakets über HTTP-Range-Anfragen, daraus die Datei
`NEUES.txt` („Was ist neu“), vergleicht Größe und CRC-32 jeder Datei mit der laufenden Fassung, kopiert Unverändertes
von dort und lädt nur die geänderten Dateien (`pflege.fetch`); beim Entpacken prüft sie deren Prüfsummen. Von 0.15.2
auf 1.0.0 waren das 4 Dateien, rund 12 statt 112 MB. Von selbst fragt die App nur im Netz nach, wenn „Einmal am
Tag von selbst nach Updates fragen“ eingeschaltet ist (`update_check`, ab Werk aus): dann einmal je 23 Stunden,
dieselbe Anfrage wie beim Klick, ohne Meldung, wenn es nichts Neues gibt oder das Netz fehlt.
**Aus ZIP-Datei aktualisieren**: für Rechner, die GitHub nicht erreichen; die App entpackt das gewählte Paket.

Ab 1.2.0 ersetzt ein Update nichts mehr (`diktat/ort.py`, `diktat/pflege.py`):

```
LocalScribe\LocalScribe.exe          die einmal entpackte Fassung; sie startet immer
LocalScribe\aktuell.txt              Nummer der Fassung, die laufen soll
LocalScribe\fassungen\1.2.1\…       jede spätere Fassung vollständig in einem eigenen Ordner
LocalScribe\modelle, …\daten        gehören allen Fassungen
```

Beide Update-Wege legen `fassungen\<Nummer>` an, schreiben zuletzt die Markierung `.vollstaendig` hinein und danach
`aktuell.txt`. `LocalScribe.exe` im Programmordner liest beim Start `aktuell.txt`; nennt sie eine vollständige,
neuere Fassung, startet sie deren `LocalScribe.exe` und beendet sich (`ort.handover`, vor allen schweren Importen).
Verknüpfungen und Autostart zeigen deshalb immer auf die EXE im Programmordner. Folgen:

- Keine Datei, die gerade jemand benutzt, wird angefasst. Ein Update geht, während LocalScribe läuft, auf demselben
  Rechner und auf beliebig vielen anderen, die aus demselben Ordner eines gemeinsamen Laufwerks arbeiten.
- Gebraucht wird nur das Recht, im Programmordner Ordner und Dateien anzulegen; umbenannt oder gelöscht wird für das
  Update nichts. Wer das Recht nicht hat, sieht „wird zentral gepflegt“ und kann nichts ändern.
- Jede laufende App liest alle zehn Minuten `aktuell.txt` (eine kleine Datei im Programmordner, keine Netzabfrage
  nach außen). Liegt eine neuere Fassung bereit, steht im Fenster eine Leiste mit „Was ist neu“ und „Jetzt neu
  starten“, im Menü neben der Uhr „Fassung … starten“. Nichts springt auf. Ohne Klick gilt die neue Fassung ab dem
  nächsten Start, in Kliniken also meist am nächsten Morgen.
- Ältere Ordner unter `fassungen` löscht die App beim Start, wenn niemand mehr daraus arbeitet. Probe ist das
  Umbenennen des Ordners: Solange irgendwo eine `LocalScribe.exe` daraus läuft, verweigert Windows das. Erlaubt das
  Laufwerk kein Löschen, bleiben die Ordner liegen (je rund 300 MB) und können von Hand entfernt werden.
- Zurück: `aktuell.txt` löschen (dann läuft die Fassung im Programmordner) oder eine ältere, noch vorhandene Nummer
  hineinschreiben, die neuer ist als die Fassung im Programmordner.
- Zentral verteilen ohne Klick in der App: neues Paket nach `fassungen\<Nummer>` entpacken (Inhalt des Ordners
  `LocalScribe` aus der ZIP, ohne `modelle`), darin eine Datei `.vollstaendig` anlegen, die Nummer in `aktuell.txt`
  schreiben.

Wer von einer Fassung vor 1.2.0 kommt, aktualisiert einmal auf dem alten Weg (die App beendet sich, ein Skript
tauscht den Ordner); auf einem gemeinsamen Laufwerk müssen dafür einmal alle LocalScribe beenden, oder man entpackt
1.2.0 in einen neuen Ordner. Einstellungen, Verlauf und Modell im Benutzerkonto bleiben bei jedem Update erhalten.

Entfernen: Einstellungen, „LocalScribe entfernen“. Löscht die Verknüpfungen, den Autostart-Eintrag und den
Programmordner, auf Wunsch auch `%LOCALAPPDATA%\LocalScribe` und die Schlüssel in der Anmeldeinformationsverwaltung.
Von Hand: App beenden, Programmordner und `%LOCALAPPDATA%\LocalScribe` löschen. Lässt sich der Ordner nicht löschen
oder erscheint `LocalScribe.exe` auf einem Netzlaufwerk nach dem Löschen wieder, läuft das Programm noch aus diesem
Ordner: Das Fenster zu schließen beendet es nicht (es bleibt im Infobereich), und ein Server gibt eine geöffnete
Datei erst frei, wenn der Prozess endet. Beenden über das Symbol neben der Uhr oder im Task-Manager (Details,
`LocalScribe.exe`). Beobachtet auf einem
Klinik-Netzlaufwerk: Auch danach blieben die Ordner gesperrt und ließen sich erst unmittelbar nach einem Neustart des
Rechners löschen. Welcher Prozess die Dateien dort nach der Anmeldung wieder öffnete (Autostart der App, Virenscanner
oder Indexdienst), ist nicht geklärt. Abhilfe: „Mit Windows starten“ ausschalten, neu starten, gleich löschen.

Eine Fassung je Sitzung: Startet jemand LocalScribe aus einem zweiten Ordner, während es aus einem anderen läuft,
fragt die App, welche bleiben soll, und beendet auf Wunsch die andere (`winio.others`, `winio.end`). Vorher ging
still das Fenster der laufenden Fassung auf, und deren Ordner blieb gesperrt. Autostart-Eintrag und vorhandene
Verknüpfungen zieht die App beim Start auf den Ordner nach, aus dem sie läuft (`winio.follow`).

Prüfsumme: Beim Bau entsteht `dist\SHA256SUMS.txt` mit den SHA-256-Summen beider ZIP-Dateien.

## 4. Aufbau

Python 3.11, Oberfläche mit PySide6 (Qt), Spracherkennung mit ONNX Runtime auf der CPU über `onnx-asr`.
Gepackt mit PyInstaller zu einem Ordner mit `LocalScribe.exe`; `build.ps1` streicht dabei ungenutzte Qt-Teile.

| Modul | Aufgabe |
|---|---|
| `run.pyw` | Start; ein Absturz beim Start landet in `absturz.log` |
| `diktat/app.py` | Ablauf: Tastenkürzel, Aufnahme, Erkennung, Nachbearbeitung, Einfügen |
| `diktat/engine.py` | Mikrofon, Pausenerkennung, Laden und Aufruf des Sprachmodells, regelbasierte Nachbearbeitung |
| `diktat/beam.py` | Dekodieren mit mehreren Lesarten und Wortschatz-Bonus |
| `diktat/wortschatz.py` | Wortschatz dafür: Kernliste, eigene Begriffe, gelernte Fachwörter |
| `diktat/fach.py` | Fachbegriffe am Klang reparieren (Lexikon mit 39.600 Begriffen, Wirkstoffendungen) |
| `diktat/training.py` | Stimmtraining: Übungs- und Prüfsätze je Fachrichtung, Lernen aus vorgelesenen Sätzen und aus Aufnahmen mit Transkript, Wortfehler einer Messung |
| `werkzeug/lesetexte/` | Quelltexte der Übungssätze je Fachrichtung und `bauen.py`, das sie prüft, ordnet und `diktat/lesetexte.json` schreibt |
| `diktat/visite.py` | Visite & Übergabe: Fall auswerten lassen (Arztbrief-Entwurf, Sicherheitsnetz, Rückfragen), Fallablage mit Papierkorb |
| `diktat/jev.py` | Jev (TypeSafe): je Rahmen ein fester Fragesatz in einer Anfrage, Antworten als Wahrscheinlichkeiten. Notaufnahme: 17 Fragen aus WacheNG (Ersteinschätzung). Station: 17, Intensiv: 19 Fragen (Tages-Check: Lage und „heute prüfen“) |
| `diktat/sprecher.py` | Sprecher trennen: pyannote-Segmentierung und WeSpeaker-Stimmabdrücke (ONNX, CPU) |
| `diktat/vad.py` | Sprache oder Stille (Silero VAD) |
| `diktat/longform.py` | lange Aufnahmen und Tondateien stückweise |
| `diktat/modelle.py` | Sprachmodelle finden, einmal laden, Fortschritt melden |
| `diktat/llm.py`, `korrektor.py` | optionale Nachbearbeitung und Fachkorrektur über eine OpenAI-kompatible Schnittstelle |
| `diktat/schutz.py` | Namen, Daten, Orte, Nummern ersetzen, bevor Text an einen fremden Server geht |
| `diktat/handy.py` | Handy als Mikrofon: HTTPS-Seite im eigenen Netz |
| `diktat/winio.py` | Windows: globale Tasten, Einfügen, Zielfenster, Autostart |
| `diktat/hub.py`, `ui.py` | Fenster, Statusleiste, Tray-Symbol, Verlauf |
| `diktat/config.py` | Einstellungen und Ablageorte |

## 5. Vom Ton zum Text

1. **Aufnahme** mit 16 kHz mono (`sounddevice`). Der Ton liegt nur im Arbeitsspeicher.
2. **Stücke**: Die Pausenerkennung teilt an Sprechpausen (ab 0,3 Sekunden) in Stücke von höchstens 12 Sekunden.
   Auf der Seite Aufnahme kommt eine **Vorschau** dazu: Solange jemand spricht, liest die App die laufende
   Äußerung etwa jede Sekunde schnell mit (einfaches Dekodieren, `Transcriber.glimpse`) und zeigt das Ergebnis
   grau an. Der gültige Text entsteht weiter aus der ganzen Äußerung; das Endergebnis ist mit und ohne Vorschau
   dasselbe. Die Vorschau entfällt von selbst, wenn der Rechner mit dem Ton nicht nachkommt, und ist mit
   `"live_preview": false` abschaltbar.
3. **Sprachmodell**: primeline-Parakeet (NVIDIA Parakeet TDT 0.6B, auf Deutsch nachtrainiert, CC BY 4.0) als ONNX.
   Der Encoder ist auf 8 Bit gekürzt (je Kanal, 840 MB), Decoder und Joint 69 MB.
4. **Dekodieren** (`beam.py`): Acht Lesarten laufen nebeneinander. Eine Lesart, deren entstehendes Wort der Anfang
   eines Begriffs aus dem Wortschatz ist, bekommt je Wortstück einen Bonus; er wird abgezogen, wenn am Wortende
   kein ganzer Begriff dasteht. Liefert die Suche deutlich weniger Wörter als das einfache Dekodieren, gilt das
   einfache. Abschaltbar mit `"beam": 0`.
5. **Nachbearbeitung** ohne Sprachmodell (`engine.postprocess`): persönliches Wörterbuch, Basiswörterbuch bekannter
   Fehlschreibungen, Reparatur am Klang gegen das Fachlexikon (`fach.correct`), diktierte Satzzeichen, Leerzeichen.
6. **Optional**: Fachkorrektur oder Umformulieren durch ein Sprachmodell (siehe 8). Ab Werk aus.
7. **Einfügen** über die Zwischenablage in das aktive oder das gemerkte Zielfenster; die vorherige Zwischenablage
   wird wiederhergestellt, der Eintrag ist vom Windows-Zwischenablageverlauf ausgenommen.

**Sprecher trennen** (`sprecher.py`, nur Seiten Aufnahme und Datei): Der Ton läuft parallel durch das
Segmentierungsmodell von pyannote (segmentation-3.0 als ONNX, 6 MB, im Programm enthalten): Fenster von zehn
Sekunden im Abstand von fünf, je Rahmen von 17 ms die Aussage, welche von bis zu drei Stimmen spricht. Jede
Stimme eines Fensters bekommt je drei Sekunden, die sie allein spricht, einen Stimmabdruck (WeSpeaker ResNet34,
26 MB); die kurzen Abschnitte fangen Wechsel zwischen ähnlichen Stimmen auf, die die Segmentierung überhört. Am Ende werden die Abdrücke gruppiert (immer die zwei ähnlichsten Gruppen, bis die Ähnlichkeit unter 0,42
fällt; wer unter drei Sekunden oder zwei Prozent der Redezeit bleibt, zählt nicht als eigener Sprecher) und zu einer Zeitleiste „wer spricht wann“ zusammengesetzt. Die Spracherkennung liefert für jedes Wort den
Zeitpunkt; das Wort bekommt den Sprecher der Zeitleiste. So kann der Wechsel mitten in einer Äußerung liegen. Liegt
ein Wechsel höchstens zwei Wörter neben einem Satzende, rückt er dorthin. Das
ist der Aufbau von pyannote.audio 3.1, aber ohne PyTorch. Im Speicher liegt nie mehr als ein Fenster Ton.

Geschwindigkeit (i7-13700KF, 45 Sekunden Diktat): rund 2 Sekunden mit Wortschatz, 1,4 Sekunden ohne. Wichtig dafür
ist `session.intra_op.allow_spinning = 0` für beide ONNX-Sitzungen; sonst bremsen sich die Rechen-Threads von
Encoder und Decoder gegenseitig (vorher 6 Sekunden).

## 6. Lernen

Nichts davon verändert das Sprachmodell; gelernt wird in Wörterbuch und Wortschatz, beides in der Einstellungsdatei.

| Weg | Was gelernt wird |
|---|---|
| Diktieren | Fachwörter aus dem Lexikon, die im fertigen Text stehen, kommen in den Wortschatz (`learn_terms`) |
| Stimmtraining, Sätze vorlesen | Verhörer: „was die Erkennung schrieb“ → „was dastand“, wenn es ähnlich klingt und kein echtes Wort ist |
| Stimmtraining, Aufnahme mit Transkript | beides: Verhörer aus dem Vergleich, Fachwörter aus dem Transkript |
| Stimmtraining, eigene Texte | Fachwörter aus Briefen oder Befunden (docx, odt, txt, rtf, html) |
| Wörterbuch, Wort einsprechen und Einträge „(am Klang)“ | einzelne Begriffe von Hand |
| Aus Korrektur lernen | Verhörer aus dem berichtigten letzten Diktat |

In den Wortschatz kommen nur einzelne Wörter, die im mitgelieferten Lexikon stehen, höchstens 4.000. Sätze und
Namen von Patienten können so nicht hineingeraten. Tondateien werden beim Lernen nur gelesen.

**Übungssätze (seit 1.6.0).** `diktat/lesetexte.json` entsteht aus `werkzeug/lesetexte/*.txt`: je Fachrichtung
eine Datei, jede Zeile ein Satz in Sprechform (Zahlen als Wörter) mit einer Art davor: `A|` Ärztin oder Arzt diktiert
oder übergibt, `P|` Gespräch mit Patientin oder Patient, `O|` Organisation, `T|` Prüfsatz. `bauen.py` prüft Länge
(6 bis 30 Wörter), Satzende, Dubletten und dass kein Prüfsatz einem Übungssatz gleicht, und ordnet die Übungssätze
gierig: Der nächste Satz ist der, der die meisten neuen Lautfolgen und Fachwörter bringt, die Arten gemischt. Wer
nach zehn Minuten aufhört, hat deshalb das meiste schon abgedeckt. Enthalten sind der Grundstock (90 Sätze, etwa
9 Minuten), Notfallmedizin (284 Sätze, 32 Minuten) und Innere Medizin und Nephrologie (284 Sätze, 31 Minuten); eine
Fachrichtung wird immer nach dem Grundstock gelesen. Die 19 früheren Themen bleiben wählbar. Eine weitere
Fachrichtung ist eine weitere Textdatei.

**Messung.** Je Fachrichtung liegen 24 Prüfsätze bei, zum Grundstock 16; das Training zeigt sie nie. „Messen …“
lässt sie vorlesen und rechnet die Wortfehlerquote (`training.score`): Beide Seiten werden vorher gleich
geschrieben (`training.plain`: Zahlwörter zu Ziffern, Einheiten kurz, Satzzeichen weg), damit „zwölf Milligramm“
und „12 mg“ nicht als Fehler zählen. Das Ergebnis steht mit Datum und den bis dahin gelesenen Minuten in
`training_scores`. Die Messung lernt nichts ins Wörterbuch.

**Material für ein Nachtraining.** Das Stimmtraining hebt die vorgelesenen, erfundenen Sätze als WAV mit Text in
`training\` auf (Prüfsätze in `training\pruef\`), nie Diktate oder eingelesene Aufnahmen; seit 1.6.0 ohne
Schalter im Fenster (`training_keep`, ab Werk an). Ob ein Nachtraining des Sprachmodells auf die eigene Stimme die
Erkennung verbessert, ist an einer echten Stimme noch nicht gemessen. Das Training läuft außerhalb der App und
braucht eine Grafikkarte: `werkzeug/training/stimme.py <training-Ordner> <Arbeitsordner>` trainiert nur den kleinen
Schreibteil des Modells (69 MB) in Stufen (5, 10, 20, 40 Minuten Vorlesen), `stimme_messen.py` misst jede Stufe
über den Weg der App an den Prüfsätzen und, wenn gewünscht, an freien Diktaten. Nichts wird hochgeladen. Probelauf
mit einer künstlichen Stimme: `ERGEBNIS.md`.

**Profil sichern (seit 1.6.0).** „Profil sichern …“ unter Einstellungen schreibt eine Datei `.lsprofil`: ein
ZIP-Archiv mit `einstellungen.json` (wie die bisherige Sicherung, ohne Schlüssel und ohne Verlauf) und dem Ordner
`training\`. „Profil zurückholen …“ liest `.lsprofil` oder eine frühere `.json`; Stimmaufnahmen werden ergänzt,
vorhandene nicht überschrieben (`config.export`, `config.restore`). Diktate, Fälle und der Schlüssel für ein
Sprachmodell-Konto sind nicht enthalten.

**Profile (seit 1.7.0).** Für mehrere Personen an einem Programmordner, typisch ein Netzlaufwerk, aus dem viele
Rechner starten. Ein Profil ist ein Ordner `profile\<Name>` neben `LocalScribe.exe` mit `profil.json` (die
persönlichen Einstellungen, `config.PERSONAL`: Wörterbuch, Wortschatz, gelernte Wörter, Berichtigungen,
Textbausteine, Befehle, Aufträge, Tasten, Satzzeichen-Schalter, Fachrichtung, Fortschritt und Messungen des
Stimmtrainings) und `training\` (Stimmaufnahmen). Angeboten wird das, wenn es den Ordner `profile` gibt oder das
Programm auf einem Netzlaufwerk liegt, in das sich schreiben lässt (`config.profiles_on`); das erste Profil legt
den Ordner an. Welches Profil gilt, steht je Windows-Konto in `config.json` (`profile_name`); dort bleiben auch
die Einstellungen des Geräts (Mikrofon, Modellordner, Server, Verlauf) und unverändert die persönlichen Daten von
„Dieser Rechner“. Geschrieben wird mit Zusammenführen (`config._merge`): Die App merkt sich den Stand beim letzten
Lesen; was nur eine Seite geändert hat, gilt, bei Wörterbuch und Listen Eintrag für Eintrag, im echten Konflikt
gewinnt der schreibende Rechner. Ist der Programmordner nicht erreichbar, gilt die Kopie unter
`profil-kopie\<Name>.json` im Datenordner des Rechners, Aufnahmen sammeln sich daneben und wandern beim nächsten
Kontakt ins Profil. Es gibt kein Passwort und keine Rollen: Zugriffsschutz ist die Windows-Anmeldung und das
Recht auf den Programmordner. Verlauf, Fälle, Protokoll und Schlüssel liegen nie im Profil.

## 7. Daten auf dem Rechner

Alles Eigene, auch der gelernte Wortschatz, liegt unter `%LOCALAPPDATA%\LocalScribe`, also je Windows-Konto
(nicht im Roaming-Profil, wandert also nicht durchs Firmennetz). Ausnahme auf Wunsch: Gibt es neben
`LocalScribe.exe` einen Ordner `daten`, liegt alles dort (Einstellungen, „Daten in diesem Programmordner ablegen“).
So hat jede Person mit eigenem Programmordner ihre eigene Fassung mit eigenem Wortschatz und Verlauf, auch auf einem
Sammelkonto. Das gehört nur in einen Ordner, den sonst niemand lesen kann. Der Ordner gehört allen Fassungen und bleibt
bei Updates, wo er ist. Ohne diesen Ordner gilt:
Die Daten, auch das Protokoll, bleiben im Konto, selbst wenn das Programm auf einem Netzlaufwerk liegt: Der Programmordner
wird oft von mehreren geteilt und ist häufig schreibgeschützt, Verlauf und Protokoll gehören dort nicht hin. Bei
einem Sammelkonto teilen sich alle, die es benutzen, dieselben Einstellungen und denselben Verlauf. Lässt sich
`%LOCALAPPDATA%` ausnahmsweise nicht beschreiben, weicht die App auf `%APPDATA%`, das Benutzerverzeichnis und
zuletzt `%TEMP%` aus (`config._dir`).

| Datei oder Ordner | Inhalt |
|---|---|
| `config.json` | Einstellungen, Wörterbuch, Wortschatz, Textbausteine. Keine Schlüssel. |
| `sicherung\einstellungen-….json` | Kopien von `config.json`: vor jedem Wechsel der Fassung und vor dem Zurückholen, die letzten zehn (`config.backup`). Zurückholen und in eine Datei sichern: Einstellungen, „Einstellungen sichern“. |
| `verlauf.sqlite` | Verlauf der Diktate als Text, mit einstellbarer Aufbewahrungsfrist; abschaltbar |
| `profil-kopie\` | nur mit gewähltem Profil: dessen letzte Kopie für den Fall, dass der Programmordner fehlt |
| `modelle\` | Sprachmodell, Stimmmodell für die Sprechertrennung |
| `diktat.log`, `absturz.log` | Betriebsmeldungen: Dauer, Zeichenzahl, Fehler. Kein diktierter Text. |
| `aufnahmen\` | Sicherung einer laufenden langen Aufnahme; wird gelöscht, sobald der Text fertig ist |
| `visite.sqlite` | Fälle aus „Visite & Übergabe“: Eingabe und Ergebnis als Text, mit Papierkorb |
| `training\` | vorgelesene Übungssätze des Stimmtrainings als Ton mit Text (`index.jsonl`), Prüfsätze in `pruef\`; nie Diktate |

Der Schlüssel für ein Sprachmodell-Konto liegt in der Windows-Anmeldeinformationsverwaltung (`keyring`), nicht in
einer Datei. Ton aus Diktaten per Taste wird nie auf die Platte geschrieben.

## 8. Netzwerkverbindungen

Von sich aus baut die App genau eine Art von Verbindung auf: den einmaligen Download der Modelle. Dazu kommt die
Frage nach einer neuen Fassung: nur auf Klick, oder einmal am Tag, wenn das in den Einstellungen eingeschaltet ist.

| Ziel | Wann | Was geht hinaus |
|---|---|---|
| `github.com` (Release `modell-primeline-1`) | erster Start | nichts außer der Anfrage |
| `huggingface.co` | Ausweichquelle für das Modell; Stimmmodell beim ersten Einschalten der Sprechertrennung | nichts außer der Anfrage |
| `github.com` (Releases) | auf Klick (unten links im Fenster oder „Nach Updates suchen“) und beim Laden der geänderten Dateien; einmal am Tag nur mit `update_check` (ab Werk aus) | nichts außer der Anfrage |
| selbst eingetragener Sprachmodell-Server | nur wenn KI-Nachbearbeitung oder Fachkorrektur eingeschaltet sind oder in „Visite & Übergabe“ auf „Auswerten“ gedrückt wird | der diktierte Text bzw. der Fall, nach dem Schutz aus `schutz.py` |
| selbst eingetragener Sprachmodell-Server, `/models` | auf Klick „Modelle abrufen“, nach dem Speichern eines neuen Schlüssels und nach der Wahl eines Servers, zu dem schon ein Schlüssel gespeichert ist (lokale Server und OpenRouter auch ohne) | nichts außer der Anfrage; ein gespeicherter Schlüssel geht nur an den Server, zu dem er gehört |
| `api.noirdoc.de/v1/prices` | einmal je Programmlauf, zusammen mit der Modellliste von Noirdoc | nichts außer der Anfrage, ohne Schlüssel; daraus liest die App, welcher Anbieter ein Modell ausliefert (`llm.noirdoc_out`) |
| `openrouter.ai/api/v1/systemone` (Jev) | nur bei „Auswerten“ in „Visite & Übergabe“ und nur, wenn OpenRouter der eingetragene Server ist | der Fall nach dem Schutz aus `schutz.py`, dazu die festen Fragen und, falls eingetragen, die Hausregeln |
| eigenes Netz, Port 8765 | nur wenn „Handy als Mikrofon“ eingeschaltet ist | nichts; das Telefon schickt Ton an den Rechner |

Telemetrie, Lizenzabfragen oder Updates ohne Klick gibt es nicht. Für eine Firewall genügt es, nach dem ersten
Start alles zu sperren.

Ist ein Sprachmodell-Server außerhalb des Rechners eingetragen, ersetzt `schutz.py` vor dem Versand Namen,
Geburts- und andere Daten, Orte, Nummern und Kontaktangaben durch Platzhalter und setzt sie in der Antwort wieder
ein. Zwei Stufen: Regeln (Daten, Nummern, Kontaktdaten, Anschriften, Namen hinter Anrede oder Titel) und ein
Erkennungsmodell für Namen, Orte und Einrichtungen (GLiNER multi PII als ONNX, 293 MB, CPU; im Komplettpaket, sonst
per Knopf geladen). **Fehlt das Erkennungsmodell, wird nichts gesendet** (`schutz.blocked`): Nachbearbeitung und
„Visite & Übergabe“ melden das, die Fachkorrektur lässt den Text unverändert. Der Schutz gilt für alle drei Wege und
lässt sich je Anbieter abschalten; für Server im eigenen Netz (localhost, private Adressen) gilt er nicht.

Gemessen (`werkzeug/messen/schutz.py`, 17 erfundene klinische Sätze mit 34 persönlichen Angaben): Regeln allein
ersetzen 20, beide Stufen zusammen alle 34; Fachbegriffe wie Parkinson und Messwerte bleiben stehen. Das ist eine
kleine Stichprobe. Was die Erkennung übersieht oder die Spracherkennung falsch schreibt, geht lesbar hinaus, und
auch der ersetzte Text bleibt klinischer Text über eine Person (pseudonymisiert, nicht anonym). Das senkt das Risiko,
ersetzt aber keine Vereinbarung zur Auftragsverarbeitung; ob klinischer Text an einen solchen Server gehen darf,
entscheidet der Betreiber.

**Sprachmodell im eigenen Haus:** Die Schnittstelle ist OpenAI-kompatibel. Damit lässt sich jedes lokal betriebene
Sprachmodell anschließen: auf dem eigenen Rechner oder auf einem Rechner mit Grafikkarte im Kliniknetz, zum Beispiel
über Ollama, LM Studio, llama.cpp oder vLLM. Der eigene Rechner und private IP-Adressen (10.x, 172.16–31.x, 192.168.x) gelten als lokal;
Fachkorrektur und „Visite & Übergabe“ arbeiten dann, ohne dass Text das Haus verlässt, und ohne Kosten je Anfrage.

Handy als Mikrofon: Die App öffnet einen HTTPS-Server mit eigenem Zertifikat im lokalen Netz. Zugang nur mit einem
zufälligen Schlüssel aus dem QR-Code. Ab Werk aus.

## 9. Einstellungen

`config.json`, die wichtigsten Schlüssel (alle über die Oberfläche erreichbar, außer den markierten):

| Schlüssel | Bedeutung | ab Werk |
|---|---|---|
| `hotkey_hold`, `hotkey_lock`, `hotkey_paste_last`, `hotkey_target`, `hotkey_next_field` | Tasten | Strg+Win, Leertaste, Umschalt+F7, F9, F8 |
| `model_choice` | `de` (primeline-Parakeet) oder `multi` (Parakeet v3, 25 Sprachen). Das frühere `genau` (NVIDIA Canary 1B v2) wird beim Laden zu `de` | `de` |
| `beam` (nur Datei) | Zahl der Lesarten beim Dekodieren; 0 schaltet den Wortschatz-Bonus ab | 8 |
| `learn_terms`, `learned` | Wortschatz aus Diktaten mitlernen; die gelernten Wörter | an, leer |
| `vocabulary`, `dictionary` | eigene Begriffe (im Wörterbuch als „(am Klang)“); Wörterbuch „falsch → richtig“ | leer |
| `base_dictionary` | mitgeliefertes medizinisches Wörterbuch und Lexikon anwenden | an |
| `speakers` | Sprecher trennen bei Aufnahme, Datei und Übergabe; bei nur einer Stimme bleibt der Text unverändert | an (seit 1.5.0, einmal umgestellt) |
| `handover_frame` | zuletzt gewählter Rahmen der Übergabe: `zna`, `station` oder `its` | `zna` |
| `spoken_punctuation` | „Punkt“, „Komma“, „neue Zeile“ als Zeichen schreiben | aus |
| `llm`, `llm_fix` | Sprachmodell-Server und Fachkorrektur. Die Fachkorrektur nimmt bei OpenRouter und Noirdoc das schnelle Modell aus `llm.QUICK`, sonst das gewählte | aus |
| `llm_profiles`, `llm_models` | gespeicherte Anbieter (Name, Adresse, Modell; der Schlüssel liegt im Windows-Schlüsselspeicher) und eigene Modellnamen je Server. Die kurze Liste je Anbieter steht in `llm.PICKS`, das erste ist die Vorgabe | leer |
| `prompts` | Aufträge an das Sprachmodell: Name, Anweisung, Taste, und `record` (als Knopf auf der Seite Aufnahme). Mitgeliefert: Glätten, E-Mail, Stichpunkte, Arztbrief, Zusammenfassung, Meeting-Protokoll, Visite (SOAP), Pflegebericht. Beim Wechsel auf 1.7.1 kommen die zwei neuen einmal dazu; die Zeile der Aufnahme wird nur umgestellt, wenn sie noch der Vorgabe entsprach (`config._prompts_v8`) | Aufnahme zeigt Visite, Meeting-Protokoll, Arztbrief, Pflegebericht |
| `visite_prompt` | eigene Anweisung für den Rahmen Notaufnahme; leer = die mitgelieferte. Station und Intensiv haben feste Aufträge (`visite.STATION`, `visite.ITS`) | leer |
| `visite_model`, `visite_jev`, `visite_rules` | Modell für Arztbrief, Visiteneintrag und Übergabe (leer: bei OpenRouter `google/gemini-3.8-flash@low`, sonst das LLM-Modell; der Zusatz `@low` geht bei OpenRouter als `reasoning.effort` hinaus, bei jedem anderen Server als `reasoning_effort`, und einmal ohne, wenn der Server die Angabe ablehnt: `llm.model_of`, `llm._ask`), Jev-Modell (leer: `~typesafe/jev-latest`), Hausregeln für Jev | leer |
| `update_check` | einmal am Tag von selbst bei GitHub nach einer neueren Fassung fragen | aus |
| `profile_name` | gewähltes Profil am Programmordner; leer = die Daten dieses Rechners | leer |
| `training_keep` | vorgelesene Übungs- und Prüfsätze als Ton aufheben (kein Schalter im Fenster; für eine zentrale Vorgabe) | an (seit 1.6.0) |
| `field`, `training_scores` | Fachrichtung im Stimmtraining; Messungen mit Prüfsätzen (Zeitpunkt, Wortfehler, Trainingsminuten) | leer |
| `phone` | Handy als Mikrofon | aus |
| `model_dir` | eigener Ordner mit den Sprachmodellen, zum Beispiel ein Netzlaufwerk | leer |
| `live_preview` (nur Datei) | Vorschau auf die laufende Äußerung in der Aufnahme | an |
| `threads` (nur Datei) | Zahl der Rechen-Threads; 0 überlässt es der Laufzeit | 0 |

## 10. Bauen und Prüfen

Bauen: `build.ps1` (braucht `uv`, keine Adminrechte) erzeugt `dist\LocalScribe\` und den ZIP samt Prüfsumme.
Abhängigkeiten stehen in `requirements.txt`, Lizenzen in `THIRD_PARTY.md`.

Prüfen:

| | |
|---|---|
| `tests/test_neu.py` | Einheiten: Nachbearbeitung, Wörterbuch, Schutz, Wortschatz, Training, Visite, Handy-Server, Einstellungen |
| `tests/test_woerterbuch.py` | Fachlexikon: was repariert wird und was unangetastet bleiben muss |
| `tests/test_flow.py` | Ablauf mit Oberfläche: Diktat, Einfügen, Verlauf, Nachbearbeitung |
| `tests/test_download.py`, `test_long.py`, `test_llm.py`, `test_hotkey.py` | Modell-Download, lange Aufnahmen, Sprachmodell-Anbindung, Tasten |
| `LocalScribe.exe --selftest <wav>` | die gepackte App erkennt eine Datei und meldet Dauer und Text |

Messwerkzeuge liegen in `werkzeug/messen` (Wortfehlerrate an eigenen Diktaten, Corti Med-Dictate, GraSCCo,
MultiMed; Sprechertrennung; Geschwindigkeit), das Werkzeug zum Kürzen des Modells in `werkzeug/modell`, der Bau
des Lexikons in `werkzeug/woerterbuch`, die Versuche zum Nachtraining in `werkzeug/training`.

## 11. Benchmark-Ergebnisse

Wortfehlerrate nach der Nachbearbeitung, ohne Sprachmodell-Korrektur. Methode, Einzelwerte und Einschränkungen in
`ERGEBNIS.md`.

| Material | LocalScribe | zum Vergleich |
|---|---|---|
| fünf eigene ärztliche Diktate (412 Wörter, ein Sprecher) | 8,3 % | Drei Cloud-Dienste für ärztliche Dokumentation: 8,3 %, 9,7 %, 9,7 %. Lokal: Whisper Large v3 Turbo Deutsch mit Wortliste 14,1 %, VibeVoice 16,3 % |
| Corti Med-Dictate, neun echte Diktate, 33 Minuten | 15,4 % mit Kernliste; 11,1 % mit dem Wortschatz aus den eigenen Texten | 16,6 % ohne Wortschatz beim Dekodieren |
| dieselben mit Fachkorrektur durch ein Sprachmodell (älterer Stand, ohne Wortschatz beim Dekodieren) | 7,5 % und 13,7 % | – |

| Weitere Größen | Wert |
|---|---|
| Rechenzeit für 45 s Diktat (i7-13700KF, nur Prozessor) | 2,0 s mit Wortschatz, 1,4 s ohne |
| allererster Start mit Modell-Download (910 MB) | 61 s; jeder weitere Start 2 s |
| Sprechertrennung | 92,7 % richtig zugeordnete Sprechzeit bei Interviews (Sprecherzahl richtig bei 8 von 10), 81,3 % am Telefon (10 von 12); nicht erkannte Sprache zählt als falsch. Bisheriges Verfahren: 88,6 % (5 von 10) und 75,4 % (8 von 12). Deutsches Gespräch aus zwei ähnlichen Stimmen ohne Pause zwischen den Redebeiträgen: 94 % der Wörter beim richtigen Sprecher, mit 0,15 s Pause 100 % |
| Arbeitsspeicher im Betrieb | rund 1,4 GB |

Modellgröße: Der Encoder mit 8 Bit je Kanal hat 841 MB. Geprüft und verworfen sind die verbreitete Fassung mit
654 MB (eigene Diktate 18,0 % statt 14,3 % vor dem Wörterbuch-Ausbau) und eine 4-Bit-Fassung der Matrizen mit
655 MB (eigene Diktate 10,0 % statt 9,0 %, Corti 17,4 % statt 16,6 %, dazu 1,8-mal so lange Rechenzeit).

## 12. Bekannte Grenzen

- Der Wortschatz-Bonus hilft nur für Wörter, die im Wortschatz stehen. Am ersten Tag ist das die Kernliste.
- Die Programmdatei ist nicht signiert; SmartScreen warnt beim ersten Start.
- Nur Windows. Keine Anbindung an ein Krankenhausinformationssystem; der Text wird wie getippt eingefügt.
- Dialekt, laute Umgebung und mehrere gleichzeitig Sprechende sind nicht gemessen.
- Ein Nachtraining des Sprachmodells auf die eigene Stimme ist nicht eingebaut und nicht gemessen; die App kann nur
  das Material dafür sammeln. Versuche mit künstlichen Stimmen brachten an echten Stimmen keinen Gewinn.
- „Visite & Übergabe“ ist so gut wie die Modelle dahinter. Die Ausgaben sind ungeprüfte Entwürfe, die Werte von Jev
  Wahrscheinlichkeiten ohne Begründung. Gemessen an erfundenen Fällen: Jev antwortet in 0,4 bis 4 Sekunden, der
  Arztbrief mit dem Standardmodell (Gemini 3.8 Flash, wenig Nachdenken) braucht 10 bis 24 Sekunden. Die Fragesätze für
  Station und Intensiv sind an sechs erfundenen Fällen auf Plausibilität angesehen, nicht ausgewertet. Eine Auswertung
  der Treffsicherheit gibt es nicht.
- Echte Wörter, die das Sprachmodell für einen Fachbegriff setzt („Disney“ für „Dyspnoe“ bei einem Sprecher), fängt die
  Klangsuche nicht, weil es das Wort gibt. `fach.MISHEARD` ersetzt solche Wörter nur im klinischen Satz; aufgenommen
  ist bisher dieses eine beobachtete Paar. An den neun Diktaten echter Sprecher (Corti) wurde „Dyspnoe“ richtig erkannt.
- Die Seite für das Handy als Mikrofon ist bisher nur mit simuliertem Mikrofon geprüft.

## 13. Lizenz

GPL-3.0-or-later. Sprachmodell primeline-Parakeet (CC BY 4.0), Stimmmodell WeSpeaker (CC BY 4.0), Silero VAD (MIT);
alle Bestandteile in `THIRD_PARTY.md`.
