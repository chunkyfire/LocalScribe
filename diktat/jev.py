"""Jev (TypeSafe): schnelle Ersteinschätzung eines Falls als Wahrscheinlichkeiten, übernommen aus WacheNG.

Jev schreibt keinen Text. Es beantwortet festgelegte Fragen zu einem Fall (EKG? Zugang? Notaufnahme oder
Notdienstpraxis? Welche Abteilung führt? Bett suchen? Schockraum?) jeweils mit einer Wahrscheinlichkeit. Alle Fragen
gehen in einer Anfrage hinaus und werden unabhängig voneinander beantwortet; die Antwort ist in etwa einer Sekunde da.

Erreichbar ist Jev über OpenRouter (Adresse …/api/v1/systemone). Es sieht nur die geschützte Fassung des Falls
(schutz.py). Experimenteller Modus, kein Medizinprodukt: Die Werte sind Entscheidungswahrscheinlichkeiten eines Modells
für Benchmarking, Forschung und Lehre, keine Anordnung und keine Diagnose.
"""
import time

from . import llm

MODEL = "~typesafe/jev-latest"     # bei OpenRouter der Zeiger auf die jeweils neueste Fassung
HIGH = 0.7            # ab hier gilt eine Maßnahme als vorgeschlagen
CONTEXT = "Patient in einem deutschen integrierten Notfallzentrum mit Notaufnahme und Notdienstpraxis."


def _noul(instructions, yes, no):
    return {"type": "noul", "instructions": instructions, "criteria": {"true": yes, "false": no}}


