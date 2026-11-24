"""Einstellungen und Daten liegen unter %LOCALAPPDATA%\\LocalScribe, also je Windows-Konto.

Ausnahme: Liegt neben LocalScribe.exe ein Ordner „daten“, liegt alles dort. So hat jede Person, die das Programm in
ihrem eigenen Ordner hält, ihre eigenen Einstellungen, ihren Verlauf und ihren gelernten Wortschatz, auch auf einem
Windows-Konto, das sich mehrere teilen.

Bewusst nicht unter %APPDATA% (Roaming): Dort würden Verlauf und Aufnahmen in Firmennetzen
mit dem Benutzerprofil auf einen Server wandern.
"""
import copy
import hashlib
import json
import logging
import os
import shutil
import time
from pathlib import Path

APP = "LocalScribe"
PORTABLE = "daten"       # Ordner neben LocalScribe.exe: gibt es ihn, liegen dort alle eigenen Daten

def _dir() -> Path:
    """Der erste Ordner, in den sich schreiben lässt: „daten“ neben dem Programm, wenn es ihn gibt, sonst das
    eigene Windows-Konto. Von sich aus legt die App nie Daten in den Programmordner: Der liegt oft auf einem
    Netzlaufwerk, das sich mehrere teilen, und dort hätten Verlauf und Protokoll ungefragt nichts zu suchen."""
    import sys
    import tempfile
    from . import ort
    own = ort.root() / PORTABLE if ort.root() else None
    places = [own] if own is not None and own.is_dir() else []
    places += [Path(base) / APP for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA"),
                                             str(Path.home()), tempfile.gettempdir()) if base]
    for path in places:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".schreibtest"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            return path
        except OSError:
            continue
    return Path(tempfile.gettempdir()) / APP


DIR = _dir()
RECORDINGS = "aufnahmen"
FILE = DIR / "config.json"
LOG = DIR / "diktat.log"
DB = DIR / "verlauf.sqlite"
ICON = DIR / "diktat.ico"

GERMAN = ("de",)              # Modelle, bei denen die deutsche Nachbearbeitung gilt

# Sprachmodelle zur Auswahl. Die Fassung ist festgeschrieben: Es wird nie stillschweigend eine andere geladen.
MODELS = {
    "de": {"label": "Deutsch (Parakeet, auf Deutsch nachtrainiert)",
           "repo": "OpenVoiceOS/primeline-parakeet-onnx", "revision": "411093fba73540a11c451841a8e7922c13b0fb00",
           # Dieselben Gewichte, schonender auf 8 Bit gekürzt (werkzeug/modell/kuerzen.py): so genau wie die
           # vollen 2,5 GB, so schnell wie bisher. Dateiname: [Größe, SHA-256].
           "release": {"name": "primeline-parakeet-kanal8-1",
                       "url": "https://github.com/chunkyfire/LocalScribe/releases/download/modell-primeline-1/",
                       "files": {
                           "config.json": [121, "db59e29a3c1fde6a081bf04965e72bba26cd65be1aee65b064360df8aef468e5"],
                           "vocab.txt": [93939, "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d"],
                           "decoder_joint-model.int8.onnx": [72520894, "e713d02c73176e629de49948f755a8e855b4850d4341124088d69adcfbc833c1"],
                           "encoder-model.int8.onnx": [881780860, "d3183080403232b0db42ba461ec4dc917996811fe689de42492747dc723a10d2"]}}},
    "multi": {"label": "Mehrsprachig (Parakeet v3, 25 europäische Sprachen)",
              "repo": "istupakov/parakeet-tdt-0.6b-v3-onnx", "revision": "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce"},
}

SUMMARY = ("Fasse den Text zusammen und erfinde nichts; Zahlen, Namen und Zeitangaben bleiben, wie sie genannt wurden. "
           "Geht es um eine Patientin oder einen Patienten (Anamnese, Visite, Fallbesprechung), schreibe eine knappe "
           "klinische Dokumentation mit den Abschnitten Anlass, Anamnese, Befunde, Beurteilung und Vorgehen; Abschnitte, "
           "zu denen nichts gesagt wurde, weglassen. Sonst fünf bis acht Sätze, das Wichtigste zuerst.")
MEETING = ("Schreibe das Protokoll einer Besprechung mit den Abschnitten Teilnehmende, Themen, Entscheidungen und Aufgaben "
           "(wer, was, bis wann). Knapp und sachlich, in ganzen Sätzen. Übernimm nur, was gesagt wurde; was nicht genannt "
           "wurde, weglassen.")
OLD_V4 = {"Zusammenfassung": "Fasse den Text in fünf bis acht Sätzen zusammen, das Wichtigste zuerst. Erfinde nichts.",
          "Meeting-Protokoll": "Schreibe ein Protokoll mit den Abschnitten Teilnehmende, Besprochenes, Entscheidungen und "
                               "Aufgaben (wer, was, bis wann). Übernimm nur, was gesagt wurde; was nicht genannt wurde, "
                               "weglassen."}
OLD_ROW = ("Glätten", "Zusammenfassung", "Meeting-Protokoll")         # bis 1.7.0 ab Werk auf der Seite Aufnahme
ON_RECORD = ("Visite", "Meeting-Protokoll", "Arztbrief", "Pflegebericht")   # ab Werk als Knöpfe auf der Seite Aufnahme, in dieser Reihenfolge
UNCLEAR = ("Wörter, die nach einem Hörfehler aussehen (Arzneimittel, Zahlen, Einheiten), nicht stillschweigend berichtigen: "
           "das Gehörte stehen lassen und so kennzeichnen: [unklar: …].")
AS_SAID = ("Übernimm nur, was gesagt wurde, und erfinde nichts: keine Einheit, keine Dosis, keine Häufigkeit und kein Datum "
           "ergänzen, auch wenn sie üblich wären. Eine Zahl ohne Einheit bleibt ohne Einheit („Kreatinin 1,9“ bleibt "
           "„Kreatinin 1,9“, „Blutdruck 128 zu 76“ wird „RR 128/76“). Lass nichts weg, was zur Sache gehört: Jede genannte "
           "Beobachtung, jeder Wert, jede Maßnahme und jede Uhrzeit kommt vor.")
# Für die Akte eines Krankenhauses: Der Eintrag muss vor dem Medizinischen Dienst und vor Gericht bestehen. Das Modell
# ergänzt dafür nichts; es lässt aber auch nichts liegen und sagt am Ende, was im Diktat gefehlt hat.
ALWAYS = ("Schreibe immer einen verwendbaren Eintrag, auch wenn der Text kurz ist oder nur Routine nennt. Kommentiere das "
          "Diktat nicht, belehre nicht und stelle keine Rückfrage. Ausdrücklich genannte Normalbefunde und Verneinungen "
          "(„keine Schmerzen“, „kein Sturz“, „keine neuen Vorkommnisse“) gehören in den Eintrag: Sie belegen, dass danach "
          "gesehen wurde. Wer etwas gesagt, beobachtet, angeordnet oder getan hat, bleibt, wie es im Text steht; mache "
          "aus einer Feststellung der sprechenden Person keine Aussage der Patientin oder des Patienten.")
