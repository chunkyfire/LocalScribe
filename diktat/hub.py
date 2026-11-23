"""Das App-Fenster: Verlauf, Wörterbuch, Textbausteine, KI-Nachbearbeitung, Einstellungen."""
import collections
import copy
import difflib
import logging
import math
import os
import re
import threading
import time

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QTimer, Signal

import secrets

from . import __version__, config, engine, fach, handy, jev, llm, pflege, schutz, training, visite, wortschatz
from . import sprecher
from .longform import LongJob
from .ui import make_icon, make_pixmap, private_mime

log = logging.getLogger("diktat")

# Formulierungen für unauffällige Untersuchungsbefunde, als Textbausteine zum Abrufen per Stichwort.
# Reine Schreibhilfe: Der Baustein steht nur da, wenn man ihn diktiert, und muss zum Befund passen.
NORMAL = {
    "Normalbefund Allgemein": "Allgemeinzustand gut, Ernährungszustand normal. Haut und Schleimhäute rosig, kein Ikterus, keine Zyanose, keine Ruhedyspnoe.",
    "Normalbefund Kopf und Hals": "Kopf und Hals: Rachen reizlos, keine Lymphknotenschwellungen, Schilddrüse nicht vergrößert, keine Halsvenenstauung.",
    "Normalbefund Herz": "Herz: Herztöne rein und rhythmisch, keine pathologischen Geräusche.",
    "Normalbefund Lunge": "Lunge: Vesikuläres Atemgeräusch beidseits, keine Rasselgeräusche, kein Giemen, sonorer Klopfschall.",
    "Normalbefund Abdomen": "Abdomen: Weich, kein Druckschmerz, keine Abwehrspannung, keine Resistenzen, Darmgeräusche regelrecht in allen vier Quadranten.",
    "Normalbefund Nierenlager": "Nierenlager beidseits frei, Wirbelsäule nicht klopfschmerzhaft.",
    "Normalbefund Extremitäten": "Extremitäten: Keine Ödeme, Fußpulse beidseits tastbar, Waden weich und nicht druckschmerzhaft.",
    "Normalbefund Neurologie": "Neurologie: Wach, zu Person, Ort, Zeit und Situation orientiert. Pupillen isokor, prompte Lichtreaktion beidseits. Keine Paresen, kein sensibles Defizit, kein Meningismus.",
    "Normalbefund EKG": "EKG: Sinusrhythmus, Indifferenztyp, regelrechte Überleitungszeiten, keine Erregungsrückbildungsstörungen.",
    "Normalbefund Haut": "Haut: Warm, trocken, keine Effloreszenzen, Rekapillarisierungszeit unter zwei Sekunden.",
    # eine Vorlage mit Sprungmarken: Umschalt + F8 springt von Marke zu Marke, dort weiterdiktieren
    "Vorlage Aufnahme": "Anamnese: [ ]\nVorerkrankungen: [ ]\nMedikation: [ ]\nBefund: [ ]\nBeurteilung: [ ]\nProcedere: [ ]",
}