QUESTIONS = {
    "placement": {
        "type": "choice",
        "instructions": "Wohin sollte der Patient im integrierten Notfallzentrum laut `fall` gesteuert werden?",
        "criteria": {
            "emergency_department": "Notaufnahme: benötigt Labor, akute Bildgebung (Röntgen/CT/MRT), Monitoring, i.v.-Therapie, Überwachung oder möglicherweise stationäre Aufnahme.",
            "urgent_care_practice": "Notdienstpraxis: ambulant lösbar mit Beratung, Untersuchung, ggf. Sonografie, Rezept und elektiv vereinbarter Bildgebung; kein Akutlabor oder Monitoring nötig.",
        },
    },
    "specialty": {
        "type": "choice",
        "instructions": "Angenommen, der Patient wird in die Notaufnahme geroutet: Welche EINE Fachabteilung sollte laut `fall` die federführende Weiterbehandlung übernehmen? Wähle die spezifischste passende Abteilung.",
        "criteria": {
            "internal_medicine": "Allgemeine Innere Medizin: internistische Fälle ohne klar führende Subspezialität oder mit mehreren internistischen Problemen.",
            "cardiology": "Kardiologie: führende akute kardiale oder kreislaufbezogene Fragestellung, z. B. ACS, Rhythmusstörung oder Herzinsuffizienz.",
            "neurology": "Neurologie: führende neurologische Fragestellung, z. B. Schlaganfall, Krampfanfall oder akutes neurologisches Defizit.",
            "general_surgery": "Allgemein-/Viszeralchirurgie: akutes Abdomen, operationsbedürftige viszerale oder allgemeinchirurgische Erkrankung.",
            "trauma_surgery": "Unfallchirurgie/Orthopädie: Trauma, Fraktur, Gelenk- oder akute muskuloskelettale Erkrankung.",
            "urology": "Urologie: führende akute Erkrankung der Harnwege oder männlichen Genitalorgane.",
            "gynecology": "Gynäkologie: führende gynäkologische oder geburtshilfliche Akutfragestellung.",
            "pediatrics": "Pädiatrie: Patient im Kindes- oder Jugendalter mit pädiatrischer Akutfragestellung.",
            "psychiatry": "Psychiatrie: führende psychiatrische Krise ohne vorrangige somatische Behandlungsnotwendigkeit.",
            "ent": "HNO: führende akute Erkrankung von Hals, Nase oder Ohren.",
            "ophthalmology": "Augenheilkunde: führende akute ophthalmologische Erkrankung.",
            "dermatology": "Dermatologie: führende akute Hauterkrankung ohne vorrangige internistische oder chirurgische Ursache.",
            "other": "Andere Fachabteilung oder die vorliegenden Angaben erlauben keine sinnvolle Zuordnung zu den genannten Abteilungen.",
        },
    },
    "admission": _noul(
        "Wird der Patient laut `fall` voraussichtlich für mindestens eine Nacht stationär aufgenommen werden müssen?",
        "Behandlungsbedürftige Erkrankung, Überwachungsbedarf, Operation, fehlende häusliche Versorgung oder hohes Risiko.",
        "Ambulante Versorgung und Entlassung nach Diagnostik wahrscheinlich."),
    "shock_red": _noul(
        "Erfüllt der Fall ein Schockraum-Kriterium ROT (konservativ oder operativ)?",
        "Mindestens ein ROT-Kriterium liegt laut `fall` vor, z. B. A-Problem, Atemfrequenz unter 8 oder über 30, Beatmung, Vasopressor, Breitkomplextachykardie, neue Vigilanzminderung ohne Erweckbarkeit.",
        "Kein ROT-Kriterium liegt vor."),
    "shock_orange": _noul(
        "Erfüllt der Fall ein Schockraum-Kriterium ORANGE (konservativ oder operativ)?",
        "Mindestens ein ORANGE-Kriterium liegt laut `fall` vor, z. B. SpO2 unter 90 %, symptomatische Hypotonie, okklusiver Myokardinfarkt, frisches fokal-neurologisches Defizit, akutes Abdomen.",
        "Kein ORANGE-Kriterium liegt vor."),
    "ecg": _noul(
        "Sollte laut `fall` ein 12-Kanal-EKG geschrieben werden?",
        "Thoraxschmerz, Dyspnoe, Synkope, Rhythmusstörung, Elektrolytstörung, Oberbauchschmerz beim älteren Patienten oder kardiale Vorerkrankung.",
        "Kein kardialer Bezug erkennbar, z. B. isolierte Extremitätenverletzung beim jungen Patienten."),
    "iv_access": _noul(
        "Sollte laut `fall` ein peripherer Venenzugang gelegt werden?",
        "i.v.-Medikation, Volumengabe, Kontrastmittel, potenziell instabiler Patient oder absehbare Intervention.",
        "Keine i.v.-Therapie absehbar, stabiler Patient mit Bagatellbeschwerde."),
    "blood": _noul(
        "Sollte bei diesem Notaufnahme-Patienten laut `fall` eine Blutentnahme erfolgen?",
        "Laborwerte werden für Diagnose, Risikostratifizierung oder Therapie benötigt.",
        "Bagatellbeschwerde oder rein klinische Diagnose, Labor ändert das Management nicht."),
    "lab_profile": {
        "type": "choice",
        "instructions": "Angenommen, es erfolgt eine Blutentnahme: Welches EINE Laborprofil ist laut `fall` am besten geeignet?",
        "criteria": {
            "none": "Kein Labor: Allergie, Augenprobleme, Bisse/Stiche, Extremitätenprobleme, Fremdkörper, Hautausschläge, Kopfverletzung ohne weitere Kriterien, Wunden, Zahnprobleme, Rückenschmerz unterhalb des Bauchnabels, Sturz ohne internistische Ursache, Gesichtsverletzung durch Trauma.",
            "basis": "Basis: kleines Blutbild, Elektrolyte, Kreatinin, CRP, Gerinnung.",
            "basis2": "Basis 2: Basis plus BGA.",
            "thorax": "Thoraxlabor: Basis 2 plus Troponin, CK/CK-MB, D-Dimere, NT-proBNP. Nur bei Thoraxschmerz und Rückenschmerz oberhalb des Bauchnabels.",
            "bauch": "Bauchlabor: Basis plus Lipase, GOT/GPT, GGT, AP, Bilirubin. Bei allen abdominellen Schmerzen bei Erwachsenen, unabhängig von der Lokalisation.",
            "neuro_basis": "Neuro-Basis: bei Krampfanfall und Schlaganfallverdacht.",
            "polytrauma": "Polytrauma-Labor (inklusive Troponin und Kreuzblut): bei schwerem Trauma.",
            "vigilanz": "Profil unklare Vigilanzminderung mit BGA.",
        },
    },
    "monitoring": _noul(
        "Benötigt der Patient laut `fall` ein kontinuierliches Monitoring (EKG, SpO2, RR) in der Notaufnahme?",
        "Instabile oder grenzwertige Vitalparameter, Verdacht auf ACS, Rhythmusstörung, Sepsis, relevante Blutung oder Bewusstseinsstörung.",
        "Stabiler Patient ohne Risiko einer akuten Verschlechterung."),
    "sepsis_screening": _noul(
        "Ist ein Sepsis-Screening (mit Messinstrument, Blutkulturen vor Antibiose) indiziert?",
        "Infektverdacht mit Zeichen einer systemischen Reaktion oder Organdysfunktion.",
        "Kein Infekt- bzw. Sepsisverdacht."),
    "img_sono": _noul(
        "Ist eine Sonografie (Abdomen, FAST, Gefäße, Weichteile, Harnwege; ohne Echokardiografie) laut `fall` indiziert?",
        "Abdominelle, urologische, gynäkologische, Gefäß- oder Weichteilfragestellung, FAST beim Trauma.",
        "Sonografie trägt zur Fragestellung nicht bei."),
    "img_xray": _noul(
        "Ist ein konventionelles Röntgen laut `fall` indiziert?",
        "Frakturverdacht an Extremität, Thoraxröntgen bei Dyspnoe, Pneumonie oder Herzinsuffizienz.",
        "Röntgen ist nicht ausreichend oder nicht zielführend."),
    "img_ct": _noul(
        "Ist eine CT laut `fall` indiziert?",
        "Schädel-Hirn-Trauma unter Antikoagulation, Schlaganfallverdacht, LAE, Aortendissektion, Polytrauma, akutes Abdomen, Wirbelsäulentrauma.",
        "Sonografie oder Röntgen reichen, keine CT-Indikation."),
    "ct_contrast": {
        "type": "choice",
        "instructions": "Angenommen, es wird eine CT durchgeführt: Sollte sie laut `fall` mit oder ohne Kontrastmittel erfolgen?",
        "criteria": {
            "with_contrast": "Mit Kontrastmittel: z. B. LAE, Aortendissektion, Abszess, Tumor, akutes Abdomen, Gefäßdarstellung.",
            "without_contrast": "Ohne Kontrastmittel: z. B. cCT bei Trauma/Blutungsausschluss, Urolithiasis, knöcherne Frakturdiagnostik, oder Kontraindikation (Niereninsuffizienz, KM-Allergie, Hyperthyreose).",
        },
    },
    "img_mri": _noul(
        "Ist laut `fall` eine MRT (akut oder zeitnah elektiv) indiziert?",
        "Z. B. Kaudasyndrom, spinale Kompression, Schlaganfall-Zeitfenster unklar, Spondylodiszitis, Weichteil-/Bandverletzung mit Therapierelevanz.",
        "Keine MRT-Fragestellung, andere Bildgebung ausreichend."),
    "img_echo": _noul(
        "Ist laut `fall` eine Echokardiografie indiziert?",
        "Dyspnoe mit V. a. Herzinsuffizienz, Perikarderguss, Endokarditis, LAE mit Rechtsherzbelastung, Synkope mit Herzgeräusch, Schock.",
        "Keine kardiale Fragestellung für eine Echokardiografie."),
}
RULE_HINT = " Entscheide nach `hausregeln`, wo diese eine Regel enthalten; sonst nach allgemeinem notfallmedizinischem Standard."

