"""Visite & Übergabe: aus einem diktierten Fall einen Arztbrief-Entwurf, ein Sicherheitsnetz und gezielte Rückfragen.

Übernommen aus WacheNG (Prompt in den Einstellungen änderbar). Zwei Schritte laufen nebeneinander: Jev gibt in etwa
einer Sekunde eine Ersteinschätzung als Wahrscheinlichkeiten (jev.py), ein Sprachmodell schreibt den Arztbrief-Entwurf
mit Sicherheitsnetz und Rückfragen. Server und Schlüssel stehen in den Einstellungen unter LLM; liegt der Server
außerhalb des Rechners, sehen beide nur die geschützte Fassung (schutz.py). Fälle liegen in einer eigenen Datei auf
diesem Rechner, Löschen führt zuerst in den Papierkorb.

Experimenteller Modus, kein Medizinprodukt: Die Ausgaben sind Entwürfe eines Sprachmodells für Benchmarking, Forschung
und Lehre, keine Diagnose- oder Therapieempfehlung. Er dient dazu, mit Messwerten zu prüfen, ob sich eine eigene
Entwicklung im Haus (Inhouse-Ausnahme nach Art. 5 Abs. 5 MDR) lohnt.
"""
import json
import re
import sqlite3
import time

from . import config, jev, llm, schutz

PROMPT = """Du bist ein erfahrener Notarzt-Assistent auf Oberarzt-Niveau (Top 0,1%). Du kennst seltene Erkrankungen, Red Flags und differentialdiagnostische Schlüsselfragen aus dem Effeff. Analysiere die Patientendaten und erstelle:

WICHTIG:
- Antworte AUSSCHLIESSLICH mit einem einzigen, gültigen JSON-Objekt.
- KEIN Markdown, KEINE Code-Fences (keine ```), KEIN Fließtext außerhalb des JSON.
- Verwende doppelte Anführungszeichen für JSON-Keys und Strings.
- Achte besonders auf korrekte JSON-Syntax (Kommas zwischen Array-Elementen/Objekt-Keys, keine trailing commas).
- ALLE TEXTE AUF DEUTSCH!

1. **Strukturierte Dokumentation** für das KIS:
   - Anamnese/Verlauf (präzise Zusammenfassung)
   - Status/Befund (Untersuchungsbefunde)
   - Prozedere/Plan (Reasoning, geplante Maßnahmen)
   - procedere: NUR das von der Ärztin/dem Arzt im Diktat oder Text AUSDRÜCKLICH genannte weitere Vorgehen, möglichst wörtlich. KEINE eigenen Ergänzungen oder Empfehlungen. Leerer String, wenn kein Vorgehen genannt wurde.
   - Vorerkrankungen: EXTRAHIERE ALLE Vorerkrankungen aus ALLEN Dokumenten (OCR-Text, Arztbriefe, Diagnosen-Listen). Fasse zusammen, aber lass KEINE relevanten Diagnosen weg. Schreibe sie als Fließtext oder Auflistung.
   - Vormedikation: EXTRAHIERE ALLE Medikamente mit VOLLSTÄNDIGEM Einnahmeschema (z.B. "Metoprolol 47,5mg 1-0-0", "Eliquis 5mg 1-0-1", "Ramipril 5mg 0-0-1"). Wenn kein Schema angegeben: nur Name und Dosis. Liste ALLE Medikamente auf, die in den Dokumenten erwähnt werden!

2. **ICD-10-GM & OPS Codes** für die Abrechnung:
   - Identifiziere alle relevanten Diagnose-Codes
   - Markiere PCCL-relevante Codes (z.B. Z92.1 bei Antikoagulation)
   - Schlage OPS-Prozeduren vor

3. **Safety Alerts** (Plausibilitätsprüfung) - ALLE AUF DEUTSCH:
   - Prüfe auf Widersprüche zwischen Diktat und Dokumenten
   - Identifiziere Risiken (z.B. Antikoagulation + Trauma)
   - Formuliere "context" als kurze Überschrift (z.B. "Medikation & Blutung")
   - Formuliere "suggestion" als konkrete deutsche Handlungsempfehlung
   - Der Text stammt oft aus Spracherkennung. Klingt ein Arzneimittel, eine Dosis, eine Einheit oder ein Vorzeichen nach einem Hörfehler oder passt nicht zum Zusammenhang, melde das als Safety Alert und nenne den gehörten Wortlaut; korrigiere nicht stillschweigend.

4. **Gezielte Rückfragen** (EXAKT 3 entscheidende Weichensteller):
   - Erzeuge zunächst intern mehrere mögliche Rückfragen und wähle anschließend ausschließlich die drei mit dem höchsten erwarteten Informationsgewinn aus.
   - Eine Frage ist nur dann geeignet, wenn ihre Antwort die aktuelle Arbeitsdiagnose, Dringlichkeit, Diagnostik, Therapie oder Disposition konkret verändern könnte.
   - Bevorzuge Gegenhypothesen und gefährliche Alternativerklärungen: Frage nach dem fehlenden Merkmal, das den Fall in eine relevante andere Richtung drehen würde.
   - Nutze ausschließlich Informationen, die in Diktat und Dokumenten noch NICHT beantwortet sind. Keine Wiederholungen, keine Routineanamnese und keine Fragen ohne direkte Konsequenz.
   - Die drei Fragen müssen unterschiedliche klinische Entscheidungsachsen abdecken und nach Einfluss auf die unmittelbare Entscheidung absteigend sortiert sein.
   - Formuliere jeweils eine kurze, direkt stellbare Frage ohne Doppelfrage. Die Rationale benennt knapp: welche Alternative geprüft wird und welche Entscheidung von der Antwort abhängt.
   - Priorisiere: "critical" (unmittelbar entscheidungs- oder sicherheitsrelevant), "high" (relevanter Richtungswechsel), "medium" nur wenn keine dritte höherwertige Frage existiert.

5. **Patienteninfo** auf Grundschul-Niveau (5. Klasse Lesbarkeit)

GIB GENAU DIESES JSON-SCHEMA ZURÜCK:
{
  "documentation": {
    "anamnese": "...",
    "befund": "...",
    "prozedere": "...",
    "procedere": "...",
    "vorerkrankungen": "...",
    "vormedikation": "..."
  },
  "codes": [
    {"code": "S01.81", "description": "...", "type": "ICD", "revenueRelevant": false},
    {"code": "Z92.1", "description": "Dauertherapie Antikoagulanzien", "type": "ICD", "revenueRelevant": true}
  ],
  "safetyAlerts": [
    {"severity": "warning", "context": "Medikation & Blutung", "suggestion": "Gerinnungsparameter kontrollieren und Reversierungsprotokoll prüfen."}
  ],
  "followUpQuestions": [
    {"question": "Gab es eine Bewusstlosigkeit direkt nach dem Ereignis?", "rationale": "Ausschluss Synkope als Sturzursache bei Vorhofflimmern", "priority": "critical"},
    {"question": "Wann war die letzte INR-Kontrolle?", "rationale": "Supratherapeutische INR erhöht ICB-Risiko erheblich", "priority": "high"}
  ],
  "patientHandout": {
    "title": "Ihre Diagnose",
    "content": "..."
  }
}"""