EXACT = ("Genau und vollständig übernehmen, soweit genannt: Uhrzeiten und Daten; Namen und Funktion der Beteiligten (wer "
         "hat angeordnet, informiert, aufgeklärt, durchgeführt); Seite und Lokalisation; Größe, Grad oder Stadium; Dosis, "
         "Dauer und Häufigkeit; die Zahl der beteiligten Personen.")
MISSING = ("Fehlen im Text Angaben aus der folgenden Liste, die zu diesem Eintrag gehören, ende mit einer eigenen letzten "
           "Zeile, die mit „Nicht diktiert:“ beginnt und die fehlenden Angaben nennt, höchstens fünf, durch Komma "
           "getrennt, ohne Erklärung und ohne medizinischen Vorschlag. Fehlt nichts, entfällt die Zeile. Liste: ")
NOTES = ("Nicht diktiert:", "Zusätzlich dokumentieren:")    # solche Schlusszeilen sind Hinweise, kein Teil des Eintrags
SOAP = ("Schreibe aus dem Text einen ärztlichen Visiten- und Verlaufseintrag nach dem SOAP-Schema für die Akte eines "
        "Krankenhauses. " + AS_SAID + " " + ALWAYS + " " + EXACT + " Abschnitte, zu denen nichts gesagt wurde, weglassen.\n"
        "Ist genannt, wer an der Visite teilnahm (Oberärztin, Chefarzt, Pflege), beginne mit der Zeile „Visite mit …“.\n"
        "S – Subjektiv: Befinden und Beschwerden, wie die Patientin oder der Patient sie schildert; Angaben von "
        "Angehörigen und Pflege.\n"
        "O – Objektiv: Untersuchungsbefund, Vitalwerte, Labor mit Verlauf, Bildgebung, Bilanz, Zugänge und Drainagen; "
        "auch genannte Normalbefunde.\n"
        "A – Beurteilung: die Einschätzung, wie sie gesagt wurde (Verlauf, Diagnosen, offene Fragen). Eine Nebendiagnose "
        "oder Komplikation steht zusammen mit dem, was ihretwegen getan wird, wenn beides genannt ist. Hierher gehört "
        "auch der genannte Grund, warum die Behandlung im Krankenhaus weiter nötig ist. Keine eigene Beurteilung "
        "hinzufügen.\n"
        "P – Plan: Anordnungen und nächste Schritte als kurze Liste: Diagnostik, Therapie und Medikation (neu, geändert, "
        "abgesetzt), Konsile, Entlassplanung, wer was bis wann. Ebenso Aufklärung, Einwilligung oder Ablehnung und "
        "Gespräche mit Angehörigen oder Betreuung: wer, worüber, mit welchem Ergebnis.\n"
        "Form: Jeder Abschnitt beginnt mit seinem Buchstaben und Doppelpunkt („S:“, „O:“, „A:“, „P:“) in einer eigenen "
        "Zeile, darunter knappe Stichsätze, je Zeile ein Gedanke mit Spiegelstrich; jede Angabe nur einmal. " + UNCLEAR + "\n"
        + MISSING + "Befinden, Untersuchungsbefund, Beurteilung, weiteres Vorgehen, Grund für die weitere Behandlung im "
        "Krankenhaus (entfällt, wenn die Entlassung genannt ist).")
NURSING = ("Schreibe aus dem Text einen Eintrag für den Pflegebericht eines Krankenhauses. " + AS_SAID + " " + ALWAYS + " "
           + EXACT + " Schlage keine Pflegediagnosen, Ziele oder Maßnahmen vor: Die Einschätzung bleibt bei der "
           "Pflegefachperson.\n"
           "Sachlich und ohne Wertung: was zu sehen, zu hören und zu messen war. Was im Text als Aussage der Patientin "
           "oder des Patienten steht, wörtlich in Anführungszeichen. Steht im Text eine Wertung über das Verhalten (etwa "
           "„aggressiv“, „unkooperativ“), übernimm sie nicht als Tatsache: Schreibe das geschilderte Verhalten und an "
           "die Stelle der Wertung [Wertung, bitte Verhalten beschreiben]. Eine fachliche Einschätzung der sprechenden "
           "Person kennzeichne mit „Einschätzung:“.\n"
           "Was die Pflege besonders gebunden hat (etwa Sitzwache, Isolation, Lagern zu zweit, Begleitung zu einer "
           "Untersuchung, Hilfe beim Essen), steht mit Dauer, Häufigkeit und Zahl der Personen im Eintrag, soweit genannt.\n"
           "Form: Ein Ereignis ist, was vom gewohnten Verlauf abweicht und eine Reaktion verlangt hat (Sturz, geklagte "
           "Schmerzen, neue Wunde, Unruhe, Bedarfsmedikation, Verschlechterung, Zwischenfall). Ein unauffälliger Wert, "
           "ein trockener Verband oder eine übliche Mobilisation sind kein Ereignis. Ohne Ereignis: ein bis vier kurze "
           "Sätze ohne die Überschriften Beobachtung, Maßnahme, Wirkung und Weitergabe. Mit Ereignis gliedere so; je "
           "Ereignis jede Zeile höchstens einmal, Zeilen ohne Inhalt weglassen:\n"
           "Beobachtung: …\nMaßnahme: … (was, durch wen)\nWirkung: … (Reaktion, Ergebnis)\n"
           "Weitergabe: … (wer wurde wann informiert, was hat die Ärztin oder der Arzt angeordnet)\n"
           "Danach, nur wenn genannt: „Werte:“ (Vitalzeichen, Schmerz, Blutzucker, Ein- und Ausfuhr) und „Offen für die "
           "nächste Schicht:“. Dorthin gehört auch, worum die sprechende Person Kolleginnen und Kollegen bittet; das ist "
           "keine Anordnung.\n"
           "Kurze ganze Sätze. " + UNCLEAR + "\n"
           "Geht es um einen Sturz, eine Wunde oder einen Dekubitus, eine freiheitsentziehende Maßnahme (Fixierung, "
           "Bettgitter; eine Sitzwache ist keine) oder einen Medikationsfehler, setze danach die Zeile „Zusätzlich dokumentieren:“ mit dem passenden Blatt "
           "(Sturzprotokoll, Wunddokumentation, Fixierungsprotokoll, Fehlermeldung).\n"
           + MISSING + "bei Sturz: Uhrzeit, Hergang oder Auffindesituation, Verletzungszeichen, Vitalzeichen, ärztliche "
           "Information; bei Wunde oder Dekubitus: Lokalisation, Größe, Aussehen oder Kategorie, Versorgung; bei Schmerz: "
           "Lokalisation, Stärke, Maßnahme, Wirkung; bei Bedarfsmedikation: Uhrzeit, Anlass, Wirkung; bei "
           "freiheitsentziehender Maßnahme: Art, Anordnung, Beginn und Ende; bei ärztlicher Information: wer, wann, "
           "Anordnung. Ohne Ereignis entfällt die Zeile immer.")