STYLE = """
QWidget { background: transparent; color: #F1F3F2; font-family: "Segoe UI Variable Text", "Segoe UI"; font-size: 10pt; }
QDialog, QMessageBox, QToolTip { background: #121416; }
QToolTip { color: #F1F3F2; border: 1px solid #2A2E33; padding: 5px 8px; }
QLabel, QCheckBox { background: transparent; }
QLabel#h1 { font-family: "Space Grotesk", "Segoe UI Variable Display", "Segoe UI"; font-size: 20pt; font-weight: 500; }
QLabel#h2 { font-size: 11pt; font-weight: 600; }
QLabel#brand { font-family: "Space Grotesk", "Segoe UI Variable Display", "Segoe UI"; font-size: 13.5pt; font-weight: 700; }
QLabel#muted, QLabel#time { color: #9AA0A6; }
QLabel#day { color: #8C8C8C; font-size: 8pt; font-weight: 700; padding: 14px 4px 6px 4px; }
QLabel#num { font-size: 16pt; font-weight: 600; }
QLabel#tag { color: #0B0B0B; background: #C6FF3D; border-radius: 7px; padding: 1px 7px;
             font-size: 8pt; font-weight: 600; }
QLabel#ok { color: #C6FF3D; }
QLabel#bad { color: #FF7A6B; }
QFrame#side { background: rgba(255, 255, 255, 0.028); border: none; border-right: 1px solid rgba(255, 255, 255, 0.07); }
QFrame#side QPushButton { text-align: left; padding: 11px 16px; border: 1px solid transparent; border-radius: 12px;
                          color: #B9BEC4; background: transparent; font-size: 10.5pt; }
QFrame#side QPushButton:hover { background: rgba(255, 255, 255, 0.05); }
QFrame#side QPushButton:checked { background: rgba(198, 255, 61, 0.10); border: 1px solid rgba(198, 255, 61, 0.28);
                                  color: #C6FF3D; font-weight: 600; }
QFrame#side QPushButton#update { padding: 9px 12px; font-size: 9.5pt; font-weight: 600; color: #C6FF3D;
                                 background: rgba(198, 255, 61, 0.08); border: 1px solid rgba(198, 255, 61, 0.35); }
QFrame#side QPushButton#update:hover { background: rgba(198, 255, 61, 0.16); }
QFrame#side QPushButton#update:disabled { color: #9AA0A6; background: rgba(255, 255, 255, 0.04);
                                          border: 1px solid rgba(255, 255, 255, 0.12); }
QFrame#side QPushButton#updateGo { padding: 9px 12px; font-size: 9.5pt; font-weight: 700; color: #0B0B0B;
                                   background: #C6FF3D; border: 1px solid #C6FF3D; }
QFrame#side QPushButton#updateGo:hover { background: #D4FF6A; }
QFrame#side QPushButton#updateIdle { padding: 7px 12px; font-size: 9pt; color: #8A9096; background: transparent;
                                     border: 1px solid transparent; }
QFrame#side QPushButton#updateIdle:hover { color: #C9CED4; background: rgba(255, 255, 255, 0.05); }
QFrame#side QPushButton#profile { padding: 8px 12px; font-size: 9.5pt; color: #D7DBDF; background: rgba(255, 255, 255, 0.04);
                                  border: 1px solid rgba(255, 255, 255, 0.10); }
QFrame#side QPushButton#profile:hover { background: rgba(255, 255, 255, 0.08); }
QFrame#side QPushButton#profile::menu-indicator { image: none; width: 0; }
QFrame#card { background: rgba(255, 255, 255, 0.045); border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 18px; }
QFrame#card QWidget { background: transparent; }
QFrame#row { background: transparent; border: none; border-bottom: 1px solid rgba(255, 255, 255, 0.06); }
QFrame#row:hover { background: rgba(255, 255, 255, 0.04); }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QFrame#card QLineEdit, QFrame#card QPlainTextEdit,
QFrame#card QComboBox, QFrame#card QSpinBox {
    background: rgba(0, 0, 0, 0.30); border: 1px solid rgba(255, 255, 255, 0.11); border-radius: 12px; padding: 7px 12px;
    selection-background-color: #C6FF3D; selection-color: #0B0B0B; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #C6FF3D; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #151515; border: 1px solid #2A2A2A;
                              selection-background-color: #C6FF3D; selection-color: #0B0B0B; }
QPushButton, QFrame#card QPushButton { background: rgba(255, 255, 255, 0.065); border: 1px solid rgba(255, 255, 255, 0.12);
                                       border-radius: 11px; padding: 7px 15px; }
QPushButton:hover { border-color: rgba(255, 255, 255, 0.34); background: rgba(255, 255, 255, 0.10); }
QPushButton#tab, QFrame#card QPushButton#tab { border-radius: 12px; padding: 6px 16px; color: #B9BEC4; }
QPushButton#tab:checked, QFrame#card QPushButton#tab:checked { color: #C6FF3D; background: rgba(198, 255, 61, 0.10);
                                                              border-color: rgba(198, 255, 61, 0.45); }
QPushButton#seg { border-radius: 10px; padding: 4px 12px; color: #9AA0A6; background: transparent;
                  border: 1px solid rgba(255, 255, 255, 0.10); font-size: 12px; }
QPushButton#seg:checked { color: #0B0B0B; background: #C6FF3D; border-color: #C6FF3D; }
QPushButton:disabled { color: #5A5A5A; }
QPushButton#primary, QFrame#card QPushButton#primary { background: #C6FF3D; color: #0B0B0B;
                                                       border: none; font-weight: 600; }
QPushButton#primary:hover, QFrame#card QPushButton#primary:hover { background: #D4FF6A; }
QPushButton#primary:disabled, QFrame#card QPushButton#primary:disabled { background: rgba(255, 255, 255, 0.08); color: #6A6F75; }
QPushButton#ghost, QFrame#card QPushButton#ghost, QFrame#row QPushButton {
    background: transparent; border: none; color: #8C8C8C; padding: 4px 8px; }
QPushButton#ghost:hover, QFrame#row QPushButton:hover { color: #C6FF3D; }
QPushButton::menu-indicator { image: none; width: 0; }
QMenu { background: #15181B; border: 1px solid #2A2E33; border-radius: 10px; padding: 5px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: #C6FF3D; color: #0B0B0B; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid rgba(255, 255, 255, 0.22); border-radius: 5px;
                       background: rgba(0, 0, 0, 0.30); }
QCheckBox::indicator:checked { background: #C6FF3D; border-color: #C6FF3D; }
QListWidget, QTableWidget { background: rgba(0, 0, 0, 0.24); border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 14px;
                            outline: none; gridline-color: rgba(255, 255, 255, 0.06); }
QListWidget::item { padding: 7px 10px; }
QListWidget::item:selected, QTableWidget::item:selected { background: rgba(198, 255, 61, 0.10); color: #C6FF3D; }
QHeaderView { background: transparent; }
QHeaderView::section { background: rgba(255, 255, 255, 0.04); color: #9AA0A6; border: none;
                       border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding: 8px 10px; font-weight: 600; }
QTableCornerButton::section { background: transparent; border: none; }
QTableWidget::item { padding: 0 10px; }
QTableWidget QLineEdit { background: #15181B; border-radius: 0; padding: 0 9px; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; border: none; }
QScrollArea { border: none; }
QProgressBar { background: rgba(255, 255, 255, 0.08); border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }
QProgressBar::chunk { background: #C6FF3D; border-radius: 3px; }
QPushButton#rec, QFrame#card QPushButton#rec { background: #C6FF3D; color: #0B0B0B; border: none;
    border-radius: 48px; font-size: 11pt; font-weight: 700; }
QPushButton#recOn, QFrame#card QPushButton#recOn { background: #FF5A4D; color: #0B0B0B; border: none;
    border-radius: 48px; font-size: 11pt; font-weight: 700; }
QPushButton#rec:disabled { background: #2A2A2A; color: #6A6A6A; }
QLabel#clock { font-size: 22pt; font-weight: 600; }
QFrame#drop { background: rgba(255, 255, 255, 0.03); border: 1px dashed rgba(255, 255, 255, 0.22); border-radius: 18px; }
QFrame#drop[over="true"] { border-color: #C6FF3D; background: #141810; }
QFrame#drop QWidget { background: transparent; }
QFrame#box { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.11); border-radius: 18px; }
QFrame#box QWidget { background: transparent; }
QFrame#box QLabel#boxTitle { color: #C6FF3D; font-size: 10pt; font-weight: 700; }
QFrame#box QLabel#kicker { color: #6F6F6F; font-size: 8pt; font-weight: 700; padding-top: 4px; }
QFrame#box QLabel#strong { font-weight: 600; }
QFrame#box QLabel#pct { font-weight: 700; }
QFrame#box QLabel#warn { color: #FFB454; font-weight: 600; }
QFrame#box QLabel#chip, QFrame#box QLabel#chipOff, QFrame#box QLabel#chipWarn, QFrame#box QLabel#chipRed {
    border-radius: 10px; padding: 4px 10px; font-weight: 600; }
QFrame#box QLabel#chip { background: #1D2A0B; color: #C6FF3D; border: 1px solid #3C5412; }
QFrame#box QLabel#chipOff { background: rgba(255, 255, 255, 0.05); color: #9AA0A6; border: 1px solid rgba(255, 255, 255, 0.09); font-weight: 400; }
QFrame#box QLabel#chipWarn { background: #2A1D09; color: #FFB454; border: 1px solid #5C4012; }
QFrame#box QLabel#chipRed { background: #2F1210; color: #FF7A6B; border: 1px solid #6E2A24; }
QFrame#box QLabel#chipSmall { background: #1D2A0B; color: #C6FF3D; border-radius: 6px; padding: 0 6px; font-size: 8pt; }
QFrame#box QFrame#alert { background: #18130A; border: none; border-left: 3px solid #FFB454; border-radius: 6px; }
QFrame#box QFrame#ask { background: rgba(0, 0, 0, 0.24); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; }
QFrame#box QPushButton#fold { background: transparent; border: none; text-align: left; padding: 5px 0; font-weight: 600; }
QFrame#box QPushButton#fold:hover { color: #C6FF3D; }
QFrame#box QProgressBar { background: #1D1D1D; max-height: 4px; min-height: 4px; border-radius: 2px; }
QFrame#box QProgressBar#on::chunk { background: #C6FF3D; border-radius: 2px; }
QFrame#box QProgressBar#dim::chunk { background: #3A3A3A; border-radius: 2px; }
QFrame#box QLabel { font-size: 9pt; }
QFrame#box QLabel#chipLine { background: transparent; color: #C6FF3D; border: 1px solid #3C5412; border-radius: 9px;
    padding: 2px 8px; font-weight: 600; }
QPushButton#recPill { background: #C6FF3D; color: #0B0B0B; border: none; border-radius: 18px; padding: 9px 20px; font-weight: 700; }
QPushButton#recPill:hover { background: #D4FF6A; }
QPushButton#recHero { background: #C6FF3D; color: #0B0B0B; border: none; border-radius: 32px; padding: 0 34px;
                      font-size: 12.5pt; font-weight: 600; }
QPushButton#recHero:hover { background: #D4FF6A; }
QPushButton#recHero:disabled { background: #2A2A2A; color: #6A6A6A; }
QPushButton#recPillOn { background: #FF7A4D; color: #16100D; border: none; border-radius: 18px; padding: 9px 20px; font-weight: 700; }
QPushButton#recPillOn:hover { background: #FF9068; }
QPushButton#fileBtn { padding: 9px 18px; border-radius: 12px; }
QPushButton#recPill:disabled { background: #2A2A2A; color: #6A6A6A; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.14); border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.28); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

PRESETS = [("Ollama (lokal)", "http://localhost:11434/v1"),
           ("LM Studio (lokal)", "http://localhost:1234/v1"),
           ("OpenRouter", "https://openrouter.ai/api/v1"),
           ("Noirdoc", "https://api.noirdoc.de/v1"),
           ("IONOS AI Model Hub", "https://openai.inference.de-txl.ionos.com/v1"),
           ("STACKIT AI Model Serving", "https://api.openai-compat.model-serving.eu01.onstackit.cloud/v1"),
           ("Eigene Adresse", "")]
# Welches Modell wofür: gemessen am 19.11.2026 an erfundenen Fällen (werkzeug/messen/ERGEBNIS.md)
ADVICE = (("noirdoc", "Noirdoc verarbeitet in der EU. Die Maskierung dort ist ab Werk aus: Lass den Schutz unten an. Modelle "
                      "zweier Unteranbieter ohne Verschwiegenheitsverpflichtung fehlen in der Liste mit Absicht."),
          ("ionos", "Empfehlung bei IONOS: gpt-oss-120b („Modelle abrufen“, dann auswählen). In der Messung 10 bis 17 Sekunden "
                    "je Arztbrief; verhörte Arzneimittelnamen bemerkt es seltener als das Standardmodell bei OpenRouter."),
          ("stackit", "Empfehlung bei STACKIT: gpt-oss-120b oder Gemma 4 31b („Modelle abrufen“, dann auswählen). Beide schreiben "
                      "einen Arztbrief in 6 bis 17 Sekunden; verhörte Arzneimittelnamen bemerken sie seltener als das "
                      "Standardmodell bei OpenRouter."))
# Kurze Liste der Modelle: gemessen am 23.11.2026 an sechs erfundenen Diktaten (Visite, Pflegebericht) über OpenRouter
MODEL_TIP = ("Das oberste Modell ist die Vorgabe. Gemessen an kurzen Aufträgen: Gemini 4 Hydrogen 5 bis 14 Sekunden, "
             "Gemini 3.1 Flash Lite 1 bis 4 Sekunden, dafür übersieht das kleine Modell eher einen Hörfehler.")
ADVICE_LOCAL = ("Auf dem eigenen Rechner: Für Glätten und Zusammenfassen genügt ein Modell um 9 Milliarden Parameter (etwa "
                "Qwen3.5 9B, braucht rund 8 GB Grafikspeicher). Für Arztbrief und Übergabe sind so kleine Modelle zu ungenau: "
                "In der Messung übernahmen sie Hörfehler oder setzten Werte ein, die niemand gesagt hatte.")


def glyph(kind, color):
    """Kleines Zeichen für den Update-Knopf: Pfeil in die Ablage (laden) oder Kreispfeil (neu starten)."""
    pm = QtGui.QPixmap(48, 48)
    pm.fill(Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtGui.QPen(QtGui.QColor(color), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    P = QtCore.QPointF
    if kind == "person":
        p.drawEllipse(P(24, 16), 8, 8)
        p.drawArc(QtCore.QRectF(8, 29, 32, 30), 20 * 16, 140 * 16)
    elif kind == "down":
        p.drawLine(P(24, 7), P(24, 29))
        p.drawPolyline([P(14, 20), P(24, 30), P(34, 20)])
        p.drawLine(P(10, 41), P(38, 41))
    else:
        p.drawArc(QtCore.QRectF(9, 9, 30, 30), 110 * 16, -300 * 16)
        p.drawPolyline([P(9, 8), P(17, 11), P(11, 19)])
    p.end()
    return QtGui.QIcon(pm)


FONT = ["Space Grotesk", "Segoe UI Variable Display", "Segoe UI"]     # Überschriften und Zeit; Space Grotesk liegt bei


def load_fonts():
    """Die mitgelieferte Schrift einmal anmelden (Space Grotesk, SIL Open Font License; diktat/schrift)."""
    if getattr(load_fonts, "done", False):
        return
    load_fonts.done = True
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schrift")
    try:
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith(".ttf"):
                QtGui.QFontDatabase.addApplicationFont(os.path.join(folder, name))
    except OSError:
        log.warning("Schrift nicht gefunden: %s", folder)      # dann greift die Schrift von Windows


def _canvas(size):
    """Zeichenfläche für ein Zeichen auf 24 x 24 Einheiten, dreifach aufgelöst: scharf bei jeder Bildschirmskalierung."""
    pm = QtGui.QPixmap(size * 3, size * 3)
    pm.setDevicePixelRatio(3)
    pm.fill(Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.scale(size / 24, size / 24)
    return pm, p


def _mic(p):
    p.drawRoundedRect(QtCore.QRectF(9, 3, 6, 12), 3, 3)
    p.drawArc(QtCore.QRectF(5, 4, 14, 14), 180 * 16, 180 * 16)
    p.drawLine(QtCore.QPointF(12, 18), QtCore.QPointF(12, 21))


def rec_icon(kind, color="#0B0B0B", size=24):
    """Mikrofon oder Stopp-Quadrat für den Aufnahmeknopf: gezeichnet und damit genau mittig, kein Schriftzeichen."""
    pm, p = _canvas(size)
    if kind == "stop":
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QColor(color))
        p.drawRoundedRect(QtCore.QRectF(6.5, 6.5, 11, 11), 2.2, 2.2)
    else:
        p.setPen(QtGui.QPen(QtGui.QColor(color), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        _mic(p)
    p.end()
    return QtGui.QIcon(pm)


def nav_icon(kind, size=18):
    """Zeichen vor den Menüpunkten: grau, beim gewählten Punkt in Lime."""
    P, R = QtCore.QPointF, QtCore.QRectF
    icon = QtGui.QIcon()
    for color, state in (("#A3A9B0", QtGui.QIcon.Off), ("#C6FF3D", QtGui.QIcon.On)):
        pm, p = _canvas(size)
        p.setPen(QtGui.QPen(QtGui.QColor(color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if kind == "Verlauf":                               # Uhr
            p.drawEllipse(P(12, 12), 8.5, 8.5)
            p.drawPolyline([P(12, 7.5), P(12, 12), P(15, 14)])
        elif kind == "Aufnahme":                            # Mikrofon
            _mic(p)
        elif kind == "Übergabe":                            # zwei Pfeile, hin und zurück
            p.drawLine(P(4, 8), P(17, 8))
            p.drawPolyline([P(14, 5), P(17, 8), P(14, 11)])
            p.drawLine(P(20, 16), P(7, 16))
            p.drawPolyline([P(10, 13), P(7, 16), P(10, 19)])
        elif kind == "Wortschatz":                          # Buch
            path = QtGui.QPainterPath(P(5, 4.5))
            path.lineTo(16, 4.5)
            path.arcTo(R(13, 4.5, 6, 6), 90, -90)
            path.lineTo(19, 19.5)
            path.lineTo(8, 19.5)
            path.arcTo(R(5, 13.5, 6, 6), 270, -90)
            path.closeSubpath()
            p.drawPath(path)
            p.drawLine(P(9, 9), P(15, 9))
            p.drawLine(P(9, 13), P(13, 13))
        else:                                               # Einstellungen: zwei Schieberegler
            p.drawLine(P(4, 7), P(14, 7))
            p.drawLine(P(18, 7), P(20, 7))
            p.drawEllipse(P(16, 7), 2, 2)
            p.drawLine(P(4, 17), P(6, 17))
            p.drawLine(P(10, 17), P(20, 17))
            p.drawEllipse(P(8, 17), 2, 2)
        p.end()
        icon.addPixmap(pm, QtGui.QIcon.Normal, state)
    return icon


class Clock(QtWidgets.QWidget):
    """Zeitanzeige in der Schrift der Überschriften. Jede Ziffer bekommt dieselbe Breite, damit beim Zählen nichts
    springt; die Höhe ist genau die der Ziffern, damit nichts abgeschnitten wird und die Abstände stimmen."""

    def __init__(self, px=104, color="#F1F3F2"):
        super().__init__()
        self.text, self.color = "00:00", QtGui.QColor(color)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.set_px(px)

    def set_px(self, px):
        self.px = max(12, int(px))
        self.font_ = QtGui.QFont()
        self.font_.setFamilies(FONT)
        self.font_.setPixelSize(self.px)
        self.font_.setWeight(QtGui.QFont.Light)
        fm = QtGui.QFontMetricsF(self.font_)
        self.cell = max(fm.horizontalAdvance(d) for d in "0123456789") * 0.95
        self.colon = fm.horizontalAdvance(":") * 0.9
        box = fm.tightBoundingRect("0123456789:")
        self.base = 3 - box.top()
        self.high = int(box.height() + 6.99)
        self._size()

    def _size(self):
        width = sum(self.colon if c == ":" else self.cell for c in self.text)
        self.setFixedSize(int(width + 2.99), self.high)

    def setText(self, text):
        if text != self.text:
            grow = len(text) != len(self.text)
            self.text = text
            if grow:
                self._size()
            self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.TextAntialiasing)
        p.setFont(self.font_)
        p.setPen(self.color)
        fm, x = QtGui.QFontMetricsF(self.font_), 1.0
        for c in self.text:
            wide = self.colon if c == ":" else self.cell
            p.drawText(QtCore.QPointF(x + (wide - fm.horizontalAdvance(c)) / 2, self.base), c)
            x += wide
        p.end()


class Wave(QtWidgets.QWidget):
    """Wellenform aus Strichen: in Ruhe eine feste Form, bei der Aufnahme der Pegel der letzten Sekunden (neu = rechts)."""
    LIME, GREY = QtGui.QColor("#C6FF3D"), QtGui.QColor(255, 255, 255, 51)

    def __init__(self, bars=64, height=96, width=None):
        super().__init__()
        self.n, self.live = bars, False
        self.setFixedHeight(height)
        if width:
            self.setFixedWidth(width)
        else:
            self.setMinimumWidth(160)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        half = bars / 2
        self.rest = [0.08 + 0.74 * abs(math.sin(i * 1.7) * math.sin(i * 0.37 + 1)) * (0.35 + 0.65 * (1 - abs(i - half) / half))
                     for i in range(bars)]
        self.levels = collections.deque([0.0] * bars, maxlen=bars)

    def start(self):
        self.live = True
        self.levels.extend([0.0] * self.n)
        self.update()

    def stop(self):
        self.live = False
        self.update()

    def feed(self, level):
        """level: Effektivwert des letzten Tonstücks (0 bis 1); Sprache liegt meist zwischen 0,01 und 0,2."""
        self.levels.append(min(1.0, (max(0.0, level) * 9) ** 0.6))
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        step = self.width() / self.n
        bar = max(2.0, min(4.0, step * 0.45))
        values = list(self.levels) if self.live else self.rest
        for i, v in enumerate(values):
            hot = i >= self.n - 12 if self.live else abs(i - self.n / 2 + 0.5) <= 6
            h = max(bar, v * self.height())
            p.setBrush(self.LIME if hot and (v > 0.04 or not self.live) else self.GREY)
            p.drawRoundedRect(QtCore.QRectF((i + 0.5) * step - bar / 2, (self.height() - h) / 2, bar, h), bar / 2, bar / 2)
        p.end()


class Hero(QtWidgets.QWidget):
    """Leerer Zustand der Seite Aufnahme: große Zeit, Wellenform, breiter Startknopf, darunter „Datei laden“.
    Passt sich der Höhe an: Wird es eng (kleines Fenster, Band mit einem Download darüber), werden Zeit, Wellenform
    und Abstände kleiner, zuletzt entfällt die Wellenform. Abgeschnitten oder übereinander liegt nie etwas."""

    def __init__(self, start, load):
        super().__init__()
        self.clock = Clock(104)
        self.wave = Wave(64, 96, 576)
        self.go = button("  Aufnahme starten", start, "recHero")
        self.go.setIconSize(QtCore.QSize(24, 24))
        self.go.setIcon(rec_icon("mic"))
        glow = QtWidgets.QGraphicsDropShadowEffect(self.go)
        glow.setBlurRadius(48)
        glow.setOffset(0, 0)
        glow.setColor(QtGui.QColor(198, 255, 61, 66))
        self.go.setGraphicsEffect(glow)
        self.file = button("Datei laden …", load, "fileBtn")
        self.file.setToolTip("Audio- oder Videodatei transkribieren. Sie verlässt diesen Rechner nicht.")
        self.hint = label("Ein zweiter Klick beendet. Der Text läuft live mit und wird gespeichert.", "muted")
        self.note = label("", "bad")
        self.note.setAlignment(Qt.AlignHCenter)
        self.note.setWordWrap(True)
        self.note.hide()
        self.lay = QtWidgets.QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.addStretch(5)
        self.lay.addWidget(self.clock, 0, Qt.AlignHCenter)
        self.lay.addWidget(self.wave, 0, Qt.AlignHCenter)
        self.lay.addWidget(self.go, 0, Qt.AlignHCenter)
        self.lay.addLayout(hbox(None, self.file, self.hint, None, spacing=14))
        self.lay.addWidget(self.note)
        self.lay.addStretch(6)
        self.setMinimumHeight(150)
        self.scale = None
        self.fit(1.0, True)

    def say(self, text):
        self.note.setText(text)
        self.note.setVisible(bool(text))
        self._refit()

    def need(self, s, wave):
        """Höhe des Inhalts bei Maßstab s."""
        gap, rows = round(26 * s), 3 if wave else 2
        note = self.note.sizeHint().height() + gap if self.note.isVisible() else 0
        return (Clock(round(104 * s)).high + (round(96 * s) if wave else 0) + max(48, round(64 * s))
                + self.file.sizeHint().height() + rows * gap + note)

    def fit(self, s, wave):
        if (s, wave) == self.scale:
            return
        self.scale = (s, wave)
        high = max(48, round(64 * s))
        self.clock.set_px(round(104 * s))
        self.wave.setVisible(wave)
        self.wave.setFixedSize(round(576 * s), round(96 * s))
        self.go.setFixedHeight(high)
        self.go.setStyleSheet(f"border-radius: {high // 2}px;")     # Rundung nie größer als die halbe Höhe
        self.lay.setSpacing(round(26 * s))

    def _refit(self):
        room = self.height() - 8
        for s in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
            if self.need(s, True) <= room:
                return self.fit(s, True)
        self.fit(0.5, self.need(0.5, True) <= room + 40)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refit()


def restyle(widget, name):
    """Objektname wechseln und den Stil dafür neu anwenden."""
    widget.setObjectName(name)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def label(text, name=None, wrap=False):
    w = QtWidgets.QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


SITE = "https://cemmec.ai"
LINKEDIN = "https://www.linkedin.com/in/cem-%C3%B6zel-ab0b37113"
REPO = "https://github.com/chunkyfire/LocalScribe"


def link(html_text):
    """Grauer Text mit anklickbaren Verweisen, die im Browser aufgehen."""
    w = label(html_text, "muted", wrap=True)
    w.setTextFormat(Qt.RichText)
    w.setOpenExternalLinks(True)
    return w


def button(text, slot=None, name=None):
    b = QtWidgets.QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    if name:
        b.setObjectName(name)
    if slot:
        b.clicked.connect(slot)
    return b


def card(*rows, spacing=10):
    f = QtWidgets.QFrame(objectName="card")
    lay = QtWidgets.QVBoxLayout(f)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(spacing)
    for r in rows:
        if isinstance(r, QtWidgets.QLayout):
            lay.addLayout(r)
        else:
            lay.addWidget(r)
    return f


def hbox(*items, spacing=10):
    lay = QtWidgets.QHBoxLayout()
    lay.setSpacing(spacing)
    for it in items:
        if it is None:
            lay.addStretch(1)
        elif isinstance(it, QtWidgets.QLayout):
            lay.addLayout(it)
        elif isinstance(it, tuple):
            (lay.addLayout if isinstance(it[0], QtWidgets.QLayout) else lay.addWidget)(it[0], it[1])
        else:
            lay.addWidget(it)
    return lay


def form(*pairs):
    g = QtWidgets.QGridLayout()
    g.setHorizontalSpacing(14)
    g.setVerticalSpacing(10)
    g.setColumnStretch(1, 1)
    for i, (name, field) in enumerate(pairs):
        top = isinstance(field, QtWidgets.QPlainTextEdit)
        cap = label(name, "muted")
        if top:
            cap.setContentsMargins(0, 7, 0, 0)
        g.addWidget(cap, i, 0, Qt.AlignLeft | (Qt.AlignTop if top else Qt.AlignVCenter))
        if isinstance(field, QtWidgets.QLayout):
            g.addLayout(field, i, 1)
        else:
            g.addWidget(field, i, 1)
    return g


KEY_LABEL = {"ctrl": "Strg", "win": "Win", "alt": "Alt", "shift": "Umschalt", "space": "Leertaste"}


def keys_text(keys) -> str:
    return " + ".join(KEY_LABEL.get(k, k.upper()) for k in (keys or []))


def show_notes(parent, items, version):
    """Fenster „Was ist neu“: je Fassung eine Überschrift und ihre Punkte."""
    box = QtWidgets.QDialog(parent)
    box.setWindowTitle(f"Was ist neu in LocalScribe {version}")
    box.setStyleSheet(STYLE)
    box.resize(640, 520)
    inner = QtWidgets.QVBoxLayout()
    inner.setContentsMargins(22, 18, 22, 18)
    inner.setSpacing(8)
    if not items:
        inner.addWidget(label("Für diese Fassung liegen hier keine Angaben vor. Alle Änderungen stehen bei GitHub "
                              "unter Releases.", "muted", wrap=True))
    for number, text in items:
        inner.addWidget(label(f"LocalScribe {number}", "h2"))
        for point in re.split(r"\n(?=- )", text):
            inner.addWidget(label(point.lstrip("- ").strip() if point.startswith("- ") else point, wrap=True))
        inner.addSpacing(8)
    inner.addStretch(1)
    body = QtWidgets.QWidget()
    body.setLayout(inner)
    area = QtWidgets.QScrollArea(widgetResizable=True)
    area.setFrameShape(QtWidgets.QFrame.NoFrame)
    area.setWidget(body)
    lay = QtWidgets.QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 12)
    lay.addWidget(area, 1)
    foot = hbox(None, button("Schließen", box.accept, "primary"))
    foot.setContentsMargins(0, 0, 18, 0)
    lay.addLayout(foot)
    box.exec()


class KeyField(QtWidgets.QLineEdit):
    """Tastenkürzel festlegen: hineinklicken, Kombination drücken, fertig. Entf leert, Esc bricht ab."""
    sig_keys = Signal(object)
    IDLE = "Klicken, dann Tasten drücken"

    def __init__(self, ctl, single=False, optional=True):
        super().__init__(placeholderText=self.IDLE)
        self.ctl, self.single, self.optional = ctl, single, optional
        self.listening, self.before = False, ""
        self.setReadOnly(hasattr(ctl, "capture_keys"))         # ohne Tastatur-Haken bleibt das Feld zum Tippen
        self.setCursor(Qt.PointingHandCursor)
        self.sig_keys.connect(self._got)                       # die Meldung kommt aus dem Tastatur-Thread

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        if self.isReadOnly() and not self.listening:
            self.listening, self.before = True, self.text()
            self.clear()
            self.setPlaceholderText("Jetzt drücken …" + ("  Entf leert," if self.optional else "") + "  Esc bricht ab")
            self.ctl.capture_keys(self.sig_keys.emit)

    def focusOutEvent(self, e):
        if self.listening:
            self.ctl.capture_keys(None)
            self._got(None)
        super().focusOutEvent(e)

    def _got(self, keys):
        if not self.listening:
            return
        self.listening = False
        self.setPlaceholderText(self.IDLE)
        if keys is None or (not keys and not self.optional):
            return self.setText(self.before)
        self.setText(keys_text(keys[-1:] if self.single else keys))


class Page(QtWidgets.QWidget):
    """Seite mit Überschrift, optionalem Untertitel und scrollbarem Inhalt."""

    def __init__(self, title, subtitle="", scroll=True):
        super().__init__()
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(30, 26, 30, 20)
        outer.setSpacing(14)
        self.head = QtWidgets.QHBoxLayout()
        self.head.addWidget(label(title, "h1"))
        self.head.addStretch(1)
        outer.addLayout(self.head)
        if subtitle:
            outer.addWidget(label(subtitle, "muted", wrap=True))
        self.body = QtWidgets.QVBoxLayout()
        self.body.setSpacing(14)
        if scroll:
            inner = QtWidgets.QWidget()
            inner.setLayout(self.body)
            self.body.setContentsMargins(0, 0, 8, 0)
            area = QtWidgets.QScrollArea(widgetResizable=True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(inner)
            outer.addWidget(area, 1)
        else:
            outer.addLayout(self.body, 1)

    def saved(self, note, text="Gespeichert", ok=True):
        restyle(note, "ok" if ok else "bad")
        note.setText(text)
        if ok:
            QTimer.singleShot(2500, lambda: note.setText(""))


# ---------------------------------------------------------------- Verlauf
class Row(QtWidgets.QFrame):
    def __init__(self, page, ident, zeit, text, prompt):
        super().__init__(objectName="row")
        self.page, self.ident, self.text = page, ident, text
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Klicken kopiert")
        self.stamp = time.strftime("%H:%M", time.localtime(zeit))
        self.time = label(self.stamp, "time")
        self.time.setFixedWidth(58)
        shown = text.strip()
        if len(shown) > 500:  # lange Aufnahmen: kopiert wird trotzdem alles
            shown = shown[:500].rstrip() + " …"
        body = label(shown, wrap=True)
        body.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 11, 6, 11)
        lay.setSpacing(10)
        lay.addWidget(self.time, 0, Qt.AlignTop)
        lay.addWidget(body, 1)
        side = QtWidgets.QHBoxLayout()
        side.setSpacing(0)
        if prompt:
            side.addWidget(label(prompt, "tag"), 0, Qt.AlignTop)
            side.addSpacing(6)
        names = page.prompt_names()
        if names:
            ki = button("KI")
            ki.setToolTip("Mit einem Prompt nachbearbeiten")
            menu = QtWidgets.QMenu(ki)
            for n in names:
                menu.addAction(n, lambda n=n: page.ctl.rework(self.text, n))
            ki.setMenu(menu)
            side.addWidget(ki, 0, Qt.AlignTop)
        side.addWidget(button("Löschen", lambda: page.delete(self.ident)), 0, Qt.AlignTop)
        lay.addLayout(side)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            QtGui.QGuiApplication.clipboard().setMimeData(private_mime(self.text))
            restyle(self.time, "ok")
            self.time.setText("Kopiert")
            QTimer.singleShot(1300, self._reset)

    def _reset(self):
        try:
            restyle(self.time, "time")
            self.time.setText(self.stamp)
        except RuntimeError:
            pass  # Zeile wurde inzwischen neu aufgebaut


class HistoryPage(Page):
    def __init__(self, ctl):
        super().__init__("Verlauf", scroll=False)
        self.ctl = ctl
        self.search = QtWidgets.QLineEdit(placeholderText="Suchen …")
        self.search.setFixedWidth(240)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.head.addWidget(self.search)

        self.nums = [label("0", "num") for _ in range(3)]
        tiles = QtWidgets.QHBoxLayout()
        tiles.setSpacing(12)
        for num, cap in zip(self.nums, ("Wörter gesamt", "Wörter pro Minute", "Wörter heute")):
            col = QtWidgets.QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(num)
            col.addWidget(label(cap, "muted"))
            tiles.addWidget(card(col), 1)
        self.body.addLayout(tiles)

        self.list = QtWidgets.QVBoxLayout()
        self.list.setContentsMargins(0, 0, 8, 0)
        self.list.setSpacing(0)
        inner = QtWidgets.QWidget()
        inner.setLayout(self.list)
        area = QtWidgets.QScrollArea(widgetResizable=True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(inner)
        self.body.addWidget(area, 1)

        self.hint = label("", "muted")
        self.body.addLayout(hbox(self.hint, None, button("Verlauf leeren", self.clear, "ghost")))

    def prompt_names(self):
        cfg = self.ctl.cfg
        if not cfg["llm"].get("enabled"):
            return []
        return [p["name"] for p in cfg.get("prompts") or [] if p.get("name")]

    def refresh(self):
        while self.list.count():
            w = self.list.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        total, wpm, today = self.ctl.store.stats()
        for num, value in zip(self.nums, (total, wpm, today)):
            num.setText(f"{value:,}".replace(",", "."))
        rows = self.ctl.store.recent(self.search.text())
        last_day = None
        for ident, zeit, text, prompt in rows:
            day = self._day(zeit)
            if day != last_day:
                self.list.addWidget(label(day, "day"))
                last_day = day
            self.list.addWidget(Row(self, ident, zeit, text, prompt))
        if not self.ctl.cfg.get("history_enabled", True):
            self.list.addWidget(label("Der Verlauf ist ausgeschaltet (Einstellungen). Diktate werden nicht gespeichert.",
                                      "muted", wrap=True))
        elif not rows:
            empty = "Keine Treffer." if self.search.text() else \
                f"Noch nichts diktiert. {keys_text(self.ctl.cfg['hotkey_hold'])} halten und sprechen."
            self.list.addWidget(label(empty, "muted"))
        self.list.addStretch(1)
        days = self.ctl.cfg.get("history_days") or 0
        parts = ["Klick kopiert"]
        paste = keys_text(self.ctl.cfg.get("hotkey_paste_last"))
        if paste:
            parts.append(f"{paste} fügt den letzten Text ein")
        parts.append(f"Löschung nach {days} Tagen" if days else "keine automatische Löschung")
        self.hint.setText("  ·  ".join(parts))

    @staticmethod
    def _day(zeit):
        t, now = time.localtime(zeit), time.localtime()
        if t[:3] == now[:3]:
            return "HEUTE"
        if t[:3] == time.localtime(time.time() - 86400)[:3]:
            return "GESTERN"
        return time.strftime("%d.%m.%Y", t)

    def delete(self, ident):
        self.ctl.store.delete(ident)
        self.refresh()

    def clear(self):
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Verlauf leeren")
        box.setText("Alle Einträge im Verlauf löschen?")
        yes = box.addButton("Löschen", QtWidgets.QMessageBox.DestructiveRole)
        box.addButton("Abbrechen", QtWidgets.QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is yes:
            self.ctl.store.clear()
            self.refresh()


# ---------------------------------------------------------------- Aufnahme / Datei
def clock(seconds) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


class Transcript(QtWidgets.QWidget):
    """Textfeld für ein langes Transkript mit Kopieren, Speichern und KI-Nachbearbeitung."""
    sig_llm = Signal(str, str)

    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.text = QtWidgets.QPlainTextEdit(placeholderText="Hier erscheint der Text.")
        self.copy = button("Kopieren", self._copy, "primary")
        self.save = button("Als Textdatei speichern …", self._save)
        self.ki = button("KI")
        self.ki.setToolTip("Den ganzen Text mit einem Prompt nachbearbeiten")
        self.note = label("", "muted")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(self.text, 1)
        lay.addLayout(hbox(self.copy, self.save, self.ki, self.note, None))
        self.sig_llm.connect(self._llm_done)
        self.busy = False
        self.set_busy(False)

    def refresh(self):
        cfg = self.ctl.cfg
        names = [p["name"] for p in cfg.get("prompts") or [] if p.get("name")] if cfg["llm"].get("enabled") else []
        self.ki.setVisible(bool(names))
        menu = QtWidgets.QMenu(self.ki)
        for n in names:
            menu.addAction(n, lambda n=n: self._llm(n))
        self.ki.setMenu(menu)

    def set_busy(self, busy):
        self.busy = busy
        self.text.setReadOnly(busy)
        has = bool(self.text.toPlainText().strip())
        self.copy.setEnabled(has)                 # Zwischenstand lässt sich jederzeit kopieren
        for b in (self.save, self.ki):
            b.setEnabled(has and not busy)

    def set_text(self, text, glimpse=""):
        """Text ersetzen. Wer gerade weiter oben mitliest, bleibt dort; sonst läuft das Ende mit.
        glimpse: vorläufiger Text der Äußerung, die gerade gesprochen wird; steht grau am Ende."""
        bar = self.text.verticalScrollBar()
        follow = bar.value() >= bar.maximum() - 4
        position = bar.value()
        self.final = text
        self.text.setPlainText(text)
        if glimpse:
            cursor = self.text.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            grey = QtGui.QTextCharFormat()
            grey.setForeground(QtGui.QColor("#7A7A7A"))
            cursor.insertText((" " if text else "") + glimpse + " …", grey)
        bar.setValue(bar.maximum() if follow else position)
        self.copy.setEnabled(bool(text.strip()))

    def set_glimpse(self, glimpse):
        self.set_text(getattr(self, "final", ""), glimpse)

    def _copy(self):
        # während der Aufnahme nur den gültigen Text kopieren, nicht die graue Vorschau
        text = getattr(self, "final", "") if self.busy else self.text.toPlainText()
        QtGui.QGuiApplication.clipboard().setMimeData(private_mime(text))
        self.note.setText("Kopiert")
        QTimer.singleShot(1500, lambda: self.note.setText(""))

    def _save(self):
        start = os.path.join(os.path.expanduser("~"), "Documents", time.strftime("Transkript %Y-%m-%d %H-%M.txt"))
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Transkript speichern", start, "Textdatei (*.txt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.text.toPlainText())
                self.note.setText("Gespeichert")
            except OSError as e:
                self.note.setText(f"Nicht speicherbar: {e}")

    def _llm(self, name):
        prompt = next((p for p in self.ctl.cfg.get("prompts") or [] if p.get("name") == name), None)
        if not prompt:
            return
        self.set_busy(True)
        self.note.setText(f"„{name}“ läuft …")
        cfg, source = dict(self.ctl.cfg["llm"]), self.text.toPlainText()

        def work():
            try:
                self.sig_llm.emit(llm.run(cfg, prompt.get("text", ""), source), "")
            except Exception as e:
                self.sig_llm.emit("", str(e) or type(e).__name__)
        threading.Thread(target=work, daemon=True).start()

    def _llm_done(self, text, error):
        if not error:
            self.text.setPlainText(text)
        self.set_busy(False)
        self.note.setText(error[:120] if error else "Bearbeitet")


class LongPage(Page):
    """Gemeinsames für Aufnahme- und Dateiseite."""
    sig_voice = Signal(str)

    def __init__(self, ctl, title, subtitle, source):
        super().__init__(title, subtitle, scroll=False)
        self.ctl, self.source = ctl, source
        self.job = LongJob(ctl)
        self.job.part.connect(self.on_part)
        self.job.glimpse.connect(lambda text: self.out.set_glimpse(text))
        self.job.finished.connect(self.on_finished)
        self.started = 0.0
        self.out = Transcript(ctl)
        self.split = QtWidgets.QCheckBox("Sprecher trennen (Gespräche: „Sprecher 1: …“, „Sprecher 2: …“)")
        self.split.setToolTip("Für Gespräche mit mehreren Personen. Die App hört mit, wer wann spricht, auch wenn die "
                              "Sprecher ohne Pause wechseln, und ordnet jedes Wort einer Stimme zu. Läuft auf diesem Rechner.")
        self.split.toggled.connect(self._split)
        self.sig_voice.connect(lambda text: self.info(text))

    def _split(self, on):
        if on != bool(self.ctl.cfg.get("speakers")):
            self.ctl.cfg["speakers"] = on
            self.ctl.apply_cfg()
        if on and not sprecher.ready():          # Stimmmodell einmalig holen, Fortschritt in der Statuszeile
            def work():
                try:
                    sprecher.prepare(lambda done, total: self.sig_voice.emit(
                        f"Stimmmodell wird einmalig geladen · {100 * done / max(1, total):.0f} % von {total / 1048576:.0f} MB"))
                    self.sig_voice.emit("Stimmmodell geladen. Sprecher werden ab jetzt getrennt.")
                except Exception as e:
                    log.warning("Stimmmodell nicht ladbar: %s", e)
                    self.sig_voice.emit("Das Stimmmodell (26 MB) ließ sich nicht herunterladen, vermutlich sperrt das "
                                        "Netz den Download. Im Komplettpaket liegt es bei. Bis dahin laufen Aufnahmen "
                                        "ohne Sprecherzeilen.")
            threading.Thread(target=work, daemon=True).start()

    def refresh(self):
        self.out.refresh()
        self.split.setChecked(bool(self.ctl.cfg.get("speakers")))

    def speakers_note(self) -> str:
        if not self.ctl.cfg.get("speakers"):
            return ""
        if not sprecher.ready():
            return " Sprecher nicht getrennt: Das Stimmmodell fehlt auf diesem Rechner (im Komplettpaket liegt es bei)."
        n = self.job.speakers
        return f" {n} Sprecher erkannt." if n > 1 else " Nur eine Stimme erkannt, daher ohne Sprecherzeilen."

    def model_ready(self) -> bool:
        if self.ctl.ready:
            return True
        self.info("Das Sprachmodell lädt noch – gleich noch einmal versuchen.")
        return False

    def info(self, text):
        raise NotImplementedError

    def on_part(self, text, done, total):
        self.out.set_text(text)

    def on_finished(self, text, seconds, error):
        self.out.set_text(text)
        self.out.set_busy(False)
        if text.strip():
            self.ctl.remember(text, seconds, time.time() - self.started)

    def problems(self) -> str:
        """Hinweise nach einem Lauf, bei dem nicht alles glatt ging."""
        notes = []
        if self.job.failed:
            notes.append(f"Achtung: {self.job.failed} Stelle(n) konnten nicht erkannt werden und sind im Text "
                         "markiert.")
        if self.job.overflows:
            notes.append(f"Der Audiotreiber meldete {self.job.overflows} Aussetzer.")
        if self.job.kept:
            notes.append(f"Die Tonaufnahme wurde deshalb nicht gelöscht: {self.job.kept}")
        return " ".join(notes)


# ---------------------------------------------------------------- Wörterbuch / Textbausteine
def learn_verdict(target: str, heard: str, error: str = ""):
    """Entscheidet, ob eine eingesprochene Fehlerkennung ins Wörterbuch darf.

    Gibt (Hinweis, Fehlschreibung oder None) zurück. Gesprochen werden darf das Wort allein oder
    in einem Satz; im Satz wird die Stelle gesucht, die dem richtigen Wort am ähnlichsten ist.
    Übernommen wird nur, was dem richtigen Wort ähnlich ist. Sonst könnte ein Versprecher dafür
    sorgen, dass künftig ein ganz anderes, richtig erkanntes Wort ersetzt wird.
    """
    if error:
        return f"Das hat nicht geklappt: {error}", None
    if not heard:
        return "Nichts erkannt. Knopf halten, kurz warten, dann sprechen.", None
    if target.casefold() in heard.casefold():
        return f"Gehört: „{heard}“. Das Wort wird schon richtig erkannt.", None
    words = [w.strip(".,;:!?…\"„“()") for w in heard.split()]
    words = [w for w in words if w]
    n = max(1, len(target.split()))
    best, score = "", 0.0
    for size in {n, n + 1, max(1, n - 1)}:
        for i in range(0, len(words) - size + 1):
            candidate = " ".join(words[i:i + size])
            ratio = difflib.SequenceMatcher(None, candidate.casefold(), target.casefold()).ratio()
            if ratio > score:
                best, score = candidate, ratio
    if score < 0.6:
        return (f"Gehört: „{heard}“. Darin ist nichts, was „{target}“ ähnelt; es wird nichts übernommen. "
                "Wenn es stimmt, unten von Hand eintragen."), None
    return f"Gehört: „{heard}“ – „{best}“ wird ab jetzt durch „{target}“ ersetzt.", best


class MapPage(Page):
    """Tabelle für ein Wörterbuch in der Konfiguration (Schlüssel -> Wert)."""

    def __init__(self, ctl, title, subtitle, key, headers, learn=False, starter=None):
        super().__init__(title, subtitle, scroll=False)
        self.ctl, self.key, self.loading, self.starter = ctl, key, False, starter
        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 260)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.itemChanged.connect(self.store)
        if learn:
            self.word = QtWidgets.QLineEdit(placeholderText="Richtige Schreibweise, z. B. Apixaban")
            self.speak = button("Halten und sprechen", name="primary")
            self.speak.pressed.connect(self._listen)
            self.speak.released.connect(self.ctl.listen_stop)
            self.heard = label("Wort eintippen, Knopf halten und es so sprechen wie im Diktat. Was die Erkennung daraus "
                               "macht, wird künftig ersetzt. Ohne Einsprechen: unten „Hinzufügen“ und nur die rechte Spalte "
                               "ausfüllen; LocalScribe erkennt den Begriff dann am Klang (Riba wird RIVA).", "muted", wrap=True)
            self.body.addWidget(card(label("Wort einsprechen", "h2"), hbox((self.word, 1), self.speak), self.heard))
            self.ctl.sig_heard.connect(self._heard)
            self.base = QtWidgets.QCheckBox()
            self.base.toggled.connect(self._base)
            self.body.addWidget(self.base)
        self.body.addWidget(self.table, 1)
        row = [button("Hinzufügen", self.add, "primary"), button("Entfernen", self.remove)]
        if learn:
            row.append(button("Aus Korrektur lernen", self._correct))
        if starter:
            row.append(button(starter[0], self._starter))
        self.note = label("", "muted", wrap=True)
        self.body.addLayout(hbox(*row, (self.note, 1)))

    def _starter(self):
        """Mitgelieferte Einträge ergänzen; was es schon gibt, bleibt, wie es ist."""
        data = dict(self.ctl.cfg.get(self.key) or {})
        new = {k: v for k, v in self.starter[1].items() if k not in data}
        data.update(new)
        self.ctl.cfg[self.key] = data
        self.ctl.apply_cfg()
        self.refresh()
        self.note.setText(f"{len(new)} Einträge ergänzt." if new else "Alle Einträge sind schon da.")

    def _correct(self):
        """Das letzte Diktat berichtigen lassen und daraus Wörterbucheinträge ableiten."""
        heard = self.ctl.store.last().strip()
        if not heard:
            return self.note.setText("Der Verlauf ist leer. Erst diktieren, dann hier berichtigen.")
        box = QtWidgets.QDialog(self)
        box.setWindowTitle("Aus Korrektur lernen")
        box.resize(640, 380)
        lay = QtWidgets.QVBoxLayout(box)
        lay.addWidget(label("Dein letztes Diktat. Berichtige die falsch erkannten Wörter und klicke auf Lernen. "
                            "Verhörte Fachwörter kommen ins Wörterbuch.", "muted", wrap=True))
        edit = QtWidgets.QPlainTextEdit(heard)
        lay.addWidget(edit, 1)
        ok = button("Lernen", box.accept, "primary")
        lay.addLayout(hbox(None, button("Abbrechen", box.reject), ok))
        if box.exec() != QtWidgets.QDialog.Accepted:
            return
        self.note.setText(self.learn_from(heard, edit.toPlainText().strip()))

    def learn_from(self, heard, fixed) -> str:
        if fixed == heard:
            return "Nichts geändert."
        read, learned, open_ = training.learn(fixed, heard)
        if not read:
            return "Der berichtigte Text weicht zu stark ab, daraus lässt sich nichts lernen."
        data = dict(self.ctl.cfg.get(self.key) or {})
        new = [(w, r) for w, r in learned if data.get(w) != r]
        for w, r in new:
            data[w] = r
        if new:
            self.ctl.cfg[self.key] = data
            self.ctl.apply_cfg()
            self.refresh()
        parts = []
        if new:
            parts.append("Gelernt: " + ", ".join(f"„{w}“ → „{r}“" for w, r in new) + ".")
        if open_:
            # ein richtiges Wort an falscher Stelle: Das klärt nur der Zusammenhang, also merkt es sich die Fachkorrektur
            memory = [list(x) for x in self.ctl.cfg.get("corrections") or []]
            for w, r in open_:
                if [w, r] not in memory:
                    memory.append([w, r])
            self.ctl.cfg["corrections"] = memory[-200:]
            self.ctl.apply_cfg()
            parts.append("Für die Fachkorrektur gemerkt (das Erkannte ist selbst ein richtiges Wort, darüber "
                         "entscheidet der Zusammenhang): " + ", ".join(f"„{w}“ → „{r}“" for w, r in open_) + ".")
        return " ".join(parts) or "Keine verhörten Wörter gefunden."

    def _base(self, on):
        if not self.loading and on != bool(self.ctl.cfg.get("base_dictionary", True)):
            self.ctl.cfg["base_dictionary"] = on
            self.ctl.apply_cfg()

    def refresh(self):
        self.loading = True
        if hasattr(self, "base"):
            n, m = len(engine.base_dictionary()), len(fach.load()[0])
            self.base.setText(f"Medizinisches Basiswörterbuch anwenden: {m:,} Fachbegriffe werden am Klang erkannt, "
                              f"dazu {n:,} bekannte Fehlschreibungen".replace(",", "."))
            self.base.setChecked(bool(self.ctl.cfg.get("base_dictionary", True)))
        data = self.ctl.cfg.get(self.key) or {}
        self.table.setRowCount(0)
        for k, v in data.items():
            self._append(k, v.replace("\n", "\\n"))
        if hasattr(self, "base"):                        # eigene Begriffe: nur die Schreibweise, erkannt wird am Klang
            for term in self.ctl.cfg.get("vocabulary") or []:
                self._append(self.BY_SOUND, term)
        self.loading = False

    BY_SOUND = "(am Klang)"

    def _append(self, k, v):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(k))
        self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(v))
        return r

    def add(self):
        self.loading = True
        r = self._append("", "")
        self.loading = False
        self.table.setCurrentCell(r, 0)
        self.table.editItem(self.table.item(r, 0))

    def remove(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self.store()

    def _listen(self):
        if not self.word.text().strip():
            restyle(self.heard, "bad")
            return self.heard.setText("Erst die richtige Schreibweise eintippen.")
        error = self.ctl.listen_start(self)
        restyle(self.heard, "bad" if error else "muted")
        self.heard.setText(error or "Höre zu …")

    def _heard(self, text, error):
        if self.ctl.listener is not self:
            return
        target = self.word.text().strip()
        heard = re.sub(r"[.,;:!?…]+$", "", text.strip()).strip()
        note, wrong = learn_verdict(target, heard, error)
        if wrong:
            data = dict(self.ctl.cfg.get(self.key) or {})
            data[wrong] = target
            self.ctl.cfg[self.key] = data
            self.ctl.apply_cfg()
            self.refresh()
        restyle(self.heard, "ok" if wrong or "schon richtig" in note else "bad")
        self.heard.setText(note)

    def store(self, *_):
        if self.loading:
            return
        data, terms = {}, []
        for r in range(self.table.rowCount()):
            k = (self.table.item(r, 0).text() if self.table.item(r, 0) else "").strip()
            v = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            if hasattr(self, "base") and k in ("", self.BY_SOUND):
                if v.strip() and v.strip() not in terms:
                    terms.append(v.strip())
                    if not k:                            # eben eingetragen: zeigen, wie der Eintrag wirkt
                        self.loading = True
                        self.table.item(r, 0).setText(self.BY_SOUND)
                        self.loading = False
            elif k:
                data[k] = v.replace("\\n", "\n")
        self.ctl.cfg[self.key] = data
        if hasattr(self, "base"):
            self.ctl.cfg["vocabulary"] = terms
        self.ctl.apply_cfg()


# ---------------------------------------------------------------- Visite & Übergabe
class Flow(QtWidgets.QLayout):
    """Legt Kärtchen nebeneinander und bricht um, wenn die Zeile voll ist."""

    def __init__(self, gap=8):
        super().__init__()
        self.items, self.gap = [], gap
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, i):
        return self.items[i] if 0 <= i < len(self.items) else None

    def takeAt(self, i):
        return self.items.pop(i) if 0 <= i < len(self.items) else None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(width, False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._place(rect.width(), True, rect.x(), rect.y())

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize(0, 0)
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _place(self, width, move, left=0, top=0):
        x = y = row = 0
        for item in self.items:
            hint = item.sizeHint()
            if x and x + hint.width() > width:
                x, y, row = 0, y + row + self.gap, 0
            if move:
                item.setGeometry(QtCore.QRect(left + x, top + y, hint.width(), hint.height()))
            x += hint.width() + self.gap
            row = max(row, hint.height())
        return y + row


class Tall(QtWidgets.QWidget):
    """Inhalt eines Rollbereichs, dessen Höhe von der Breite abhängt (umbrechender Text, Kärtchen).

    Ein Rollbereich fragt seinen Inhalt nicht, wie hoch er bei der gegebenen Breite sein müsste; er drückt ihn auf die
    sichtbare Höhe zusammen. Hier meldet der Inhalt seine nötige Höhe selbst, bei jeder Änderung von Breite oder Inhalt."""

    def event(self, e):
        if e.type() in (QtCore.QEvent.LayoutRequest, QtCore.QEvent.Resize):
            lay = self.layout()
            need = lay.heightForWidth(self.width()) if lay is not None and lay.hasHeightForWidth() else 0
            if need != self.minimumHeight():
                self.setMinimumHeight(need)
        return super().event(e)


def copy_button(get_text, text="Kopieren"):
    """Knopf, der einen Text in die Zwischenablage legt und das kurz bestätigt."""
    b = button(text, name="ghost")

    def go():
        QtGui.QGuiApplication.clipboard().setMimeData(private_mime(get_text()))
        b.setText("Kopiert ✓")
        QTimer.singleShot(1300, lambda: b.setText(text))
    b.clicked.connect(go)
    return b


def chip(text, kind="chip"):
    w = label(text, kind)
    w.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
    return w


class Box(QtWidgets.QFrame):
    """Ein Block im Ergebnis: Titel, rechts Knöpfe, darunter der Inhalt; auf Wunsch zugeklappt."""

    def __init__(self, title, hint="", copy=None, folded=None):
        super().__init__(objectName="box")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 16)
        lay.setSpacing(10)
        self.head = hbox(label(title, "boxTitle"), label(hint, "muted"), None, spacing=10)
        lay.addLayout(self.head)
        self.inner = QtWidgets.QWidget()
        self.rows = QtWidgets.QVBoxLayout(self.inner)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(8)
        lay.addWidget(self.inner)
        lay.addStretch(1)
        if copy:
            self.head.addWidget(copy_button(copy))
        if folded is not None:
            self.toggle = button("", self._flip, "ghost")
            self.head.addWidget(self.toggle)
            self.opened = folded
            self._flip()

    def _flip(self, _=False):
        self.opened = not self.opened
        self.inner.setVisible(self.opened)
        self.toggle.setText("Einklappen ▴" if self.opened else "Anzeigen ▾")

    def add(self, item):
        if isinstance(item, QtWidgets.QLayout):
            self.rows.addLayout(item)
        else:
            self.rows.addWidget(item)
        return item


class Fold(QtWidgets.QWidget):
    """Ein Abschnitt zum Auf- und Zuklappen mit eigenem Kopierknopf."""

    def __init__(self, title, text, opened=False):
        super().__init__()
        self.title = title
        self.toggle = button("", self.flip, "fold")
        self.body = label(text, wrap=True)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.setContentsMargins(18, 0, 0, 8)
        self.opened = not opened
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addLayout(hbox((self.toggle, 1), copy_button(lambda: text)))
        lay.addWidget(self.body)
        self.flip()

    def flip(self, _=False, to=None):
        self.opened = (not self.opened) if to is None else to
        self.body.setVisible(self.opened)
        self.toggle.setText(("▾  " if self.opened else "▸  ") + self.title)


class VisitPage(Page):
    """Fall aufnehmen oder tippen, korrigieren, auswerten: Jev-Ersteinschätzung, Arztbrief-Entwurf, Sicherheitsnetz,
    Rückfragen. Jeder Teil steht in einem eigenen Block."""
    sig_done = Signal(object, str, int)
    sig_jev = Signal(object, str, int)
    sig_voice = Signal(str)
    sig_text = Signal(str, str, str, int)        # Name des Auftrags, Ergebnis, Fehler, Fall
    PRIORITY = {"critical": ("entscheidend", "chipRed"), "high": ("wichtig", "chipWarn"), "medium": ("ergänzend", "chipOff")}

    SHOWN = config.ON_RECORD     # ab Werk auf der Seite Aufnahme: Visite, Meeting-Protokoll, Arztbrief, Pflegebericht
    voice_asked = False
    FRAME_TIPS = {
        "zna": "Notaufnahme: Ersteinschätzung (wohin, welche Abteilung, Bett, Schockraum, erste Maßnahmen) und Arztbrief.",
        "station": "Station: Tages-Check (Verschlechterung, Entlassung, was heute zu prüfen ist) und Visiteneintrag.",
        "its": "Intensiv: Tages-Check (Eskalation, Verlegung, Aufwachversuch, Tagesroutine) und Übergabe nach Organsystemen.",
    }
    FRAME_HINTS = {
        "zna": "Diktat oder Text zum Fall: Anamnese, Befund, Verlauf, Vormedikation, geplantes Vorgehen. Mehrere Teile "
               "nacheinander kommen über „Zur Ablage legen“ zusammen.",
        "station": "Visite oder Verlauf: Befinden, Befunde, Labor mit Verlauf, Medikation und was heute geändert wird, Plan. "
                   "Ein mitgeschnittenes Visitengespräch geht auch.",
        "its": "Übergabe oder Visite: Kurzvorstellung, dann nach Organsystemen. Perfusoren mit Rate, Antiinfektiva mit Tag, "
               "Katheter, offene Punkte.",
    }

    def __init__(self, ctl, mode="record"):
        self.mode = mode
        self.handover = handover = mode == "handover"
        self.items = []                                  # Übergabe: die Ablage des Falls
        if handover:
            super().__init__("Übergabe",
                             "Für Visite und Übergabe: aufnehmen oder tippen, auswerten, Rückfragen beantworten, neu "
                             "erzeugen. Experimentell, für Benchmarking, Forschung und Lehre. Kein Medizinprodukt: Die "
                             "Ausgaben sind Entwürfe und Wahrscheinlichkeiten von Modellen und vor jeder Verwendung zu "
                             "prüfen.", scroll=False)
        else:
            super().__init__("Aufnahme", scroll=False)
        self.ctl = ctl
        self.tab_names = ("Fall", "Fälle", "Papierkorb") if handover else ("Aufnahme", "Gespeichert", "Papierkorb")
        self.store = visite.Store(config.DIR / ("visite.sqlite" if handover else "aufnahme.sqlite"))
        self.case, self.result, self.waiting, self.errors = None, None, set(), {}
        self.tabs = QtWidgets.QButtonGroup(self)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        for i, name in enumerate(self.tab_names):
            b = QtWidgets.QPushButton(name, checkable=True, objectName="tab")
            b.setCursor(Qt.PointingHandCursor)
            self.tabs.addButton(b, i)
            (row if handover else self.head).addWidget(b)       # Aufnahme: Reiter rechts neben der Überschrift
        row.addStretch(1)
        # Übergabe: der Rahmen bestimmt, was gefragt und geschrieben wird (Notaufnahme, Station, Intensiv)
        self.frames = QtWidgets.QButtonGroup(self)
        self.frame_bar = QtWidgets.QWidget()
        if handover:
            fl = QtWidgets.QHBoxLayout(self.frame_bar)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.setSpacing(4)
            for i, (key, name) in enumerate(jev.FRAMES):
                b = QtWidgets.QPushButton(name, checkable=True, objectName="seg")
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(self.FRAME_TIPS[key])
                self.frames.addButton(b, i)
                fl.addWidget(b)
            self.frames.idClicked.connect(self._frame_picked)
            row.addWidget(self.frame_bar)
        if handover:
            self.body.addLayout(row)
        else:
            self.head.setSpacing(6)
        self.stack = QtWidgets.QStackedWidget()
        self.body.addWidget(self.stack, 1)

        # Neuer Patient: oben eine schmale Leiste und der Text, darunter das Ergebnis über die ganze Breite
        self.name = QtWidgets.QLineEdit(placeholderText="Fallbezeichnung, z. B. Zimmer 4 oder Kürzel (kein Klarname nötig)")
        self.rec = button(" Aufnahme", self._record, "recPill")
        self.rec.setIcon(rec_icon("mic", size=18))
        self.rec.setIconSize(QtCore.QSize(18, 18))
        self.split = QtWidgets.QCheckBox("Sprecher trennen")
        self.split.setToolTip("Für Gespräche mit mehreren Personen: „Sprecher 1: …“, „Sprecher 2: …“. Läuft auf diesem Rechner.")
        self.split.toggled.connect(lambda on: LongPage._split(self, on))
        self.sig_voice.connect(self.info)
        self.state = label("Aufnehmen oder in das Feld tippen.", "muted", wrap=True)
        self.text = QtWidgets.QPlainTextEdit(placeholderText="Hier steht nach der Aufnahme der Text zum Korrigieren. "
                                             "Tippen geht auch: Anamnese, Befund, Verlauf, Vormedikation, geplantes Vorgehen.")
        self.go = button("Auswerten", self._analyse, "primary")
        self.go.setToolTip("Ersteinschätzung, Arztbrief-Entwurf, Sicherheitsnetz und Rückfragen aus dem Text und der Ablage.")
        self.note = label("", "muted")
        self.load = button("Datei …", self._file)
        self.load.setToolTip("Audio- oder Videodatei transkribieren. Sie verlässt diesen Rechner nicht.")
        self.tasks = QtWidgets.QWidget()                 # Zeile der Aufträge, wird aus den Einstellungen gefüllt
        self.task_row = Flow(gap=8)
        self.tasks.setLayout(self.task_row)
        # Übergabe: die Ablage des Falls. Jedes Diktat, jeder Text und jede beantwortete Rückfrage ist ein Eintrag;
        # ausgewertet wird immer alles zusammen.
        self.tray = QtWidgets.QWidget()
        self.tray_row = Flow(gap=6)
        self.tray.setLayout(self.tray_row)
        self.put = button("Zur Ablage legen", self._put)
        self.put.setToolTip("Legt den Text aus dem Feld als Eintrag in die Ablage und macht das Feld frei für das nächste "
                            "Diktat, etwa den Verlauf oder die Übergabe.")
        # Aufnahme: leerer Zustand mit Zeit, Wellenform und einem breiten Startknopf
        self.hero = Hero(self._record, self._file)
        self.rec_big = self.hero.go
        # Aufnahme, die beim letzten Mal nicht fertig wurde (Absturz, Stromausfall, Fehler)
        self.left_text = label("", wrap=True)
        self.left_card = card(hbox((self.left_text, 1), button("Jetzt transkribieren", self.recover, "primary"),
                                   button("Löschen", self.discard)))
        self.left_card.hide()
        self.leftover = None
        new = QtWidgets.QWidget()
        top = QtWidgets.QVBoxLayout(new)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.bar = QtWidgets.QWidget()
        self.bar.setLayout(hbox(self.rec, self.load, (self.name, 1), self.split, button("Neu", self._new)))
        top.addWidget(self.bar)
        self.live_clock = Clock(30)
        self.live_wave = Wave(96, 44)
        self.pulse = QtWidgets.QWidget()                 # nur während der Aufnahme: Zeit und Pegel
        self.pulse.setLayout(hbox(self.live_clock, (self.live_wave, 1), spacing=18))
        self.pulse.layout().setContentsMargins(4, 6, 4, 2)
        self.pulse.hide()
        top.addWidget(self.pulse)
        top.addWidget(self.left_card)
        top.addWidget(self.hero, 1)
        top.addLayout(hbox((self.state, 1), self.note))
        top.addWidget(self.text, 1)
        if handover:
            top.addWidget(self.tray)
            self.task_row.addWidget(self.go)
            self.task_row.addWidget(self.put)
            self.name.setPlaceholderText("Fallbezeichnung, z. B. Zimmer 4 oder Kürzel (kein Klarname nötig)")
        else:
            self.tray.hide()
            self.go.hide()
            self.name.setPlaceholderText("Titel, z. B. Besprechung Montag")
            self.text.setPlaceholderText("Hier steht nach der Aufnahme das Transkript. Korrigieren und tippen geht auch.")
        top.addWidget(self.tasks)
        inner = Tall()
        col = QtWidgets.QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(12)
        self.texts = QtWidgets.QVBoxLayout()             # Ergebnisse der Aufträge, je ein Block über die ganze Breite
        self.texts.setSpacing(12)
        self.cards = QtWidgets.QGridLayout()
        self.cards.setSpacing(12)
        col.addLayout(self.texts)
        col.addLayout(self.cards)
        col.addStretch(1)
        self.text_boxes = []
        self.area = QtWidgets.QScrollArea(widgetResizable=True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setWidget(inner)
        self.area.hide()
        top.addWidget(self.area, 4)
        self.boxes, self.columns = {}, 0
        self.stack.addWidget(new)
        self.typing = False
        self.saver = QTimer(self, singleShot=True, interval=700)       # nichts geht verloren: jede Eingabe wird gesichert
        self.saver.timeout.connect(self._save)
        self.text.textChanged.connect(self.saver.start)
        self.text.textChanged.connect(self._state)
        self.name.textEdited.connect(lambda _: self.saver.start())

        # Aufnahme wie auf der Seite „Aufnahme“: Ton wird nebenbei gesichert, der Text läuft live mit
        self.job = LongJob(ctl)
        self.job.part.connect(self._part)
        self.job.glimpse.connect(lambda g: self._live(self.heard, g))
        self.job.finished.connect(self._recorded)
        self.recording, self.before, self.heard, self.started = False, "", "", 0.0
        self.tick = QTimer(self, interval=250, timeout=lambda: self.live_clock.setText(clock(time.time() - self.started)))
        self.meter = QTimer(self, interval=50, timeout=lambda: self.live_wave.feed(self.job.level))

        # Fallliste und Papierkorb
        self.lists = []
        for trash in (False, True):
            search = QtWidgets.QLineEdit(placeholderText="Suchen")
            items = QtWidgets.QListWidget()
            items.itemDoubleClicked.connect(lambda item, t=trash: None if t else self._open(item.data(Qt.UserRole)))
            search.textChanged.connect(lambda _: self._fill())
            w = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(search)
            lay.addWidget(items, 1)
            if trash:
                lay.addLayout(hbox(button("Wiederherstellen", lambda: self._each(1, lambda i: self.store.trash(i, False))),
                                   button("Endgültig löschen", lambda: self._each(1, self.store.purge)),
                                   None, button("Papierkorb leeren", self._empty)))
            else:
                lay.addLayout(hbox(button("Öffnen", lambda: self._each(0, self._open), name="primary"),
                                   button("Umbenennen …", self._rename),
                                   button("In den Papierkorb", lambda: self._each(0, self.store.trash)), None))
            self.lists.append((search, items))
            self.stack.addWidget(w)
        self.tabs.idClicked.connect(self._tab)
        self.sig_done.connect(self._done)
        self.sig_jev.connect(self._jev)
        self.sig_text.connect(self._text_done)
        self._set_frame(ctl.cfg.get("handover_frame"))
        self._tab(0)
        self._show(None)

    # ----- Übergabe: Rahmen
    def frame(self) -> str:
        i = self.frames.checkedId()
        return jev.FRAMES[i][0] if self.handover and 0 <= i < len(jev.FRAMES) else "zna"

    def _set_frame(self, key):
        if not self.handover:
            return
        key = visite.frame_of(key)
        self.frames.button([k for k, _ in jev.FRAMES].index(key)).setChecked(True)
        names = visite.NAMES[key]
        self.text.setPlaceholderText(self.FRAME_HINTS[key])
        self.go.setToolTip(f"{names['jev']}, {names['brief']}, Sicherheitsnetz und Rückfragen aus dem Text und der Ablage.")

    def _frame_picked(self, i):
        key = jev.FRAMES[i][0]
        self._set_frame(key)
        if key != self.ctl.cfg.get("handover_frame", "zna"):
            self.ctl.cfg["handover_frame"] = key            # gilt auch für den nächsten Fall
            config.save(self.ctl.cfg)
        shown = (self.result or {}).get("frame") or "zna"
        if self.case is not None and not self.waiting:      # beim Fall merken, auch wenn noch nichts ausgewertet ist
            row = self.store.get(self.case)
            if row:
                self.store.save(self.case, row[0], row[1], {**(row[2] or {}), "frame_next": key})
        if (self.result or {}).get("visit") and key != shown:
            restyle(self.note, "muted")
            self.note.setText(f"Rahmen {dict(jev.FRAMES)[key]} gewählt. „Neu erzeugen“ wertet den Fall so aus.")

    def refresh(self):
        self._fill()
        self.split.blockSignals(True)
        self.split.setChecked(bool(self.ctl.cfg.get("speakers")))
        self.split.blockSignals(False)
        if self.ctl.cfg.get("speakers") and not VisitPage.voice_asked and not sprecher.ready():
            VisitPage.voice_asked = True             # Stimmmodell fehlt noch: einmal je Programmlauf im Hintergrund holen
            LongPage._split(self, True)
        self._tasks()
        current = self.job.wav_path if self.job.running else None
        rest = [p for p in config.leftover_recordings() if p != current]
        self.leftover = rest[0] if rest else None
        if self.leftover and not self.job.running:
            minutes = max(0, self.leftover.stat().st_size - 44) / 2 / 16000 / 60
            when = time.strftime("%d.%m. um %H:%M", time.localtime(self.leftover.stat().st_mtime))
            more = f" ({len(rest)} Aufnahmen warten.)" if len(rest) > 1 else ""
            self.left_text.setText(f"Eine Aufnahme vom {when} ({minutes:.0f} Minuten) wurde nicht fertig "
                                   f"transkribiert. Der Ton ist noch da.{more}")
        self.left_card.setVisible(bool(self.leftover) and not self.job.running)
        self._tray()
        self._state()

    def _tasks(self):
        """Aufnahme: die Aufträge als Knöpfe. Gezeigt wird, was in den Einstellungen (LLM) dafür angekreuzt ist."""
        if self.handover:
            return
        names = [p.get("name", "") for p in self.ctl.cfg.get("prompts") or []
                 if (p.get("text") or "").strip() and p.get("record", p.get("name") in self.SHOWN)]
        first = {n: i for i, n in enumerate(self.SHOWN)}
        names.sort(key=lambda n: first.get(n, len(first)))      # die vier ab Werk vorn, in fester Reihenfolge
        if getattr(self, "task_names", None) == names:
            return
        self.task_names = names
        while self.task_row.count():
            w = self.task_row.takeAt(0).widget()
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self.task_row.addWidget(label("Daraus machen:", "muted"))
        for name in names:
            self.task_row.addWidget(button(name.replace("&", "&&"), lambda _=False, n=name: self._task(n)))
        if not names:
            self.task_row.addWidget(label("Kein Auftrag angekreuzt (Einstellungen, LLM).", "muted"))

    def _state(self):
        """Aufnahme ohne Inhalt zeigt nur den großen Knopf; sobald aufgenommen oder getippt wird, Text und Aufträge."""
        empty = (not self.handover and not self.recording and not self.job.running and self.result is None
                 and not self.text.toPlainText().strip() and not self.typing)
        self.hero.setVisible(empty)
        self.pulse.setVisible(self.recording)
        for w in (self.bar, self.state, self.note, self.text, self.tasks):
            w.setVisible(not empty)
        if self.handover:
            self.go.setText("Neu erzeugen" if (self.result or {}).get("visit") or (self.result or {}).get("documentation")
                            else "Auswerten")

    # ----- Übergabe: Ablage
    def _input(self) -> str:
        """Alles, was zum Fall gehört: die Einträge der Ablage und der Text im Feld."""
        parts = [f"[{i.get('label', 'Eintrag')}]\n{i.get('content', '').strip()}" for i in self.items if i.get("content", "").strip()]
        text = self.text.toPlainText().strip()
        if text:
            parts.append(f"[Aktueller Text]\n{text}" if parts else text)
        return "\n\n".join(parts)

    def _tray(self):
        while self.tray_row.count():
            w = self.tray_row.takeAt(0).widget()
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self.tray.setVisible(self.handover and bool(self.items))
        if not self.items:
            return
        self.tray_row.addWidget(label(f"Ablage ({len(self.items)}):", "muted"))
        for n, item in enumerate(self.items):
            words = " ".join((item.get("content") or "").split())
            b = button(f"{item.get('label', 'Eintrag')} · {words[:34]}{'…' if len(words) > 34 else ''}".replace("&", "&&"),
                       lambda _=False, i=n: self._item(i), "tab")
            b.setToolTip("Ansehen, ändern oder aus der Ablage nehmen")
            self.tray_row.addWidget(b)

    def _items_changed(self, note):
        """Ablage sichern. Das Ergebnis bleibt stehen, bis neu erzeugt wird."""
        if self.case is None:
            self.case = self.store.save(None, self.name.text().strip(), self.text.toPlainText())
        row = self.store.get(self.case)
        merged = dict((row[2] if row else None) or {})
        merged["items"] = self.items
        self.store.save(self.case, self.name.text().strip(), self.text.toPlainText(), merged)
        self.result = {**(self.result or {}), "items": self.items} if self.result is not None else self.result
        self._tray()
        self._state()
        restyle(self.note, "muted")
        self.note.setText(note)

    def _put(self, label_text=None, content=None):
        text = (content if content is not None else self.text.toPlainText()).strip()
        if not text:
            restyle(self.note, "bad")
            return self.note.setText("Das Feld ist leer.")
        if self.recording or self.job.running:
            return
        kind = label_text or f"Eintrag {1 + sum(1 for i in self.items if i.get('label', '').startswith('Eintrag'))}"
        self.items.append({"label": kind, "content": text})
        if content is None:
            self.text.blockSignals(True)
            self.text.clear()
            self.text.blockSignals(False)
        had = bool((self.result or {}).get("visit") or (self.result or {}).get("documentation"))
        self._items_changed("In der Ablage. „Neu erzeugen“ berücksichtigt den Eintrag." if had else "In der Ablage.")

    def _item(self, index):
        item = self.items[index]
        box = QtWidgets.QDialog(self)
        box.setWindowTitle(item.get("label", "Eintrag"))
        box.setStyleSheet(STYLE)
        box.resize(620, 420)
        edit = QtWidgets.QPlainTextEdit(item.get("content", ""))
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.addWidget(edit, 1)
        done = {}
        lay.addLayout(hbox(button("Aus der Ablage nehmen", lambda: (done.update(drop=True), box.accept())), None,
                           button("Abbrechen", box.reject), button("Speichern", box.accept, "primary")))
        if not box.exec():
            return
        if done.get("drop"):
            self.items.pop(index)
            return self._items_changed("Aus der Ablage genommen.")
        if edit.toPlainText().strip() != item.get("content", "").strip():
            item["content"] = edit.toPlainText().strip()
            self._items_changed("Eintrag geändert. „Neu erzeugen“ berücksichtigt ihn.")

    def _answer(self, number, question, answer):
        answer = answer.strip()
        if not answer:
            return
        name = f"Rückfrage {number} · Antwort"
        self.items = [i for i in self.items if not (i.get("label") == name and i.get("content", "").startswith(f"Frage: {question}"))]
        self._put(name, f"Frage: {question}\nAntwort: {answer}")

    def _file(self):
        if self.recording or self.job.running or self.window().busy():
            return self.info("Es läuft schon eine Aufnahme oder Transkription.", bad=True)
        if not self.ctl.ready:
            return self.info("Das Sprachmodell lädt noch – gleich noch einmal versuchen.", bad=True)
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Audiodatei auswählen", "",
            "Audio und Video (*.mp3 *.m4a *.wav *.flac *.ogg *.opus *.aac *.wma *.mp4 *.mkv *.mov *.webm);;Alle Dateien (*)")
        if path:
            self._long(lambda: self.job.start_file(path), f"Transkribiere {os.path.basename(path)} …")

    def recover(self):
        if self.job.running or not self.leftover or not self.ctl.ready:
            return
        self.left_card.hide()
        path = self.leftover
        self._long(lambda: self.job.start_recovery(path), "Hole die Aufnahme nach …")

    def discard(self):
        if self.leftover:
            try:
                self.leftover.unlink()
            except OSError as e:
                return self.info(f"Nicht löschbar: {e}", bad=True)
        self.refresh()

    def _long(self, start, text):
        """Datei oder liegengebliebene Aufnahme: läuft wie eine Aufnahme, nur ohne Mikrofon."""
        self.saver.stop()
        self._save()
        self.heard = ""
        self.before = self.text.toPlainText().rstrip()
        self.text.setReadOnly(True)
        self.tasks.setEnabled(False)
        self.rec.setEnabled(False)
        self.info(text)
        self.typing = True                               # Text und Fortschritt zeigen, nicht den großen Knopf
        self._state()
        try:
            start()
        except Exception as e:
            self._recorded("", 0.0, str(e))

    def _task(self, name):
        """Einen Auftrag aus den Einstellungen auf den Text anwenden; das Ergebnis kommt als eigener Block."""
        text = self.text.toPlainText().strip()
        prompt = config.prompt_by_name(self.ctl.cfg, name)
        restyle(self.note, "bad")
        if not text:
            return self.note.setText("Erst aufnehmen, eine Datei laden oder tippen.")
        server = copy.deepcopy(self.ctl.cfg.get("llm") or {})
        if not prompt or not (server.get("base_url") or "").strip() or not (server.get("model") or "").strip():
            return self.note.setText("Kein Sprachmodell eingestellt. Unter Einstellungen, LLM, Server und Modell wählen.")
        if name in self.waiting:
            return
        if schutz.blocked(server) and self.window().shield_wait(lambda n=name: self._task(n)):
            restyle(self.note, "muted")           # statt einer Fehlermeldung: laden und danach von selbst weitermachen
            return self.note.setText("Die Namenserkennung wird einmalig geladen. Der Auftrag startet danach von selbst.")
        self.saver.stop()
        self._save()
        restyle(self.note, "muted")
        self.note.setText("Läuft …")
        case, instruction = self.case, prompt["text"]
        self.waiting.add(name)
        self._show({**(self.result or {}), **self.errors})

        def run():
            try:
                self.sig_text.emit(name, llm.run(server, instruction, text), "", case)
            except Exception as e:
                log.warning("Auftrag fehlgeschlagen: %s", type(e).__name__)
                self.sig_text.emit(name, "", str(e) or type(e).__name__, case)
        threading.Thread(target=run, daemon=True).start()

    def _text_done(self, name, text, error, case):
        row = self.store.get(case)
        if row and not error:
            merged = dict(row[2] or {})
            merged["texts"] = {**(merged.get("texts") or {}), name: text}
            self.store.save(case, row[0], row[1], merged)
        if case != self.case:
            return self._fill()
        self.waiting.discard(name)
        fails = dict(self.errors.get("text_errors") or {})
        fails.pop(name, None)
        if error:
            fails[name] = error
        self.errors["text_errors"] = fails
        if not self.waiting:
            restyle(self.note, "bad" if error else "ok")
            self.note.setText("Nicht geklappt, siehe unten." if error else "Fertig. Bitte prüfen, bevor du etwas übernimmst.")
        self._show({**((self.store.get(case) or (0, 0, {}))[2] or {}), **self.errors})
        self._fill()

    def info(self, text, bad=False):
        restyle(self.state, "bad" if bad else "muted")
        self.state.setText(text)
        self.hero.say(text if bad else "")

    def _tab(self, i):
        self.tabs.button(i).setChecked(True)
        self.stack.setCurrentIndex(i)
        self.frame_bar.setVisible(self.handover and i == 0)
        self._fill()

    def _fill(self):
        for trash, (search, items) in enumerate(self.lists):
            items.clear()
            rows = self.store.rows(bool(trash), search.text())
            for case_id, name, text, created, _ in rows:
                first = " ".join((text or "").split())[:80]
                item = QtWidgets.QListWidgetItem(f"{name or 'ohne Bezeichnung'}   ·   "
                                                 f"{time.strftime('%d.%m.%Y %H:%M', time.localtime(created))}   ·   {first}")
                item.setData(Qt.UserRole, case_id)
                items.addItem(item)
            self.tabs.button(1 + trash).setText(self.tab_names[1 + trash] + (f" ({len(rows)})" if rows else ""))

    def _each(self, which, action):
        for item in self.lists[which][1].selectedItems() or ([self.lists[which][1].currentItem()] if self.lists[which][1].currentItem() else []):
            action(item.data(Qt.UserRole))
        self._fill()

    def _rename(self):
        item = self.lists[0][1].currentItem()
        if not item:
            return
        case_id = item.data(Qt.UserRole)
        name, ok = QtWidgets.QInputDialog.getText(self, "Fall umbenennen", "Bezeichnung:",
                                                  text=(self.store.get(case_id) or [""])[0] or "")
        if ok:
            self.store.rename(case_id, name)
            if case_id == self.case:
                self.name.setText(name.strip())
            self._fill()

    def _empty(self):
        if not self.store.rows(True):
            return
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Papierkorb leeren")
        box.setText("Alle Fälle im Papierkorb endgültig löschen?")
        yes = box.addButton("Löschen", QtWidgets.QMessageBox.DestructiveRole)
        box.addButton("Abbrechen", QtWidgets.QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is yes:
            self.store.purge()
            self._fill()

    def _save(self):
        if self.recording:
            return                                  # während der Aufnahme sichert _part den gültigen Text
        if self.case is None and not self.text.toPlainText().strip() and not self.name.text().strip():
            return
        self.case = self.store.save(self.case, self.name.text().strip(), self.text.toPlainText())

    def _new(self):
        if self.recording or self.job.running:
            return self.info("Erst die Aufnahme beenden.", bad=True)
        self.saver.stop()
        self._save()
        self.case, self.result, self.waiting, self.items, self.typing = None, None, set(), [], False
        self._tray()
        for w in (self.name, self.text):
            w.blockSignals(True)
            w.clear()
            w.blockSignals(False)
        self.note.setText("")
        self.info("Aufnehmen oder in das Feld tippen.")
        self._set_frame(self.ctl.cfg.get("handover_frame"))
        self._show(None)
        self._tab(0)

    def _open(self, case_id):
        self._new()
        row = self.store.get(case_id)
        if not row or self.recording:
            return
        self.case = case_id
        self.name.setText(row[0] or "")
        self.text.blockSignals(True)
        self.text.setPlainText(row[1] or "")
        self.text.blockSignals(False)
        self.items = [dict(i) for i in ((row[2] or {}).get("items") or []) if isinstance(i, dict)]
        self._tray()
        self._set_frame((row[2] or {}).get("frame_next") or (row[2] or {}).get("frame"))
        self._show(row[2])

    # ----- Aufnahme
    def _rec_look(self, on):
        """Knopf in der Leiste und die Zeile mit Zeit und Pegel: Aufnahme läuft oder nicht."""
        restyle(self.rec, "recPillOn" if on else "recPill")
        self.rec.setText(" Stopp" if on else " Aufnahme")
        self.rec.setIcon(rec_icon("stop", "#16100D", 18) if on else rec_icon("mic", size=18))
        self.live_clock.setText("00:00")
        if on:
            self.live_wave.start()
            self.tick.start()
            self.meter.start()
        else:
            self.tick.stop()
            self.meter.stop()
            self.live_wave.stop()
        self.pulse.setVisible(on)

    def _record(self):
        if self.recording:
            self.recording = False
            self.ctl.keep_awake(False)
            self.job.stop_recording()
            self.rec.setEnabled(False)
            self._rec_look(False)
            self.rec.setText(" Schreibt …")
            return self.info("Schreibe den Rest fertig …")
        if self.job.running or self.window().busy():
            return self.info("Es läuft schon eine Aufnahme oder Transkription.", bad=True)
        if not self.ctl.ready:
            return self.info("Das Sprachmodell lädt noch – gleich noch einmal versuchen.", bad=True)
        self.saver.stop()
        self._save()
        try:
            self.job.start_recording()
        except Exception as e:
            return self.info(f"Mikrofon nicht verfügbar: {e}", bad=True)
        self.ctl.keep_awake(True)
        self.recording, self.started, self.heard = True, time.time(), ""
        self._state()
        self.before = self.text.toPlainText().rstrip()        # schon Getipptes bleibt, die Aufnahme kommt dahinter
        self.text.setReadOnly(True)
        self.tasks.setEnabled(False)
        self._rec_look(True)
        self.info("Nimmt auf … Der Text läuft mit.")

    def _whole(self, text):
        return (self.before + "\n\n" + text if self.before and text else self.before or text)

    def _live(self, text, glimpse=""):
        bar = self.text.verticalScrollBar()
        self.text.blockSignals(True)
        self.text.setPlainText(self._whole(text))
        if glimpse:
            cursor = self.text.textCursor()
            cursor.movePosition(QtGui.QTextCursor.End)
            grey = QtGui.QTextCharFormat()
            grey.setForeground(QtGui.QColor("#7A7A7A"))
            cursor.insertText((" " if text else "") + glimpse + " …", grey)
        self.text.blockSignals(False)
        bar.setValue(bar.maximum())

    def _part(self, text, done, total):
        self.heard = text
        self._live(text)
        self.case = self.store.save(self.case, self.name.text().strip(), self._whole(text))

    def _recorded(self, text, seconds, error):
        if self.recording:                              # Abbruch durch einen Fehler mitten in der Aufnahme
            self.recording = False
            self.ctl.keep_awake(False)
            self.job.stop_recording()
            self._rec_look(False)
        self.heard = text
        self._live(text)
        self.text.setReadOnly(False)
        self.rec.setEnabled(True)
        self.rec.setText(" Aufnahme")
        self.tasks.setEnabled(True)
        self.refresh()
        if text.strip() or self.before:
            self.case = self.store.save(self.case, self.name.text().strip(), self._whole(text))
        notes = []
        if self.job.failed:
            notes.append(f"{self.job.failed} Stelle(n) konnten nicht erkannt werden und sind im Text markiert.")
        if self.job.kept:
            notes.append(f"Die Tonaufnahme wurde deshalb nicht gelöscht: {self.job.kept}")
        if error:
            self.info(f"Fehler: {error}. {' '.join(notes)}", bad=True)
        elif notes:
            self.info(" ".join(notes), bad=True)
        elif text.strip():
            n = self.job.speakers
            who = f" {n} Sprecher erkannt." if self.ctl.cfg.get("speakers") and n > 1 else ""
            then = "„Auswerten“" if self.handover else "unten wählen, was daraus werden soll"
            self.info(f"Fertig – {clock(seconds)}, {len(text.split())} Wörter.{who} Text prüfen und korrigieren, dann "
                      f"{then}. Die Tonaufnahme ist gelöscht.")
        else:
            self.info("Kein Text erkannt. Die Tonaufnahme ist gelöscht.")

    # ----- Auswerten
    def _analyse(self):
        text = self._input()
        restyle(self.note, "bad")
        if not text:
            return self.note.setText("Erst den Fall aufnehmen oder eintippen.")
        cfg = copy.deepcopy(self.ctl.cfg)
        server = visite.writer(cfg)
        if not (server.get("base_url") or "").strip() or not (server.get("model") or "").strip():
            return self.note.setText("Kein Sprachmodell eingestellt. Unter Einstellungen, LLM, Server und Modell wählen.")
        self.saver.stop()
        self._save()
        if self.waiting & {"brief", "jev"}:
            return
        if schutz.blocked(server) and self.window().shield_wait(self._analyse):
            restyle(self.note, "muted")
            return self.note.setText("Die Namenserkennung wird einmalig geladen. Die Auswertung startet danach von selbst.")
        restyle(self.note, "muted")
        self.note.setText("Läuft …")
        case, frame = self.case, self.frame()
        keep = {k: (self.result or {})[k] for k in ("texts", "items") if (self.result or {}).get(k)}
        if self.items:
            keep["items"] = self.items
        self.result = {**keep, "visit": True, "frame": frame}
        self.errors = {k: v for k, v in self.errors.items() if k == "text_errors"}
        self.waiting |= {"brief"} | ({"jev"} if jev.available(server) else set())
        self._show(self.result)

        def run(call, signal):
            try:
                signal.emit(call(cfg, text, frame=frame), "", case)
            except Exception as e:
                log.warning("Visite: %s fehlgeschlagen: %s", call.__name__, type(e).__name__)
                signal.emit(None, str(e) or type(e).__name__, case)
        if "jev" in self.waiting:
            threading.Thread(target=run, args=(visite.triage, self.sig_jev), daemon=True).start()
        threading.Thread(target=run, args=(visite.analyse, self.sig_done), daemon=True).start()

    def _arrived(self, part, result, error, case):
        """Ein Teilergebnis ist da: zum Fall legen, sichern, anzeigen."""
        row = self.store.get(case)
        if row and result is not None:
            merged = dict(row[2] or {})
            if part == "jev":
                merged["jev"] = result
                if "documentation" not in merged:
                    merged["frame"] = result.get("frame") or "zna"
            else:
                merged = {**result, **{k: merged[k] for k in ("jev", "texts", "items") if merged.get(k)}}
                if (merged.get("jev") or {}).get("frame", "zna") != merged.get("frame", "zna"):
                    merged.pop("jev")                # Ersteinschätzung aus einem anderen Rahmen passt nicht mehr dazu
            merged.pop("frame_next", None)
            merged["visit"] = True
            self.store.save(case, row[0], row[1], merged)
        if case != self.case:
            return self._fill()
        self.waiting.discard(part)
        if result is None:
            self.errors["jev_error" if part == "jev" else "error"] = error
        if not self.waiting:
            failed = self.errors.get("error")
            restyle(self.note, "bad" if failed else "ok")
            self.note.setText("Der Arztbrief ließ sich nicht erzeugen, siehe unten." if failed
                              else "Fertig. Bitte prüfen, bevor du etwas übernimmst.")
        self._show({**((row[2] if row and result is None else self.store.get(case)[2]) or {}), **self.errors})
        self._fill()

    def _jev(self, result, error, case):
        self._arrived("jev", result, error, case)

    def _done(self, result, error, case):
        self._arrived("brief", result, error, case)

    # ----- Ergebnis in Blöcken
    ORDER = ("jev", "netz", "fragen", "brief", "codes", "info")
    TITLES = {"jev": "Ersteinschätzung", "netz": "Sicherheitsnetz", "fragen": "Gezielte Rückfragen", "brief": "Arztbrief",
              "codes": "Kodierung", "info": "Patienteninfo"}

    def _show(self, result):
        """Sechs Blöcke, immer an derselben Stelle: oben Ersteinschätzung, Sicherheitsnetz und Rückfragen nebeneinander,
        darunter der Arztbrief, daneben Kodierung und Patienteninfo. Was noch läuft oder fehlt, sagt der Block selbst."""
        self.result = result
        for box in self.boxes.values():
            box.setParent(None)
            box.deleteLater()
        for box in self.text_boxes:
            box.setParent(None)
            box.deleteLater()
        self.boxes, self.columns, self.text_boxes = {}, 0, []
        done, fails = (result or {}).get("texts") or {}, (result or {}).get("text_errors") or {}
        running = [n for n in self.waiting if n not in ("brief", "jev")]
        structured = bool(result) and bool(result.get("visit") or self.waiting & {"brief", "jev"}
                                           or any(k in result for k in ("documentation", "jev", "error", "jev_error")))
        output = bool(done or fails or running or structured)
        self.area.setVisible(output)
        self.text.setMaximumHeight(118 if output else 16777215)     # mit Ergebnis tritt der Text zurück
        self._state()
        if not output:
            return
        for name in list(dict.fromkeys(running + list(fails) + list(reversed(list(done))))):
            if name in running or name in fails:
                box = Box(name)
                box.add(label(f"Nicht geklappt: {fails[name]}" if name in fails and name not in running
                              else "Das Sprachmodell schreibt …", "bad" if name in fails and name not in running else "muted",
                              wrap=True))
            else:
                body = done[name]
                box = Box(name, copy=lambda b=body: b)
                out = label(body, wrap=True)
                out.setTextFormat(Qt.PlainText)
                out.setTextInteractionFlags(Qt.TextSelectableByMouse)
                box.add(out)
            self.texts.addWidget(box)
            self.text_boxes.append(box)
        if not structured:
            return
        # Was gerade neu erzeugt wird, zeigt den Wartetext statt der alten Fassung
        made = {"jev": self._jev_box(result["jev"]) if result.get("jev") and "jev" not in self.waiting else None,
                **({} if "brief" in self.waiting else self._letter_boxes(result))}
        pending = self.frame() if self.waiting & {"brief", "jev"} else result.get("frame")
        titles = {**self.TITLES, **visite.NAMES[visite.frame_of(pending)]}
        for key in self.ORDER:
            box = made.get(key)
            if box is None:
                part = "jev" if key == "jev" else "brief"
                error = result.get("jev_error" if key == "jev" else "error")
                text = (f"Nicht geklappt: {error}" if error else
                        ("Jev bewertet den Fall …" if key == "jev" else "Das Sprachmodell schreibt …") if part in self.waiting else
                        "Nur über OpenRouter (Einstellungen, LLM)." if key == "jev" else "Keine Angabe.")
                box = Box(titles[key])
                box.add(label(text, "bad" if error else "muted", wrap=True))
            box.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)   # Spalten gleich breit
            self.boxes[key] = box
        self._place()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place()

    def _place(self):
        """Blöcke ins Raster legen: drei Spalten im breiten Fenster, zwei im schmalen, eine im sehr schmalen."""
        if not self.boxes:
            return
        width = self.area.viewport().width() or self.width()
        columns = 3 if width >= 840 else 2 if width >= 560 else 1
        if columns == self.columns:
            return
        self.columns = columns
        spots = {3: {"jev": (0, 0, 1, 1), "netz": (0, 1, 1, 1), "fragen": (0, 2, 1, 1), "brief": (1, 0, 2, 2),
                     "codes": (1, 2, 1, 1), "info": (2, 2, 1, 1)},
                 2: {"jev": (0, 0, 1, 1), "netz": (0, 1, 1, 1), "fragen": (1, 0, 1, 2), "brief": (2, 0, 1, 2),
                     "codes": (3, 0, 1, 1), "info": (3, 1, 1, 1)},
                 1: {key: (i, 0, 1, 1) for i, key in enumerate(self.ORDER)}}[columns]
        for key, box in self.boxes.items():
            self.cards.removeWidget(box)
        for c in range(3):
            self.cards.setColumnStretch(c, 1 if c < columns else 0)
        for key, box in self.boxes.items():
            self.cards.addWidget(box, *spots[key])
        self.cards.setRowStretch(4, 1)

    @staticmethod
    def _jev_box(d):
        v = jev.view(d)
        if v.get("frame") in jev.LAYOUT:             # Station und Intensiv: Lage als Kärtchen, darunter „heute prüfen“
            box = Box(v["title"], "Jev", copy=lambda: jev.export(d))
            chips = Flow(gap=6)
            for text, p, kind in v["flags"]:
                if p is not None:
                    chips.addWidget(chip(f"{text} · {jev.pct(p)}", kind if p >= jev.HIGH else "chipOff"))
            box.add(chips)
            rows = [(n, p) for n, p, _ in v["measures"] + v["imaging"] if p is not None]
            yes, no = [r for r in rows if r[1] >= jev.HIGH], [r for r in rows if r[1] < jev.HIGH]
            if yes:
                box.add(label("HEUTE PRÜFEN", "kicker"))
                line = Flow(gap=6)
                for name, p in sorted(yes, key=lambda r: -r[1]):
                    line.addWidget(chip(f"{name} {jev.pct(p)}", "chipLine"))
                box.add(line)
            if no:
                box.add(label("Unter 70 %: " + ", ".join(f"{n} {jev.pct(p).replace(' ', '')}" for n, p in no), "muted", wrap=True))
            return box
        box = Box("Ersteinschätzung", "Jev", copy=lambda: jev.export(d))
        chips = Flow(gap=6)
        if v["shock"]:
            chips.addWidget(chip(f"Schockraum {v['shock'][0]} · {jev.pct(v['shock'][1])}",
                                 "chipRed" if v["shock"][0] == "ROT" else "chipWarn"))
        if v["place"]:
            chips.addWidget(chip(f"{v['place']} · {jev.pct(v['place_p'])}"))
        if v["specialty"]:
            chips.addWidget(chip(f"Fallführung: {v['ward']}"))
        if not v["practice"] and v["admission"] is not None:
            chips.addWidget(chip(f"Bett suchen: {v['ward'] or 'offen'} · {jev.pct(v['admission'])}", "chipWarn")
                            if v["bed"] else chip(f"kein Bett · Aufnahme {jev.pct(v['admission'])}", "chipOff"))
        if v["sepsis"]:
            chips.addWidget(chip("Sepsis-Screening, Blutkulturen", "chipWarn"))
        box.add(chips)
        rows = v["measures"] + v["imaging"]
        short = {"12-Kanal-EKG": "EKG", "i.v.-Zugang": "Zugang", "Sonografie": "Sono"}      # die Spalte ist schmal
        yes = [(n, p, x) for n, p, x in rows if p is not None and p >= jev.HIGH]
        no = [(n, p) for n, p, x in rows if p is not None and p < jev.HIGH]
        if yes:
            box.add(label("VORGESCHLAGEN", "kicker"))
            line = Flow(gap=6)
            for name, p, extra in yes:
                line.addWidget(chip(f"{short.get(name, name)}{' ' + extra if extra else ''} {jev.pct(p)}", "chipLine"))
            box.add(line)
        if no:
            box.add(label("Unter 70 %: " + ", ".join(f"{short.get(n, n)} {jev.pct(p).replace(' ', '')}" for n, p in no), "muted", wrap=True))
        return box

    def _letter_boxes(self, result):
        boxes = {}
        names = visite.NAMES[visite.frame_of(result.get("frame"))]
        doc = result.get("documentation") or {}
        parts = [(title, str(doc[key]).strip()) for key, title in visite.sections(result.get("frame"))
                 if str(doc.get(key) or "").strip()]
        if parts:
            box = Box(names["brief"], "Entwurf", copy=lambda: visite.letter(result))
            folds = [box.add(Fold(title, text, opened=(i == 0))) for i, (title, text) in enumerate(parts)]
            more = button("Alle öffnen", name="ghost")
            more.clicked.connect(lambda: [f.flip(to=True) for f in folds])
            box.head.insertWidget(box.head.count() - 1, more)
            boxes["brief"] = box
        if "documentation" not in result:
            return boxes
        alerts = [a for a in result.get("safetyAlerts") or [] if isinstance(a, dict)]
        box = Box("Sicherheitsnetz", copy=(lambda: "\n".join(f"{a.get('context', '')}: {a.get('suggestion', '')}" for a in alerts)) if alerts else None)
        for a in alerts:
            row = QtWidgets.QFrame(objectName="alert")
            lay = QtWidgets.QVBoxLayout(row)
            lay.setContentsMargins(11, 7, 10, 8)
            lay.setSpacing(2)
            lay.addWidget(label(str(a.get("context") or ""), "warn", wrap=True))
            lay.addWidget(label(str(a.get("suggestion") or ""), wrap=True))
            box.add(row)
        if not alerts:
            box.add(label("Keine Hinweise.", "muted"))
        boxes["netz"] = box
        asks = [q for q in result.get("followUpQuestions") or [] if isinstance(q, dict)]
        box = Box("Gezielte Rückfragen", copy=(lambda: "\n".join(f"{i}. {q.get('question', '')}" for i, q in enumerate(asks, 1))) if asks else None)
        for i, q in enumerate(asks, 1):
            word, kind = self.PRIORITY.get(q.get("priority"), self.PRIORITY["medium"])
            row = QtWidgets.QFrame(objectName="ask")
            lay = QtWidgets.QVBoxLayout(row)
            lay.setContentsMargins(11, 8, 10, 9)
            lay.setSpacing(4)
            lay.addWidget(label(f"{i}.  {q.get('question') or ''}", "strong", wrap=True))
            if q.get("rationale"):
                lay.addWidget(label(str(q["rationale"]), "muted", wrap=True))
            lay.addLayout(hbox(chip(word, kind), None))
            if self.handover:
                asked = str(q.get("question") or "")
                had = next((it for it in self.items if it.get("label") == f"Rückfrage {i} · Antwort"
                            and it.get("content", "").startswith(f"Frage: {asked}")), None)
                reply = QtWidgets.QLineEdit(placeholderText="Antwort eintragen …")
                if had:
                    reply.setText(had["content"].split("\nAntwort: ", 1)[-1])
                    reply.setCursorPosition(0)
                send = button("Ändern" if had else "Ablegen", lambda _=False, n=i, a=asked, e=reply: self._answer(n, a, e.text()))
                reply.returnPressed.connect(send.click)
                lay.addLayout(hbox((reply, 1), send))
            box.add(row)
        if not asks:
            box.add(label("Keine Rückfragen.", "muted"))
        boxes["fragen"] = box
        codes = [c for c in result.get("codes") or [] if isinstance(c, dict)]
        if codes:
            box = Box("Kodierung", copy=lambda: "\n".join(f"{c.get('code', '')} {c.get('description', '')}" for c in codes))
            for c in codes:
                box.add(hbox(chip(str(c.get("code") or ""), "chip" if c.get("revenueRelevant") else "chipOff"),
                             (label(str(c.get("description") or ""), wrap=True), 1)))
            boxes["codes"] = box
        info = result.get("patientHandout") or {}
        if str(info.get("content") or "").strip():
            box = Box(names["info"], folded=True,
                      copy=lambda: f"{info.get('title', '')}\n{info.get('content', '')}".strip())
            box.add(label(str(info.get("title") or ""), "strong", wrap=True))
            text = label(str(info.get("content") or ""), wrap=True)
            text.setTextInteractionFlags(Qt.TextSelectableByMouse)
            box.add(text)
            boxes["info"] = box
        return boxes


# ---------------------------------------------------------------- Stimmtraining
class TrainPage(Page):
    """Sätze vorlesen; was die Erkennung dabei falsch schreibt, kommt ins persönliche Wörterbuch."""
    sig_pairs = Signal(object, int, object, int)

    def __init__(self, ctl):
        super().__init__("Stimmtraining",
                         "Lies medizinische Sätze vor. LocalScribe vergleicht, was es verstanden hat, mit dem, was "
                         "dasteht, und merkt sich deine Aussprache der Fachbegriffe im Wörterbuch. Freiwillig, "
                         "jederzeit unterbrechbar. Die wichtigsten Sätze kommen zuerst: Auch fünf Minuten lohnen sich. "
                         "Der Ton dieser erfundenen Sätze wird auf diesem Rechner aufgehoben, damit das Sprachmodell "
                         "später auf deine Stimme nachtrainiert werden kann; Diktate werden nie aufgehoben.")
        self.ctl = ctl
        self.topic = QtWidgets.QComboBox()
        self.topic.addItem(f"Grundstock für alle · {training.minutes(training.sentences()):.0f} Minuten", training.BASE)
        for name in training.fields():
            self.topic.addItem(f"{name} · {training.minutes(training.sentences(name)):.0f} Minuten", name)
        if training.topics():
            self.topic.insertSeparator(self.topic.count())
        for name in training.topics():
            self.topic.addItem(f"{name} · bisherige Sätze ({len(training.sentences(name))})", name)
        self.topic.setToolTip("Eine Fachrichtung beginnt mit dem Grundstock und bringt danach ihre eigenen Sätze. "
                              "Die Minuten gelten für beides zusammen.")
        # die Auswahl darf die Karte nicht breiter machen als das Fenster: Sie füllt den Platz, statt ihn zu fordern
        self.topic.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.topic.setMinimumContentsLength(16)
        self.topic.setMaximumWidth(460)
        self.topic.setCurrentIndex(max(0, self.topic.findData(ctl.cfg.get("field") or training.BASE)))
        self.topic.currentIndexChanged.connect(self._field)
        self.testing = None                              # läuft eine Messung: {"items", "errors", "words", "n", "field"}
        self.count = label("", "muted")
        self.count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.sentence = label("", "h2", wrap=True)
        self.sentence.setMinimumHeight(74)
        self.speak = button("Halten und vorlesen", name="primary")
        self.speak.pressed.connect(self._listen)
        self.speak.released.connect(self.ctl.listen_stop)
        self.result = label("Knopf gedrückt halten, den Satz in deinem normalen Diktiertempo vorlesen, loslassen. "
                            "Zahlen und Einheiten so sprechen, wie du es sonst auch tust.", "muted", wrap=True)
        self.test_btn = button("Messen …", self._test)
        self.test_btn.setToolTip("Liest Prüfsätze, die im Training nie vorkommen, und zeigt deine Wortfehlerquote. "
                                 "Einmal vor dem Training und später wieder: So siehst du, was das Vorlesen gebracht hat.")
        self.scores = label("", "muted", wrap=True)
        self.body.addWidget(card(hbox(label("Fachrichtung"), (self.topic, 1), self.count),
                                 self.sentence,
                                 hbox(self.speak, button("Überspringen", self._skip),
                                      button("Zurück", lambda: self.next(-1)), None, self.test_btn),
                                 self.result, self.scores))
        self.learned = label("", "muted", wrap=True)
        self.learned.hide()                              # steht im Wörterbuch; hier nur die Meldung nach jedem Satz
        self.pairs = label("Diktate mit fertigem Text: Tondateien wählen, das Transkript liegt als Textdatei gleichen "
                           "Namens daneben oder wird im zweiten Schritt gewählt. Eigene Briefe und Befunde: LocalScribe "
                           "liest daraus nur einzelne Fachwörter. Ton und Texte werden nur gelesen, nicht gespeichert.",
                           "muted", wrap=True)
        self.pair_btn = button("Aufnahmen mit Transkript wählen …", self._pairs)
        self.words = label("", "muted", wrap=True)
        self.words.setMaximumHeight(40)
        self.words_n = label("", "muted")
        self.body.addWidget(card(label("Aus eigenem Material lernen", "h2"), self.pairs,
                                 hbox(self.pair_btn, button("Aus eigenen Texten lernen …", self._learn_files), None,
                                      self.words_n, button("Leeren", self._learn_clear)), self.words))
        self.kept = label("", "muted", wrap=True)
        self.body.addWidget(card(label("Deine Stimmaufnahmen", "h2"), self.kept,
                                 hbox(button("Ordner öffnen", self._open_store), button("Alle löschen", self._clear), None)))
        self.sig_pairs.connect(self._pairs_done)
        self.body.addStretch(1)
        self.items, self.pos, self.session = [], 0, []
        self.ctl.sig_heard.connect(self._heard)

    def refresh(self):
        self.next(0)
        self._kept()
        self._words()
        self._scores()

    def _field(self, _):
        """Fachrichtung gewählt: merken, eine laufende Messung endet."""
        self.testing = None
        self.test_btn.setText("Messen …")
        name = self.topic.currentData() or training.BASE
        if name != (self.ctl.cfg.get("field") or training.BASE):
            self.ctl.cfg["field"] = name
            config.save(self.ctl.cfg)
        self.next(0)

    def _items(self):
        if self.testing:
            return self.testing["items"]
        return training.sentences(self.topic.currentData() or training.BASE)

    def next(self, step):
        self.items = self._items()
        if self.testing:                            # Messung: der Reihe nach, ohne Zurück
            self.pos = min(self.testing["n"], len(self.items) - 1)
            self.sentence.setText(self.items[self.pos])
            return self.count.setText(f"Messung: Satz {self.pos + 1} von {len(self.items)}")
        done = set(self.ctl.cfg.get("training_done") or [])
        if step == 0:                               # beim Öffnen: erster noch nicht gelesener Satz
            self.pos = next((i for i, s in enumerate(self.items) if s not in done), 0)
        else:
            self.pos = (self.pos + step) % len(self.items)
        self.sentence.setText(self.items[self.pos])
        read = [s for s in self.items if s in done]
        self.count.setText(f"{len(read)} von {len(self.items)} gelesen · {training.minutes(read):.0f} von "
                           f"{training.minutes(self.items):.0f} Minuten")
        if self.session:
            self.learned.setText("In dieser Sitzung: " + ", ".join(f"„{w}“ → „{r}“" for w, r in self.session))
        else:
            n = len(self.ctl.cfg.get("dictionary") or {})
            self.learned.setText(f"Im Wörterbuch stehen {n} Einträge. Neue erscheinen hier und auf der Seite Wörterbuch; "
                                 "dort lassen sie sich ändern oder löschen.")

    def _learn_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Eigene Texte auswählen (Briefe, Befunde, Textbausteine)", "",
            "Texte (*.docx *.odt *.txt *.md *.rtf *.html);;Alle Dateien (*)")
        if not paths:
            return
        added, failed = wortschatz.learn_files(self.ctl.cfg, paths)
        self.ctl.apply_cfg()
        self._words()
        note = f"{added} neue Fachwörter aus {len(paths) - len(failed)} Datei(en) gelernt."
        if failed:
            note += " Nicht lesbar: " + ", ".join(failed[:5]) + "."
        self.words.setText(note)

    def _learn_clear(self):
        if self.ctl.cfg.get("learned"):
            self.ctl.cfg["learned"] = []
            self.ctl.apply_cfg()
            self._words()

    def _words(self):
        n = len(self.ctl.cfg.get("learned") or [])
        self.words_n.setText(f"{n:,} Fachwörter gelernt".replace(",", "."))
        self.words.setText("Fachwörter aus deinen Diktaten, Transkripten und eingelesenen Briefen; beim Erkennen werden sie "
                           "bevorzugt. Übernommen werden nur einzelne Wörter aus dem Lexikon, keine Sätze, keine Namen.")

    # ----- Messen: Prüfsätze, die im Training nie vorkommen
    def _test(self):
        if self.testing:                            # abbrechen
            self.testing = None
            self.test_btn.setText("Messen …")
            restyle(self.result, "muted")
            self.result.setText("Messung abgebrochen.")
            return self.next(0)
        name = self.topic.currentData() or training.BASE
        items = training.held_out(name if name in training.fields() else training.BASE)
        if not items:
            return self.result.setText("Für diese Auswahl gibt es keine Prüfsätze.")
        self.testing = {"items": items, "errors": 0, "words": 0, "n": 0, "field": name}
        self.test_btn.setText("Messung abbrechen")
        restyle(self.result, "muted")
        self.result.setText(f"Messung mit {len(items)} Prüfsätzen, etwa {max(1, round(training.minutes(items)))} Minuten. Lies jeden "
                            "Satz einmal, so wie du diktierst. Hier wird nichts gelernt, nur gezählt.")
        self.next(0)

    def _measured(self, expected, text, audio):
        """Ein Prüfsatz ist gelesen: zählen, Ton zu den Prüfsätzen legen, am Ende das Ergebnis festhalten."""
        cfg, t = self.ctl.cfg, self.testing
        heard = engine.postprocess(text, dict(cfg, trailing_space=False))      # so, wie der Text beim Diktieren ankäme
        if not heard.strip():
            restyle(self.result, "bad")
            return self.result.setText("Nichts verstanden – bitte noch einmal, Knopf erst drücken, dann sprechen.")
        wrong, words = training.score(expected, heard)
        t["errors"], t["words"], t["n"] = t["errors"] + wrong, t["words"] + words, t["n"] + 1
        if cfg.get("training_keep", True) and audio is not None and len(audio):
            try:
                training.keep(audio, expected, test=True)
            except OSError:
                log.exception("Prüfsatz ließ sich nicht aufheben")
        if t["n"] < len(t["items"]):
            restyle(self.result, "muted")
            self.result.setText(f"Verstanden: „{heard.strip()}“")
            return self.next(1)
        self._test_done()

    def _skip(self):
        if not self.testing:
            return self.next(1)
        self.testing["n"] += 1                      # ausgelassener Prüfsatz zählt nicht mit
        if self.testing["n"] < len(self.testing["items"]):
            return self.next(1)
        self._test_done()

    def _test_done(self):
        cfg, t = self.ctl.cfg, self.testing
        self.testing = None
        self.test_btn.setText("Messen …")
        if not t["words"]:
            restyle(self.result, "muted")
            self.result.setText("Messung ohne gelesenen Satz beendet.")
            return self.next(0)
        rate = 100 * t["errors"] / max(1, t["words"])
        cfg["training_scores"] = (cfg.get("training_scores") or [])[-19:] + [{
            "at": time.time(), "field": t["field"], "wer": round(rate, 1), "words": t["words"],
            "minutes": round(training.kept()[1] / 60, 1)}]
        self.ctl.apply_cfg()
        restyle(self.result, "ok")
        self.result.setText(f"Messung fertig: {f'{rate:.1f}'.replace('.', ',')} % Wortfehler ({t['words']} Wörter). "
                            "Wiederhole sie nach dem Training zum Vergleich.")
        self._scores()
        self._kept()
        self.next(0)

    def _scores(self):
        rows = self.ctl.cfg.get("training_scores") or []
        if not rows:
            return self.scores.setText("Noch keine Messung. Miss einmal vor dem Training („Messen …“, etwa fünf Minuten): "
                                       "Dann zeigt dir eine spätere Messung, was das Vorlesen gebracht hat.")
        self.scores.setText("Messungen: " + "  →  ".join(
            f"{time.strftime('%d.%m.', time.localtime(r.get('at', 0)))} {str(r.get('wer')).replace('.', ',')} % "
            f"(nach {str(r.get('minutes', 0)).replace('.', ',')} Minuten Training)" for r in rows[-4:]))

    def _open_store(self):
        training.store().mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(training.store())))

    def _kept(self):
        n, sec = training.kept()
        tests = training.kept(test=True)[0]
        self.kept.setText(f"{n} Übungs{'satz' if n == 1 else 'sätze'}, {sec / 60:.1f} Minuten".replace(".", ",")
                          + (f", dazu {tests} Prüfsätze" if tests else "")
                          + ". Sie liegen im Datenordner von LocalScribe, verlassen ihn nicht und gehören zu deinem Profil "
                          "(Einstellungen, „Profil sichern“). Aufgehoben werden nur die erfundenen Sätze dieser Seite, nie "
                          "Diktate. Ab etwa 30 Minuten lohnt ein Nachtraining des Sprachmodells auf deine Stimme.")

    def _pairs(self):
        if self.ctl.transcriber is None or not getattr(self.ctl, "ready", True):
            return self.pairs.setText("Das Sprachmodell ist noch nicht bereit.")
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Aufnahmen wählen", "", "Ton (*.wav *.mp3 *.m4a *.ogg *.flac *.opus *.wma *.aac *.mp4);;Alle Dateien (*)")
        if not paths:
            return
        jobs, missing = [], []
        for path in paths:
            text = training.partner(path)
            (jobs if text else missing).append((path, text))
        if len(missing) == 1:
            text, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Transkript zu " + os.path.basename(missing[0][0]), os.path.dirname(missing[0][0]),
                "Text (*.txt *.docx *.odt *.md *.rtf)")
            if text:
                jobs.append((missing[0][0], text))
                missing = []
        if not jobs:
            return self.pairs.setText("Zu den gewählten Aufnahmen liegt kein Transkript mit gleichem Namen im selben Ordner.")
        self.pair_btn.setEnabled(False)
        self.pairs.setText(f"Lerne aus {len(jobs)} Aufnahme{'n' if len(jobs) != 1 else ''} …")
        skipped = [os.path.basename(p) for p, _ in missing]

        def work():
            new, words, bad, good = [], 0, list(skipped), 0
            for audio, text in jobs:
                try:
                    ok, pairs, n = training.from_recording(self.ctl.transcriber, self.ctl.cfg, audio, wortschatz.read(text))
                    if ok:
                        good += 1
                        new += pairs
                        words += n
                    else:
                        bad.append(os.path.basename(audio))
                except Exception:
                    log.exception("Lernen aus Aufnahme fehlgeschlagen")
                    bad.append(os.path.basename(audio))
            self.sig_pairs.emit(new, words, bad, good)
        threading.Thread(target=work, daemon=True).start()

    def _pairs_done(self, new, words, bad, good):
        self.pair_btn.setEnabled(True)
        self.ctl.apply_cfg()
        self.session += new
        note = (f"Aus {good} Aufnahme{'n' if good != 1 else ''} gelernt: "
                f"{len(new)} Verhörer fürs Wörterbuch, {words} Fachwörter für den Wortschatz.")
        if new:
            note += " " + ", ".join(f"„{w}“ → „{r}“" for w, r in new[:12]) + ("." if len(new) <= 12 else " …")
        if bad:
            note += " Nicht verwendet (kein passendes Transkript oder nicht lesbar): " + ", ".join(bad[:6]) + "."
        self.pairs.setText(note + " Der Ton wurde nicht gespeichert.")
        self.next(0)
        self._words()

    def _clear(self):
        n, _ = training.kept()
        if not n:
            return
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Aufnahmen löschen")
        box.setText(f"{n} Aufnahmen aus dem Stimmtraining und alle Prüfsätze endgültig löschen?")
        yes = box.addButton("Löschen", QtWidgets.QMessageBox.DestructiveRole)
        box.addButton("Abbrechen", QtWidgets.QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is yes:
            training.clear()
            self._kept()

    def _listen(self):
        error = self.ctl.listen_start(self)
        restyle(self.result, "bad" if error else "muted")
        self.result.setText(error or "Höre zu …")

    def _heard(self, text, error):
        if self.ctl.listener is not self:
            return
        if error:
            restyle(self.result, "bad")
            return self.result.setText(f"Das hat nicht geklappt: {error}")
        cfg = self.ctl.cfg
        if self.testing:
            return self._measured(self.items[self.pos], text, getattr(self.ctl, "heard_audio", None))
        # so, wie der Text ohne persönliches Wörterbuch ankäme: gelernt wird nur, was dann noch falsch ist
        heard = engine.postprocess(text, {"dictionary": {}, "trailing_space": False,
                                          "base_dictionary": cfg.get("base_dictionary", True),
                                          "model_choice": cfg.get("model_choice", "de")})
        expected = self.items[self.pos]
        read, learned, open_ = training.learn(expected, heard)
        if not read:
            restyle(self.result, "bad")
            return self.result.setText(f"Verstanden: „{heard or 'nichts'}“. Das passt nicht zum Satz – bitte noch "
                                       "einmal, Knopf erst drücken, dann sprechen.")
        data = dict(cfg.get("dictionary") or {})
        new = [(w, r) for w, r in learned if data.get(w) != r]
        for w, r in new:
            data[w] = r
        cfg["dictionary"] = data
        cfg["training_done"] = sorted(set(cfg.get("training_done") or []) | {expected})
        self.ctl.apply_cfg()
        audio = getattr(self.ctl, "heard_audio", None)
        if cfg.get("training_keep", True) and audio is not None and len(audio):
            try:
                training.keep(audio, expected)
            except OSError:
                log.exception("Aufnahme ließ sich nicht aufheben")
            self._kept()
        self.session += new
        parts = []
        if new:
            parts.append("Gelernt: " + ", ".join(f"„{w}“ → „{r}“" for w, r in new) + ".")
        if open_:
            parts.append("Nicht lernbar, weil das Verstandene selbst ein richtiges Wort ist: "
                         + ", ".join(f"„{w}“ statt „{r}“" for w, r in open_) + ".")
        if not parts:
            parts.append("Alles richtig verstanden.")
        restyle(self.result, "ok" if not open_ else "muted")
        self.result.setText(" ".join(parts))
        self.next(1)


# ---------------------------------------------------------------- KI
class LlmPage(Page):
    sig_models = Signal(object, str)
    sig_test = Signal(str, str, float)
    sig_shield = Signal(float, str)

    def __init__(self, ctl):
        super().__init__("LLM",
                         "Das Sprachmodell für die KI-Nachbearbeitung (Transkript mit einem deiner Prompts überarbeiten), "
                         "die Fachkorrektur und die Übergabe. Funktioniert mit jedem Server, der die "
                         "OpenAI-Schnittstelle spricht – auf diesem Rechner oder bei einem Anbieter deiner Wahl.")
        self.ctl = ctl
        self.prompts, self.current = [], -1
        self.note = label("")
        self.head.addWidget(self.note)
        self.head.addWidget(button("Speichern", self.save, "primary"))

        # Verbindung
        self.active = ""                  # Name des gewählten gespeicherten Anbieters
        self.profile = QtWidgets.QComboBox()
        self.profile.setMinimumWidth(220)
        self.profile.activated.connect(self._pick)
        self.protect = QtWidgets.QCheckBox("Vor dem Versand schützen: Namen, Daten, Nummern und Anschriften durch Platzhalter ersetzen")
        self.protect.setToolTip("Gilt für jeden Server außerhalb dieses Rechners. Der Server sieht „[NAME_1] kam am "
                                "[DATUM_1]“; die Antwort wird hier zurückübersetzt.")
        self.shield = label("", "muted", wrap=True)
        self.shield_btn = button("Namenserkennung laden (293 MB)", self._shield_load)
        self.enabled = QtWidgets.QCheckBox("KI-Nachbearbeitung einschalten")
        self.preset = QtWidgets.QComboBox()
        for name, _ in PRESETS:
            self.preset.addItem(name)
        self.preset.activated.connect(self._preset)
        self.url = QtWidgets.QLineEdit(placeholderText="https://…/v1")
        self.url.textEdited.connect(lambda: self.preset.setCurrentIndex(len(PRESETS) - 1))
        self.url.textChanged.connect(self._where)
        self.url.editingFinished.connect(lambda: self._fill_models())
        self.where = label("", "muted", wrap=True)
        self.advice = label("", "muted", wrap=True)
        self.advice.hide()
        self.key = QtWidgets.QLineEdit()
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.remote = {}                  # Server -> Modelle, die er in diesem Programmlauf gemeldet hat
        self.model = QtWidgets.QComboBox()
        self.model.setMaxVisibleItems(14)
        self.model.setPlaceholderText("Modelle abrufen oder mit + eintragen")
        self.model.setToolTip(MODEL_TIP)
        self.model.currentIndexChanged.connect(self._model_picked)
        self.add = button("+", self._add_model)
        self.add.setToolTip("Eigenen Modellnamen hinzufügen, so wie ihn der Server kennt. Der Zusatz @low hinter dem "
                            "Namen lässt ein denkendes Modell weniger nachdenken.")
        self.drop = button("Entfernen", self._drop_model, "ghost")
        self.drop.hide()
        self.status = label("", "muted", wrap=True)
        self.status.hide()
        self.fetch = button("Modelle abrufen", self.load_models)
        self.fix = QtWidgets.QCheckBox("Fachkorrektur: Hörfehler bei Fachbegriffen vom Sprachmodell korrigieren lassen")
        self.fix.setToolTip("Das Sprachmodell schlägt vor, was bei verhörten Wörtern gemeint war. Übernommen wird nur, "
                            "was selbst ein Fachbegriff ist, ähnlich klingt und keine Zahl ändert. Kostet je Diktat "
                            "eine Anfrage an den Server oben; mit kleinen lokalen Modellen bringt es wenig. Bei "
                            "OpenRouter und Noirdoc nimmt sie immer Gemini 3.1 Flash Lite, damit kein Diktat wartet.")
        self.body.addWidget(card(
            self.enabled,
            self.fix,
            form(("Anbieter", hbox((self.profile, 1), button("Speichern als …", self._save_as),
                                   button("Löschen", self._delete, "ghost"))),
                 ("Server", hbox(self.preset, (self.url, 1))),
                 ("API-Schlüssel", hbox((self.key, 1), button("Entfernen", self.drop_key, "ghost"))),
                 ("Modell", hbox((self.model, 1), self.add, self.drop, self.fetch))),
            self.where, self.advice, self.status,
            self.protect, hbox((self.shield, 1), self.shield_btn)))

        # Prompts
        self.list = QtWidgets.QListWidget()
        self.list.setFixedWidth(190)
        self.list.currentRowChanged.connect(self._select)
        self.name = QtWidgets.QLineEdit()
        self.name.textEdited.connect(self._rename)
        self.hotkey = KeyField(ctl)
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setMinimumHeight(110)
        self.auto = QtWidgets.QComboBox()
        left = QtWidgets.QVBoxLayout()
        left.addWidget(self.list, 1)
        left.addLayout(hbox(button("Neu", self.new_prompt), button("Löschen", self.del_prompt), None, spacing=6))
        self.on_record = QtWidgets.QCheckBox("Auf der Seite Aufnahme als Knopf anbieten")
        right = form(("Name", self.name), ("Halte-Taste", self.hotkey), ("Anweisung", self.text), ("", self.on_record))
        self.body.addWidget(card(
            label("Aufträge (Prompts)", "h2"),
            label("Aufträge stehen im Verlauf unter „KI“ und, wenn angekreuzt, auf der Seite Aufnahme als Knopf unter "
                  "dem Transkript. Mit einer Halte-Taste wendet sich ein Auftrag gleich beim Diktieren an.", "muted", wrap=True),
            hbox(left, (self._wrap(right), 1), spacing=16),
            form(("Bei jedem Diktat", self.auto))))

        # Visite & Übergabe
        self.v_prompt = QtWidgets.QPlainTextEdit()
        self.v_prompt.setMinimumHeight(170)
        self.v_note = label("", "muted")
        self.v_writer = QtWidgets.QComboBox(editable=True)
        for name, model in visite.WRITERS:
            self.v_writer.addItem(name, model)
        for box in (self.v_writer, self.model, self.profile):    # lange Einträge dürfen die Karte nicht breiter machen
            box.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(18)
        self.v_writer.view().setMinimumWidth(self.v_writer.view().sizeHintForColumn(0) + 28)   # aufgeklappt ganz lesbar
        self.v_writer.activated.connect(lambda _: self.v_writer.lineEdit().setCursorPosition(0))  # Anfang zeigen, nicht das Ende
        self.v_writer.setToolTip("Auswählen oder einen eigenen Modellnamen eintippen. Der Zusatz @low hinter dem Namen lässt "
                                 "ein denkendes Modell bei OpenRouter weniger nachdenken; das macht es deutlich schneller.")
        self.v_rules = QtWidgets.QPlainTextEdit(placeholderText="Optional: Hausregeln für die Ersteinschätzung, zum Beispiel "
                                                "Schockraum-Kriterien, Laborprofile, Zuständigkeiten. Jev entscheidet danach, wo sie eine Regel enthalten.")
        self.v_rules.setFixedHeight(84)
        self.body.addWidget(card(
            label("Übergabe", "h2"),
            label("Ersteinschätzung und Tages-Check kommen von Jev (TypeSafe, nur über OpenRouter). Arztbrief, "
                  "Visiteneintrag und Übergabe schreibt ein Sprachmodell über den Server von oben.", "muted", wrap=True),
            form(("Modell für Brief und Übergabe", self.v_writer), ("Hausregeln für Jev", self.v_rules)),
            label("Prompt für den Rahmen Notaufnahme: bestimmt, was aus einem Fall erzeugt wird (Arztbrief-Entwurf, "
                  "Sicherheitsnetz, Rückfragen, Kodierung, Patienteninfo). Die Namen der Felder im JSON-Schema am Ende "
                  "müssen bleiben, sonst kann LocalScribe das Ergebnis nicht anzeigen. Station und Intensiv haben "
                  "eigene, fest eingebaute Aufträge.", "muted", wrap=True),
            self.v_prompt,
            hbox(button("Speichern", self._visit_save, name="primary"),
                 button("Standard wiederherstellen", self._visit_reset), None, self.v_note)))

        # Ausprobieren
        self.sample = QtWidgets.QPlainTextEdit(
            "Ähm, also ich wollte nur kurz sagen, dass wir uns morgen, also am Dienstag, "
            "um zehn treffen, ja, im Besprechungsraum.")
        self.sample.setFixedHeight(74)
        self.result = QtWidgets.QPlainTextEdit(readOnly=True, placeholderText="Ergebnis")
        self.result.setFixedHeight(96)
        self.try_btn = button("Ausprobieren", self.try_prompt)
        self.try_note = label("", "muted")
        self.body.addWidget(card(
            label("Ausprobieren", "h2"),
            self.sample, hbox(self.try_btn, self.try_note, None), self.result))
        self.body.addStretch(1)

        self.sig_models.connect(self._models)
        self.sig_test.connect(self._tested)
        self.sig_shield.connect(self._shield_progress)

    def _visit_save(self):
        text = self.v_prompt.toPlainText().strip()
        self.ctl.cfg["visite_prompt"] = "" if text == visite.PROMPT.strip() else text
        self.ctl.cfg["visite_model"] = self._writer_value()
        self.ctl.cfg["visite_rules"] = self.v_rules.toPlainText().strip()
        self.ctl.apply_cfg()
        self.saved(self.v_note)

    def _writer_value(self) -> str:
        """Gewähltes Modell für Brief und Übergabe: der Wert des Eintrags oder der eingetippte Name."""
        text = self.v_writer.currentText().strip()
        i = self.v_writer.findText(text)
        return self.v_writer.itemData(i) if i >= 0 else text

    def _visit_reset(self):
        self.v_prompt.setPlainText(visite.PROMPT)
        self._visit_save()

    # ----- gespeicherte Anbieter
    def _profiles(self):
        return self.ctl.cfg.setdefault("llm_profiles", [])

    def _migrate(self):
        """Wer vor den Anbieterprofilen schon einen Server eingetragen hatte, bekommt ihn als ersten Eintrag."""
        l = self.ctl.cfg["llm"]
        if self._profiles() or not (l.get("base_url") and l.get("model")):
            return
        host = llm.urllib.parse.urlsplit(l["base_url"]).hostname or "Server"
        name = next((n for n, u in PRESETS if u and u == l["base_url"]), host)
        self._profiles().append({"name": name, "base_url": l["base_url"], "model": l["model"]})
        key = llm.get_key()
        if key:
            try:
                llm.set_key(key, name)
            except Exception:
                log.exception("Schlüssel nicht übertragbar")
        l["profile"] = name
        self.ctl.apply_cfg()

    def _fill_profiles(self):
        self.profile.blockSignals(True)
        self.profile.clear()
        self.profile.addItem("– nicht gespeichert –", "")
        for p in self._profiles():
            self.profile.addItem(f"{p['name']} · {p.get('model', '')}", p["name"])
        self.profile.setCurrentIndex(max(0, self.profile.findData(self.active)))
        self.profile.blockSignals(False)

    def _pick(self, _=None):
        """Einen gespeicherten Anbieter wählen: Adresse, Modell und Schlüssel wechseln mit."""
        name = self.profile.currentData() or ""
        p = next((p for p in self._profiles() if p["name"] == name), None)
        self.active = name
        if p:
            self.url.setText(p.get("base_url", ""))
            self._fill_models(p.get("model", ""))
            urls = [u for _, u in PRESETS]
            self.preset.setCurrentIndex(urls.index(self.url.text()) if self.url.text() in urls[:-1] else len(urls) - 1)
        self._key_hint()
        if p:
            self.saved(self.note, f"„{name}“ gewählt – mit Speichern übernehmen")

    # ----- Modellwahl
    def model_name(self) -> str:
        return self.model.currentData() or ""

    def _own(self) -> list:
        """Eigene Modellnamen für den Server, der gerade im Feld steht."""
        return (self.ctl.cfg.get("llm_models") or {}).get(llm.host_of(self.url.text()), [])

    def _fill_models(self, select=None):
        """Die Auswahl neu aufbauen: oben die kurze Liste des Anbieters (das erste ist die Vorgabe), dann eigene
        Namen, darunter alles Weitere, was der Server gemeldet hat. select=None behält die jetzige Wahl."""
        url = self.url.text().strip()
        wanted = self.model_name() if select is None else select
        seen = self.remote.get(llm.host_of(url))
        known = {m.lower() for m in seen} if seen else None          # ohne Liste vom Server gilt die mitgelieferte
        self.model.blockSignals(True)
        self.model.clear()
        for name, text in llm.picks(url):
            if known is None or llm.model_of({"model": name})[0].lower() in known:
                self.model.addItem(text, name)
        for name in self._own():
            if self.model.findData(name) < 0:
                self.model.addItem(name, name)
        if wanted and self.model.findData(wanted) < 0 and wanted not in (seen or ()):
            self.model.addItem(wanted, wanted)           # eine frühere Wahl bleibt wählbar
        rest = [m for m in seen or () if self.model.findData(m) < 0]
        if rest and self.model.count():
            self.model.insertSeparator(self.model.count())
        for name in rest:
            self.model.addItem(name, name)
        i = self.model.findData(wanted) if wanted else -1
        self.model.setCurrentIndex(i if i >= 0 else (0 if self.model.count() else -1))
        self.model.blockSignals(False)
        self._model_picked()

    def _model_picked(self, _=None):
        self.drop.setVisible(bool(self.model_name()) and self.model_name() in self._own())

    def _add_model(self):
        if not self.url.text().strip():
            return self.saved(self.note, "Erst den Server wählen.", ok=False)
        name, ok = QtWidgets.QInputDialog.getText(self, "Eigenes Modell", "Modellname, wie ihn der Server kennt:")
        name = (name or "").strip()
        if not ok or not name:
            return
        if llm.refused(self.llm_cfg(), name):
            return self.saved(self.note, "Dieses Modell bietet LocalScribe bei Noirdoc nicht an: Einer seiner Anbieter "
                                         "hat keine Verschwiegenheitsverpflichtung.", ok=False)
        if name not in self._own():
            self.ctl.cfg.setdefault("llm_models", {}).setdefault(llm.host_of(self.url.text()), []).append(name)
        self._fill_models(name)

    def _drop_model(self):
        name = self.model_name()
        if name in self._own():
            self._own().remove(name)
            self._fill_models("")

    def _home(self, name) -> str:
        """Adresse, zu der der gespeicherte Schlüssel dieses Anbieters gehört."""
        p = next((p for p in self._profiles() if p["name"] == name), None)
        if p:
            return p.get("base_url", "")
        stored = self.ctl.cfg["llm"]
        return stored.get("base_url", "") if not name and not stored.get("profile") else ""

    def _own_key(self) -> bool:
        """Gehört der gespeicherte Schlüssel zu dem Server, der gerade im Feld steht?"""
        return llm.host_of(self._home(self.active)) == llm.host_of(self.url.text())

    def _key_hint(self):
        self.key.clear()
        local = llm._is_local(self.url.text().strip())
        self.key.setPlaceholderText("gespeichert – zum Ändern neu eingeben" if self._own_key() and llm.get_key(self.active)
                                    else "bei lokalen Servern meist leer" if local or not self.url.text().strip()
                                    else "Schlüssel des Anbieters einfügen")

    def _live(self):
        """Server und Schlüssel für einen Abruf vor dem Speichern. Ein gespeicherter Schlüssel geht nur an den Server,
        zu dem er gehört: Steht im Feld inzwischen ein anderer, gilt nur ein frisch eingetippter."""
        key = self.typed_key()
        return self.llm_cfg(), key if key is not None or self._own_key() else ""

    def _save_as(self):
        url, model = self.url.text().strip(), self.model_name()
        if not url or not model:
            return self.saved(self.note, "Erst Server und Modell wählen.", ok=False)
        host = llm.urllib.parse.urlsplit(url).hostname or "Server"
        suggestion = next((n for n, u in PRESETS if u and u == url), host)
        name, ok = QtWidgets.QInputDialog.getText(self, "Anbieter speichern", "Name für diesen Anbieter:", text=suggestion)
        name = (name or "").strip()
        if not ok or not name:
            return
        key = self.typed_key() or (llm.get_key(self.active) if self._own_key() else "")
        profiles = [p for p in self._profiles() if p["name"] != name] + [{"name": name, "base_url": url, "model": model}]
        self.ctl.cfg["llm_profiles"] = profiles
        try:
            if key:
                llm.set_key(key, name)
        except Exception as e:
            return self.saved(self.note, f"Schlüssel nicht speicherbar: {e}", ok=False)
        self.active = name
        self.save()

    def _delete(self):
        name = self.profile.currentData() or ""
        if not name:
            return
        self.ctl.cfg["llm_profiles"] = [p for p in self._profiles() if p["name"] != name]
        llm.set_key("", name)
        if self.ctl.cfg["llm"].get("profile") == name:
            self.ctl.cfg["llm"]["profile"] = ""
        self.active = ""
        self.ctl.apply_cfg()
        self.refresh()
        self.saved(self.note, f"„{name}“ gelöscht")

    # ----- Schutz vor dem Versand
    def _shield_state(self):
        ready = schutz.ready()
        self.shield_btn.setVisible(not ready)
        self.shield.setText("Namenserkennung geladen: Namen werden auch ohne Anrede erkannt. Kein Verfahren findet alles."
                            if ready else
                            "Die Namenserkennung fehlt auf diesem Rechner. Solange der Schutz eingeschaltet ist, geht "
                            "deshalb nichts an einen Server außerhalb: Die Regeln allein lassen Namen ohne Anrede durch. "
                            "Im Komplettpaket liegt sie bei.")

    def _shield_load(self):
        self.shield_btn.setEnabled(False)
        if getattr(self.ctl, "shield_start", None):          # ein einziger Download, egal wer ihn anstößt
            if not self.window().shield_wait(retry=True):
                self._shield_progress(1.0, "")
            return

        def work():
            try:
                schutz.prepare(lambda done, total: self.sig_shield.emit(done / total if total else 0.0, ""))
                self.sig_shield.emit(1.0, "")
            except Exception as e:
                self.sig_shield.emit(-1.0, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _shield_progress(self, fraction, error):
        if error or fraction >= 1.0:
            self.shield_btn.setEnabled(True)
            self._shield_state()
            if error:
                self.shield.setText(f"Laden fehlgeschlagen: {error[:140]}")
        else:
            self.shield.setText(f"Lade Namenserkennung … {fraction * 100:.0f} %")

    @staticmethod
    def _wrap(layout):
        w = QtWidgets.QWidget()
        layout.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        return w

    # ----- Laden / Speichern
    def refresh(self):
        self._migrate()
        cfg = self.ctl.cfg
        self.v_prompt.setPlainText(visite.prompt(cfg))
        chosen = cfg.get("visite_model") or ""
        i = self.v_writer.findData(chosen)
        if i >= 0:
            self.v_writer.setCurrentIndex(i)
        else:
            self.v_writer.setEditText(chosen)
        self.v_writer.lineEdit().setCursorPosition(0)
        self.v_rules.setPlainText(cfg.get("visite_rules") or "")
        l = cfg["llm"]
        self.active = l.get("profile") or ""
        self._fill_profiles()
        self.protect.setChecked(bool(l.get("protect", True)))
        self._shield_state()
        self.enabled.setChecked(bool(l.get("enabled")))
        self.fix.setChecked(bool(cfg.get("llm_fix")))
        self.url.setText(l.get("base_url") or "")
        urls = [u for _, u in PRESETS]
        self.preset.setCurrentIndex(urls.index(self.url.text()) if self.url.text() in urls[:-1] else len(urls) - 1)
        self._key_hint()
        self._fill_models(l.get("model") or "")
        self.prompts = copy.deepcopy(cfg.get("prompts") or [])
        self.current = -1
        self.list.clear()
        for p in self.prompts:
            self.list.addItem(p.get("name") or "Ohne Namen")
        self._fill_auto(l.get("auto_prompt") or "")
        self.list.setCurrentRow(0 if self.prompts else -1)
        self._enable_form(bool(self.prompts))

    def _fill_auto(self, selected):
        self.auto.clear()
        self.auto.addItem("nur der diktierte Text", "")
        for p in self.prompts:
            self.auto.addItem(f"„{p.get('name', '')}“ anwenden", p.get("name", ""))
        i = self.auto.findData(selected)
        self.auto.setCurrentIndex(max(0, i))

    def llm_cfg(self):
        l = dict(self.ctl.cfg["llm"])
        l.update(enabled=self.enabled.isChecked(), base_url=self.url.text().strip(),
                 model=self.model_name(), auto_prompt=self.auto.currentData() or "",
                 profile=self.active, protect=self.protect.isChecked())
        return l

    def typed_key(self):
        """Neu eingetippter Schlüssel, sonst None (= gespeicherten verwenden)."""
        return self.key.text().strip() or None

    def save(self):
        if not self._commit():
            return
        names = [p["name"] for p in self.prompts]
        if len(set(names)) != len(names) or not all(names):
            return self.saved(self.note, "Jeder Prompt braucht einen eigenen Namen.", ok=False)
        typed = self.typed_key()
        if self.active and self.url.text().strip() and all(p["name"] != self.active for p in self._profiles()):
            # ein Anbieter aus der Liste „Server“ bekommt beim ersten Speichern seinen eigenen Eintrag samt Schlüssel
            self._profiles().append({"name": self.active, "base_url": self.url.text().strip(), "model": self.model_name()})
        if typed:
            try:
                llm.set_key(typed, self.active)
            except Exception as e:
                return self.saved(self.note, f"Schlüssel nicht speicherbar: {e}", ok=False)
        self.ctl.cfg["llm"] = self.llm_cfg()
        for p in self._profiles():                 # der gewählte Anbieter merkt sich Adresse und Modell
            if p["name"] == self.active:
                p.update(base_url=self.ctl.cfg["llm"]["base_url"], model=self.ctl.cfg["llm"]["model"])
        self.ctl.cfg["llm_fix"] = self.fix.isChecked()
        self.ctl.cfg["prompts"] = copy.deepcopy(self.prompts)
        self.ctl.apply_cfg()
        selected = self.current
        self.refresh()
        self.list.setCurrentRow(selected)
        self.saved(self.note)
        if typed:                                  # ein neuer Schlüssel zeigt gleich, ob er gilt
            self.load_models()

    def drop_key(self):
        if self._own_key():
            llm.set_key("", self.active)
        self._key_hint()

    def _where(self, url):
        url = url.strip()
        tip = ADVICE_LOCAL if url and llm._is_local(url) else next((text for part, text in ADVICE if part in url.lower()), "")
        self.advice.setText(tip)
        self.advice.setVisible(bool(tip))
        if not url:
            return self.where.setText("")
        if llm._is_local(url):
            restyle(self.where, "muted")
            self.where.setText("Dieser Server steht auf diesem Rechner oder im eigenen Netz.")
        else:
            host = llm.urllib.parse.urlsplit(url).hostname or url
            restyle(self.where, "bad")
            self.where.setText(f"Mit dieser Adresse verlassen die Texte diesen Rechner und gehen an {host}.")

    def _preset(self, i):
        """Einen Server aus der Liste wählen: Ist er schon als Anbieter gespeichert, kommen dessen Modell und Schlüssel
        mit; sonst gilt die Vorgabe des Anbieters, und der Schlüssel eines anderen bleibt, wo er ist."""
        name, url = PRESETS[i]
        if not url:
            return self.url.setFocus()
        if url == self.url.text().strip():
            return
        self.url.setText(url)
        known = next((p for p in self._profiles() if p.get("base_url") == url), None)
        taken = {p["name"] for p in self._profiles()}
        self.active = known["name"] if known else next(n for n in [name] + [f"{name} {k}" for k in range(2, 99)]
                                                       if n not in taken)
        self._fill_profiles()
        self._key_hint()
        self._fill_models(known.get("model", "") if known else "")
        if llm._is_local(url) or "openrouter.ai" in url or (known and llm.get_key(self.active)):
            self.load_models(quiet=True)

    # ----- Prompts
    def _enable_form(self, on):
        for w in (self.name, self.hotkey, self.text):
            w.setEnabled(on)
            if not on:
                w.clear()

    def _commit(self) -> bool:
        """Formular in den aktuell gewählten Prompt übernehmen."""
        if 0 <= self.current < len(self.prompts):
            keys = self.ctl.parse_keys(self.hotkey.text())
            if keys is None:
                self.saved(self.note, "Unbekannte Taste in der Halte-Taste.", ok=False)
                return False
            self.prompts[self.current] = {"name": self.name.text().strip(), "hotkey": keys,
                                          "text": self.text.toPlainText().strip(), "record": self.on_record.isChecked()}
        return True

    def _select(self, row):
        if row == self.current:
            return
        if not self._commit():
            self.list.blockSignals(True)
            self.list.setCurrentRow(self.current)
            self.list.blockSignals(False)
            return
        self.current = row
        if 0 <= row < len(self.prompts):
            p = self.prompts[row]
            self._enable_form(True)
            self.name.setText(p.get("name", ""))
            self.hotkey.setText(keys_text(p.get("hotkey") or []))
            self.text.setPlainText(p.get("text", ""))
            self.on_record.setChecked(bool(p.get("record", p.get("name") in VisitPage.SHOWN)))
        else:
            self._enable_form(False)

    def _rename(self, text):
        if self.list.currentItem():
            self.list.currentItem().setText(text or "Ohne Namen")

    def new_prompt(self):
        if not self._commit():
            return
        self.prompts.append({"name": f"Prompt {len(self.prompts) + 1}", "hotkey": [], "text": ""})
        self.list.addItem(self.prompts[-1]["name"])
        self.list.setCurrentRow(len(self.prompts) - 1)
        self.name.setFocus()
        self.name.selectAll()

    def del_prompt(self):
        row = self.list.currentRow()
        if row < 0:
            return
        self.current = -1
        del self.prompts[row]
        self.list.takeItem(row)
        self.list.setCurrentRow(min(row, len(self.prompts) - 1))
        self._enable_form(bool(self.prompts))

    # ----- Netz
    def load_models(self, _=None, quiet=False):
        """Die Modellliste des Servers holen. quiet: nebenbei nach der Wahl eines Servers, ohne Fehlermeldung."""
        cfg, key = self._live()
        if not cfg["base_url"]:
            return
        self.fetch.setEnabled(False)
        restyle(self.status, "muted")
        self.status.setText("Frage den Server …")
        self.status.setVisible(not quiet)
        host = llm.host_of(cfg["base_url"])

        def work():
            try:
                self.sig_models.emit((host, llm.list_models(cfg, key), quiet), "")
            except Exception as e:
                self.sig_models.emit((host, [], quiet), str(e) or type(e).__name__)
        threading.Thread(target=work, daemon=True).start()

    def _models(self, answer, error):
        host, models, quiet = answer
        self.fetch.setEnabled(True)
        if error:
            restyle(self.status, "bad")
            self.status.setText(error)
            return self.status.setVisible(not quiet)
        self.remote[host] = models
        if host != llm.host_of(self.url.text()):
            return                                 # inzwischen steht ein anderer Server im Feld
        self._fill_models()
        restyle(self.status, "ok")
        self.status.setText(f"Verbunden – {len(models)} Modelle gefunden." if models
                            else "Verbunden, aber der Server meldet keine Modelle.")
        self.status.show()

    def try_prompt(self):
        instruction = self.text.toPlainText().strip()
        if not instruction:
            return self.try_note.setText("Erst links einen Prompt wählen.")
        self.try_btn.setEnabled(False)
        self.try_note.setText("Modell arbeitet …")
        (cfg, key), sample = self._live(), self.sample.toPlainText()

        def work():
            t = time.time()
            try:
                self.sig_test.emit(llm.run(cfg, instruction, sample, key), "", time.time() - t)
            except Exception as e:
                self.sig_test.emit("", str(e) or type(e).__name__, time.time() - t)
        threading.Thread(target=work, daemon=True).start()

    def _tested(self, text, error, seconds):
        self.try_btn.setEnabled(True)
        self.result.setPlainText(error or text)
        self.try_note.setText("Fehlgeschlagen" if error else f"{seconds:.1f} s".replace(".", ","))


# ---------------------------------------------------------------- Einstellungen
class SettingsPage(Page):
    def __init__(self, ctl):
        super().__init__("Einstellungen")
        self.ctl = ctl
        self.note = label("")
        self.head.addWidget(self.note)
        self.head.addWidget(button("Speichern", self.save, "primary"))
        self.hold = KeyField(ctl, optional=False)
        self.lock = KeyField(ctl, single=True)
        self.paste = KeyField(ctl)
        self.field = KeyField(ctl)
        self.target = KeyField(ctl)
        self.mic = QtWidgets.QComboBox()
        self.sounds = QtWidgets.QCheckBox("Töne bei Start und Ende der Aufnahme")
        self.clip = QtWidgets.QCheckBox("Zwischenablage nach dem Einfügen wiederherstellen")
        self.warm = QtWidgets.QCheckBox("Mikrofon offen halten: Diktat startet ohne Verzögerung, die erste Silbe geht nicht verloren")
        self.signs = QtWidgets.QCheckBox("Satzzeichen diktieren: „Punkt“, „Komma“, „Doppelpunkt“, „neue Zeile“, „neuer Absatz“ werden zu Zeichen")
        self.warm.setToolTip("Das Mikrofon bleibt geöffnet, solange LocalScribe läuft (Windows zeigt das Mikrofon-Symbol). "
                             "Außerhalb eines Diktats wird nur die letzte Viertelsekunde im Arbeitsspeicher gehalten.")
        self.phone = QtWidgets.QCheckBox("Handy als Mikrofon: Telefon im selben WLAN nimmt auf, der Text erscheint hier")
        self.auto = QtWidgets.QCheckBox("Mit Windows starten")
        self.history = QtWidgets.QCheckBox("Verlauf führen (auf gemeinsam genutzten Windows-Konten ausschalten)")
        self.days = QtWidgets.QSpinBox(minimum=0, maximum=3650, suffix=" Tage", specialValueText="nie löschen")
        self.days.setFixedWidth(150)
        self.model = QtWidgets.QComboBox()
        for key, m in config.MODELS.items():
            self.model.addItem(m["label"], key)
        self.model_dir = QtWidgets.QLineEdit(placeholderText="leer: Modelle liegen beim Programm oder in deinem Konto")
        self.body.addWidget(card(
            label("Sprachmodell", "h2"), form(("Modell", self.model)),
            label("Deutsch ist für Diktate und Gespräche auf Deutsch gedacht; dafür gelten das medizinische "
                  "Basiswörterbuch und die deutsche Nachbearbeitung. Mehrsprachig erkennt die gesprochene Sprache "
                  "selbst, darunter Englisch, Französisch und Spanisch (einmalig 670 MB).",
                  "muted", wrap=True),
            form(("Modellordner", hbox(self.model_dir, button("Ordner wählen …", self._pick_models)))),
            label("Optional: ein gemeinsamer Ordner mit den Sprachmodellen, zum Beispiel auf einem Netzlaufwerk. "
                  "Gemeint ist der Ordner „modelle“ aus dem Komplettpaket. Dann braucht nicht jeder Programmordner "
                  "sein eigenes Modell. Ohne Einstellung geht dasselbe, wenn ein Ordner „modelle“ direkt neben den "
                  "Programmordnern liegt. Gilt ab dem nächsten Start.", "muted", wrap=True)))
        self.body.addWidget(card(
            label("Tasten", "h2"),
            form(("Diktieren (halten)", self.hold), ("Freihand (dazu drücken)", self.lock),
                 ("Letzten Text einfügen", self.paste),
                 ("Nächste Sprungmarke [ ]", self.field),
                 ("Zielfenster merken / lösen", self.target)),
            label("In ein Feld klicken und die gewünschte Kombination drücken, dann oben „Speichern“. Eine einzelne "
                  "Taste wie Strg startet nach kurzem Halten; Strg+C, Strg+Klick und andere Kürzel funktionieren "
                  "weiter wie gewohnt. Esc bricht eine laufende Aufnahme ab.", "muted", wrap=True)))
        self.body.addWidget(card(label("Aufnahme", "h2"), form(("Mikrofon", self.mic)),
                                 self.sounds, self.clip, self.warm, self.signs))
        self.body.addWidget(card(
            label("Handy als Mikrofon", "h2"), self.phone,
            label("Einschalten, speichern, dann den QR-Code mit dem Telefon scannen. Das Telefon zeigt einmal eine "
                  "Zertifikatswarnung (die Seite kommt von diesem Rechner, nicht aus dem Internet): „Erweitert“ und "
                  "„Trotzdem öffnen“. Fragt Windows beim Einschalten nach der Firewall, den Zugriff im privaten Netz "
                  "erlauben. Der Ton geht nur vom Telefon zu diesem Rechner und wird nicht gespeichert.",
                  "muted", wrap=True),
            hbox(button("QR-Code zeigen", self.show_qr), None)))
        self.body.addWidget(card(label("Verlauf und Start", "h2"),
                                 self.history, form(("Einträge löschen nach", hbox(self.days, None))),
                                 label("Tonaufnahmen werden nie aufbewahrt: Diktate per Taste bleiben im Arbeitsspeicher, "
                                       "lange Aufnahmen werden nach dem Transkribieren gelöscht.", "muted", wrap=True),
                                 self.auto,
                                 hbox(button("Verknüpfungen auf Desktop und im Startmenü anlegen", self.shortcuts),
                                      None)))
        self.own_note = label("", "muted", wrap=True)
        self.body.addWidget(card(
            label("Eigene Daten", "h2"),
            label("Einstellungen, Verlauf, Wörterbuch und alles Gelernte liegen in deinem Windows-Konto. Teilen sich "
                  "mehrere ein Konto, teilen sie auch das. Wer seine eigene Fassung will, legt die Daten in diesen "
                  "Programmordner: Dann gehört zu jedem Programmordner ein eigener Wortschatz, ein eigener Verlauf "
                  "und eigene Einstellungen. Nur in einem Ordner sinnvoll, den nur du öffnen kannst, denn dort "
                  "liegen dann auch Verlauf und Fälle.", "muted", wrap=True),
            hbox(button("Daten in diesem Programmordner ablegen", self._own), None),
            self.own_note))
        self.keep_note = label("", "muted", wrap=True)
        self.body.addWidget(card(
            label("Profil sichern", "h2"),
            label("Dein Profil in eine Datei schreiben und daraus zurückholen, etwa für einen anderen Rechner: Wörterbuch, "
                  "gelernter Wortschatz, Textbausteine, Aufträge, Tasten, Server und die Stimmaufnahmen aus dem "
                  "Stimmtraining. Updates fassen das Profil nicht an; vor jedem Wechsel der Fassung legt LocalScribe "
                  "zusätzlich eine Kopie der Einstellungen ab (Ordner „sicherung“, die letzten zehn). API-Schlüssel "
                  "stehen nicht in der Datei: Die liegen im Schlüsselspeicher von Windows.", "muted", wrap=True),
            hbox(button("Profil sichern …", self._keep), button("Profil zurückholen …", self._bring),
                 button("Ordner mit den Sicherungen öffnen", self._kept_open), None),
            self.keep_note))
        self.many_note = label("", "muted", wrap=True)
        self.many_btn = button("Profile einschalten", self._many)
        self.many = card(
            label("Mehrere Personen an diesem Programm", "h2"),
            label("Arbeiten mehrere Personen mit diesem Programmordner (gemeinsamer Rechner, Netzlaufwerk, viele Rechner), "
                  "bekommt jede ein eigenes Profil: Wörterbuch, Wortschatz, Textbausteine, Aufträge, Tasten und "
                  "Stimmaufnahmen liegen dann im Programmordner unter „profile“ und folgen der Person an jeden Rechner. "
                  "Gewählt wird unten links im Fenster. Profile haben kein Passwort; Verlauf, Fälle und Schlüssel "
                  "bleiben auf dem jeweiligen Rechner. Liegt das Programm auf einem Netzlaufwerk, ist das von selbst an.",
                  "muted", wrap=True),
            hbox(self.many_btn, None), self.many_note)
        self.body.addWidget(self.many)
        self.care_note = label("", "muted", wrap=True)
        self.auto_check = QtWidgets.QCheckBox("Einmal am Tag von selbst nach Updates fragen (bei GitHub; von dir wird dabei nichts "
                                              "übertragen). Gibt es eines, leuchtet unten links der Knopf „Update“.")
        self.auto_check.toggled.connect(self._auto_check)
        self.check_button = button("Nach Updates suchen", self._check, name="primary")
        self.found = None                    # neuere Fassung bei GitHub, sobald gefunden
        self.notes_button = button("Was ist neu", self._notes)
        self.body.addWidget(card(
            label("Aktualisieren und entfernen", "h2"),
            label(f"Installiert ist Fassung {__version__}. „Nach Updates suchen“ fragt bei GitHub nach der neuesten "
                  "Fassung und lädt auf Wunsch nur die Dateien, die sich geändert haben. Erreicht der Rechner GitHub "
                  "nicht (häufig in Kliniken): die ZIP-Datei an einem anderen Rechner laden und hier auswählen, das "
                  "kleine Paket genügt. Ein Update richtet die neue Fassung neben der laufenden ein: Du arbeitest "
                  "weiter, sie gilt ab dem nächsten Start. Einstellungen, Verlauf, Wörterbuch und Sprachmodell bleiben.",
                  "muted", wrap=True),
            hbox(self.check_button, self.notes_button, button("Aus ZIP-Datei aktualisieren …", self._update),
                 button("LocalScribe entfernen …", self._remove), None),
            self.auto_check, self.care_note))
        self.quiet = False                   # läuft gerade die stille tägliche Nachfrage?
        self.sig_latest.connect(self._latest)
        self.sig_loading.connect(self._loading)
        self.sig_unpacked.connect(self._unpacked)
        a = 'style="color:#C6FF3D; text-decoration:none"'
        self.body.addWidget(card(
            label("Über LocalScribe", "h2"),
            link(f'LocalScribe {__version__} · by <a href="{SITE}" {a}>cemmec.ai</a> · Dr. Cem Özel'),
            label(f"Läuft aus: {pflege.program() or 'dem Quelltext'}  ·  Daten in: {config.DIR}", "muted", wrap=True),
            link(f'Support, Rückfragen und Änderungswünsche: <a href="{LINKEDIN}" {a}>Cem Özel auf LinkedIn</a>. '
                 f'Fehler melden und Quelltext: <a href="{REPO}" {a}>GitHub</a>. '
                 f'Handbuch: <a href="https://chunkyfire.github.io/LocalScribe/" {a}>online</a>.')))
        self.body.addStretch(1)

    sig_unpacked = Signal(str, str)      # Nummer der neuen Fassung, Fehlertext
    sig_latest = Signal(object, str)     # Auskunft von GitHub, Fehlertext
    sig_loading = Signal(int, int)       # geladene Bytes, zu ladende Bytes

    def _pick_models(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Ordner mit den Sprachmodellen", self.model_dir.text())
        if path:
            self.model_dir.setText(os.path.normpath(path))

    def _own(self):
        """Eigene Daten künftig im Programmordner: Ordner „daten“ anlegen, Einstellungen und Wortschatz mitnehmen."""
        prog = pflege.program()
        if not prog:
            return self.saved(self.own_note, "Diese Fassung läuft aus dem Quelltext, dort gibt es keinen Programmordner.", ok=False)
        target = prog / config.PORTABLE
        if config.DIR == target:
            return self.saved(self.own_note, f"Die Daten liegen schon hier: {target}", ok=False)
        try:
            target.mkdir(exist_ok=True)
            config.save(self.ctl.cfg)
            import shutil
            shutil.copy2(config.FILE, target / config.FILE.name)
        except OSError as e:
            return self.saved(self.own_note, f"In diesem Ordner lässt sich nichts anlegen ({e.strerror or e}).", ok=False)
        restyle(self.own_note, "ok")
        self.own_note.setText(f"Angelegt: {target}. Einstellungen, Wörterbuch und Gelerntes sind dorthin kopiert, der "
                              "bisherige Verlauf bleibt im Konto. Gilt ab dem nächsten Start: LocalScribe über das "
                              "Symbol neben der Uhr beenden und neu starten. Rückgängig: den Ordner „daten“ löschen.")

    def _many(self):
        try:
            config.profiles_enable()
        except (ValueError, OSError) as e:
            return self.saved(self.many_note, f"Nicht möglich: {e}", ok=False)
        self.ctl.hub.profile_refresh()
        self.refresh()
        self.saved(self.many_note, "Eingeschaltet. Unten links im Fenster steht jetzt „Dieser Rechner“: Klick, „Neues Profil …“.")

    def _auto_check(self, on):
        self.ctl.cfg["update_check"] = bool(on)
        config.save(self.ctl.cfg)

    def _care_ready(self) -> bool:
        if self.ctl.hub.busy():
            self.saved(self.care_note, "Erst die laufende Aufnahme oder Transkription beenden.", ok=False)
            return False
        return True

    def start_update(self):
        """Vom Update-Knopf unten links im Fenster: die gefundene Fassung laden und einrichten."""
        if self.found and self.check_button.isEnabled():
            self._online()

    def _check(self, quiet=False):
        """Erster Klick: bei GitHub nachfragen. Zweiter Klick (wenn es Neues gibt): laden und ersetzen.
        quiet: die tägliche stille Nachfrage der App; sie meldet sich nur, wenn es etwas Neues gibt."""
        if quiet and (self.found or not self.check_button.isEnabled()):
            return
        if self.found:
            return self._online()
        self.quiet = bool(quiet)
        if not quiet:
            restyle(self.care_note, "muted")
            self.care_note.setText("Frage bei GitHub nach der neuesten Fassung …")
        self.check_button.setEnabled(False)

        def work():
            try:
                info = pflege.latest()
                if info["newer"]:
                    info["notes"] = pflege.remote_notes(info)
                self.sig_latest.emit(info, "")
            except Exception as e:
                self.sig_latest.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _keep(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Profil sichern", f"LocalScribe-Profil-{time.strftime('%Y-%m-%d')}{config.PROFILE}",
            f"Profil mit Stimmaufnahmen (*{config.PROFILE});;Nur Einstellungen (*.json)")
        if not path:
            return
        try:
            config.save(self.ctl.cfg)
            voice = config.export(path)                  # bei gewähltem Profil: dessen Daten und Stimmaufnahmen
        except OSError as e:
            return self.saved(self.keep_note, f"Nicht gesichert: {e}", ok=False)
        self.saved(self.keep_note, f"Gesichert in {path}" + (f" ({voice} Stimmaufnahmen)" if voice else ""))

    def _bring(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Profil zurückholen", "",
                                                        f"Profil oder Einstellungen (*{config.PROFILE} *.json)")
        if not path:
            return
        try:
            cfg = config.restore(path)
        except (ValueError, OSError) as e:
            return self.saved(self.keep_note, str(e), ok=False)
        voice = cfg.pop("_voice", 0)
        self.ctl.cfg.clear()
        self.ctl.cfg.update(cfg)
        self.ctl.apply_cfg()
        self.window().refresh()
        self.refresh()
        self.saved(self.keep_note, "Zurückgeholt" + (f", dazu {voice} Stimmaufnahmen" if voice else "")
                   + ". Die bisherigen Einstellungen liegen als Kopie im Ordner „sicherung“.")

    def _kept_open(self):
        folder = config.DIR / config.BACKUPS
        folder.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))

    def _notes(self):
        """Vor dem Update: was die neue Fassung bringt. Sonst: was die letzten Fassungen gebracht haben."""
        if self.found:
            return show_notes(self, self.found.get("notes") or [], self.found["version"])
        show_notes(self, pflege.notes()[:8], __version__)

    def _latest(self, info, error):
        self.check_button.setEnabled(True)
        quiet, self.quiet = self.quiet, False
        if quiet and (error or not info["newer"] or not pflege.program()):
            return                               # stille Nachfrage: kein Netz oder nichts Neues ist keine Meldung wert
        if error:
            self.ctl.hub.update_hint("GitHub ist von hier nicht erreichbar.", error)
            return self.saved(self.care_note, error, ok=False)
        if not info["newer"]:
            self.ctl.hub.update_hint("Du hast die neueste Fassung.")
            restyle(self.care_note, "ok")
            return self.care_note.setText(f"Du hast die neueste Fassung ({__version__}).")
        if not pflege.program():
            return self.saved(self.care_note, f"Fassung {info['version']} ist da. Diese hier läuft aus dem Quelltext; "
                              "aktualisiert wird sie mit git.", ok=False)
        if pflege.complete(pflege.program(), info["version"]):
            self.ctl.watch_update()
            restyle(self.care_note, "ok")
            return self.care_note.setText(f"Fassung {info['version']} ist hier schon eingerichtet und startet beim "
                                          "nächsten Start von LocalScribe.")
        self.found = info
        self.notes_button.setText(f"Was ist neu in {info['version']}")
        reason = pflege.readonly(pflege.program())
        if reason:
            self.ctl.hub.update_hint(f"Fassung {info['version']} ist da, der Ordner ist aber schreibgeschützt.", reason)
            return self.saved(self.care_note, f"Fassung {info['version']} ist da, du hast {__version__}. {reason}",
                              ok=False)
        self.check_button.setText(f"Auf {info['version']} aktualisieren")
        self.ctl.hub.update_offer(info["version"])
        restyle(self.care_note, "ok")
        self.care_note.setText(f"Fassung {info['version']} ist da, du hast {__version__}. Ein Klick lädt nur, was sich "
                               "geändert hat, und richtet die neue Fassung neben der laufenden ein. Du kannst dabei "
                               "weiterarbeiten.")

    def _online(self):
        prog, info = pflege.program(), self.found
        self.check_button.setEnabled(False)
        self.ctl.hub.update_loading("Lädt …")
        restyle(self.care_note, "muted")
        self.care_note.setText("Vergleiche die installierten Dateien mit der neuen Fassung …")

        def work():
            try:
                version, _, _ = pflege.fetch(info, prog, progress=self.sig_loading.emit)
                self.sig_unpacked.emit(version, "")
            except Exception as e:
                self.sig_unpacked.emit("", str(e))
        threading.Thread(target=work, daemon=True).start()

    def _loading(self, done, total):
        self.care_note.setText(f"Lade die geänderten Dateien: {done / 1e6:.0f} von {total / 1e6:.0f} MB …")
        self.ctl.hub.update_loading(f"Lädt … {100 * done // max(total, 1)} %")

    def _update(self):
        prog = pflege.program()
        if not prog:
            self.saved(self.care_note, "Diese Fassung läuft aus dem Quelltext; aktualisiert wird sie mit git.", ok=False)
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "ZIP-Datei der neuen Fassung", "", "LocalScribe-Paket (*.zip)")
        if not path:
            return
        restyle(self.care_note, "muted")
        self.care_note.setText("Die neue Fassung wird eingerichtet. Du kannst dabei weiterarbeiten …")

        def work():
            try:
                self.sig_unpacked.emit(pflege.unpack(path, prog), "")
            except Exception as e:
                self.sig_unpacked.emit("", str(e))
        threading.Thread(target=work, daemon=True).start()

    def _unpacked(self, new, error):
        self.check_button.setEnabled(True)
        if error:
            self.ctl.hub.update_failed(error)
            self.saved(self.care_note, error, ok=False)
            return
        self.found = None
        self.check_button.setText("Nach Updates suchen")
        self.notes_button.setText("Was ist neu")
        restyle(self.care_note, "ok")
        self.care_note.setText(f"Fassung {new} ist eingerichtet. Sie startet beim nächsten Start von LocalScribe; "
                               "oben im Fenster steht „Jetzt neu starten“. Läuft LocalScribe aus diesem Ordner auch "
                               "auf anderen Rechnern, übernehmen die sie ebenfalls bei ihrem nächsten Start.")
        self.ctl.watch_update()

    def _remove(self):
        if not self._care_ready():
            return
        prog = pflege.program()
        reason = pflege.blocked(prog) if prog else ""
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("LocalScribe entfernen")
        text = "Entfernt werden die Verknüpfungen auf dem Desktop und im Startmenü und der automatische Start"
        if prog and not reason:
            text += f", dazu der Programmordner {prog}."
        elif prog:
            text += (f". Der Programmordner {prog} bleibt liegen: {reason} Löschen kann ihn, wer dort die Rechte "
                     "hat, oder du selbst nach dem Ab- und Anmelden.")
        else:
            text += "."
        box.setText(text)
        data = QtWidgets.QCheckBox("Auch meine Einstellungen, den Verlauf, das Wörterbuch, gespeicherte Schlüssel und "
                                   "die heruntergeladenen Sprachmodelle in diesem Benutzerkonto löschen")
        box.setCheckBox(data)
        yes = box.addButton("Entfernen", QtWidgets.QMessageBox.DestructiveRole)
        box.addButton("Abbrechen", QtWidgets.QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is yes:
            self.ctl.uninstall(data.isChecked())

    def refresh(self):
        cfg = self.ctl.cfg
        self.hold.setText(keys_text(cfg["hotkey_hold"]))
        self.model.setCurrentIndex(max(0, self.model.findData(cfg.get("model_choice", "de"))))
        self.model_dir.setText(cfg.get("model_dir") or "")
        self.lock.setText(keys_text([cfg["hotkey_lock"]] if cfg.get("hotkey_lock") else []))
        self.paste.setText(keys_text(cfg.get("hotkey_paste_last") or []))
        self.field.setText(keys_text(cfg.get("hotkey_next_field") or []))
        self.target.setText(keys_text(cfg.get("hotkey_target") or []))
        self.mic.clear()
        self.mic.addItem("Standardgerät", None)
        for name in self.ctl.input_devices():
            self.mic.addItem(name, name)
        self.mic.setCurrentIndex(max(0, self.mic.findData(cfg.get("microphone"))))
        self.sounds.setChecked(bool(cfg.get("sounds")))
        self.clip.setChecked(bool(cfg.get("restore_clipboard", True)))
        self.warm.setChecked(bool(cfg.get("mic_warm")))
        self.signs.setChecked(bool(cfg.get("spoken_punctuation")))
        self.phone.setChecked(bool((cfg.get("phone") or {}).get("enabled")))
        self.days.setValue(int(cfg.get("history_days") or 0))
        self.history.setChecked(bool(cfg.get("history_enabled", True)))
        self.auto.setChecked(self.ctl.autostart_enabled())
        self.many.setVisible(bool(pflege.program()))
        self.many_btn.setVisible(not config.profiles_on())
        if config.profiles_on() and not self.many_note.text():
            self.many_note.setText("Profile sind an. Gewählt wird unten links im Fenster.")
        self.auto_check.blockSignals(True)
        self.auto_check.setChecked(bool(cfg.get("update_check")))
        self.auto_check.blockSignals(False)

    def show_qr(self):
        server = self.ctl.phone
        if not server:
            return self.saved(self.note, "Erst „Handy als Mikrofon“ ankreuzen und speichern.", ok=False)
        box = QtWidgets.QDialog(self)
        box.setWindowTitle("Handy als Mikrofon")
        lay = QtWidgets.QVBoxLayout(box)
        pic = QtGui.QPixmap()
        pic.loadFromData(handy.qr_png(server.url()))
        code = QtWidgets.QLabel()
        code.setPixmap(pic)
        code.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(code)
        lay.addWidget(label("1. Telefon ins selbe WLAN wie diesen Rechner.\n2. Mit der Kamera den Code scannen.\n"
                            "3. Warnung bestätigen: „Erweitert“, „Trotzdem öffnen“.\n"
                            "4. „Aufnehmen“ tippen, sprechen, „Stopp“ tippen. Der Text landet dort, wo am Rechner "
                            "der Cursor steht (oder im Zielfenster).", wrap=True))
        link = QtWidgets.QLineEdit(server.url())
        link.setReadOnly(True)
        lay.addWidget(link)
        box.exec()

    def shortcuts(self):
        try:
            self.ctl.create_shortcuts()
            self.saved(self.note, "Verknüpfungen angelegt")
        except Exception as e:
            self.saved(self.note, f"Verknüpfungen nicht anlegbar: {e}", ok=False)

    def save(self):
        hold = self.ctl.parse_keys(self.hold.text())
        lock = self.ctl.parse_keys(self.lock.text())
        paste = self.ctl.parse_keys(self.paste.text())
        field = self.ctl.parse_keys(self.field.text())
        target = self.ctl.parse_keys(self.target.text())
        if not hold or lock is None or paste is None or field is None or target is None or len(lock) > 1:
            return self.saved(self.note, "Eine Taste ist unbekannt oder das Diktier-Kürzel fehlt.", ok=False)
        choice = self.model.currentData()
        if choice != self.ctl.cfg.get("model_choice", "de"):
            if not self.ctl.ready or self.window().busy():
                return self.saved(self.note, "Das Sprachmodell lässt sich erst wechseln, wenn nichts mehr läuft.", ok=False)
            self.ctl.cfg["model_choice"] = choice
        self.ctl.cfg.update(hotkey_hold=hold, hotkey_lock=lock[0] if lock else "", hotkey_paste_last=paste, hotkey_next_field=field,
                            hotkey_target=target,
                            microphone=self.mic.currentData(), sounds=self.sounds.isChecked(),
                            restore_clipboard=self.clip.isChecked(), mic_warm=self.warm.isChecked(),
                            spoken_punctuation=self.signs.isChecked(),
                            history_days=self.days.value(),
                            history_enabled=self.history.isChecked(),
                            model_dir=self.model_dir.text().strip())
        phone = dict(self.ctl.cfg.get("phone") or {})
        phone.update(enabled=self.phone.isChecked(), token=phone.get("token") or secrets.token_urlsafe(9),
                     port=phone.get("port") or handy.PORT)
        self.ctl.cfg["phone"] = phone
        try:
            self.ctl.set_autostart(self.auto.isChecked())
        except Exception as e:
            return self.saved(self.note, f"Autostart nicht änderbar: {e}", ok=False)
        self.ctl.apply_cfg()
        self.saved(self.note)


class Tabs(QtWidgets.QWidget):
    """Mehrere Seiten unter einem Menüpunkt, oben als Reiter: [(Name, Seite), …]."""

    def __init__(self, entries):
        super().__init__()
        self.pages = [page for _, page in entries]
        self.tabs = QtWidgets.QButtonGroup(self)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(30, 18, 30, 0)
        row.setSpacing(6)
        self.stack = QtWidgets.QStackedWidget()
        for i, (name, _) in enumerate(entries):
            b = QtWidgets.QPushButton(name, checkable=True, objectName="tab")
            b.setCursor(Qt.PointingHandCursor)
            self.tabs.addButton(b, i)
            row.addWidget(b)
            self.stack.addWidget(self.pages[i])
        row.addStretch(1)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addLayout(row)
        lay.addWidget(self.stack, 1)
        self.tabs.idClicked.connect(self.show_tab)
        self.tabs.button(0).setChecked(True)

    def show_tab(self, i):
        self.tabs.button(i).setChecked(True)
        self.pages[i].refresh()
        self.stack.setCurrentIndex(i)

    def refresh(self):
        self.pages[self.stack.currentIndex()].refresh()


# ---------------------------------------------------------------- Fenster
class Hub(QtWidgets.QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.setWindowTitle("LocalScribe")
        self.setWindowIcon(make_icon())
        load_fonts()
        self.setStyleSheet(STYLE)
        self.resize(1000, 680)
        self.setMinimumSize(860, 560)

        side = QtWidgets.QFrame(objectName="side")
        side.setFixedWidth(210)
        nav = QtWidgets.QVBoxLayout(side)
        nav.setContentsMargins(14, 20, 14, 16)
        nav.setSpacing(4)
        mark = QtWidgets.QLabel()
        mark.setPixmap(make_pixmap(26))
        nav.addLayout(hbox(mark, label("LocalScribe", "brand"), None, spacing=9))
        by = link(f'by <a href="{SITE}" style="color:#C6FF3D; text-decoration:none">cemmec.ai</a>')
        by.setContentsMargins(36, 0, 0, 0)
        nav.addWidget(by)
        nav.addSpacing(14)

        self.stack = QtWidgets.QStackedWidget()
        self.pages = [
            ("Verlauf", HistoryPage(ctl)),
            ("Aufnahme", VisitPage(ctl)),
            ("Übergabe", VisitPage(ctl, "handover")),
            ("Wortschatz", Tabs([("Wörterbuch", MapPage(ctl, "Wörterbuch",
                                   "Wörter, die falsch erkannt werden, automatisch ersetzen. "
                                   "Groß- und Kleinschreibung spielt beim Erkennen keine Rolle.",
                                   "dictionary", ["Erkannt wird", "Ersetzen durch"], learn=True)),
                                  ("Stimmtraining", TrainPage(ctl)),
                                  ("Textbausteine", MapPage(ctl, "Textbausteine",
                                      "Ein gesprochenes Stichwort wird durch den hinterlegten Text ersetzt. "
                                      "Für einen Zeilenumbruch \\n schreiben.",
                                      "snippets", ["Stichwort", "Text"],
                                      starter=("Normalbefunde hinzufügen", NORMAL)))])),
            ("Einstellungen", Tabs([("Allgemein", SettingsPage(ctl)), ("LLM", LlmPage(ctl))])),
        ]
        self.buttons = QtWidgets.QButtonGroup(self)
        for i, (name, page) in enumerate(self.pages):
            b = QtWidgets.QPushButton("  " + name.replace("&", "&&"), checkable=True)
            b.setIcon(nav_icon(name))
            b.setIconSize(QtCore.QSize(18, 18))
            b.setCursor(Qt.PointingHandCursor)
            self.buttons.addButton(b, i)
            nav.addWidget(b)
            self.stack.addWidget(page)
        self.buttons.idClicked.connect(self.show_page)
        nav.addStretch(1)
        # Update-Bereich unten links: erscheint nur, wenn es etwas zu tun gibt. Ein Klick lädt, ein zweiter startet neu.
        self.settings = self.pages[-1][1].pages[0]
        self.update_state, self.update_version = "", ""      # "", "available", "loading", "ready"
        self.update_btn = button("", self._update_click, "update")
        self.update_btn.setIconSize(QtCore.QSize(16, 16))
        self.update_note = label("", "muted", wrap=True)
        self.update_btn.hide()
        self.update_note.hide()
        if pflege.program():                 # aus dem Quelltext gestartet gibt es nichts zu aktualisieren
            self.update_idle()
        # Wer diktiert? Nur wenn mehrere Personen an diesem Programmordner arbeiten (Ordner „profile“ oder Netzlaufwerk).
        self.profile_btn = button("", self._profile_menu, "profile")
        self.profile_btn.setIcon(glyph("person", "#B9BEC4"))
        self.profile_btn.setIconSize(QtCore.QSize(16, 16))
        nav.addWidget(self.profile_btn)
        nav.addSpacing(2)
        self.profile_refresh()
        nav.addWidget(self.update_btn)
        nav.addWidget(self.update_note)
        nav.addSpacing(8)
        self.status = label("", "muted", wrap=True)
        nav.addWidget(self.status)
        self.loadbar = QtWidgets.QProgressBar(textVisible=False)
        self.loadbar.setRange(0, 1000)
        self.loadbar.hide()
        nav.addWidget(self.loadbar)
        self.shield_note = label("", "muted", wrap=True)      # Namenserkennung wird geladen
        self.shield_bar = QtWidgets.QProgressBar(textVisible=False)
        self.shield_bar.setRange(0, 1000)
        self.shield_note.hide()
        self.shield_bar.hide()
        self.shield_queue = []
        nav.addWidget(self.shield_note)
        nav.addWidget(self.shield_bar)

        # Erster Start: großes Band über den Seiten, solange das Sprachmodell geladen wird
        self.banner = QtWidgets.QFrame(objectName="card")
        self.banner_title = label("Das Sprachmodell wird einmalig heruntergeladen", "h2")
        self.banner_text = label("", "muted", wrap=True)
        self.banner_text.setMinimumHeight(36)
        self.banner_bar = QtWidgets.QProgressBar(textVisible=False)
        self.banner_bar.setRange(0, 1000)
        bl = QtWidgets.QVBoxLayout(self.banner)
        bl.setContentsMargins(22, 16, 22, 18)
        bl.setSpacing(8)
        bl.addWidget(self.banner_title)
        bl.addWidget(self.banner_text)
        bl.addWidget(self.banner_bar)
        self.banner_retry = button("Erneut versuchen", lambda: self.ctl.retry_load(), "primary")
        self.banner_log = button("Protokoll öffnen", lambda: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(config.LOG))))
        self.banner_get = button("Komplettpaket herunterladen", lambda: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl("https://github.com/chunkyfire/LocalScribe/releases/latest")))
        self.banner_actions = QtWidgets.QWidget()
        al = hbox(self.banner_retry, self.banner_get, self.banner_log, None)
        al.setContentsMargins(0, 4, 0, 0)
        self.banner_actions.setLayout(al)
        self.banner_actions.hide()
        bl.addWidget(self.banner_actions)
        self.banner.hide()
        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        wrap = QtWidgets.QVBoxLayout()
        wrap.setContentsMargins(28, 18, 28, 0)
        wrap.addWidget(self.banner)
        self.banner_wrap = QtWidgets.QWidget()
        self.banner_wrap.setLayout(wrap)
        self.banner_wrap.hide()
        right.addWidget(self.banner_wrap)
        # Schmale Leiste: neue Fassung liegt bereit, oder nach einem Update „Was ist neu“
        self.news = QtWidgets.QFrame(objectName="card")
        self.news_text = label("", wrap=True)
        self.news_go = button("Jetzt neu starten", lambda: self.ctl.restart_new(), "primary")
        self.news_what = button("Was ist neu", self._news_notes)
        self.news_close = button("Schließen", self._news_done)
        nl = hbox(self.news_text, self.news_what, self.news_go, self.news_close)
        nl.setContentsMargins(16, 10, 12, 10)
        nl.setStretch(0, 1)
        self.news.setLayout(nl)
        nw = QtWidgets.QVBoxLayout()
        nw.setContentsMargins(28, 14, 28, 0)
        nw.addWidget(self.news)
        self.news_wrap = QtWidgets.QWidget()
        self.news_wrap.setLayout(nw)
        self.news_wrap.hide()
        self.news_since, self.news_version = "", ""
        right.addWidget(self.news_wrap)
        right.addWidget(self.stack, 1)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side)
        lay.addLayout(right, 1)
        self.show_page(0)

    def paintEvent(self, _):
        """Hintergrund: fast schwarz mit drei weichen Lichtflecken. Die halb durchsichtigen Karten davor wirken dadurch
        wie Milchglas, ohne dass das Fenster selbst durchsichtig sein muss (das ginge nicht auf jedem Windows)."""
        p = QtGui.QPainter(self)
        w, h = self.width(), self.height()
        base = QtGui.QLinearGradient(0, 0, w, h)
        base.setColorAt(0, QtGui.QColor("#0B0D0F"))
        base.setColorAt(1, QtGui.QColor("#08090B"))
        p.fillRect(self.rect(), base)
        for cx, cy, radius, color in ((0.10, 0.02, 0.55, QtGui.QColor(198, 255, 61, 34)),
                                      (0.98, 0.10, 0.50, QtGui.QColor(70, 150, 255, 30)),
                                      (0.62, 1.05, 0.60, QtGui.QColor(40, 210, 170, 24))):
            glow = QtGui.QRadialGradient(cx * w, cy * h, radius * max(w, h))
            glow.setColorAt(0, color)
            glow.setColorAt(1, QtGui.QColor(color.red(), color.green(), color.blue(), 0))
            p.fillRect(self.rect(), glow)
        p.end()

    def profile_refresh(self):
        """Den Profil-Knopf unten links auf den Stand bringen: Name des gewählten Profils oder „Dieser Rechner“."""
        on = config.profiles_on()
        self.profile_btn.setVisible(on)
        if not on:
            return
        name = config.ACTIVE or "Dieser Rechner"
        self.profile_btn.setText(name + (" · ohne Ordner" if config.OFFLINE else ""))
        if config.OFFLINE:
            tip = ("Der Programmordner mit den Profilen ist gerade nicht erreichbar. LocalScribe arbeitet mit der Kopie von "
                   "diesem Rechner weiter und führt beides zusammen, sobald der Ordner wieder da ist.")
        elif config.ACTIVE:
            tip = (f"Es diktiert: {config.ACTIVE}. Wörterbuch, Wortschatz, Textbausteine, Aufträge, Tasten und "
                   "Stimmaufnahmen kommen aus diesem Profil. Klick: Profil wechseln.")
        else:
            tip = ("Kein Profil gewählt: Es gelten die Einstellungen dieses Rechners, für alle, die hier diktieren. "
                   "Klick: eigenes Profil wählen oder anlegen. Es folgt dir an jeden Rechner an diesem Programmordner.")
        self.profile_btn.setToolTip(tip)

    def profile_actions(self, menu):
        """Die Einträge des Profil-Menüs; auch das Symbol neben der Uhr zeigt sie."""
        menu.clear()
        for name in config.profile_names():
            a = menu.addAction(name, lambda n=name: self.profile_pick(n))
            a.setCheckable(True)
            a.setChecked(name == config.ACTIVE)
        a = menu.addAction("Dieser Rechner (ohne Profil)", lambda: self.profile_pick(""))
        a.setCheckable(True)
        a.setChecked(not config.ACTIVE)
        menu.addSeparator()
        menu.addAction("Neues Profil …", self.profile_new)

    def _profile_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(STYLE)
        self.profile_actions(menu)
        menu.exec(self.profile_btn.mapToGlobal(QtCore.QPoint(0, -menu.sizeHint().height() - 4)))

    def profile_pick(self, name):
        """Auf ein Profil wechseln: Wörterbuch, Tasten und alles Persönliche gelten sofort."""
        if name == config.ACTIVE:
            return
        if self.busy():
            return QtWidgets.QMessageBox.information(self, "Profil", "Erst die laufende Aufnahme oder Transkription beenden.")
        try:
            config.profile_use(self.ctl.cfg, name)
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Profil", str(e))
            return self.profile_refresh()
        self.ctl.apply_cfg()
        self.profile_refresh()
        self.pages[self.stack.currentIndex()][1].refresh()

    def profile_new(self):
        box = QtWidgets.QDialog(self)
        box.setWindowTitle("Neues Profil")
        box.setStyleSheet(STYLE)
        box.setFixedWidth(560)
        name = QtWidgets.QLineEdit(os.environ.get("USERNAME", ""))
        name.selectAll()
        take = QtWidgets.QCheckBox("Mit den Einstellungen beginnen, die hier gerade gelten")
        take.setToolTip("Wörterbuch, Wortschatz, Textbausteine, Aufträge und Tasten gehen als Startstand ins neue Profil. "
                        "Ohne Haken beginnt es mit der Werkseinstellung.")
        take.setChecked(not config.ACTIVE)
        note = label("", "bad", wrap=True)
        note.hide()
        done = {}

        def create():
            try:
                done["name"] = config.profile_create(name.text(), self.ctl.cfg if take.isChecked() else None)
                box.accept()
            except ValueError as e:
                note.setText(str(e))
                note.show()
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(10)
        lay.addWidget(label("Neues Profil", "h2"))
        about = label("Ein Profil gehört einer Person: Wörterbuch, Wortschatz, Textbausteine, Aufträge, Tasten und "
                      "Stimmaufnahmen. Es liegt im Programmordner und folgt dir an jeden Rechner, der LocalScribe "
                      "von dort startet. Es hat kein Passwort: Jede Person an diesem Programmordner kann es wählen. "
                      "Verlauf, Fälle und Schlüssel bleiben auf dem jeweiligen Rechner.", "muted", wrap=True)
        about.setFixedWidth(516)
        about.ensurePolished()
        about.setMinimumHeight(about.heightForWidth(516) + 6)   # sonst schneidet der Dialog den umbrochenen Text ab
        lay.addWidget(about)
        lay.addWidget(label("Name oder Kürzel"))
        lay.addWidget(name)
        lay.addWidget(take)
        lay.addWidget(note)
        lay.addLayout(hbox(None, button("Abbrechen", box.reject), button("Anlegen", create, "primary")))
        name.returnPressed.connect(create)
        if box.exec() == QtWidgets.QDialog.Accepted and done.get("name"):
            self.profile_pick(done["name"])

    def _update_show(self, state, name, kind, color, text, note, tip, enabled=True):
        self.update_state = state
        restyle(self.update_btn, name)
        self.update_btn.setIcon(glyph(kind, color))
        self.update_btn.setText(text)
        self.update_btn.setToolTip(tip)
        self.update_btn.setEnabled(enabled)
        self.update_note.setText(note)
        self.update_note.setToolTip("")
        self.update_btn.show()
        self.update_note.setVisible(bool(note))

    def update_idle(self):
        """Ruhezustand: unauffällig die laufende Fassung; ein Klick fragt bei GitHub nach einer neueren."""
        self._update_show("", "updateIdle", "down", "#8A9096", f"Fassung {__version__}", "",
                          "Nach Updates suchen: fragt bei GitHub nach der neuesten Fassung. Gibt es eine, lädt der nächste "
                          "Klick nur die geänderten Dateien und richtet sie neben der laufenden ein.")

    def update_hint(self, text, tip=""):
        """Kurze Auskunft unter dem Knopf (neueste Fassung, kein Netz); verschwindet von selbst wieder."""
        if self.update_state in ("loading", "ready"):
            return
        if self.update_state == "asking":
            self.update_idle()
        self.update_note.setText(text)
        self.update_note.setToolTip(tip)
        self.update_note.setVisible(bool(text) and self.update_btn.isVisible())
        QtCore.QTimer.singleShot(9000, lambda: self.update_note.text() == text and self.update_state == ""
                                 and self.update_note.hide())

    def update_offer(self, version):
        """Bei GitHub liegt eine neuere Fassung. Ein Klick lädt nur, was sich geändert hat, und richtet sie ein."""
        if self.update_state in ("loading", "ready"):
            return
        self.update_version = version
        self._update_show("available", "update", "down", "#C6FF3D", f"Update {version}", "Ein Klick, du arbeitest weiter.",
                          f"Fassung {version} ist da, hier läuft {__version__}. Ein Klick lädt nur die geänderten Dateien "
                          "und richtet die neue Fassung neben der laufenden ein. Einstellungen, Wörterbuch, Verlauf und "
                          "Sprachmodell bleiben.")

    def update_loading(self, text):
        self._update_show("loading", "update", "down", "#9AA0A6", text, "Du kannst weiterarbeiten.", "", enabled=False)

    def update_failed(self, error):
        if self.update_state != "loading":
            return
        self._update_show("available", "update", "down", "#C6FF3D", f"Update {self.update_version}",
                          "Hat nicht geklappt. Ein Klick versucht es noch einmal.", error)

    def _update_click(self):
        if self.update_state == "ready":
            self.ctl.restart_new()
        elif self.update_state == "available":
            self.settings.start_update()
        elif self.update_state == "":
            self._update_show("asking", "updateIdle", "down", "#8A9096", f"Fassung {__version__}", "Frage bei GitHub nach …",
                              "", enabled=False)
            self.settings._check()

    def offer_restart(self, version):
        """Eine neuere Fassung ist eingerichtet (hier oder von einem anderen Rechner am selben Ordner)."""
        self.news_since, self.news_version = __version__, version
        self.update_version = version
        self._update_show("ready", "updateGo", "turn", "#0B0B0B", "Neu starten", f"Fassung {version} ist eingerichtet.",
                          f"LocalScribe {version} ist eingerichtet, hier läuft noch {__version__}. Ein Klick startet neu; "
                          "sonst gilt die neue Fassung ab dem nächsten Start.")

    def announce(self, before):
        """Erster Start nach einem Update."""
        self.news_since, self.news_version = before, ""
        self.news_text.setText(f"LocalScribe ist jetzt auf dem Stand {__version__} (vorher {before}).")
        self.news_go.hide()
        self.news_wrap.show()

    def news_note(self, text):
        self.news_text.setText(text)
        if self.update_state:
            self.update_note.setText(text)

    def _news_notes(self):
        show_notes(self, pflege.notes(self.news_since, self.news_version), self.news_version or __version__)

    def _news_done(self):
        self.news_wrap.hide()
        if not self.news_version:
            self.ctl.seen()

    def show_page(self, i):
        self.buttons.button(i).setChecked(True)
        self.pages[i][1].refresh()
        self.stack.setCurrentIndex(i)

    def refresh(self):
        """Aktuelle Seite neu laden, wenn das Fenster sichtbar ist (z. B. nach neuem Diktat)."""
        if self.isVisible() and self.stack.currentIndex() == 0:
            self.pages[0][1].refresh()

    def set_status(self, text):
        self.status.setText(text)

    def set_download(self, fraction, text):
        """fraction: Anteil 0..1, solange das Sprachmodell geladen wird; None, wenn nicht (mehr)."""
        active = fraction is not None
        self.loadbar.setVisible(active)
        self.banner_wrap.setVisible(active)
        self.banner.setVisible(active)
        if active:
            self.loadbar.setValue(int(fraction * 1000))
            self.banner_bar.setValue(int(fraction * 1000))
            self.banner_text.setText(text.split(" · ", 1)[-1] + ". Nur beim ersten Start – danach bleibt das Modell auf diesem "
                                     "Rechner. Diktieren geht, sobald der Balken voll ist.")

    def shield_wait(self, then=None, force=True, retry=False) -> bool:
        """Fehlt die Namenserkennung für den eingestellten Server, wird sie jetzt geladen; „then“ läuft, sobald
        sie da ist. Gibt True zurück, wenn gewartet wird, sonst False (nichts zu laden oder nicht ladbar)."""
        start = getattr(self.ctl, "shield_start", None)
        if not start or not start(force, retry):
            return False
        if then:
            self.shield_queue.append(then)
        return True

    def set_shield(self, fraction, text):
        """fraction: Anteil 0..1, solange die Namenserkennung geladen wird; None am Ende (text: Fehler oder leer)."""
        active = fraction is not None
        self.shield_bar.setVisible(active)
        self.shield_note.setVisible(active or bool(text))
        page = self.pages[-1][1].pages[1]                     # Einstellungen, LLM: dort steht derselbe Stand
        if active:
            self.shield_bar.setValue(int(fraction * 1000))
            self.shield_note.setText(text)
            page._shield_progress(min(fraction, 0.99), "")
            return
        self.shield_note.setText(f"Namenserkennung nicht geladen: {text[:140]}" if text else "")
        page._shield_progress(1.0, text)
        waiting, self.shield_queue = self.shield_queue, []
        for then in waiting:                                  # die Aufträge, die darauf gewartet haben
            then()

    def set_error(self, error):
        """Das Sprachmodell ließ sich nicht laden: Grund und Ausweg im Fenster zeigen, nicht nur im Protokoll."""
        failed = bool(error)
        self.banner_actions.setVisible(failed)
        self.banner_bar.setVisible(not failed)
        self.banner_title.setText("Das Sprachmodell konnte nicht geladen werden" if failed
                                  else "Das Sprachmodell wird einmalig heruntergeladen")
        if failed:
            self.banner_text.setText(
                error + "\n\nIn Netzen, die solche Downloads sperren (häufig in Kliniken), hilft das Komplettpaket: "
                "Dort liegt das Sprachmodell schon im Ordner, LocalScribe braucht dann kein Internet. "
                f"Das Protokoll liegt unter {config.LOG}.")
            self.banner_wrap.show()
            self.banner.show()

    def busy(self) -> bool:
        """Läuft gerade eine lange Aufnahme oder Transkription?"""
        every = [q for _, page in self.pages for q in ([page] + list(getattr(page, "pages", [])))]
        return any(getattr(page, "job", None) is not None and page.job.running for page in every)

    def open(self):
        self.pages[self.stack.currentIndex()][1].refresh()
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        e.ignore()  # läuft im Infobereich weiter
        self.hide()
