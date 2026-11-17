"""Das App-Fenster: Verlauf, Wörterbuch, Textbausteine, KI-Nachbearbeitung, Einstellungen."""
import copy
import difflib
import logging
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
QWidget { background: #0B0B0B; color: #EDEDED; font-family: "Segoe UI"; font-size: 10pt; }
QLabel, QCheckBox { background: transparent; }
QLabel#h1 { font-size: 17pt; font-weight: 600; }
QLabel#h2 { font-size: 11pt; font-weight: 600; }
QLabel#brand { font-size: 13pt; font-weight: 700; }
QLabel#muted, QLabel#time { color: #8C8C8C; }
QLabel#day { color: #8C8C8C; font-size: 8pt; font-weight: 700; padding: 14px 4px 6px 4px; }
QLabel#num { font-size: 16pt; font-weight: 600; }
QLabel#tag { color: #0B0B0B; background: #C6FF3D; border-radius: 7px; padding: 1px 7px;
             font-size: 8pt; font-weight: 600; }
QLabel#ok { color: #C6FF3D; }
QLabel#bad { color: #FF7A6B; }
QFrame#side { background: #0B0B0B; border: none; border-right: 1px solid #1E1E1E; }
QFrame#side QPushButton { text-align: left; padding: 9px 14px; border: none; border-radius: 8px;
                          color: #B4B4B4; background: transparent; }
QFrame#side QPushButton:hover { background: #161616; }
QFrame#side QPushButton:checked { background: #1B1B1B; color: #C6FF3D; font-weight: 600; }
QFrame#card { background: #131313; border: 1px solid #222222; border-radius: 12px; }
QFrame#card QWidget { background: transparent; }
QFrame#row { background: transparent; border: none; border-bottom: 1px solid #1D1D1D; }
QFrame#row:hover { background: #191919; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QFrame#card QLineEdit, QFrame#card QPlainTextEdit,
QFrame#card QComboBox, QFrame#card QSpinBox {
    background: #0B0B0B; border: 1px solid #2A2A2A; border-radius: 8px; padding: 6px 10px;
    selection-background-color: #C6FF3D; selection-color: #0B0B0B; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #C6FF3D; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #151515; border: 1px solid #2A2A2A;
                              selection-background-color: #C6FF3D; selection-color: #0B0B0B; }
