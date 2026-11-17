"""Was verlässt den Rechner? Erfundene klinische Sätze mit persönlichen Angaben durch die Schutzschicht schicken und
zählen, welche Angaben in der geschützten Fassung noch lesbar sind. Einmal nur mit Regeln, einmal mit Erkennungsmodell.

    python werkzeug/messen/schutz.py
"""
import pathlib, sys, types
root = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root)); sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))
from diktat import schutz
CASES = [   # (Text, [Angaben, die nicht lesbar bleiben dürfen])
 ("Herr Müller, geboren am 12.03.1957, stellt sich mit Thoraxschmerzen vor.", ["Müller", "12.03.1957"]),
 ("Frau Aylin Demirci, geb. 4. Mai 1982, wohnhaft Bismarckstraße 12, 51373 Leverkusen.", ["Aylin", "Demirci", "4. Mai 1982", "Bismarckstraße 12", "51373", "Leverkusen"]),
 ("Patientin Kowalczyk berichtet über Luftnot seit drei Tagen.", ["Kowalczyk"]),
 ("Özdemir kam heute Nacht mit dem Rettungsdienst.", ["Özdemir"]),
 ("Rücksprache mit Dr. Hoffmann aus der Kardiologie, Telefon 0214 131234.", ["Hoffmann", "0214 131234"]),
 ("Die Tochter, Sabine Krause, ist erreichbar unter 0171 2345678 oder sabine.krause@example.org.", ["Sabine", "Krause", "0171 2345678", "sabine.krause@example.org"]),
 ("Fallnummer 20261117045, Versichertennummer A123456789.", ["20261117045", "A123456789"]),
 ("Hausarzt ist Dr. med. Petra Lindqvist in Opladen.", ["Lindqvist", "Opladen"]),
 ("Mehmet wurde vom Pflegeheim Haus Rheinblick zugewiesen.", ["Mehmet", "Rheinblick"]),
 ("Der Ehemann Jürgen Baumgartner gibt an, sie nehme Marcumar.", ["Jürgen", "Baumgartner"]),
 ("Verlegung ins Klinikum Leverkusen am 17.11.2026 geplant.", ["17.11.2026", "Klinikum Leverkusen"]),
 ("Thomas Nguyen, 34 Jahre, Sturz vom Fahrrad in Köln-Mülheim.", ["Thomas", "Nguyen", "Köln-Mülheim"]),
 ("Bekannt bei Kollegin Yıldırım aus der Neurologie.", ["Yıldırım"]),
 ("IBAN DE89 3704 0044 0532 0130 00 für die Rechnung.", ["DE89 3704 0044 0532 0130 00"]),
 ("Betreuerin ist Frau von Hohenstein, Anschrift Am Markt 3, 51379 Leverkusen.", ["Hohenstein", "Am Markt 3", "51379"]),
 ("Bei Morbus Parkinson und Morbus Crohn keine Änderung, Hodgkin-Lymphom in Remission.", []),
 ("Patient 67 Jahre, Kreatinin 1,4 mg/dl, Blutdruck 140/90, Troponin 52.", []),
]
keep = ["Parkinson", "Crohn", "Hodgkin", "Kreatinin", "1,4", "140/90", "67 Jahre", "Thoraxschmerzen", "Marcumar"]
for label, model in (("nur Regeln", False), ("mit Erkennungsmodell", True)):
    if model and not schutz.ready():
        print("mit Erkennungsmodell: Modell liegt hier nicht"); continue
    total = leaked = 0; lost = []; rows = []
    for text, secrets in CASES:
        hidden = schutz.Mask(model=model).hide(text)
        bad = [s for s in secrets if s in hidden]
        total += len(secrets); leaked += len(bad); rows.append((hidden, bad))
        lost += [k for k in keep if k in text and k not in hidden]
    print(f"\n== {label}: {total - leaked} von {total} Angaben ersetzt, {leaked} lesbar geblieben; medizinische Angaben fälschlich ersetzt: {lost}")
    for hidden, bad in rows:
        print(("  LESBAR " + str(bad) if bad else "  ok    "), "|", hidden)