# ---- Station und Intensiv: derselbe Aufbau, anderer Blick ----
_HEAD = PROMPT[PROMPT.index("WICHTIG:"):PROMPT.index("1. **Strukturierte")]
_SCHEMA = PROMPT[PROMPT.index("GIB GENAU DIESES JSON-SCHEMA ZURÜCK"):]
_ASKS = """   - Erzeuge zunächst intern mehrere mögliche Rückfragen und wähle anschließend ausschließlich die drei mit dem höchsten erwarteten Informationsgewinn aus.
   - Nutze ausschließlich Informationen, die im Text noch NICHT beantwortet sind. Keine Wiederholungen, keine Routinefragen und keine Fragen ohne direkte Konsequenz.
   - Die drei Fragen müssen unterschiedliche Entscheidungen betreffen und nach Einfluss absteigend sortiert sein.
   - Formuliere jeweils eine kurze, direkt stellbare Frage ohne Doppelfrage. Die Rationale benennt knapp, welche Entscheidung von der Antwort abhängt.
   - Priorisiere: "critical" (unmittelbar entscheidungs- oder sicherheitsrelevant), "high" (relevanter Richtungswechsel), "medium" nur wenn keine dritte höherwertige Frage existiert."""
_HEARD = ("   - Der Text stammt oft aus Spracherkennung. Klingt ein Arzneimittel, eine Dosis, eine Einheit oder ein Vorzeichen nach "
          "einem Hörfehler oder passt nicht zum Zusammenhang, melde das als Safety Alert und nenne den gehörten Wortlaut; "
          "korrigiere nicht stillschweigend.")