QPushButton, QFrame#card QPushButton { background: #1B1B1B; border: 1px solid #2C2C2C;
                                       border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { border-color: #555555; }
QPushButton:disabled { color: #5A5A5A; }
QPushButton#primary, QFrame#card QPushButton#primary { background: #C6FF3D; color: #0B0B0B;
                                                       border: none; font-weight: 600; }
QPushButton#primary:disabled, QFrame#card QPushButton#primary:disabled { background: #2A2A2A; color: #6A6A6A; }
QPushButton#ghost, QFrame#card QPushButton#ghost, QFrame#row QPushButton {
    background: transparent; border: none; color: #8C8C8C; padding: 4px 8px; }
QPushButton#ghost:hover, QFrame#row QPushButton:hover { color: #C6FF3D; }
QPushButton::menu-indicator { image: none; width: 0; }
QMenu { background: #151515; border: 1px solid #2A2A2A; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: #C6FF3D; color: #0B0B0B; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #3A3A3A; border-radius: 4px;
                       background: #0B0B0B; }
QCheckBox::indicator:checked { background: #C6FF3D; border-color: #C6FF3D; }
QListWidget, QTableWidget { background: #0B0B0B; border: 1px solid #2A2A2A; border-radius: 8px;
                            outline: none; gridline-color: #1D1D1D; }
QListWidget::item { padding: 7px 10px; }
QListWidget::item:selected, QTableWidget::item:selected { background: #1F1F1F; color: #C6FF3D; }
QHeaderView::section { background: #131313; color: #8C8C8C; border: none;
                       border-bottom: 1px solid #222222; padding: 7px 10px; font-weight: 600; }
QTableWidget::item { padding: 0 10px; }
QTableWidget QLineEdit { border-radius: 0; padding: 0 9px; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; border: none; }
QScrollArea { border: none; }
QProgressBar { background: #1B1B1B; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }
QProgressBar::chunk { background: #C6FF3D; border-radius: 3px; }
QPushButton#rec, QFrame#card QPushButton#rec { background: #C6FF3D; color: #0B0B0B; border: none;
    border-radius: 48px; font-size: 11pt; font-weight: 700; }
QPushButton#recOn, QFrame#card QPushButton#recOn { background: #FF5A4D; color: #0B0B0B; border: none;
    border-radius: 48px; font-size: 11pt; font-weight: 700; }
QPushButton#rec:disabled { background: #2A2A2A; color: #6A6A6A; }
QLabel#clock { font-size: 22pt; font-weight: 600; }
QFrame#drop { background: #101010; border: 1px dashed #3A3A3A; border-radius: 12px; }
QFrame#drop[over="true"] { border-color: #C6FF3D; background: #141810; }
QFrame#drop QWidget { background: transparent; }
QFrame#box { background: #121212; border: 1px solid #232323; border-radius: 14px; }
QFrame#box QWidget { background: transparent; }
QFrame#box QLabel#boxTitle { color: #C6FF3D; font-size: 10pt; font-weight: 700; }
QFrame#box QLabel#kicker { color: #6F6F6F; font-size: 8pt; font-weight: 700; padding-top: 4px; }
QFrame#box QLabel#strong { font-weight: 600; }
QFrame#box QLabel#pct { font-weight: 700; }
QFrame#box QLabel#warn { color: #FFB454; font-weight: 600; }
QFrame#box QLabel#chip, QFrame#box QLabel#chipOff, QFrame#box QLabel#chipWarn, QFrame#box QLabel#chipRed {
    border-radius: 10px; padding: 4px 10px; font-weight: 600; }
QFrame#box QLabel#chip { background: #1D2A0B; color: #C6FF3D; border: 1px solid #3C5412; }
QFrame#box QLabel#chipOff { background: #181818; color: #8C8C8C; border: 1px solid #272727; font-weight: 400; }
QFrame#box QLabel#chipWarn { background: #2A1D09; color: #FFB454; border: 1px solid #5C4012; }
QFrame#box QLabel#chipRed { background: #2F1210; color: #FF7A6B; border: 1px solid #6E2A24; }
QFrame#box QLabel#chipSmall { background: #1D2A0B; color: #C6FF3D; border-radius: 6px; padding: 0 6px; font-size: 8pt; }
QFrame#box QFrame#alert { background: #18130A; border: none; border-left: 3px solid #FFB454; border-radius: 6px; }
QFrame#box QFrame#ask { background: #0E0E0E; border: 1px solid #202020; border-radius: 10px; }
QFrame#box QPushButton#fold { background: transparent; border: none; text-align: left; padding: 5px 0; font-weight: 600; }
QFrame#box QPushButton#fold:hover { color: #C6FF3D; }
QFrame#box QProgressBar { background: #1D1D1D; max-height: 4px; min-height: 4px; border-radius: 2px; }
QFrame#box QProgressBar#on::chunk { background: #C6FF3D; border-radius: 2px; }
QFrame#box QProgressBar#dim::chunk { background: #3A3A3A; border-radius: 2px; }
QFrame#box QLabel { font-size: 9pt; }
QFrame#box QLabel#chipLine { background: transparent; color: #C6FF3D; border: 1px solid #3C5412; border-radius: 9px;
    padding: 2px 8px; font-weight: 600; }
QPushButton#recPill { background: #C6FF3D; color: #0B0B0B; border: none; border-radius: 15px; padding: 7px 16px; font-weight: 700; }
QPushButton#recPillOn { background: #FF5A4D; color: #0B0B0B; border: none; border-radius: 15px; padding: 7px 16px; font-weight: 700; }
QPushButton#recPill:disabled { background: #2A2A2A; color: #6A6A6A; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2C2C2C; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #454545; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

PRESETS = [("Ollama (lokal)", "http://localhost:11434/v1"),
           ("LM Studio (lokal)", "http://localhost:1234/v1"),
           ("OpenRouter", "https://openrouter.ai/api/v1"),
           ("IONOS AI Model Hub", "https://openai.inference.de-txl.ionos.com/v1"),
           ("Eigene Adresse", "")]


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


class RecordPage(LongPage):
    def __init__(self, ctl):
        super().__init__(ctl, "Aufnahme",
                         "Einmal drücken startet, noch einmal drücken beendet – auch nach einer Stunde. "
                         "Der Text läuft live mit: Schon beim Sprechen steht er grau als Vorschau da, nach jeder Sprechpause "
                         "wird daraus der gültige Text. "
                         "Der Ton wird nebenbei gesichert und gelöscht, sobald der Text vollständig ist.",
                         "Aufnahme")
        self.btn = button("Start", self.toggle, "rec")
        self.btn.setFixedSize(96, 96)
        self.clock = label("00:00", "clock")
        self.state = label("Bereit", "muted", wrap=True)
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(2)
        col.addStretch(1)
        col.addWidget(self.clock)
        col.addWidget(self.state)
        col.addStretch(1)
        self.body.addWidget(card(hbox(self.btn, (self._wrap(col), 1), spacing=22), self.split))

        # Aufnahme, die beim letzten Mal nicht fertig wurde (Absturz, Stromausfall, Fehler)
        self.left_text = label("", wrap=True)
        self.left_card = card(hbox((self.left_text, 1), button("Jetzt transkribieren", self.recover, "primary"),
                                   button("Löschen", self.discard)))
        self.left_card.hide()
        self.body.addWidget(self.left_card)
        self.body.addWidget(self.out, 1)
        self.recording = self.warned = False
        self.done = 0.0
        self.leftover = None
        self.tick = QTimer(self, interval=250, timeout=self._tick)

    @staticmethod
    def _wrap(layout):
        w = QtWidgets.QWidget()
        layout.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        return w

    def info(self, text, bad=False):
        restyle(self.state, "bad" if bad else "muted")
        self.state.setText(text)

    def refresh(self):
        super().refresh()
        current = self.job.wav_path if self.job.running else None
        rest = [p for p in config.leftover_recordings() if p != current]
        self.leftover = rest[0] if rest else None
        if self.leftover and not self.job.running:
            minutes = max(0, self.leftover.stat().st_size - 44) / 2 / 16000 / 60
            when = time.strftime("%d.%m. um %H:%M", time.localtime(self.leftover.stat().st_mtime))
            more = f" ({len(rest)} Aufnahmen warten.)" if len(rest) > 1 else ""
            self.left_text.setText(f"Eine Aufnahme vom {when} ({minutes:.0f} Minuten) wurde nicht fertig "
                                   f"transkribiert. Der Ton ist noch da.{more}")
            self.left_card.show()
        else:
            self.left_card.hide()

    def recover(self):
        if self.job.running or not self.leftover or not self.model_ready():
            return
        self.left_card.hide()
        self.started = time.time()
        self.out.set_text("")
        self.out.set_busy(True)
        self.btn.setEnabled(False)
        self.info("Hole die Aufnahme nach …")
        self.job.start_recovery(self.leftover)

    def discard(self):
        if self.leftover:
            try:
                self.leftover.unlink()
            except OSError as e:
                return self.info(f"Nicht löschbar: {e}", bad=True)
        self.refresh()

    def toggle(self):
        if self.recording:
            self.recording = False
            self.tick.stop()
            self.ctl.keep_awake(False)
            self.job.stop_recording()
            self.btn.setEnabled(False)
            restyle(self.btn, "rec")
            self.btn.setText("Start")
            self.info("Schreibe den Rest fertig …")
            return
        if self.job.running or not self.model_ready():
            return
        try:
            self.job.start_recording()
        except Exception as e:
            return self.info(f"Mikrofon nicht verfügbar: {e}", bad=True)
        self.ctl.keep_awake(True)   # kein Ruhezustand mitten in der Aufnahme
        self.recording, self.warned, self.started, self.done = True, False, time.time(), 0.0
        self.left_card.hide()
        self.out.set_text("")
        self.out.set_busy(True)
        restyle(self.btn, "recOn")
        self.btn.setText("Stopp")
        self.info("Nimmt auf …")
        self.tick.start()

    def _tick(self):
        self.clock.setText(clock(time.time() - self.started))
        if not self.job.mic_alive():
            if not self.warned:
                self.warned = True
                QtWidgets.QApplication.beep()
            return self.info("Das Mikrofon liefert keinen Ton mehr! Aufnahme beenden und Mikrofon prüfen – "
                             "alles bisher Gesprochene bleibt erhalten.", bad=True)
        self.warned = False
        behind = time.time() - self.started - self.done
        if behind > 30:
            # eine Äußerung dauert höchstens 12 s; mehr Rückstand heißt, der Rechner kommt nicht nach
            return self.info(f"Nimmt auf – die Erkennung hängt {behind:.0f} s hinterher. Es geht nichts verloren, "
                             "der Text kommt nach.", bad=True)
        self.info(f"Live – Text bis {clock(self.done)} erkannt. Er erscheint nach jeder Sprechpause.")

    def on_part(self, text, done, total):
        super().on_part(text, done, total)
        self.done = done
        if not self.recording and total > 0:   # Nachholen einer alten Aufnahme
            self.clock.setText(clock(done))
            self.info(f"Hole die Aufnahme nach … {clock(done)} von {clock(total)}")

    def on_finished(self, text, seconds, error):
        super().on_finished(text, seconds, error)
        if self.recording:                      # Abbruch durch einen Fehler mitten in der Aufnahme
            self.recording = False
            self.tick.stop()
            self.ctl.keep_awake(False)
            self.job.stop_recording()
            restyle(self.btn, "rec")
            self.btn.setText("Start")
        self.btn.setEnabled(True)
        notes = self.problems()
        if error:
            self.info(f"Fehler: {error}. {notes}", bad=True)
        elif notes:
            self.info(notes, bad=True)
        elif text.strip():
            where = " Der Text steht auch im Verlauf." if self.ctl.cfg.get("history_enabled", True) else ""
            self.info(f"Fertig – {clock(seconds)} aufgenommen, {len(text.split())} Wörter."
                      f"{self.speakers_note()} Die Tonaufnahme ist gelöscht.{where}")
        else:
            self.info("Kein Text erkannt. Die Tonaufnahme ist gelöscht.")
        self.refresh()


class DropZone(QtWidgets.QFrame):
    dropped = Signal(str)

    def __init__(self):
        super().__init__(objectName="drop")
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)

    def _over(self, on):
        self.setProperty("over", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and e.mimeData().urls()[0].isLocalFile():
            e.acceptProposedAction()
            self._over(True)

    def dragLeaveEvent(self, e):
        self._over(False)

    def dropEvent(self, e):
        self._over(False)
        self.dropped.emit(e.mimeData().urls()[0].toLocalFile())


class FilePage(LongPage):
    def __init__(self, ctl):
        super().__init__(ctl, "Datei",
                         "Audio- oder Videodatei hineinziehen. Sie wird auf diesem Rechner transkribiert "
                         "und verlässt ihn nicht.", "Datei")
        self.zone = DropZone()
        self.zone.dropped.connect(self.start)
        self.title = label("Datei hierher ziehen", "h2")
        self.state = label("MP3, M4A, WAV, FLAC, OGG, MP4 und die meisten anderen Formate", "muted", wrap=True)
        self.pick = button("Datei auswählen …", self.choose)
        self.stop = button("Abbrechen", self.cancel)
        self.stop.hide()
        self.bar = QtWidgets.QProgressBar(textVisible=False)
        self.bar.hide()
        lay = QtWidgets.QVBoxLayout(self.zone)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(8)
        lay.addLayout(hbox(self.title, None, self.pick, self.stop))
        lay.addWidget(self.state)
        lay.addWidget(self.bar)
        lay.addWidget(self.split)
        self.body.addWidget(self.zone)
        self.body.addWidget(self.out, 1)

    def info(self, text):
        self.state.setText(text)

    def choose(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Audiodatei auswählen", "",
            "Audio und Video (*.mp3 *.m4a *.wav *.flac *.ogg *.opus *.aac *.wma *.mp4 *.mkv *.mov *.webm);;Alle Dateien (*)")
        if path:
            self.start(path)

    def start(self, path):
        if self.job.running:
            return self.info("Es läuft schon eine Transkription.")
        if not self.model_ready():
            return
        self.source = os.path.basename(path)
        self.started = time.time()
        self.title.setText(self.source)
        self.state.setText("Lese die Datei …")
        self.out.set_text("")
        self.out.set_busy(True)
        self.bar.setRange(0, 0)
        self.bar.show()
        self.pick.hide()
        self.stop.show()
        self.job.start_file(path)

    def cancel(self):
        self.state.setText("Breche ab …")
        self.job.cancel()

    def on_part(self, text, done, total):
        super().on_part(text, done, total)
        if total > 0:
            self.bar.setRange(0, 1000)
            self.bar.setValue(min(1000, int(done / total * 1000)))
            self.state.setText(f"{clock(done)} von {clock(total)}")
        else:
            self.state.setText(f"{clock(done)} transkribiert")

    def on_finished(self, text, seconds, error):
        super().on_finished(text, seconds, error)
        self.bar.hide()
        self.stop.hide()
        self.pick.show()
        took = time.time() - self.started
        notes = self.problems()
        if error:
            self.state.setText(f"Das hat nicht geklappt: {error}")
        elif notes:
            self.state.setText(notes)
        elif text.strip():
            where = " Der Text steht auch im Verlauf." if self.ctl.cfg.get("history_enabled", True) else ""
            self.state.setText(f"Fertig – {clock(seconds)} Audio in {clock(took)}, {len(text.split())} Wörter."
                               f"{self.speakers_note()}{where}")
        else:
            self.state.setText("Kein Text erkannt.")


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
            self.heard = label("Wort eintippen, Knopf halten und das Wort so sprechen wie im Diktat – am besten "
                               "zwei- bis dreimal, auch in einem kurzen Satz. Was die Erkennung daraus macht, "
                               "wird künftig durch die richtige Schreibweise ersetzt.", "muted", wrap=True)
            self.body.addWidget(card(label("Wort einsprechen", "h2"), hbox((self.word, 1), self.speak), self.heard))
            self.ctl.sig_heard.connect(self._heard)
            self.terms = QtWidgets.QLineEdit(placeholderText="z. B. RIVA, Trimbow, Tresiba, Brinkkötter")
            self.terms.editingFinished.connect(self._terms)
            self.body.addWidget(card(
                label("Meine Begriffe", "h2"), self.terms,
                label("Nur die richtige Schreibweise eintragen, durch Komma getrennt: Medikamente, Abkürzungen, Namen. "
                      "LocalScribe erkennt am Klang, wenn die Erkennung daraus etwas Ähnliches macht (Riba wird RIVA), "
                      "und schreibt den Begriff so, wie er hier steht. Wörter, die es wirklich gibt, bleiben unberührt.",
                      "muted", wrap=True)))
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

    def _terms(self):
        terms = [t.strip() for t in self.terms.text().split(",") if t.strip()]
        if terms != list(self.ctl.cfg.get("vocabulary") or []):
            self.ctl.cfg["vocabulary"] = terms
            self.ctl.apply_cfg()

    def _base(self, on):
        if not self.loading and on != bool(self.ctl.cfg.get("base_dictionary", True)):
            self.ctl.cfg["base_dictionary"] = on
            self.ctl.apply_cfg()

    def refresh(self):
        self.loading = True
        if hasattr(self, "base"):
            self.terms.setText(", ".join(self.ctl.cfg.get("vocabulary") or []))
            n, m = len(engine.base_dictionary()), len(fach.load()[0])
            self.base.setText(f"Medizinisches Basiswörterbuch anwenden: {m:,} Fachbegriffe werden am Klang erkannt, "
                              f"dazu {n:,} bekannte Fehlschreibungen".replace(",", "."))
            self.base.setChecked(bool(self.ctl.cfg.get("base_dictionary", True)))
        data = self.ctl.cfg.get(self.key) or {}
        self.table.setRowCount(0)
        for k, v in data.items():
            self._append(k, v.replace("\n", "\\n"))
        self.loading = False

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
        data = {}
        for r in range(self.table.rowCount()):
            k = (self.table.item(r, 0).text() if self.table.item(r, 0) else "").strip()
            v = self.table.item(r, 1).text() if self.table.item(r, 1) else ""
            if k:
                data[k] = v.replace("\\n", "\n")
        self.ctl.cfg[self.key] = data
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
    PRIORITY = {"critical": ("entscheidend", "chipRed"), "high": ("wichtig", "chipWarn"), "medium": ("ergänzend", "chipOff")}

    def __init__(self, ctl):
        super().__init__("Visite & Übergabe",
                         "Experimenteller Modus für Benchmarking, Forschung und Lehre. Kein Medizinprodukt: Die Ausgaben "
                         "sind Entwürfe und Wahrscheinlichkeiten von Modellen, keine Diagnose, keine Anordnung, und vor "
                         "jeder Verwendung zu prüfen. Server und Schlüssel: Einstellungen, LLM.", scroll=False)
        self.ctl = ctl
        self.store = visite.Store()
        self.case, self.result, self.waiting, self.errors = None, None, set(), {}
        self.tabs = QtWidgets.QButtonGroup(self)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        for i, name in enumerate(("Neuer Patient", "Fallliste", "Papierkorb")):
            b = QtWidgets.QPushButton(name, checkable=True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton:checked { color: #C6FF3D; border-color: #C6FF3D; }")
            self.tabs.addButton(b, i)
            row.addWidget(b)
        row.addStretch(1)
        self.body.addLayout(row)
        self.stack = QtWidgets.QStackedWidget()
        self.body.addWidget(self.stack, 1)

        # Neuer Patient: oben eine schmale Leiste und der Text, darunter das Ergebnis über die ganze Breite
        self.name = QtWidgets.QLineEdit(placeholderText="Fallbezeichnung, z. B. Zimmer 4 oder Kürzel (kein Klarname nötig)")
        self.rec = button("●  Aufnahme", self._record, "recPill")
        self.split = QtWidgets.QCheckBox("Sprecher trennen")
        self.split.setToolTip("Für Gespräche mit mehreren Personen: „Sprecher 1: …“, „Sprecher 2: …“. Läuft auf diesem Rechner.")
        self.split.toggled.connect(lambda on: LongPage._split(self, on))
        self.sig_voice.connect(self.info)
        self.state = label("Aufnehmen oder in das Feld tippen.", "muted", wrap=True)
        self.text = QtWidgets.QPlainTextEdit(placeholderText="Hier steht nach der Aufnahme der Text zum Korrigieren. "
                                             "Tippen geht auch: Anamnese, Befund, Verlauf, Vormedikation, geplantes Vorgehen.")
        self.go = button("Auswerten", self._analyse, name="primary")
        self.note = label("", "muted")
        new = QtWidgets.QWidget()
        top = QtWidgets.QVBoxLayout(new)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        top.addLayout(hbox((self.name, 1), self.rec, self.split, self.go, button("Neuer Fall", self._new)))
        top.addLayout(hbox((self.state, 1), self.note))
        top.addWidget(self.text, 1)
        inner = QtWidgets.QWidget()
        self.cards = QtWidgets.QGridLayout(inner)
        self.cards.setContentsMargins(0, 0, 8, 0)
        self.cards.setSpacing(12)
        self.area = QtWidgets.QScrollArea(widgetResizable=True)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setWidget(inner)
        self.area.hide()
        top.addWidget(self.area, 4)
        self.boxes, self.columns = {}, 0
        self.stack.addWidget(new)
        self.saver = QTimer(self, singleShot=True, interval=700)       # nichts geht verloren: jede Eingabe wird gesichert
        self.saver.timeout.connect(self._save)
        self.text.textChanged.connect(self.saver.start)
        self.name.textEdited.connect(lambda _: self.saver.start())

        # Aufnahme wie auf der Seite „Aufnahme“: Ton wird nebenbei gesichert, der Text läuft live mit
        self.job = LongJob(ctl)
        self.job.part.connect(self._part)
        self.job.glimpse.connect(lambda g: self._live(self.heard, g))
        self.job.finished.connect(self._recorded)
        self.recording, self.before, self.heard, self.started = False, "", "", 0.0
        self.tick = QTimer(self, interval=250, timeout=lambda: self.rec.setText("■  Stopp  " + clock(time.time() - self.started)))

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
        self._tab(0)
        self._show(None)

    def refresh(self):
        self._fill()
        self.split.blockSignals(True)
        self.split.setChecked(bool(self.ctl.cfg.get("speakers")))
        self.split.blockSignals(False)

    def info(self, text, bad=False):
        restyle(self.state, "bad" if bad else "muted")
        self.state.setText(text)

    def _tab(self, i):
        self.tabs.button(i).setChecked(True)
        self.stack.setCurrentIndex(i)
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
            self.tabs.button(1 + trash).setText(("Fallliste", "Papierkorb")[trash] + (f" ({len(rows)})" if rows else ""))

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
        self.case, self.result, self.waiting = None, None, set()
        for w in (self.name, self.text):
            w.blockSignals(True)
            w.clear()
            w.blockSignals(False)
        self.note.setText("")
        self.info("Aufnehmen oder in das Feld tippen.")
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
        self._show(row[2])

    # ----- Aufnahme
    def _record(self):
        if self.recording:
            self.recording = False
            self.tick.stop()
            self.ctl.keep_awake(False)
            self.job.stop_recording()
            self.rec.setEnabled(False)
            restyle(self.rec, "recPill")
            self.rec.setText("●  Aufnahme")
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
        self.before = self.text.toPlainText().rstrip()        # schon Getipptes bleibt, die Aufnahme kommt dahinter
        self.text.setReadOnly(True)
        self.go.setEnabled(False)
        restyle(self.rec, "recPillOn")
        self.rec.setText("■  Stopp  00:00")
        self.info("Nimmt auf … Der Text läuft mit.")
        self.tick.start()

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
            self.tick.stop()
            self.ctl.keep_awake(False)
            self.job.stop_recording()
            restyle(self.rec, "recPill")
            self.rec.setText("●  Aufnahme")
        self.heard = text
        self._live(text)
        self.text.setReadOnly(False)
        self.rec.setEnabled(True)
        self.go.setEnabled(not self.waiting)
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
            self.info(f"Fertig – {clock(seconds)}, {len(text.split())} Wörter.{who} Text prüfen und korrigieren, dann "
                      "„Auswerten“. Die Tonaufnahme ist gelöscht.")
        else:
            self.info("Kein Text erkannt. Die Tonaufnahme ist gelöscht.")

    # ----- Auswerten
    def _analyse(self):
        text = self.text.toPlainText().strip()
        restyle(self.note, "bad")
        if not text:
            return self.note.setText("Erst den Fall aufnehmen oder eintippen.")
        cfg = copy.deepcopy(self.ctl.cfg)
        server = visite.writer(cfg)
        if not (server.get("base_url") or "").strip() or not (server.get("model") or "").strip():
            return self.note.setText("Kein Sprachmodell eingestellt. Unter Einstellungen, LLM, Server und Modell wählen.")
        self.saver.stop()
        self._save()
        self.go.setEnabled(False)
        restyle(self.note, "muted")
        self.note.setText("Läuft …")
        case = self.case
        self.result, self.errors = {}, {}
        self.waiting = {"brief"} | ({"jev"} if jev.available(server) else set())
        self._show(self.result)

        def run(call, signal):
            try:
                signal.emit(call(cfg, text), "", case)
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
            else:
                merged = {**result, **({"jev": merged["jev"]} if merged.get("jev") else {})}
            self.store.save(case, row[0], row[1], merged)
        if case != self.case:
            return self._fill()
        self.waiting.discard(part)
        if result is None:
            self.errors["jev_error" if part == "jev" else "error"] = error
        if not self.waiting:
            self.go.setEnabled(not self.recording)
            failed = self.errors.get("error")
            restyle(self.note, "bad" if failed else "ok")
            self.note.setText("Der Arztbrief ließ sich nicht erzeugen, siehe rechts." if failed
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
        self.boxes, self.columns = {}, 0
        self.area.setVisible(result is not None)
        self.text.setMaximumHeight(16777215 if result is None else 118)     # mit Ergebnis tritt der Text zurück
        if result is None:
            return
        made = {"jev": self._jev_box(result["jev"]) if result.get("jev") else None, **self._letter_boxes(result)}
        for key in self.ORDER:
            box = made.get(key)
            if box is None:
                part = "jev" if key == "jev" else "brief"
                error = result.get("jev_error" if key == "jev" else "error")
                text = (f"Nicht geklappt: {error}" if error else
                        ("Jev bewertet den Fall …" if key == "jev" else "Das Sprachmodell schreibt …") if part in self.waiting else
                        "Nur über OpenRouter (Einstellungen, LLM)." if key == "jev" else "Keine Angabe.")
                box = Box(self.TITLES[key])
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
        doc = result.get("documentation") or {}
        parts = [(title, str(doc[key]).strip()) for key, title in visite.SECTIONS if str(doc.get(key) or "").strip()]
        if parts:
            box = Box("Arztbrief", "Entwurf", copy=lambda: visite.letter(result))
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
            box = Box("Patienteninfo", folded=True,
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
                         "jederzeit unterbrechbar – je mehr Sätze, desto besser passt die Erkennung zu deiner Stimme. "
                         "Der Ton bleibt im Arbeitsspeicher; gespeichert wird er nur, wenn du unten das Aufheben einschaltest.")
        self.ctl = ctl
        self.topic = QtWidgets.QComboBox()
        self.topic.addItem("Alle Themen", "")
        for name, sentences in training.material().items():
            self.topic.addItem(f"{name} ({len(sentences)})", name)
        self.topic.currentIndexChanged.connect(lambda _: self.next(0))
        self.count = label("", "muted")
        self.sentence = label("", "h2", wrap=True)
        self.sentence.setMinimumHeight(74)
        self.speak = button("Halten und vorlesen", name="primary")
        self.speak.pressed.connect(self._listen)
        self.speak.released.connect(self.ctl.listen_stop)
        self.result = label("Knopf gedrückt halten, den Satz in deinem normalen Diktiertempo vorlesen, loslassen. "
                            "Zahlen und Einheiten so sprechen, wie du es sonst auch tust.", "muted", wrap=True)
        self.body.addWidget(card(hbox(label("Thema"), self.topic, None, self.count),
                                 self.sentence,
                                 hbox(self.speak, button("Überspringen", lambda: self.next(1)),
                                      button("Zurück", lambda: self.next(-1)), None),
                                 self.result))
        self.learned = label("", "muted", wrap=True)
        self.body.addWidget(card(label("Gelernt", "h2"), self.learned))
        self.pairs = label("Hast du Diktate mit dem fertigen Text dazu? Wähle die Tondateien aus; das Transkript liegt als "
                           "Textdatei mit gleichem Namen daneben (befund1.wav und befund1.txt oder .docx), oder du wählst es "
                           "im zweiten Schritt. LocalScribe erkennt die Aufnahme, vergleicht mit dem Transkript und lernt "
                           "deine Verhörer und Fachwörter. Der Ton wird nur gelesen und nirgends gespeichert.",
                           "muted", wrap=True)
        self.pair_btn = button("Aufnahmen mit Transkript wählen …", self._pairs)
        self.body.addWidget(card(label("Aus Aufnahme mit Transkript lernen", "h2"), self.pairs, hbox(self.pair_btn, None)))
        self.words = label("", "muted", wrap=True)
        self.words_n = label("Gelernter Wortschatz", "h2")
        self.body.addWidget(card(
            hbox(self.words_n, None, button("Aus eigenen Texten lernen …", self._learn_files),
                 button("Leeren", self._learn_clear)), self.words))
        self.keep = QtWidgets.QCheckBox("Die oben angezeigten, erfundenen Übungssätze beim Vorlesen als Ton aufheben")
        self.keep.setChecked(bool(self.ctl.cfg.get("training_keep")))
        self.keep.toggled.connect(self._keep)
        self.kept = label("", "muted", wrap=True)
        self.body.addWidget(card(label("Material für ein Nachtraining auf deine Stimme", "h2"), self.keep, self.kept,
                                 hbox(button("Ordner öffnen", self._open_store), button("Alle löschen", self._clear), None)))
        self.sig_pairs.connect(self._pairs_done)
        self.body.addStretch(1)
        self.items, self.pos, self.session = [], 0, []
        self.ctl.sig_heard.connect(self._heard)

    def refresh(self):
        self.next(0)
        self._kept()
        self._words()

    def _items(self):
        topic = self.topic.currentData()
        return [s for name, group in training.material().items() if not topic or name == topic for s in group]

    def next(self, step):
        self.items = self._items()
        done = set(self.ctl.cfg.get("training_done") or [])
        if step == 0:                               # beim Öffnen: erster noch nicht gelesener Satz
            self.pos = next((i for i, s in enumerate(self.items) if s not in done), 0)
        else:
            self.pos = (self.pos + step) % len(self.items)
        self.sentence.setText(self.items[self.pos])
        read = sum(1 for s in self.items if s in done)
        self.count.setText(f"{read} von {len(self.items)} gelesen")
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
        self.words_n.setText(f"Gelernter Wortschatz: {n:,} Fachwörter".replace(",", "."))
        self.words.setText("Fachwörter aus deinen Diktaten, Transkripten und eingelesenen Briefen; beim Erkennen werden sie "
                           "bevorzugt. Übernommen werden nur einzelne Wörter aus dem Lexikon, keine Sätze, keine Namen.")

    def _keep(self, on):
        self.ctl.cfg["training_keep"] = bool(on)
        self.ctl.apply_cfg()

    def _open_store(self):
        training.store().mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(training.store())))

    def _kept(self):
        n, sec = training.kept()
        self.kept.setText(f"{n} Aufnahme{'n' if n != 1 else ''}, {sec / 60:.1f} Minuten, nur auf diesem Rechner. Aufgehoben werden "
                          "ausschließlich die erfundenen Übungssätze dieser Seite, während du sie vorliest. Diktate, eingelesene "
                          "Aufnahmen und alles andere werden nie gespeichert. Ab etwa 30 Minuten lohnt ein Versuch, das "
                          "Sprachmodell auf deine Stimme nachzutrainieren; ob das hilft, ist noch nicht gemessen. Ab Werk aus.")

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
        box.setText(f"{n} Aufnahmen aus dem Stimmtraining endgültig löschen?")
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
        if cfg.get("training_keep") and audio is not None and len(audio):
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
                         "die Fachkorrektur und „Visite & Übergabe“. Funktioniert mit jedem Server, der die "
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
        self.where = label("", "muted", wrap=True)
        self.key = QtWidgets.QLineEdit()
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.model = QtWidgets.QComboBox(editable=True)
        self.model.lineEdit().setPlaceholderText("Modellname")
        self.status = label("", "muted", wrap=True)
        self.status.hide()
        self.fetch = button("Modelle abrufen", self.load_models)
        self.fix = QtWidgets.QCheckBox("Fachkorrektur: Hörfehler bei Fachbegriffen vom Sprachmodell korrigieren lassen")
        self.fix.setToolTip("Das Sprachmodell schlägt vor, was bei verhörten Wörtern gemeint war. Übernommen wird nur, "
                            "was selbst ein Fachbegriff ist, ähnlich klingt und keine Zahl ändert. Kostet je Diktat "
                            "eine Anfrage an den Server oben; mit kleinen lokalen Modellen bringt es wenig.")
        self.body.addWidget(card(
            self.enabled,
            self.fix,
            form(("Anbieter", hbox((self.profile, 1), button("Speichern als …", self._save_as),
                                   button("Löschen", self._delete, "ghost"))),
                 ("Server", hbox(self.preset, (self.url, 1))),
                 ("API-Schlüssel", hbox((self.key, 1), button("Entfernen", self.drop_key, "ghost"))),
                 ("Modell", hbox((self.model, 1), self.fetch))),
            self.where, self.status,
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
        right = form(("Name", self.name), ("Halte-Taste", self.hotkey), ("Anweisung", self.text))
        self.body.addWidget(card(
            label("Prompts", "h2"),
            hbox(left, (self._wrap(right), 1), spacing=16),
            form(("Bei jedem Diktat", self.auto))))

        # Visite & Übergabe
        self.v_prompt = QtWidgets.QPlainTextEdit()
        self.v_prompt.setMinimumHeight(170)
        self.v_note = label("", "muted")
        self.v_writer = QtWidgets.QLineEdit(placeholderText=f"leer: {visite.WRITER} bei OpenRouter, sonst das Modell von oben")
        self.v_rules = QtWidgets.QPlainTextEdit(placeholderText="Optional: Hausregeln für die Ersteinschätzung, zum Beispiel "
                                                "Schockraum-Kriterien, Laborprofile, Zuständigkeiten. Jev entscheidet danach, wo sie eine Regel enthalten.")
        self.v_rules.setFixedHeight(84)
        self.body.addWidget(card(
            label("Visite & Übergabe", "h2"),
            label("Die Ersteinschätzung kommt von Jev (TypeSafe, nur über OpenRouter), den Arztbrief schreibt ein "
                  "Sprachmodell über den Server von oben.", "muted", wrap=True),
            form(("Modell für den Arztbrief", self.v_writer), ("Hausregeln für Jev", self.v_rules)),
            label("Prompt für den Arztbrief: bestimmt, was aus einem Fall erzeugt wird (Arztbrief-Entwurf, "
                  "Sicherheitsnetz, Rückfragen, Kodierung, Patienteninfo). Die Namen der Felder im JSON-Schema am Ende "
                  "müssen bleiben, sonst kann LocalScribe das Ergebnis nicht anzeigen.", "muted", wrap=True),
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
        self.ctl.cfg["visite_model"] = self.v_writer.text().strip()
        self.ctl.cfg["visite_rules"] = self.v_rules.toPlainText().strip()
        self.ctl.apply_cfg()
        self.saved(self.v_note)

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
            self.model.setEditText(p.get("model", ""))
            urls = [u for _, u in PRESETS]
            self.preset.setCurrentIndex(urls.index(self.url.text()) if self.url.text() in urls[:-1] else len(urls) - 1)
        self.key.clear()
        self.key.setPlaceholderText("gespeichert – zum Ändern neu eingeben" if llm.get_key(self.active)
                                    else "bei lokalen Servern meist leer")
        if p:
            self.saved(self.note, f"„{name}“ gewählt – mit Speichern übernehmen")

    def _save_as(self):
        url, model = self.url.text().strip(), self.model.currentText().strip()
        if not url or not model:
            return self.saved(self.note, "Erst Server und Modell eintragen.", ok=False)
        host = llm.urllib.parse.urlsplit(url).hostname or "Server"
        suggestion = next((n for n, u in PRESETS if u and u == url), host)
        name, ok = QtWidgets.QInputDialog.getText(self, "Anbieter speichern", "Name für diesen Anbieter:", text=suggestion)
        name = (name or "").strip()
        if not ok or not name:
            return
        key = self.typed_key() or llm.get_key(self.active)
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
        self.v_writer.setText(cfg.get("visite_model") or "")
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
        self.key.clear()
        self.key.setPlaceholderText("gespeichert – zum Ändern neu eingeben" if llm.get_key(self.active)
                                    else "bei lokalen Servern meist leer")
        self.model.setEditText(l.get("model") or "")
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
                 model=self.model.currentText().strip(), auto_prompt=self.auto.currentData() or "",
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
        if self.typed_key():
            try:
                llm.set_key(self.typed_key(), self.active)
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

    def drop_key(self):
        llm.set_key("", self.active)
        self.key.clear()
        self.key.setPlaceholderText("bei lokalen Servern meist leer")

    def _where(self, url):
        url = url.strip()
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
        if PRESETS[i][1]:
            self.url.setText(PRESETS[i][1])
        else:
            self.url.setFocus()

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
                                          "text": self.text.toPlainText().strip()}
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
    def load_models(self):
        self.fetch.setEnabled(False)
        restyle(self.status, "muted")
        self.status.setText("Frage den Server …")
        self.status.show()
        cfg, key = self.llm_cfg(), self.typed_key()

        def work():
            try:
                self.sig_models.emit(llm.list_models(cfg, key), "")
            except Exception as e:
                self.sig_models.emit([], str(e) or type(e).__name__)
        threading.Thread(target=work, daemon=True).start()

    def _models(self, models, error):
        self.fetch.setEnabled(True)
        if error:
            restyle(self.status, "bad")
            self.status.setText(error)
        else:
            current = self.model.currentText()
            self.model.clear()
            self.model.addItems(models)
            self.model.setEditText(current or (models[0] if models else ""))
            restyle(self.status, "ok")
            self.status.setText(f"Verbunden – {len(models)} Modelle gefunden." if models
                                else "Verbunden, aber der Server meldet keine Modelle.")

    def try_prompt(self):
        instruction = self.text.toPlainText().strip()
        if not instruction:
            return self.try_note.setText("Erst links einen Prompt wählen.")
        self.try_btn.setEnabled(False)
        self.try_note.setText("Modell arbeitet …")
        cfg, key, sample = self.llm_cfg(), self.typed_key(), self.sample.toPlainText()

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
            label("Deutsch ist das schnellste Modell. Das genauere deutsche Modell macht bei medizinischen Diktaten "
                  "weniger Fehler, braucht aber etwa doppelt so lange und beim ersten Wechsel einmalig 1 GB. "
                  "Mehrsprachig erkennt die gesprochene Sprache selbst, darunter Englisch, Französisch und "
                  "Spanisch (670 MB). Das medizinische Basiswörterbuch gilt für beide deutschen Modelle.",
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
        self.care_note = label("", "muted", wrap=True)
        self.check_button = button("Nach Updates suchen", self._check, name="primary")
        self.found = None                    # neuere Fassung bei GitHub, sobald gefunden
        self.body.addWidget(card(
            label("Aktualisieren und entfernen", "h2"),
            label(f"Installiert ist Fassung {__version__}. „Nach Updates suchen“ fragt bei GitHub nach der neuesten "
                  "Fassung und lädt auf Wunsch nur die Dateien, die sich geändert haben. Erreicht der Rechner GitHub "
                  "nicht (häufig in Kliniken): die ZIP-Datei an einem anderen Rechner laden und hier auswählen, das "
                  "kleine Paket genügt. Einstellungen, Verlauf, Wörterbuch und Sprachmodell bleiben, wie sie sind.",
                  "muted", wrap=True),
            hbox(self.check_button, button("Aus ZIP-Datei aktualisieren …", self._update),
                 button("LocalScribe entfernen …", self._remove), None),
            self.care_note))
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

    sig_unpacked = Signal(str, str)      # Ordner der neuen Fassung, Fehlertext
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

    def _care_ready(self) -> bool:
        if self.ctl.hub.busy():
            self.saved(self.care_note, "Erst die laufende Aufnahme oder Transkription beenden.", ok=False)
            return False
        return True

    def _check(self):
        """Erster Klick: bei GitHub nachfragen. Zweiter Klick (wenn es Neues gibt): laden und ersetzen."""
        if self.found:
            return self._online()
        restyle(self.care_note, "muted")
        self.care_note.setText("Frage bei GitHub nach der neuesten Fassung …")
        self.check_button.setEnabled(False)

        def work():
            try:
                self.sig_latest.emit(pflege.latest(), "")
            except Exception as e:
                self.sig_latest.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _latest(self, info, error):
        self.check_button.setEnabled(True)
        if error:
            return self.saved(self.care_note, error, ok=False)
        if not info["newer"]:
            restyle(self.care_note, "ok")
            return self.care_note.setText(f"Du hast die neueste Fassung ({__version__}).")
        if not pflege.program():
            return self.saved(self.care_note, f"Fassung {info['version']} ist da. Diese hier läuft aus dem Quelltext; "
                              "aktualisiert wird sie mit git.", ok=False)
        self.found = info
        self.check_button.setText(f"Auf {info['version']} aktualisieren")
        restyle(self.care_note, "ok")
        self.care_note.setText(f"Fassung {info['version']} ist da, du hast {__version__}. Ein Klick lädt nur, was sich "
                               "geändert hat, ersetzt den Programmordner und startet LocalScribe neu.")

    def _online(self):
        if not self._care_ready():
            return
        prog, info = pflege.program(), self.found
        self.check_button.setEnabled(False)
        restyle(self.care_note, "muted")
        self.care_note.setText("Vergleiche die installierten Dateien mit der neuen Fassung …")

        def work():
            try:
                new, _, _ = pflege.fetch(info, prog, progress=self.sig_loading.emit)
                self.sig_unpacked.emit(str(new), "")
            except Exception as e:
                self.sig_unpacked.emit("", str(e))
        threading.Thread(target=work, daemon=True).start()

    def _loading(self, done, total):
        self.care_note.setText(f"Lade die geänderten Dateien: {done / 1e6:.0f} von {total / 1e6:.0f} MB …")

    def _update(self):
        prog = pflege.program()
        if not prog:
            self.saved(self.care_note, "Diese Fassung läuft aus dem Quelltext; aktualisiert wird sie mit git.", ok=False)
            return
        if not self._care_ready():
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "ZIP-Datei der neuen Fassung", "", "LocalScribe-Paket (*.zip)")
        if not path:
            return
        restyle(self.care_note, "muted")
        self.care_note.setText("Die neue Fassung wird entpackt. Das dauert beim Komplettpaket ein bis zwei Minuten …")

        def work():
            try:
                self.sig_unpacked.emit(str(pflege.unpack(path, prog)), "")
            except Exception as e:
                self.sig_unpacked.emit("", str(e))
        threading.Thread(target=work, daemon=True).start()

    def _unpacked(self, new, error):
        self.check_button.setEnabled(True)
        if error:
            self.saved(self.care_note, error, ok=False)
            return
        from pathlib import Path
        pflege.swap(pflege.program(), Path(new))
        self.ctl.quit()

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


class SettingsTabs(QtWidgets.QWidget):
    """Einstellungen mit zwei Reitern: Allgemein und LLM."""

    def __init__(self, ctl):
        super().__init__()
        self.pages = [SettingsPage(ctl), LlmPage(ctl)]
        self.tabs = QtWidgets.QButtonGroup(self)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(30, 18, 30, 0)
        row.setSpacing(6)
        self.stack = QtWidgets.QStackedWidget()
        for i, name in enumerate(("Allgemein", "LLM")):
            b = QtWidgets.QPushButton(name, checkable=True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton:checked { color: #C6FF3D; border-color: #C6FF3D; }")
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
            ("Aufnahme", RecordPage(ctl)),
            ("Datei", FilePage(ctl)),
            ("Wörterbuch", MapPage(ctl, "Wörterbuch",
                                   "Wörter, die falsch erkannt werden, automatisch ersetzen. "
                                   "Groß- und Kleinschreibung spielt beim Erkennen keine Rolle.",
                                   "dictionary", ["Erkannt wird", "Ersetzen durch"], learn=True)),
            ("Stimmtraining", TrainPage(ctl)),
            ("Textbausteine", MapPage(ctl, "Textbausteine",
                                      "Ein gesprochenes Stichwort wird durch den hinterlegten Text ersetzt. "
                                      "Für einen Zeilenumbruch \\n schreiben.",
                                      "snippets", ["Stichwort", "Text"],
                                      starter=("Normalbefunde hinzufügen", NORMAL))),
            ("Visite & Übergabe", VisitPage(ctl)),
            ("Einstellungen", SettingsTabs(ctl)),
        ]
        self.buttons = QtWidgets.QButtonGroup(self)
        for i, (name, page) in enumerate(self.pages):
            b = QtWidgets.QPushButton(name.replace("&", "&&"), checkable=True)
            b.setCursor(Qt.PointingHandCursor)
            self.buttons.addButton(b, i)
            nav.addWidget(b)
            self.stack.addWidget(page)
        self.buttons.idClicked.connect(self.show_page)
        nav.addStretch(1)
        self.status = label("", "muted", wrap=True)
        nav.addWidget(self.status)
        self.loadbar = QtWidgets.QProgressBar(textVisible=False)
        self.loadbar.setRange(0, 1000)
        self.loadbar.hide()
        nav.addWidget(self.loadbar)

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
        right.addWidget(self.stack, 1)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side)
        lay.addLayout(right, 1)
        self.show_page(0)

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
        return any(getattr(page, "job", None) is not None and page.job.running for _, page in self.pages)

    def open(self):
        self.pages[self.stack.currentIndex()][1].refresh()
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        e.ignore()  # läuft im Infobereich weiter
        self.hide()
