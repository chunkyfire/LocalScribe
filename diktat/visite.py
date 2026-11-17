"""Visite & Übergabe: aus einem diktierten Fall einen Arztbrief-Entwurf, ein Sicherheitsnetz und gezielte Rückfragen.

Übernommen aus WacheNG (Prompt wörtlich, in den Einstellungen änderbar). Die Auswertung macht das unter
KI-Nachbearbeitung eingetragene Sprachmodell; liegt es außerhalb des Rechners, sieht es nur die geschützte Fassung
(schutz.py). Fälle liegen in einer eigenen Datei auf diesem Rechner, Löschen führt zuerst in den Papierkorb.

Kein Medizinprodukt: Die Ausgaben sind Entwürfe eines Sprachmodells für Forschung, Lehre und den Vergleich von
Modellen, keine Diagnose- oder Therapieempfehlung.
"""
import json
import re
import sqlite3
import time

from . import config, llm, schutz

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
   - case_summary_en: kompakte ENGLISCHE Fallzusammenfassung (max. 250 Wörter) mit allen klinisch relevanten Angaben (Alter, Geschlecht, Leitsymptom, Verlauf, Vitalparameter, Befunde, Vorerkrankungen, Medikation, Procedere). KEINE Namen, KEINE Daten. Einzige Ausnahme von „alle Texte auf Deutsch“.
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
    "case_summary_en": "...",
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

SHIELD_NOTE = ("\n\nPlatzhalter in eckigen Klammern wie [NAME_1] oder [DATUM_1] stehen für geschützte Angaben. "
               "Übernimm sie unverändert an der passenden Stelle.")
SECTIONS = (("anamnese", "Anamnese"), ("befund", "Befund"), ("prozedere", "Beurteilung und Plan"),
            ("procedere", "Procedere"), ("vorerkrankungen", "Vorerkrankungen"), ("vormedikation", "Vormedikation"))


def prompt(cfg: dict) -> str:
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


def analyse(cfg: dict, text: str, ask=None) -> dict:
    """Fall auswerten. ask(system, user) ersetzt in Tests den Aufruf des Sprachmodells."""
    server = dict(cfg.get("llm") or {})
    server["timeout"] = max(float(server.get("timeout") or 0), 120)      # die Auswertung ist lang
    shield = schutz.Mask() if ask is None and schutz.needed(server) else None
    system = prompt(cfg)
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
    return _restore(result, shield) if shield else result


def letter(result: dict) -> str:
    """Der Arztbrief-Entwurf als Text zum Einfügen."""
    doc = result.get("documentation") or {}
    return "\n\n".join(f"{title}:\n{str(doc[key]).strip()}" for key, title in SECTIONS if str(doc.get(key) or "").strip())


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