LETTER = ("Schreibe aus dem Text den Entwurf eines Arztbriefs eines Krankenhauses (Entlassbrief oder Brief der "
          "Notaufnahme), ohne Briefkopf, Anrede und Gruß. " + AS_SAID + " " + ALWAYS + " " + EXACT + " Abschnitte, zu "
          "denen nichts gesagt wurde, weglassen.\n"
          "Diagnosen: je Zeile eine. Zuerst, weswegen aufgenommen oder behandelt wurde; danach jede weitere Erkrankung, "
          "Verletzung oder Komplikation, die der Text beim Namen nennt, auch Vorerkrankungen und was erst im Verlauf "
          "auftrat. Aus Messwerten keine Diagnose machen, keine Schlüsselnummern ergänzen.\n"
          "Prozeduren: Eingriffe und Interventionen mit Datum, wenn genannt.\n"
          "Anamnese: Anlass der Aufnahme oder Vorstellung, Beschwerden mit Beginn und Verlauf, Vorerkrankungen, "
          "Vormedikation, Allergien.\n"
          "Befund: Untersuchungsbefund und Vitalwerte, auch genannte Normalbefunde.\n"
          "Diagnostik: Labor, EKG, Bildgebung und Konsile mit Ergebnis.\n"
          "Verlauf: was getan wurde, warum, und wie es gewirkt hat. Eine Nebendiagnose oder Komplikation steht "
          "zusammen mit dem, was ihretwegen getan wurde, wenn beides genannt ist.\n"
          "Medikation bei Entlassung: Liste mit Dosis und Schema wie genannt; neu, geändert oder abgesetzt so "
          "kennzeichnen, mit Grund, wenn genannt.\n"
          "Procedere: Empfehlungen, Kontrollen, Termine, ausstehende Befunde, Arbeitsunfähigkeit.\n"
          "Aufklärung: worüber aufgeklärt wurde (Warnzeichen, Wiedervorstellung), Einwilligung, Ablehnung oder Entlassung "
          "gegen ärztlichen Rat, wer dabei war; nah am Wortlaut.\n"
          "Form: jede Überschrift mit Doppelpunkt in einer eigenen Zeile; im Verlauf ganze Sätze, sonst knapp. Jede "
          "Angabe steht nur einmal, im passenden Abschnitt. " + UNCLEAR + "\n"
          + MISSING + "Diagnose, Anamnese, Befund, Verlauf oder Therapie, weiteres Vorgehen, bei Entlassung nach Hause "
          "die Aufklärung über Warnzeichen und Wiedervorstellung.")
SMOOTH = ("Entferne Füllwörter, Versprecher und Wiederholungen. Korrigiere Grammatik und Zeichensetzung. Ändere weder "
          "Inhalt noch Tonfall und füge nichts hinzu; Zahlen, Einheiten, Arzneimittel und Namen bleiben unverändert.")
POINTS = ("Fasse den Inhalt in knappen Stichpunkten zusammen, ein Gedanke pro Zeile. Erfinde nichts; Zahlen, "
          "Arzneimittel und Namen bleiben unverändert.")

# Seite Aufnahme, Zeichen neben dem eigenen Prompt: aus einer kurzen Eingabe einen ausformulierten Prompt machen
SPARK = ("Du schreibst Prompts für ein Sprachmodell, das ein Transkript bearbeitet. Mache aus der kurzen Eingabe einen "
         "ausformulierten Prompt in drei bis fünf Sätzen: was entstehen soll, für wen, in welcher Form und Länge und "
         "worauf der Schwerpunkt liegt. Bleib bei dem, was die Eingabe verlangt: Die Form (etwa Mail, Liste, "
         "Zusammenfassung) nicht austauschen und den Umfang nicht ausweiten; steht dort „kurz“, bleibt es kurz. "
         "Richte dich nach der Art des Transkripts (Diktat, Gespräch, Besprechung), übernimm aber keine Inhalte "
         "daraus. Platzhalter in eckigen Klammern wie [NAME_1] stehen für geschützte Angaben; lass sie weg. "
         "Der Prompt endet mit diesen zwei Sätzen: Übernimm nur, was gesagt wurde, und erfinde nichts. Ergänze keine "
         "Einheit, keine Dosis, keine Bewertung und kein Datum. "
         "Gib nur den Prompt zurück, auf Deutsch, ohne Einleitung und ohne Anführungszeichen.")

# Einstellungen, Reiter Prompts, Zeichen neben der Anweisung: Stichworte ausformulieren oder einen Prompt verbessern.
POLISH = ("Du schreibst Prompts für ein Sprachmodell, das ein Transkript bearbeitet (Diktat, Gespräch, Besprechung). Du "
          "bekommst den Namen eines Prompts und eine Eingabe: Stichworte oder einen schon geschriebenen Prompt. Gib den "
          "fertigen Prompt zurück. Aus Stichworten machst du drei bis sechs klare Sätze: was entstehen soll, für wen, in "
          "welcher Form, Gliederung und Länge, und was wegbleibt. Einen schon ausführlichen Prompt verbesserst du "
          "behutsam: Inhalt, Gliederung und Länge bleiben, Unklares wird eindeutig, Doppeltes fällt weg, Widersprüche "
          "löst du im Sinn der Eingabe auf; nichts Neues kommt dazu, und Regeln der Eingabe gehen nicht verloren. Bleib "
          "bei dem, was die Eingabe verlangt: die Form (etwa Mail, Liste, Zusammenfassung) nicht austauschen, den "
          "Umfang nicht ausweiten. Sprich das Sprachmodell mit „du“ an. Fehlt der Gedanke in der Eingabe, endet der "
          "Prompt mit diesen zwei Sätzen: Übernimm nur, was gesagt wurde, und erfinde nichts. Ergänze keine Einheit, "
          "keine Dosis, keine Bewertung und kein Datum. "
          "Gib nur den Prompt zurück, auf Deutsch, ohne Einleitung, ohne Erklärung und ohne Anführungszeichen.")

