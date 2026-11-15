# Langzeittest: eine Stunde Diktat

Stand 15.11.2026, LocalScribe 0.4.0 (Sprechpausen über Silero VAD), Rechner: Intel i7-13700KF, nur CPU.

## Aufbau

- 370 verschiedene Diktatsätze (Anamnese, Laborwerte mit Kommazahlen, Medikamente mit Dosis,
  Bildgebung, Vitalwerte), jeder mit einem Zähler „Befund N.“ davor. Erzeugt von `saetze.py`.
- Vorgelesen von der deutschen Windows-Stimme, zu 60 Minuten zusammengesetzt mit zufälligen
  Pausen: 15 % der Sätze ohne jede Pause, 60 % mit 0,2 bis 0,7 s, 20 % mit 0,8 bis 2 s,
  5 % mit 3 bis 8 s, dazu einmal 45 s Stille. Leises Raumrauschen über allem.
- Bestfall zum Vergleich: jeder Satz einzeln erkannt. Mehr kann das Modell nicht liefern.
- Gezählt werden Inhaltswörter (ab vier Buchstaben) und Zahlen des vorgelesenen Textes, die im
  Ergebnis fehlen. „Milligramm“ wird zu „mg“, „Prozent“ zu „%“: Das zählt hier als fehlend,
  ist aber kein Verlust. Deshalb ist der Abstand zum Bestfall die Zahl, auf die es ankommt.

## Ergebnis

| Weg | fehlende Inhaltswörter von 3 371 | abweichend geschrieben | längste Lücke |
|---|---|---|---|
| Bestfall (Satz für Satz einzeln) | 49 | 408 | 5 Wörter |
| Datei transkribieren | 44 | 452 | 5 Wörter |
| Aufnahme (als Mikrofon-Blöcke eingespeist) | 43 | 458 | 5 Wörter |
| Nach Absturz aus der Sicherungsdatei (20 Minuten, 1 156 Wörter) | 13 (Bestfall 15) | – | – |

Die Verarbeitungskette verliert gegenüber dem Bestfall nichts. Die Lücken des Bestfalls sind
Maßeinheiten in Kurzschreibweise und Medikamentennamen, die die synthetische Stimme verschluckt.
„Abweichend geschrieben“ sind vor allem diese Medikamentennamen und Zahlen. Die Kette liegt hier
rund 45 Wörter (1,3 %) über dem Bestfall: An Schnittstellen mitten im Satz schreibt das Modell
gelegentlich Wörter zusammen oder eine Zahl als Wort aus.

Dauer: 60 Minuten Ton in rund 6 Minuten, 1 438 Stücke, längstes 11 s; 6,2 Minuten Stille
übersprungen. Die Sicherungsdatei war nach der Aufnahme gelöscht.

Live (`tests/test_live.py`, Ton im Tempo eines echten Mikrofons, 75 s): erster Text nach 5,2 s,
27 Zwischenstände, Rückstand hinter dem Gesprochenen 0,3 s, nach dem Stopp sofort fertig.

## Vorher

Mit der ersten Fassung (Stücke von 10 bis 18 s, geschnitten an der leisesten Stelle) fehlten
gegenüber dem Bestfall 454 von 5 803 Wörtern, weitere 293 wichen ab – darunter ganze Sätze.
Ursache: Das Modell lässt Satzteile weg, sobald ein Stück eine Sprechpause enthält.

| Schnitt (erste 20 Minuten, 1 975 Wörter) | fehlend gegenüber Bestfall |
|---|---|
| 10 bis 18 s, leiseste Stelle | 148 |
| 5 bis 10 s, leiseste Stelle | 80 |
| an Pausen, zu Stücken bis 12 s gebündelt | 106 |
| an jeder Pause ab 0,6 s | 39 |
| an jeder Pause ab 0,3 s (Lautstärke, 0.3.0) | 10 |

## Was der Test nicht zeigt

- Echte Stimmen, Dialekt, Nuscheln, Fachvokabular jenseits der Vorlage.
- Laute Umgebung (Notaufnahme, Monitoralarme, Gespräche im Hintergrund).
- Eine Stunde am echten Mikrofon: Die Blöcke wurden schneller als in Echtzeit eingespeist.
  Treiberaussetzer, Energiesparen und abgezogene Mikrofone sind damit nicht erprobt.

## Wiederholen

    python tests\langzeit\saetze.py 900 > <Ordner>\saetze.txt      (als UTF-8 ohne BOM speichern)
    powershell -File tests\langzeit\tts.ps1 -Dir <Ordner>
    python tests\langzeit\stunde.py <Ordner> 60
    python tests\langzeit\vergleich_schnitt.py <Ordner> 19.9 127