PLACES = {"emergency_department": "Notaufnahme", "urgent_care_practice": "Notdienstpraxis (KV)"}
SPECIALTIES = {
    "internal_medicine": "Innere Medizin", "cardiology": "Kardiologie", "neurology": "Neurologie",
    "general_surgery": "Allgemein-/Viszeralchirurgie", "trauma_surgery": "Unfallchirurgie/Orthopädie",
    "urology": "Urologie", "gynecology": "Gynäkologie", "pediatrics": "Pädiatrie", "psychiatry": "Psychiatrie",
    "ent": "HNO", "ophthalmology": "Augenheilkunde", "dermatology": "Dermatologie", "other": "andere Fachabteilung"}
SHORT = {"general_surgery": "Viszeralchirurgie", "trauma_surgery": "Unfallchirurgie", "other": "andere"}     # für schmale Kärtchen
LABS = {"none": "kein Labor", "basis": "Basis", "basis2": "Basis 2", "thorax": "Thoraxlabor", "bauch": "Bauchlabor",
        "neuro_basis": "Neuro-Basis", "polytrauma": "Polytrauma-Labor", "vigilanz": "Vigilanz-Profil"}
MEASURES = (("ecg", "12-Kanal-EKG"), ("iv_access", "i.v.-Zugang"), ("blood", "Labor"), ("monitoring", "Monitoring"))
IMAGING = (("img_sono", "Sonografie"), ("img_xray", "Röntgen"), ("img_ct", "CT"), ("img_mri", "MRT"), ("img_echo", "Echo"))


def available(server: dict) -> bool:
    """Jev gibt es nur über OpenRouter; ein lokales oder anderes Sprachmodell kann diese Fragen nicht so beantworten."""
    return "openrouter.ai" in (server.get("base_url") or "").lower()