DEFAULTS = {
    # Tasten gedrückt halten = aufnehmen, loslassen = einfügen
    "hotkey_hold": ["ctrl", "win"],
    # während des Haltens zusätzlich drücken = Freihand (weiterreden ohne Halten);
    # beenden mit erneutem Druck der Halte-Tasten, abbrechen mit Esc
    "hotkey_lock": "space",
    # letzten Text noch einmal einfügen (falls das falsche Fenster aktiv war)
    "hotkey_paste_last": ["shift", "f7"],
    "hotkey_target": ["shift", "f9"],       # Zielfenster merken oder lösen: Diktate landen dort, egal was vorn ist
    "hotkey_next_field": ["shift", "f8"],   # nächste Sprungmarke [ ] im zuletzt eingefügten Text
    # Sprachmodell: "de" oder "multi", siehe MODELS
    "model_choice": "de",
    # mitgeliefertes medizinisches Wörterbuch anwenden (nur mit dem deutschen Modell)
    "base_dictionary": True,
    "llm_fix": False,             # Fachkorrektur: Hörfehler bei Fachbegriffen vom Sprachmodell vorschlagen lassen
    "vocabulary": [],             # eigene Begriffe: nur die richtige Schreibweise, erkannt wird am Klang
    "beam": 8,                    # Dekodieren mit so vielen Kandidaten und Wortschatz-Bonus (beam.py); 0 = einfach
    "learn_terms": True,          # Fachwörter aus den eigenen Diktaten in den Wortschatz aufnehmen (nur Lexikonwörter)
    "learned": [],                # gelernte Fachwörter (aus Diktaten und eingelesenen Texten)
    "mic_warm": False,            # Mikrofon dauerhaft offen halten: kein Startverzug, erste Silbe bleibt
    "speakers": True,             # Sprecher trennen bei Aufnahme und Datei (bei nur einer Stimme bleibt der Text, wie er ist)
    "update_check": False,        # einmal am Tag still bei GitHub nach einer neueren Fassung fragen; ab Werk nur auf Klick
    "profile_name": "",           # gewähltes Profil am Programmordner (profile\\<Name>); leer = die Daten dieses Rechners
    "training_keep": True,        # Stimmtraining: vorgelesene (erfundene) Sätze als Ton aufheben, für ein Nachtraining
    "field": "",                  # Fachrichtung für die Sätze im Stimmtraining; leer = Grundstock
    "training_scores": [],        # Messungen mit Prüfsätzen: Zeitpunkt, Fachrichtung, Wortfehler, Trainingsminuten
    "live_preview": True,         # Aufnahme: laufende Äußerung schon beim Sprechen vorläufig anzeigen
    "model_dir": "",              # eigener Ordner mit Sprachmodellen (z. B. ein gemeinsames Netzlaufwerk); leer = keiner
    "handover_frame": "zna",      # Übergabe: zuletzt gewählter Bereich (zna, station, its); steht beim nächsten Mal bereit
    "menu_hidden": [],            # abgewählt: die Menüpunkte "Verlauf" und "Wortschatz", die Auswahl "Übergabe" auf der Seite Aufnahme
    "handover_ack": False,        # der einmalige Hinweis vor der ersten Übergabe (experimentell, kein Medizinprodukt) ist gelesen
    "visite_prompt": "",          # Visite & Übergabe: eigene Anweisung an das Sprachmodell; leer = die mitgelieferte
    "visite_model": "",           # Modell für den Arztbrief; leer = visite.WRITER bei OpenRouter, sonst das LLM-Modell
    "visite_jev": "",             # Jev-Modell für die Ersteinschätzung; leer = ~typesafe/jev-latest
    "seen_version": "",           # zuletzt gesehene Fassung: Nach einem Update zeigt das Fenster einmal, was neu ist
    "visite_rules": "",           # Hausregeln (Schockraum, Labor, Zuständigkeiten), die Jev mitbekommt; leer = keine
    "training_done": [],          # Stimmtraining: schon gelesene Sätze
    "phone": {"enabled": False, "port": 8765, "token": ""},   # Handy als Mikrofon (Webseite im eigenen Netz)
    "config_version": 10,
    "quantization": "int8",
    "provider": "CPUExecutionProvider",
    "threads": 0,
    "microphone": None,
    "sounds": True,
    "restore_clipboard": True,
    "trailing_space": True,
    "spoken_punctuation": False,  # „Punkt“, „Komma“, „Doppelpunkt“, „neue Zeile“ als Satzzeichen schreiben
    "min_seconds": 0.3,
    # Verlauf führen? Auf gemeinsam genutzten Windows-Konten ausschalten.
    "history_enabled": True,
    # Verlauf nach so vielen Tagen löschen (0 = nie). Er soll nur einen Text retten, der im
    # falschen Fenster gelandet ist; dafür reicht eine Woche.
    "history_days": 7,
    # gesprochene Befehle -> Text
    "commands": {"neue Zeile": "\n", "neuer Absatz": "\n\n"},
    # Wörterbuch: falsch erkannt -> richtig (Groß-/Kleinschreibung egal)
    "dictionary": {},
    # Textbausteine: gesprochenes Stichwort -> Text
    "snippets": {},
    # KI-Nachbearbeitung über eine OpenAI-kompatible Schnittstelle
    # (Ollama, LM Studio, vLLM oder ein Anbieter eigener Wahl).
    # Der API-Schlüssel liegt nicht hier, sondern in der Windows-Anmeldeinformationsverwaltung.
    "llm": {
        "enabled": False,
        "base_url": "http://localhost:11434/v1",
        "model": "",
        "temperature": 0.2,
        "timeout": 30,
        # Name eines Prompts, der auf jedes normale Diktat angewendet wird ("" = keiner)
        "auto_prompt": "",
        "profile": "",            # Name des gespeicherten Anbieters, zu dem der Schlüssel gehört ("" = alter Einzeleintrag)
        "protect": True,          # Namen, Daten, Nummern vor dem Versand an fremde Server durch Platzhalter ersetzen
    },
    "corrections": [],            # eigene Berichtigungen [erkannt, gemeint], die nur der Zusammenhang klärt (Kabel -> Cave)
    "llm_profiles": [],           # gespeicherte Anbieter: [{"name", "base_url", "model"}], Schlüssel im Schlüsselspeicher
    "llm_models": {},             # eigene Modellnamen je Server (über „+“ in den Einstellungen): {"api.noirdoc.de": [...]}
    # Jeder Prompt kann eine eigene Halte-Taste bekommen: halten, sprechen, loslassen.
    "prompts": [
        {"name": "Glätten", "hotkey": ["f8"],
         "text": SMOOTH},
        {"name": "E-Mail", "hotkey": [],
         "text": "Formuliere daraus eine kurze, freundliche E-Mail mit Anrede und Gruß. "
                 "Erfinde keine Inhalte."},
        {"name": "Stichpunkte", "hotkey": [],
         "text": POINTS},
    ] + [dict(p) for p in (
        {"name": "Arztbrief", "hotkey": [],
         "text": LETTER},
        {"name": "Zusammenfassung", "hotkey": [],
         "text": SUMMARY},
        {"name": "Meeting-Protokoll", "hotkey": [],
         "text": MEETING},
        {"name": "Visite", "hotkey": [],
         "text": SOAP},
        {"name": "Pflegebericht", "hotkey": [],
         "text": NURSING},
    )],
}
for _p in DEFAULTS["prompts"]:
    _p["record"] = _p["name"] in ON_RECORD
ADDED_V4 = ("Arztbrief", "Zusammenfassung", "Meeting-Protokoll")     # kamen mit 1.3.0 dazu
ADDED_V8 = ("Visite", "Pflegebericht")                               # kamen mit 1.7.1 dazu


