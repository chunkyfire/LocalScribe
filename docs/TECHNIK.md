# LocalScribe – Technische Dokumentation

Stand: Version 0.14.4. Für Betrieb, IT und alle, die den Code lesen oder prüfen wollen. Die Bedienung steht im
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
   `LocalScribe-<Version>-windows-komplett.zip` (rund 1 GB; Sprachmodell und Stimmmodell für die Sprechertrennung
   liegen bei, kein Internet nötig) oder
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

Scheitert der Download des Modells (Proxy, Firewall), zeigt das Fenster den Grund im Klartext, dazu die Knöpfe
„Erneut versuchen“, „Komplettpaket herunterladen“ und „Protokoll öffnen“.

Aktualisieren: Einstellungen, „Aus ZIP-Datei aktualisieren“. Die App entpackt das Paket neben den Programmordner
(`<Ordner>.neu`), beendet sich, und ein Skript im Temp-Ordner tauscht die Ordner, sobald die Dateien frei sind, und
startet neu (`diktat/pflege.py`). Modelle, die das Paket nicht mitbringt, wandern aus dem Ordner `modelle` der alten
Fassung in die neue; für ein Update genügt deshalb das kleine Paket. Ob sich der Ordner überhaupt ersetzen lässt,
prüft die App vorher: Netzwerkordner erlauben oft das Anlegen, aber nicht das Umbenennen oder Löschen. Dann sagt sie
das und ändert nichts. Wird der alte Ordner binnen 60 Sekunden nicht frei, startet die bisherige Fassung wieder und
meldet es. Einstellungen, Verlauf und Modell im Benutzerkonto bleiben bei jedem Update erhalten. Von Hand: App
beenden, neues ZIP in einen neuen Ordner entpacken.

Entfernen: Einstellungen, „LocalScribe entfernen“. Löscht die Verknüpfungen, den Autostart-Eintrag und den
Programmordner, auf Wunsch auch `%LOCALAPPDATA%\LocalScribe` und die Schlüssel in der Anmeldeinformationsverwaltung.
Von Hand: App beenden, Programmordner und `%LOCALAPPDATA%\LocalScribe` löschen. Meldet Windows dabei „Zugriff
verweigert“, läuft das Programm noch (auch in einer anderen Sitzung), oder das Konto darf in diesem Netzwerkordner
nicht löschen.

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
| `diktat/training.py` | Lernen aus vorgelesenen Sätzen und aus Aufnahmen mit Transkript |
| `diktat/visite.py` | Visite & Übergabe: Fall auswerten lassen (Arztbrief-Entwurf, Sicherheitsnetz, Rückfragen), Fallablage mit Papierkorb |
| `diktat/sprecher.py` | Sprecher trennen (WeSpeaker ResNet34, ONNX, CPU) |
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
2. **Stücke**: Die Pausenerkennung teilt an Sprechpausen in Stücke von wenigen Sekunden.
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
| Wörterbuch, Wort einsprechen und Meine Begriffe | einzelne Begriffe von Hand |
| Aus Korrektur lernen | Verhörer aus dem berichtigten letzten Diktat |

In den Wortschatz kommen nur einzelne Wörter, die im mitgelieferten Lexikon stehen, höchstens 4.000. Sätze und
Namen von Patienten können so nicht hineingeraten. Tondateien werden beim Lernen nur gelesen.