def ask(server: dict, text: str, rules: str = "", model: str = "", request=None) -> dict:
    """Fall bewerten lassen. Gibt {"noul": {Frage: Wert}, "choice": {Frage: {"choice", "p"}}, "model", "at"} zurück.

    request(server, path, body) ersetzt in Tests den Netzaufruf."""
    state = {"fall": {"kontext": CONTEXT, "anonymisierte_eingabe": text.strip()}}
    questions = QUESTIONS
    if rules.strip():
        state["hausregeln"] = rules.strip()
        questions = {k: {**q, "instructions": q["instructions"] + RULE_HINT} for k, q in QUESTIONS.items()}
    server = dict(server, timeout=min(float(server.get("timeout") or 30), 30))
    body = {"model": (model or MODEL).strip(), "state": state, "questions": questions}
    data = (request or llm._request)(server, "/systemone", body)
    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, dict) or not answers:
        raise llm.LlmError("Jev hat keine auswertbare Antwort geliefert.")
    out = {"noul": {}, "choice": {}, "model": str(data.get("model") or body["model"]), "at": time.time()}
    for key, a in answers.items():
        if not isinstance(a, dict):
            continue
        if isinstance(a.get("noul"), (int, float)):
            out["noul"][key] = float(a["noul"])
        elif a.get("choice"):
            p = (a.get("probabilities") or {}).get(a["choice"])
            out["choice"][key] = {"choice": str(a["choice"]), "p": float(p) if isinstance(p, (int, float)) else None}
    return out


def view(d: dict) -> dict:
    """Die Antworten so aufbereiten, wie das Fenster und der Text zum Kopieren sie brauchen."""
    n, c = d.get("noul") or {}, d.get("choice") or {}
    place = c.get("placement") or {}
    practice = place.get("choice") == "urgent_care_practice"
    spec = c.get("specialty") or {}
    lab = c.get("lab_profile") or {}
    ct = c.get("ct_contrast") or {}
    admission = n.get("admission")
    shock = ("ROT", n["shock_red"]) if n.get("shock_red", 0) > HIGH else \
            ("ORANGE", n["shock_orange"]) if n.get("shock_orange", 0) > HIGH else None
    rows = []
    for key, name in MEASURES:
        extra = LABS.get(lab.get("choice"), "") if key == "blood" and lab.get("choice") not in (None, "none") else ""
        rows.append((name, n.get(key), extra))
    images = [(name, n.get(key), ("mit KM" if ct.get("choice") == "with_contrast" else "ohne KM")
               if key == "img_ct" and ct.get("choice") and n.get(key, 0) >= HIGH else "") for key, name in IMAGING]
    return {
        "place": PLACES.get(place.get("choice"), ""), "place_p": place.get("p"), "practice": practice,
        "specialty": "" if practice else SPECIALTIES.get(spec.get("choice"), ""), "specialty_p": spec.get("p"),
        "ward": "" if practice else SHORT.get(spec.get("choice"), SPECIALTIES.get(spec.get("choice"), "")),
        "admission": admission, "bed": (not practice) and admission is not None and admission >= HIGH,
        "shock": shock, "sepsis": n.get("sepsis_screening", 0) >= HIGH, "measures": rows, "imaging": images,
    }


def pct(value) -> str:
    return "–" if value is None else f"{round(value * 100)} %"


def export(d: dict) -> str:
    """Klartext zum Kopieren, ohne weiteres Modell erzeugt."""
    v = view(d)
    out = ["JEV-ERSTEINSCHÄTZUNG (Vorschlag eines Modells, keine Anordnung)"]
    if v["place"]:
        out.append(f"Versorgungspfad: {v['place']} ({pct(v['place_p'])})")
    if v["shock"]:
        out.append(f"Schockraum-Kriterium {v['shock'][0]}: {pct(v['shock'][1])}")
    if v["specialty"]:
        out.append(f"Fallführende Abteilung: {v['specialty']} ({pct(v['specialty_p'])})")
    if v["admission"] is not None and not v["practice"]:
        out.append(f"Stationäre Aufnahme: {pct(v['admission'])}"
                   + (f"; Bett suchen in: {v['specialty'] or 'Abteilung offen'}" if v["bed"] else ""))
    out += [f"{name}: {pct(p)}" + (f" ({extra})" if extra else "") for name, p, extra in v["measures"]]
    if v["sepsis"]:
        out.append("Sepsis-Screening und Blutkulturen vor Antibiose")
    out += [f"{name}: {pct(p)}" + (f" ({extra})" if extra else "") for name, p, extra in v["imaging"]]
    return "\n".join(out)