def _prompts_v8(prompts) -> list:
    """1.7.1: Visite (SOAP) und Pflegebericht kommen dazu. Wer die Auswahl für die Seite Aufnahme nie geändert hat,
    sieht dort jetzt Visite, Meeting-Protokoll, Arztbrief und Pflegebericht; wer sie geändert hat, behält seine und
    bekommt die beiden neuen dazu. Gelöscht wird nichts: Glätten und Zusammenfassung bleiben unter Einstellungen."""
    prompts = [dict(p) for p in prompts or [] if isinstance(p, dict)]
    names = {p.get("name") for p in prompts}
    shown = {p.get("name") for p in prompts if p.get("record", p.get("name") in OLD_ROW)}
    prompts += [copy.deepcopy(p) for p in DEFAULTS["prompts"] if p["name"] in ADDED_V8 and p["name"] not in names]
    if shown == set(OLD_ROW) & names:
        for p in prompts:
            p["record"] = p.get("name") in ON_RECORD
    return prompts


# 2.1.0: Visite, Arztbrief und Pflegebericht sind für die Akte eines Krankenhauses neu geschrieben, drei weitere Texte
# geschärft. Wer den Text ab Werk nie geändert hat (Prüfsumme des alten Textes), bekommt den neuen; eigene bleiben.
OLD_V9 = {"Glätten": "e7070d6fb02cf9faa894e390568007094a6d6cb8ffb68db2f987ffec59fd3df3",
          "Stichpunkte": "da51f3af7452b5c9615c4d0eeb6764ebada5b400b454b379e0fc40275dcb0194",
          "Arztbrief": "a10a2e14ddd0b8e0a5aa08c178df6c2ed3560695cd2f057a3054beba3a0059bb",
          "Zusammenfassung": "fb32d50baa6f4e10a81a4c3d7e477f1749c424f24181cf9f24305f177b24f3ea",
          "Visite": "23b8ceeeb4eafcd46c8b08508c09f4fe6b6e6950dc338ebd823eb088be66a72d",
          "Pflegebericht": "6cf43e3b371c6dda0bab5d6c9a6540245088f860f904a65092d05f76fc6a8fa0"}


def _prompts_v9(prompts) -> list:
    new = {p["name"]: p["text"] for p in DEFAULTS["prompts"]}
    prompts = [dict(p) for p in prompts or [] if isinstance(p, dict)]
    for p in prompts:
        old = OLD_V9.get(p.get("name"))
        if old and hashlib.sha256(str(p.get("text") or "").encode("utf-8")).hexdigest() == old:
            p["text"] = new[p["name"]]
    return prompts


def _prompts_up(prompts, version: int) -> list:
    """Gespeicherte Prompts einer älteren Fassung auf den heutigen Stand bringen (config.json, Profil, Sicherung)."""
    if version < 8:
        prompts = _prompts_v8(prompts)
    if version < 9:
        prompts = _prompts_v9(prompts)
    return prompts


def migrate() -> None:
    """Daten früherer Fassungen übernehmen (%APPDATA%\\LocalScribe, davor %APPDATA%\\Diktat)."""
    if FILE.exists() or not os.environ.get("APPDATA"):
        return
    for old in (Path(os.environ["APPDATA"]) / APP, Path(os.environ["APPDATA"]) / "Diktat"):
        if not old.is_dir() or old == DIR:
            continue
        try:
            DIR.mkdir(parents=True, exist_ok=True)
            for item in old.iterdir():
                if not (DIR / item.name).exists():
                    shutil.move(str(item), str(DIR / item.name))
            shutil.rmtree(old, ignore_errors=True)
            return
        except OSError:
            logging.exception("Alter Datenordner nicht übernehmbar")


def leftover_recordings() -> list:
    """Sicherungsdateien von Aufnahmen, die nicht zu Ende transkribiert wurden."""
    folder = DIR / RECORDINGS
    return sorted(folder.glob("*.wav")) if folder.is_dir() else []


def purge_recordings(days) -> int:
    """Liegengebliebene Tonaufnahmen nach der Aufbewahrungsfrist löschen (ohne Frist: nach 30 Tagen)."""
    limit, n = time.time() - (days or 30) * 86400, 0
    for path in leftover_recordings():
        try:
            if path.stat().st_mtime < limit:
                path.unlink()
                n += 1
        except OSError:
            logging.exception("Aufnahme %s nicht löschbar", path)
    return n


def load() -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    cfg = copy.deepcopy(DEFAULTS)
    if FILE.exists():
        try:
            stored = json.loads(FILE.read_text(encoding="utf-8-sig"))
            llm = {**cfg["llm"], **(stored.get("llm") or {})}
            cfg.update(stored)
            cfg["llm"] = llm
            if int(stored.get("config_version") or 1) < 3:
                # Wer eine frühere Standardtaste (F7, dann Strg allein) nie geändert hat, bekommt Strg + Win.
                if stored.get("hotkey_hold") in (["f7"], ["ctrl"]):
                    cfg["hotkey_hold"] = ["ctrl", "win"]
                cfg["config_version"] = 3
            if int(stored.get("config_version") or 1) < 4:
                # Die drei neuen Aufträge einmal nachtragen; wer einen gleichnamigen hat, behält seinen.
                names = {p.get("name") for p in cfg.get("prompts") or []}
                cfg["prompts"] = list(cfg.get("prompts") or []) + [
                    {**copy.deepcopy(p), "record": p["name"] in OLD_ROW}
                    for p in DEFAULTS["prompts"] if p["name"] in ADDED_V4 and p["name"] not in names]
                cfg["config_version"] = 4
            if int(stored.get("config_version") or 1) < 5:
                # 1.4.0: Welche Aufträge die Seite Aufnahme zeigt; die beiden Texte von 1.3.0 nachziehen, wenn unverändert.
                for p in cfg.get("prompts") or []:
                    p.setdefault("record", p.get("name") in OLD_ROW)
                    if p.get("text") == OLD_V4.get(p.get("name")):
                        p["text"] = {"Zusammenfassung": SUMMARY, "Meeting-Protokoll": MEETING}[p["name"]]
                cfg["config_version"] = 5
            if int(stored.get("config_version") or 1) < 6:
                # 1.5.0: Sprecher trennen ist ab Werk an (einmal umstellen, bleibt abschaltbar). Das zweite deutsche
                # Sprachmodell (Canary) gibt es nicht mehr: seit der neuen Nachbearbeitung nicht genauer, aber langsamer.
                cfg["speakers"] = True
                if cfg.get("model_choice") == "genau":
                    cfg["model_choice"] = "de"
                cfg["config_version"] = 6
            if int(stored.get("config_version") or 1) < 7:
                # 1.6.0: Wer das Stimmtraining nutzt, will, dass die Stimme lernt: Die vorgelesenen (erfundenen) Sätze
                # werden ohne eigenen Haken aufgehoben.
                cfg["training_keep"] = True
                cfg["config_version"] = 7
            if int(stored.get("config_version") or 1) < 8:
                cfg["prompts"] = _prompts_v8(cfg.get("prompts"))
                cfg["config_version"] = 8
            if int(stored.get("config_version") or 1) < 9:
                cfg["prompts"] = _prompts_v9(cfg.get("prompts"))
                cfg["config_version"] = 9
            if int(stored.get("config_version") or 1) < 10:
                # 2.1.1: Sprecher trennen gilt wieder überall als Vorgabe (einmal umstellen). Wer es an einem Rechner
                # abgeschaltet hatte, etwa als das Stimmmodell dort noch fehlte, bekommt es zurück; abschaltbar bleibt es.
                cfg["speakers"] = True
                cfg["config_version"] = 10
            cfg.pop("model", None)
            cfg.pop("model_revision", None)
        except Exception:
            logging.exception("config.json ist nicht lesbar, nutze Standardwerte")
    global ACTIVE, OFFLINE, _base
    name, ACTIVE, OFFLINE, _base = str(cfg.get("profile_name") or ""), "", False, {}
    if name and profile_root() is not None:      # gewähltes Profil: seine persönlichen Einstellungen gelten
        fresh = _profile_load(name)
        if fresh is None:
            cfg["profile_name"] = ""             # das Profil gibt es nicht mehr: zurück zu den Daten dieses Rechners
        else:
            ACTIVE = name
            cfg.update(fresh)
    save(cfg)  # neue Schlüssel in die Datei nachtragen
    return cfg