_SAID = ("   - procedere: NUR das von der Ärztin/dem Arzt im Text AUSDRÜCKLICH genannte weitere Vorgehen, möglichst wörtlich. "
         "KEINE eigenen Ergänzungen oder Empfehlungen. Leerer String, wenn kein Vorgehen genannt wurde.")
STATION = f"""Du bist eine erfahrene Stationsärztin auf Oberarzt-Niveau und unterstützt bei Visite, Verlauf und Übergabe auf einer Normalstation. Du erkennst früh, wenn ein Verlauf kippt, und weißt, was eine Entlassung aufhält. Der Text kann ein Visitengespräch mit Sprecherzeilen, ein Diktat oder eine Übergabe sein. Analysiere ihn und erstelle:

{_HEAD}1. **Strukturierte Dokumentation** (Visiten- und Verlaufseintrag) für das KIS:
   - anamnese: Verlauf seit der letzten Visite und aktuelles Befinden (Beschwerden, Nacht, Besonderheiten). Präzise, ohne Wertung.
   - befund: Aktuelle Befunde: Vitalwerte, Untersuchung, Labor mit Verlauf (Wert und Richtung), Bildgebung, Mikrobiologie. Nur was genannt ist.
   - prozedere: Beurteilung: Wo steht der Patient heute, was ist das führende Problem, was folgt daraus. Problemorientiert, je Problem eine Zeile.
{_SAID}
   - vorerkrankungen: Aufnahmegrund, aktuelle Diagnosen und Vorerkrankungen, soweit genannt.
   - vormedikation: Aktuelle Medikation mit Dosis und Schema. Was heute neu, abgesetzt oder umgestellt wurde, ausdrücklich so kennzeichnen. Antiinfektiva mit Therapietag und geplanter Dauer, wenn genannt.

2. **ICD-10-GM & OPS Codes** für den stationären Aufenthalt:
   - Hauptdiagnose zuerst, dann Nebendiagnosen; kodiere nur, was der Text trägt
   - Markiere PCCL-relevante Nebendiagnosen als revenueRelevant
   - OPS nur für genannte Prozeduren

3. **Safety Alerts** (Stationsblick) - ALLE AUF DEUTSCH:
   - Medikation gegen Nierenfunktion, Kalium, QT-Zeit, Alter und Wechselwirkungen prüfen
   - Pausierte oder fehlende Dauermedikation (Antikoagulation, Thromboseprophylaxe, Insulin) und Allergien gegen Verordnungen
   - Zeichen einer drohenden Verschlechterung, die im Plan nicht vorkommen
   - Was vor einer Entlassung noch fehlt (ausstehende Befunde, Kontrolle, Versorgung zu Hause)
   - Formuliere "context" als kurze Überschrift und "suggestion" als konkrete Handlungsempfehlung
{_HEARD}

4. **Gezielte Rückfragen** (EXAKT 3):
   - Eine Frage ist nur dann geeignet, wenn ihre Antwort den heutigen Plan, den Entlasszeitpunkt oder eine Eskalation konkret verändern könnte.
{_ASKS}

5. **Patienteninfo** auf Grundschul-Niveau (5. Klasse Lesbarkeit): Was ist los, was passiert heute, wie geht es weiter, worauf soll ich achten.

{_SCHEMA}"""
ITS = f"""Du bist ein erfahrener Intensivmediziner auf Oberarzt-Niveau und unterstützt bei Visite und Schichtübergabe auf einer Intensivstation. Du denkst in Organsystemen, Trends und Tageszielen. Der Text ist ein Diktat oder eine mündliche Übergabe. Analysiere ihn und erstelle:

{_HEAD}1. **Strukturierte Dokumentation** (Übergabe nach Organsystemen):
   - anamnese: Kurzvorstellung: Alter, Aufnahmegrund, Behandlungstag, Verlauf der letzten 24 Stunden, aktuelle Hauptprobleme.
   - befund: Status nach Organsystemen, je System eine Zeile mit dem Systemnamen vorweg, nur was genannt ist: Neurologie und Sedierung (RASS, Analgosedierung), Atmung (Beatmungsform, FiO2, PEEP, Horovitz, Blutgase), Kreislauf (Katecholamine mit Rate, Blutdruck, Laktat mit Verlauf), Niere und Bilanz (Ausscheidung, Kreatinin, Nierenersatz, Bilanz), Abdomen und Ernährung, Infektiologie (Fokus, Erreger, Antiinfektiva mit Therapietag, Entzündungswerte mit Verlauf), Gerinnung und Blut, Zugänge und Katheter (mit Liegedauer). Systeme ohne Angabe weglassen.
   - prozedere: Beurteilung und Tagesziele: je Organsystem, was in dieser Schicht erreicht werden soll, soweit es sich aus dem Text ergibt.
{_SAID}
   - vorerkrankungen: Diagnosen und Vorerkrankungen, soweit genannt.
   - vormedikation: Laufende Medikation: Perfusoren mit Rate, Antiinfektiva mit Therapietag, Prophylaxen, Ernährung. Zahlen und Einheiten genau wie genannt; nichts umrechnen.

2. **ICD-10-GM & OPS Codes**:
   - Hauptdiagnose zuerst, dann Nebendiagnosen; kodiere nur, was der Text trägt
   - OPS für genannte Prozeduren (Beatmung, Nierenersatz, Katheteranlagen)
   - Markiere erlösrelevante Codes als revenueRelevant

3. **Safety Alerts** (Intensivblick) - ALLE AUF DEUTSCH:
   - Dosis- und Ratenangaben auf Plausibilität prüfen (Zehnerpotenz, Einheit, je Kilogramm, je Minute oder Stunde)
   - Ähnlich klingende Arzneimittel (z. B. Adrenalin und Noradrenalin, Sufentanil, Fentanyl und Remifentanil) und fehlende Vorzeichen (z. B. beim Bilanzziel) ausdrücklich melden
   - Widerspruch zwischen Verlauf und Plan (z. B. geplante, aber nicht umgesetzte Deeskalation)
   - Fehlende Tagesroutine, soweit erkennbar: Thromboseprophylaxe, Ulkusprophylaxe, Ernährung, Sedierungsziel, Liegedauer von Kathetern, Dauer der Antiinfektiva
   - Dosisanpassung bei Nierenversagen oder Nierenersatz
   - Formuliere "context" als kurze Überschrift und "suggestion" als konkrete Handlungsempfehlung
{_HEARD}

4. **Gezielte Rückfragen** (EXAKT 3):
   - Eine Frage ist nur dann geeignet, wenn ihre Antwort eine Entscheidung dieser Schicht konkret verändern könnte: Eskalation, Entwöhnung von der Beatmung, Deeskalation, Therapieziel.
{_ASKS}

5. **Information für Angehörige** im Feld patientHandout, in einfacher Sprache (5. Klasse Lesbarkeit): title "Für Angehörige"; content: wie es der Patientin oder dem Patienten heute geht, wobei die Geräte und Medikamente helfen und was als Nächstes geplant ist. Ehrlich, ohne Fachwörter, ohne Prognose zu versprechen.

{_SCHEMA}"""
PROMPTS = {"station": STATION, "its": ITS}
NAMES = {      # was die Blöcke im jeweiligen Rahmen heißen
    "zna": {"jev": "Ersteinschätzung", "brief": "Arztbrief", "info": "Patienteninfo"},
    "station": {"jev": "Tages-Check", "brief": "Visiteneintrag", "info": "Patienteninfo"},
    "its": {"jev": "Tages-Check", "brief": "Übergabe", "info": "Für Angehörige"},
}
_TITLES = {
    "station": {"anamnese": "Verlauf", "prozedere": "Beurteilung", "vorerkrankungen": "Diagnosen", "vormedikation": "Medikation"},
    "its": {"anamnese": "Kurzvorstellung und Verlauf", "befund": "Status nach Organsystemen", "prozedere": "Beurteilung und Tagesziele",
            "vorerkrankungen": "Diagnosen", "vormedikation": "Laufende Medikation"},
}