Material für ein Nachtraining: Auf Wunsch (`training_keep`, ab Werk aus) hebt das Stimmtraining die vorgelesenen,
erfundenen Sätze als WAV mit Text in `training\` auf, nie Diktate oder eingelesene Aufnahmen. Ob ein Nachtraining
des Sprachmodells auf die eigene Stimme die Erkennung verbessert, ist nicht gemessen; mit künstlichen Stimmen
brachte es nichts (`ERGEBNIS.md`). Das Training selbst läuft außerhalb der App (`werkzeug/training`, braucht eine
Grafikkarte) und würde nur den kleinen Schreibteil des Modells (69 MB) ersetzen.

## 7. Daten auf dem Rechner

Alles liegt unter `%LOCALAPPDATA%\LocalScribe` (nicht im Roaming-Profil, wandert also nicht durchs Firmennetz).
Das gilt auch für das Protokoll und auch dann, wenn das Programm auf einem Netzlaufwerk liegt: Der Programmordner
wird oft von mehreren geteilt und ist häufig schreibgeschützt, Verlauf und Protokoll gehören dort nicht hin. Bei
einem Sammelkonto teilen sich alle, die es benutzen, dieselben Einstellungen und denselben Verlauf. Lässt sich
`%LOCALAPPDATA%` ausnahmsweise nicht beschreiben, weicht die App auf `%APPDATA%`, das Benutzerverzeichnis und
zuletzt `%TEMP%` aus (`config._dir`).

| Datei oder Ordner | Inhalt |
|---|---|
| `config.json` | Einstellungen, Wörterbuch, Wortschatz, Textbausteine. Keine Schlüssel. |
| `verlauf.sqlite` | Verlauf der Diktate als Text, mit einstellbarer Aufbewahrungsfrist; abschaltbar |
| `modelle\` | Sprachmodell, Stimmmodell für die Sprechertrennung |
| `diktat.log`, `absturz.log` | Betriebsmeldungen: Dauer, Zeichenzahl, Fehler. Kein diktierter Text. |
| `aufnahmen\` | Sicherung einer laufenden langen Aufnahme; wird gelöscht, sobald der Text fertig ist |
| `visite.sqlite` | Fälle aus „Visite & Übergabe“: Eingabe und Ergebnis als Text, mit Papierkorb |
| `training\` | nur wenn eingeschaltet: vorgelesene Sätze des Stimmtrainings als Ton |

Der Schlüssel für ein Sprachmodell-Konto liegt in der Windows-Anmeldeinformationsverwaltung (`keyring`), nicht in
einer Datei. Ton aus Diktaten per Taste wird nie auf die Platte geschrieben.

## 8. Netzwerkverbindungen

Ab Werk baut die App genau eine Art von Verbindung auf: den einmaligen Download der Modelle.

| Ziel | Wann | Was geht hinaus |
|---|---|---|
| `github.com` (Release `modell-primeline-1`) | erster Start | nichts außer der Anfrage |
| `huggingface.co` | Ausweichquelle für das Modell; Stimmmodell beim ersten Einschalten der Sprechertrennung | nichts außer der Anfrage |
| selbst eingetragener Sprachmodell-Server | nur wenn KI-Nachbearbeitung oder Fachkorrektur eingeschaltet sind oder in „Visite & Übergabe“ auf „Auswerten“ gedrückt wird | der diktierte Text bzw. der Fall, nach dem Schutz aus `schutz.py` |
| eigenes Netz, Port 8765 | nur wenn „Handy als Mikrofon“ eingeschaltet ist | nichts; das Telefon schickt Ton an den Rechner |

Telemetrie, Lizenzabfragen oder automatische Updates gibt es nicht. Für eine Firewall genügt es, nach dem ersten
Start alles zu sperren.

Ist ein Sprachmodell-Server außerhalb des Rechners eingetragen, ersetzt `schutz.py` vor dem Versand Namen,
Geburts- und andere Daten, Orte, Nummern und Kontaktangaben durch Platzhalter und setzt sie in der Antwort wieder
ein. Das senkt das Risiko, ersetzt aber keine Vereinbarung zur Auftragsverarbeitung; ob klinischer Text an einen
solchen Server gehen darf, entscheidet der Betreiber.

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
| `model_choice` | `de` (primeline-Parakeet), `genau` (NVIDIA Canary 1B v2, genauer und langsamer; ohne Wortschatz-Bonus) oder `multi` (Parakeet v3, 25 Sprachen) | `de` |
| `beam` (nur Datei) | Zahl der Lesarten beim Dekodieren; 0 schaltet den Wortschatz-Bonus ab | 8 |
| `learn_terms`, `learned` | Wortschatz aus Diktaten mitlernen; die gelernten Wörter | an, leer |
| `vocabulary`, `dictionary` | Meine Begriffe; Wörterbuch „falsch → richtig“ | leer |
| `base_dictionary` | mitgeliefertes medizinisches Wörterbuch und Lexikon anwenden | an |
| `speakers` | Sprecher trennen bei Aufnahme und Datei | aus |
| `spoken_punctuation` | „Punkt“, „Komma“, „neue Zeile“ als Zeichen schreiben | aus |
| `llm`, `llm_fix` | Sprachmodell-Server und Fachkorrektur | aus |
| `visite_prompt` | eigene Anweisung für „Visite & Übergabe“; leer = die mitgelieferte | leer |
| `training_keep` | vorgelesene Sätze als Ton aufheben | aus |
| `phone` | Handy als Mikrofon | aus |
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
| fünf eigene ärztliche Diktate (412 Wörter, ein Sprecher) | 8,3 % | Whisper Large v3 Turbo Deutsch mit Wortliste 14,1 %, VibeVoice 16,3 % |
| Corti Med-Dictate, neun echte Diktate, 33 Minuten | 15,4 % mit Kernliste; 11,1 % mit dem Wortschatz aus den eigenen Texten | 16,6 % ohne Wortschatz beim Dekodieren |
| dieselben mit Fachkorrektur durch ein Sprachmodell (älterer Stand, ohne Wortschatz beim Dekodieren) | 7,5 % und 13,7 % | – |

| Weitere Größen | Wert |
|---|---|
| Rechenzeit für 45 s Diktat (i7-13700KF, nur Prozessor) | 2,0 s mit Wortschatz, 1,4 s ohne |
| allererster Start mit Modell-Download (910 MB) | 61 s; jeder weitere Start 2 s |
| Sprechertrennung | 88,6 % richtig zugeordnete Sprechzeit bei Interviews, 75,4 % am Telefon |
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
- „Visite & Übergabe“ ist so gut wie das eingestellte Sprachmodell. Die Ausgaben sind ungeprüfte Entwürfe.
- Die Seite für das Handy als Mikrofon ist bisher nur mit simuliertem Mikrofon geprüft.

## 13. Lizenz

GPL-3.0-or-later. Sprachmodell primeline-Parakeet (CC BY 4.0), Stimmmodell WeSpeaker (CC BY 4.0), Silero VAD (MIT);
alle Bestandteile in `THIRD_PARTY.md`.