def _whole() -> dict:
    """Was gerade gilt, als ein Stück: config.json, bei gewähltem Profil mit dessen persönlichen Einstellungen."""
    data = _read(FILE) or {}
    if ACTIVE:
        data.update(copy.deepcopy((_read(_copy_file(ACTIVE)) or {}).get("data") or _base))
    return data


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _read(path):
    """Inhalt einer JSON-Datei oder None (fehlt, nicht erreichbar, beschädigt)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save(cfg: dict) -> None:
    """Einstellungen schreiben. Ist ein Profil gewählt, gehen die persönlichen Teile dorthin; in config.json bleibt
    dafür stehen, was vorher zu diesem Rechner gehörte („Dieser Rechner“ bleibt, wie es war)."""
    DIR.mkdir(parents=True, exist_ok=True)
    if not ACTIVE:
        return _write(FILE, cfg)
    own = _read(FILE) or {}
    out = {k: v for k, v in cfg.items() if k not in PERSONAL}
    out.update({k: own[k] for k in PERSONAL if k in own})
    _write(FILE, out)
    _profile_save(cfg)


# ---- Profile: mehrere Personen an einem Programmordner (oft ein Netzlaufwerk, viele Rechner) ----
# Ein Profil ist ein Ordner profile\<Name> neben dem Programm: profil.json mit den persönlichen Einstellungen und
# training\ mit den Stimmaufnahmen. Kein Passwort, keine Rollen: Wer den Programmordner starten darf, kann jedes
# Profil wählen. Verlauf, Fälle, Protokoll und Schlüssel bleiben im Windows-Konto des Rechners.
PROFILES = "profile"
PROFILE_FILE = "profil.json"
COPIES = "profil-kopie"       # letzte Kopie je Profil auf diesem Rechner, falls der Programmordner gerade fehlt
PERSONAL = ("dictionary", "snippets", "vocabulary", "learned", "corrections", "commands", "prompts",
            "spoken_punctuation", "base_dictionary", "learn_terms", "sounds",
            "hotkey_hold", "hotkey_lock", "hotkey_paste_last", "hotkey_target", "hotkey_next_field",
            "field", "training_done", "training_scores", "handover_frame", "visite_prompt")
ACTIVE = ""                   # Name des gewählten Profils; leer = die Daten dieses Rechners
OFFLINE = False               # Profilordner gerade nicht erreichbar: Es gilt die Kopie von diesem Rechner
PROFILE_ROOT = None           # nur für Tests: fester Ordner statt „profile“ neben dem Programm
_base = {}                    # Stand des Profils beim letzten Lesen oder Schreiben, zum Zusammenführen
_probe = {}                   # Ordner -> lässt sich dort schreiben? (einmal je Lauf geprüft)


class _Gone:
    """Markiert „diesen Eintrag gibt es nicht“ beim Zusammenführen."""
    def __deepcopy__(self, memo):
        return self


_GONE = _Gone()


def profile_root():
    """Ordner mit den Profilen neben dem Programm; None, wenn die App aus dem Quelltext läuft."""
    if PROFILE_ROOT is not None:
        return Path(PROFILE_ROOT)
    from . import ort
    root = ort.root()
    return root / PROFILES if root else None


def _remote(path) -> bool:
    """Liegt der Ordner auf einem Netzlaufwerk (Freigabe eines Servers oder verbundener Laufwerksbuchstabe)?"""
    text = str(path)
    if text.startswith("\\\\"):
        return True
    try:
        import ctypes
        return ctypes.windll.kernel32.GetDriveTypeW(text[:3]) == 4      # DRIVE_REMOTE
    except Exception:
        return False


def _writable(folder: Path) -> bool:
    key = str(folder)
    if key not in _probe:
        try:
            probe = folder / ".schreibtest"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            _probe[key] = True
        except OSError:
            _probe[key] = False
    return _probe[key]


def profiles_on() -> bool:
    """Bietet das Fenster Profile an? Ja, wenn es den Ordner „profile“ neben dem Programm gibt, oder wenn das Programm
    auf einem Netzlaufwerk liegt, in das sich schreiben lässt: Dann legt das erste Profil den Ordner an."""
    root = profile_root()
    if root is None:
        return False
    try:
        if root.is_dir():
            return True
        return _remote(root.parent) and _writable(root.parent)
    except OSError:
        return False


def profiles_enable() -> None:
    """Profile an einem Programmordner einschalten, der nicht auf einem Netzlaufwerk liegt (legt den Ordner an)."""
    root = profile_root()
    if root is None:
        raise ValueError("Profile gibt es nur im installierten Programm.")
    root.mkdir(parents=True, exist_ok=True)


def profile_names() -> list:
    root = profile_root()
    try:
        return sorted((p.name for p in root.iterdir() if (p / PROFILE_FILE).is_file()), key=str.lower)
    except (OSError, AttributeError):
        return []


def clean_name(name: str) -> str:
    """Name eines Profils als Ordnername: ohne Zeichen, die Windows nicht erlaubt, höchstens 40 Zeichen."""
    import re
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", str(name)).strip(" .")[:40].strip(" .")
    return "" if name.upper() in ("CON", "PRN", "AUX", "NUL") or name.startswith("_") else name


def _personal(cfg: dict) -> dict:
    return {k: copy.deepcopy(cfg[k]) for k in PERSONAL if k in cfg}


def _merge(base, mine, theirs):
    """Drei Stände zusammenführen: Was nur eine Seite geändert hat, gilt; haben beide geändert, wird Eintrag für
    Eintrag weitergeschaut, und im echten Konflikt gewinnt dieser Rechner."""
    if mine == base:
        return copy.deepcopy(theirs)
    if theirs == base or mine == theirs:
        return copy.deepcopy(mine)
    if isinstance(mine, dict) and isinstance(theirs, dict):
        b = base if isinstance(base, dict) else {}
        out = {}
        for k in list(mine) + [k for k in theirs if k not in mine]:
            v = _merge(b.get(k, _GONE), mine.get(k, _GONE), theirs.get(k, _GONE))
            if v is not _GONE:
                out[k] = v
        return out
    if isinstance(mine, list) and isinstance(theirs, list):
        b = base if isinstance(base, list) else []
        named = lambda rows: all(isinstance(r, dict) and r.get("name") for r in rows)
        if mine and theirs and named(mine) and named(theirs) and named(b):   # Aufträge: nach Namen, nicht nach Platz
            merged = _merge({r["name"]: r for r in b}, {r["name"]: r for r in mine}, {r["name"]: r for r in theirs})
            return list(merged.values())
        out = [x for x in mine if not (x in b and x not in theirs)]          # was die andere Seite gestrichen hat, geht
        out += [x for x in theirs if x not in mine and x not in b]            # was die andere Seite ergänzt hat, kommt
        return copy.deepcopy(out)
    return copy.deepcopy(mine)


def _copy_file(name: str) -> Path:
    return DIR / COPIES / f"{name}.json"


def _profile_load(name: str):
    """Persönliche Einstellungen eines Profils lesen. Ist der Programmordner nicht erreichbar, gilt die Kopie von
    diesem Rechner (OFFLINE). Gibt None zurück, wenn es das Profil nicht mehr gibt."""
    global OFFLINE, _base
    root = profile_root()
    copy_file = _copy_file(name)
    kept = _read(copy_file) or {}
    try:
        reachable = root is not None and root.is_dir()
    except OSError:
        reachable = False
    if not reachable:
        if not kept:
            return None
        OFFLINE, _base = True, copy.deepcopy(kept.get("base") or {})
        return copy.deepcopy(kept.get("data") or {})
    theirs = _read(root / name / PROFILE_FILE)
    if theirs is None:
        return None
    version = int(theirs.get("config_version") or 7)
    theirs = {k: theirs[k] for k in PERSONAL if k in theirs}
    OFFLINE = False
    if version < 9 and "prompts" in theirs:   # Profil aus einer älteren Fassung: dieselben Schritte wie bei config.json
        theirs["prompts"] = _prompts_up(theirs["prompts"], version)
        if kept.get("pending") and "prompts" in (kept.get("data") or {}):
            kept["data"]["prompts"] = _prompts_up(kept["data"]["prompts"], version)
        try:
            _write(root / name / PROFILE_FILE, {**theirs, "config_version": DEFAULTS["config_version"]})
        except OSError:
            pass
    if kept.get("pending"):                 # hier wurde ohne Programmordner weitergearbeitet: jetzt zusammenführen
        base, mine = kept.get("base") or {}, kept.get("data") or {}
        merged = {k: _merge(base.get(k, _GONE), mine.get(k, _GONE), theirs.get(k, _GONE)) for k in PERSONAL}
        theirs = {k: v for k, v in merged.items() if v is not _GONE}
        try:
            _write(root / name / PROFILE_FILE, {**theirs, "config_version": DEFAULTS["config_version"]})
        except OSError:
            OFFLINE = True
    _base = copy.deepcopy(theirs)
    try:
        _write(copy_file, {"pending": OFFLINE, "base": _base, "data": theirs})
    except OSError:
        pass
    if not OFFLINE:
        voice_sync(name)
    return copy.deepcopy(theirs)


def _profile_save(cfg: dict) -> None:
    """Persönliche Einstellungen ins Profil schreiben und dabei übernehmen, was ein anderer Rechner inzwischen
    beigetragen hat. Ist der Programmordner nicht erreichbar, bleibt alles in der Kopie auf diesem Rechner."""
    global OFFLINE, _base
    mine = _personal(cfg)
    merged = mine
    path = profile_root() / ACTIVE / PROFILE_FILE
    try:
        if not path.parent.is_dir():
            raise OSError("Profilordner nicht erreichbar")
        theirs = _read(path)
        if theirs is not None:
            merged = {k: v for k, v in ((k, _merge(_base.get(k, _GONE), mine.get(k, _GONE), theirs.get(k, _GONE)))
                                        for k in PERSONAL) if v is not _GONE}
        _write(path, {**merged, "config_version": DEFAULTS["config_version"]})
        OFFLINE = False
        _base = copy.deepcopy(merged)
        for k, v in merged.items():
            if v != mine.get(k):
                cfg[k] = copy.deepcopy(v)        # was ein anderer Rechner inzwischen ergänzt hat
    except OSError:
        OFFLINE = True
    try:
        _write(_copy_file(ACTIVE), {"pending": OFFLINE, "base": _base, "data": merged})
    except OSError:
        pass


def profile_create(name: str, cfg=None) -> str:
    """Legt profile\\<Name> an. cfg: Einstellungen, deren persönlicher Teil mitgeht; ohne cfg die Werkseinstellung."""
    name = clean_name(name)
    if not name:
        raise ValueError("Bitte einen Namen eingeben (ohne Sonderzeichen wie / : * ?).")
    root = profile_root()
    if root is None:
        raise ValueError("Profile gibt es nur im installierten Programm.")
    if name.lower() in (n.lower() for n in profile_names()):
        raise ValueError(f"Das Profil „{name}“ gibt es schon.")
    try:
        _write(root / name / PROFILE_FILE, {**_personal(cfg if cfg is not None else DEFAULTS),
                                            "config_version": DEFAULTS["config_version"]})
    except OSError as e:
        raise ValueError(f"Der Programmordner lässt sich nicht beschreiben ({e}).") from e
    return name


def profile_use(cfg: dict, name: str) -> None:
    """Auf ein Profil wechseln (leer = die Daten dieses Rechners): erst den jetzigen Stand sichern, dann die
    persönlichen Einstellungen in cfg tauschen. Der Rechner merkt sich die Wahl für dieses Windows-Konto."""
    global ACTIVE, OFFLINE, _base
    save(cfg)
    if name:
        fresh = _profile_load(name)
        if fresh is None:
            raise ValueError(f"Das Profil „{name}“ ist nicht erreichbar.")
    else:
        own = _read(FILE) or {}
        fresh, OFFLINE, _base = {k: own[k] for k in PERSONAL if k in own}, False, {}
    ACTIVE = name
    cfg["profile_name"] = name
    for k in PERSONAL:
        cfg[k] = copy.deepcopy(fresh[k] if k in fresh else DEFAULTS[k])
    save(cfg)


def voice_dir(name=None) -> Path:
    """Ordner der Stimmaufnahmen: im gewählten Profil, sonst im Datenordner dieses Rechners. Ist der Programmordner
    gerade nicht erreichbar, sammelt die App auf diesem Rechner und legt die Aufnahmen später ins Profil."""
    name = ACTIVE if name is None else name
    if not name:
        return DIR / VOICE
    if OFFLINE or profile_root() is None:
        return DIR / COPIES / name / VOICE
    return profile_root() / name / VOICE


def voice_sync(name: str) -> int:
    """Aufnahmen, die ohne Programmordner auf diesem Rechner gesammelt wurden, ins Profil legen."""
    here, there, moved = DIR / COPIES / name / VOICE, profile_root() / name / VOICE, 0
    try:
        for index in sorted(here.rglob("index.jsonl")) if here.is_dir() else []:
            target = there / index.parent.relative_to(here)
            target.mkdir(parents=True, exist_ok=True)
            lines = []
            for line in index.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                    audio = Path(row["audio"]).name
                except (ValueError, KeyError, TypeError):
                    continue
                source = index.parent / audio
                if not source.is_file():
                    continue
                stem, n = Path(audio).stem, 1
                while (target / audio).exists():                 # derselbe Name ist im Profil schon vergeben
                    if (target / audio).read_bytes() == source.read_bytes():
                        break
                    n += 1
                    audio = f"{stem}-{n}.wav"
                else:
                    shutil.copyfile(source, target / audio)
                    lines.append(json.dumps(dict(row, audio=audio), ensure_ascii=False))
            if lines:
                with open(target / "index.jsonl", "a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                moved += len(lines)
        if here.is_dir():
            shutil.rmtree(here, ignore_errors=True)
    except OSError:
        pass
    return moved


BACKUPS = "sicherung"


def backup(tag: str = "") -> Path | None:
    """Kopie der Einstellungen (mit Wörterbuch, Textbausteinen, Aufträgen, Servern) im Datenordner ablegen.

    Geschieht vor jedem Versionswechsel und vor dem Zurückholen; die letzten zehn bleiben liegen. API-Schlüssel
    stehen nicht in der Datei, die liegen im Schlüsselspeicher von Windows."""
    if not FILE.exists():
        return None
    try:
        folder = DIR / BACKUPS
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"einstellungen-{time.strftime('%Y-%m-%d-%H%M%S')}{'-' + tag if tag else ''}.json"
        if ACTIVE:
            _write(target, _whole())             # mit dem, was im gewählten Profil steht
        else:
            shutil.copyfile(FILE, target)
        for old in sorted(folder.glob("einstellungen-*.json"))[:-10]:
            old.unlink()
        return target
    except OSError:
        logging.exception("Sicherung der Einstellungen fehlgeschlagen")
        return None


PROFILE = ".lsprofil"          # Profil: Einstellungen und Stimmaufnahmen in einer Datei (ein ZIP)
SETTINGS = "einstellungen.json"
VOICE = "training"


def export(path) -> int:
    """Einstellungen an einen frei gewählten Ort schreiben. Endet der Name auf .lsprofil, kommen die Stimmaufnahmen des
    Stimmtrainings (Übungs- und Prüfsätze) mit in die Datei. Gibt die Zahl der Aufnahmen zurück. API-Schlüssel sind nie dabei."""
    text = json.dumps(_whole(), indent=2, ensure_ascii=False)
    if not str(path).lower().endswith(PROFILE):
        Path(path).write_text(text, encoding="utf-8")
        return 0
    import zipfile
    count, voice = 0, voice_dir()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(SETTINGS, text)
        for f in sorted(voice.rglob("*")) if voice.is_dir() else []:
            if f.is_file() and f.suffix in (".wav", ".jsonl"):
                z.write(f, f"{VOICE}/{f.relative_to(voice).as_posix()}")
                count += f.suffix == ".wav"
    return count


def _voice_in(z) -> int:
    """Stimmaufnahmen aus einem Profil dazulegen: Vorhandene Dateien bleiben, das Verzeichnis wird ergänzt."""
    count = 0
    names = [n for n in z.namelist() if n.startswith(VOICE + "/") and ".." not in n and not n.endswith("/")]
    for name in (n for n in names if n.endswith(".jsonl")):
        folder = voice_dir() / Path(name).parent.relative_to(VOICE)
        folder.mkdir(parents=True, exist_ok=True)
        new = []
        for line in z.read(name).decode("utf-8", "replace").splitlines():
            try:
                audio = Path(json.loads(line)["audio"]).name
            except (ValueError, KeyError, TypeError):
                continue
            source = f"{Path(name).parent.as_posix()}/{audio}"
            if source in names and not (folder / audio).exists():
                (folder / audio).write_bytes(z.read(source))
                new.append(line)
        if new:
            with open(folder / Path(name).name, "a", encoding="utf-8") as f:
                f.write("\n".join(new) + "\n")
            count += len(new)
    return count


def restore(path) -> dict:
    """Einstellungen (oder ein Profil mit Stimmaufnahmen) aus einer gesicherten Datei zurückholen. Die bisherigen
    Einstellungen werden vorher gesichert; vorhandene Stimmaufnahmen bleiben und werden ergänzt."""
    import zipfile
    profile = None
    try:
        if zipfile.is_zipfile(path):
            profile = zipfile.ZipFile(path)
            stored = json.loads(profile.read(SETTINGS).decode("utf-8-sig"))
        else:
            stored = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, KeyError) as e:
        raise ValueError(f"Die Datei lässt sich nicht lesen ({e}).") from e
    if not isinstance(stored, dict) or not ({"hotkey_hold", "dictionary", "llm"} & set(stored)):
        raise ValueError("Das ist keine Einstellungsdatei von LocalScribe.")
    backup("vor-zurueckholen")
    active, own = ACTIVE, _read(FILE) or {}
    on_disk = dict(stored)
    on_disk["profile_name"] = active             # eine gesicherte Datei wählt kein Profil; das gewählte bleibt
    if active:                                   # die persönlichen Teile gehen ins gewählte Profil, nicht in „Dieser Rechner“
        on_disk = {k: v for k, v in on_disk.items() if k not in PERSONAL}
        on_disk.update({k: own[k] for k in PERSONAL if k in own})
    _write(FILE, on_disk)
    cfg = load()
    if active and ACTIVE == active:
        mine = {k: copy.deepcopy(stored[k]) for k in PERSONAL if k in stored}
        if int(stored.get("config_version") or 1) < 9 and "prompts" in mine:      # Sicherung aus einer älteren Fassung
            mine["prompts"] = _prompts_up(mine["prompts"], int(stored.get("config_version") or 1))
        cfg.update(mine)
        save(cfg)
    if profile is not None:
        with profile:
            cfg["_voice"] = _voice_in(profile)        # nur für die Meldung, wird nicht gespeichert
    return cfg


def prompt_by_name(cfg: dict, name: str):
    for p in cfg.get("prompts") or []:
        if p.get("name") == name:
            return p
    return None