SHIELD_NOTE = ("\n\nPlatzhalter in eckigen Klammern wie [NAME_1] oder [DATUM_1] stehen für geschützte Angaben. "
               "Übernimm sie unverändert an der passenden Stelle.")
SECTIONS = (("anamnese", "Anamnese"), ("befund", "Befund"), ("prozedere", "Beurteilung und Plan"),
            ("procedere", "Procedere"), ("vorerkrankungen", "Vorerkrankungen"), ("vormedikation", "Vormedikation"))


def frame_of(value) -> str:
    return value if value in dict(jev.FRAMES) else "zna"


def sections(frame="zna") -> tuple:
    """Die Abschnitte der Dokumentation mit den Überschriften des Rahmens."""
    own = _TITLES.get(frame_of(frame), {})
    return tuple((key, own.get(key, title)) for key, title in SECTIONS)


def prompt(cfg: dict, frame="zna") -> str:
    """Der Auftrag an das Sprachmodell. Ein eigener Auftrag aus den Einstellungen gilt für die Notaufnahme."""
    frame = frame_of(frame)
    if frame != "zna":
        return PROMPTS[frame]
    return (cfg.get("visite_prompt") or "").strip() or PROMPT


def parse(text: str) -> dict:
    """JSON aus der Antwort des Modells holen, auch wenn Text oder Code-Zäune darum stehen."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL | re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise llm.LlmError("Das Modell hat kein auswertbares Ergebnis geliefert.")
    body = text[a:b + 1]
    try:
        return json.loads(body)
    except ValueError:
        body = re.sub(r",\s*([}\]])", r"\1", body.replace("“", '"').replace("”", '"').replace("„", '"'))
        try:
            return json.loads(body)
        except ValueError as e:
            raise llm.LlmError("Das Modell hat kein auswertbares Ergebnis geliefert.") from e


def _restore(value, shield):
    if isinstance(value, str):
        return shield.show(value)
    if isinstance(value, list):
        return [_restore(v, shield) for v in value]
    if isinstance(value, dict):
        return {k: _restore(v, shield) for k, v in value.items()}
    return value


# Wer bei OpenRouter den Arztbrief schreibt. Gemessen am 19.11.2026 an drei erfundenen Fällen mit Hörfehlern
# (werkzeug/messen/ERGEBNIS.md): Gemini 3.8 Flash mit wenig Nachdenken braucht rund 15 s statt 45 s und meldet dieselben
# Hörfehler wie Gemini 3.1 Pro. Gemini 3.6 Flash ist noch schneller, setzt aber eher ein geratenes Vorzeichen ein.
WRITER = "google/gemini-3.8-flash@low"
WRITERS = (("Standard: bei OpenRouter Gemini 3.8 Flash, sonst das Modell oben", ""),
           ("Gründlich: Gemini 3.1 Pro, etwa 45 Sekunden (OpenRouter)", "google/gemini-3.1-pro-preview"),
           ("Schnell: Gemini 3.6 Flash, etwa 8 Sekunden, rät eher (OpenRouter)", "google/gemini-3.6-flash@low"))


def writer(cfg: dict) -> dict:
    """Server und Modell für den Arztbrief. Eigene Angabe in den Einstellungen gewinnt; sonst bei OpenRouter das
    gemessene Standardmodell, bei jedem anderen Server (Ollama im Haus, IONOS …) das unter LLM gewählte Modell."""
    server = dict(cfg.get("llm") or {})
    own = (cfg.get("visite_model") or "").strip()
    if own in [model for _, model in WRITERS] and not jev.available(server):
        own = ""                                 # diese Namen kennt nur OpenRouter: woanders gilt das gewählte Modell
    if own:
        server["model"] = own
    elif jev.available(server):
        server["model"] = WRITER
    server["timeout"] = max(float(server.get("timeout") or 0), 180)      # die Auswertung ist lang
    return server


def triage(cfg: dict, text: str, request=None, frame="zna") -> dict:
    """Ersteinschätzung durch Jev. request ersetzt in Tests den Netzaufruf."""
    server = dict(cfg.get("llm") or {})
    if not jev.available(server):
        raise llm.LlmError("Jev gibt es nur über OpenRouter. Unter Einstellungen, LLM, OpenRouter als Server wählen.")
    if request is None and schutz.blocked(server):
        raise llm.LlmError(schutz.MISSING)
    if request is None and schutz.needed(server):
        text = schutz.Mask().hide(text)          # Jev antwortet nur mit Zahlen: nichts zurückzusetzen
    return jev.ask(server, text, cfg.get("visite_rules") or "", cfg.get("visite_jev") or "", request, frame_of(frame))


def analyse(cfg: dict, text: str, ask=None, frame="zna") -> dict:
    """Arztbrief-Entwurf, Sicherheitsnetz, Rückfragen. ask(system, user) ersetzt in Tests den Aufruf des Sprachmodells."""
    server = writer(cfg)
    if ask is None and schutz.blocked(server):
        raise llm.LlmError(schutz.MISSING)
    shield = schutz.Mask() if ask is None and schutz.needed(server) else None
    frame = frame_of(frame)
    system = prompt(cfg, frame)
    if shield:
        text = shield.hide(text)
        if shield.back:
            system += SHIELD_NOTE
    user = f"DIKTAT/ANAMNESE:\n{text.strip()}"
    answer = ask(system, user) if ask else llm.chat(server, system, user, json_mode=True)
    result = parse(answer)
    if not isinstance(result, dict):
        raise llm.LlmError("Das Modell hat kein auswertbares Ergebnis geliefert.")
    if isinstance(result.get("followUpQuestions"), list):
        result["followUpQuestions"] = result["followUpQuestions"][:3]
    result["frame"] = frame
    return _restore(result, shield) if shield else result


def letter(result: dict) -> str:
    """Der Arztbrief-Entwurf als Text zum Einfügen."""
    doc = result.get("documentation") or {}
    return "\n\n".join(f"{title}:\n{str(doc[key]).strip()}" for key, title in sections(result.get("frame"))
                         if str(doc.get(key) or "").strip())


# ---- Ablage: eine Datei, Löschen ist zuerst nur der Papierkorb ----
class Store:
    def __init__(self, path=None):
        self.db = sqlite3.connect(str(path or config.DIR / "visite.sqlite"), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS faelle (id INTEGER PRIMARY KEY, name TEXT, eingabe TEXT, ergebnis TEXT, "
                        "erstellt REAL, geaendert REAL, geloescht REAL)")
        self.db.commit()

    def save(self, case_id, name: str, text: str, result=None) -> int:
        """Fall anlegen oder ändern; gibt die Nummer zurück. Ein Ergebnis bleibt stehen, wenn keines mitkommt."""
        now = time.time()
        if case_id is None:
            cur = self.db.execute("INSERT INTO faelle (name, eingabe, ergebnis, erstellt, geaendert) VALUES (?, ?, ?, ?, ?)",
                                  (name, text, json.dumps(result, ensure_ascii=False) if result else None, now, now))
            case_id = cur.lastrowid
        elif result is None:
            self.db.execute("UPDATE faelle SET name = ?, eingabe = ?, geaendert = ? WHERE id = ?", (name, text, now, case_id))
        else:
            self.db.execute("UPDATE faelle SET name = ?, eingabe = ?, ergebnis = ?, geaendert = ? WHERE id = ?",
                            (name, text, json.dumps(result, ensure_ascii=False), now, case_id))
        self.db.commit()
        return case_id

    def rows(self, trash: bool = False, query: str = "") -> list:
        sql = ("SELECT id, name, eingabe, erstellt, geaendert FROM faelle WHERE geloescht IS " + ("NOT NULL" if trash else "NULL")
               + " AND (name LIKE ? OR eingabe LIKE ?) ORDER BY geaendert DESC")
        like = f"%{query.strip()}%"
        return self.db.execute(sql, (like, like)).fetchall()

    def rename(self, case_id, name: str):
        self.db.execute("UPDATE faelle SET name = ? WHERE id = ?", (name.strip(), case_id))
        self.db.commit()

    def get(self, case_id):
        row = self.db.execute("SELECT name, eingabe, ergebnis FROM faelle WHERE id = ?", (case_id,)).fetchone()
        return (row[0], row[1], json.loads(row[2]) if row[2] else None) if row else None

    def trash(self, case_id, on: bool = True):
        self.db.execute("UPDATE faelle SET geloescht = ? WHERE id = ?", (time.time() if on else None, case_id))
        self.db.commit()

    def purge(self, case_id=None) -> int:
        """Endgültig löschen: einen Fall aus dem Papierkorb oder (ohne Nummer) den ganzen Papierkorb."""
        cur = (self.db.execute("DELETE FROM faelle WHERE geloescht IS NOT NULL AND id = ?", (case_id,)) if case_id is not None
               else self.db.execute("DELETE FROM faelle WHERE geloescht IS NOT NULL"))
        self.db.commit()
        self.db.execute("VACUUM")
        return cur.rowcount
