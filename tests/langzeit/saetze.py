"""Erzeugt abwechslungsreiche Diktatsätze für den Langzeittest (fester Zufallsstart, also wiederholbar)."""
import random
import sys

rng = random.Random(2026)
SYMPTOM = ["Oberbauchschmerzen", "Luftnot bei Belastung", "Schwindel", "Brustschmerzen", "Fieber und Schüttelfrost",
           "Übelkeit und Erbrechen", "Kopfschmerzen", "Flankenschmerzen rechts", "Beinschwellung links", "Husten mit Auswurf",
           "Herzrasen", "Bauchkrämpfe", "Rückenschmerzen", "Müdigkeit und Gewichtsverlust", "Brennen beim Wasserlassen"]
ZEIT = ["Tagen", "Wochen", "Stunden"]
LABOR = [("Kreatinin", "Milligramm pro Deziliter"), ("Kalium", "Millimol pro Liter"), ("Hämoglobin", "Gramm pro Deziliter"),
         ("CRP", "Milligramm pro Liter"), ("Natrium", "Millimol pro Liter"), ("Laktat", "Millimol pro Liter"),
         ("Troponin", "Nanogramm pro Liter"), ("Leukozytenzahl", "pro Nanoliter"), ("Harnstoff", "Milligramm pro Deziliter"),
         ("Bilirubin", "Milligramm pro Deziliter")]
MEDIKAMENT = ["Ramipril", "Metoprolol", "Pantoprazol", "Amlodipin", "Torasemid", "Metformin", "Apixaban", "Simvastatin",
              "Ceftriaxon", "Piperacillin", "Prednisolon", "Bisoprolol", "Candesartan", "Furosemid", "Novaminsulfon"]
HAEUFIG = ["einmal täglich", "zweimal täglich", "dreimal täglich", "morgens", "abends", "bei Bedarf"]
BILD = ["Sonografie des Abdomens", "Röntgenaufnahme des Thorax", "Computertomografie", "Echokardiografie", "Kernspintomografie"]
BEFUND = ["eine geringe Menge freier Flüssigkeit", "ein kleiner Pleuraerguss rechts", "eine normale Pumpfunktion",
          "eine Wandverdickung der Gallenblase", "eine Stauung der Nierenbecken", "ein unauffälliger Befund",
          "eine Verschattung im linken Unterlappen", "eine vergrößerte Leber"]
AUSSCHLUSS = ["eine Perforation", "einen Abszess", "eine Lungenembolie", "eine Blutung", "einen Tumor", "einen Ileus"]
THEMA = ["den Eingriff", "die Risiken der Therapie", "die Notwendigkeit der Aufnahme", "die Kontrastmittelgabe", "den Befund"]
STATION = ["die Intensivstation", "die Überwachungsstation", "die Normalstation", "die Kardiologie", "die Nephrologie"]


def zahl(lo, hi, komma=False):
    return f"{rng.randint(lo, hi)},{rng.randint(1, 9)}" if komma else str(rng.randint(lo, hi))


def satz(i):
    lab, einheit = rng.choice(LABOR)
    muster = [
        lambda: f"Der {zahl(19, 94)}-jährige Patient berichtet über {rng.choice(SYMPTOM)} seit {zahl(2, 9)} {rng.choice(ZEIT)}.",
        lambda: f"Die {zahl(19, 94)}-jährige Patientin stellt sich mit {rng.choice(SYMPTOM)} vor, Beginn vor {zahl(2, 9)} {rng.choice(ZEIT)}.",
        lambda: f"Das {lab} liegt bei {zahl(1, 14, True)} {einheit}, der Vorwert betrug {zahl(1, 14, True)}.",
        lambda: f"Wir empfehlen {rng.choice(MEDIKAMENT)} {rng.choice([5, 10, 20, 40, 50, 100, 500])} Milligramm {rng.choice(HAEUFIG)} und eine Kontrolle in {zahl(2, 9)} Tagen.",
        lambda: f"In der {rng.choice(BILD)} zeigt sich {rng.choice(BEFUND)} ohne Hinweis auf {rng.choice(AUSSCHLUSS)}.",
        lambda: f"Der Patient wurde über {rng.choice(THEMA)} aufgeklärt und ist mit dem Vorgehen einverstanden.",
        lambda: f"Der Blutdruck beträgt {zahl(95, 180)} zu {zahl(55, 100)}, die Herzfrequenz {zahl(48, 130)} pro Minute, die Sättigung {zahl(88, 99)} Prozent.",
        lambda: f"Wir verlegen die Patientin auf {rng.choice(STATION)} und setzen {rng.choice(MEDIKAMENT)} vorerst ab.",
        lambda: f"Unter {rng.choice(MEDIKAMENT)} und {rng.choice(MEDIKAMENT)} besserten sich die Beschwerden innerhalb von {zahl(2, 9)} Tagen deutlich.",
        lambda: f"Bei weiter steigendem {lab} besprechen wir morgen in der Visite das weitere Vorgehen mit dem Oberarzt.",
    ]
    return f"Befund {i}. " + rng.choice(muster)()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 900
    sys.stdout.reconfigure(encoding="utf-8")
    for i in range(1, n + 1):
        print(satz(i))
