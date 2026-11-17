"""Das App-Fenster: Verlauf, Wörterbuch, Textbausteine, KI-Nachbearbeitung, Einstellungen."""
import copy
import difflib
import html
import logging
import os
import re
import threading
import time

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QTimer, Signal

import secrets

from . import __version__, config, engine, fach, handy, llm, pflege, schutz, training, visite, wortschatz
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
            lay.addWidget(it[0], it[1])
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
        self.split.setToolTip("Für Gespräche mit mehreren Personen. Jede Äußerung bekommt einen Stimmabdruck, "
                              "ähnliche Stimmen werden zu einem Sprecher zusammengefasst. Läuft auf diesem Rechner.")
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
class VisitPage(Page):
    """Fall diktieren oder tippen, vom Sprachmodell auswerten lassen: Arztbrief-Entwurf, Sicherheitsnetz, Rückfragen."""
    sig_done = Signal(object, str, int)
    CSS = ("h3 { color: #C6FF3D; margin: 14px 0 4px 0; } p { margin: 0 0 6px 0; } a { color: #8A8A8A; text-decoration: none; }"
           " .warn { color: #FFB454; } .muted { color: #8A8A8A; }")
    PRIORITY = {"critical": "entscheidend", "high": "wichtig", "medium": "ergänzend"}

    def __init__(self, ctl):
        super().__init__("Visite & Übergabe",
                         "Experimenteller Modus für Benchmarking, Forschung und Lehre: Er zeigt, wie gut ein Sprachmodell "
                         "solche Entwürfe liefert. Kein Medizinprodukt; die Ausgaben sind keine Diagnose- oder "
                         "Therapieempfehlung und vor jeder Verwendung zu prüfen. Das Sprachmodell stellst du unter "
                         "KI-Nachbearbeitung ein, am besten eines im eigenen Haus (zum Beispiel über Ollama).", scroll=False)
        self.ctl = ctl
        self.store = visite.Store()
        self.case, self.result, self.copy = None, None, {}
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

        # Neuer Patient
        self.name = QtWidgets.QLineEdit(placeholderText="Fallbezeichnung, z. B. Zimmer 4 oder Kürzel (kein Klarname nötig)")
        self.text = QtWidgets.QPlainTextEdit(placeholderText="Hier klicken und diktieren (Tasten halten) oder tippen: "
                                             "Anamnese, Befund, Verlauf, Vormedikation, geplantes Vorgehen.")
        self.go = button("Auswerten", self._analyse, name="primary")
        self.note = label("", "muted", wrap=True)
        self.out = QtWidgets.QTextBrowser(openLinks=False)
        self.out.document().setDefaultStyleSheet(self.CSS)
        self.out.anchorClicked.connect(self._copy)
        self.out.setPlaceholderText("Nach „Auswerten“ stehen hier Arztbrief-Entwurf, Sicherheitsnetz, Rückfragen, "
                                    "Kodierung und Patienteninfo, jeweils zum Kopieren.")
        new = QtWidgets.QWidget()
        left = QtWidgets.QVBoxLayout()
        for w in (self.name, self.text):
            left.addWidget(w)
        left.addLayout(hbox(self.go, button("Neuer Fall", self._new), None))
        left.addWidget(self.note)
        split = QtWidgets.QHBoxLayout(new)
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(14)
        split.addLayout(left, 2)
        split.addWidget(self.out, 3)
        self.stack.addWidget(new)
        self.saver = QTimer(self, singleShot=True, interval=700)       # nichts geht verloren: jede Eingabe wird gesichert
        self.saver.timeout.connect(self._save)
        self.text.textChanged.connect(self.saver.start)
        self.name.textEdited.connect(lambda _: self.saver.start())

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
                                   button("In den Papierkorb", lambda: self._each(0, self.store.trash)), None))
            self.lists.append((search, items))
            self.stack.addWidget(w)
        self.tabs.idClicked.connect(self._tab)
        self.sig_done.connect(self._done)
        self._tab(0)

    def refresh(self):
        self._fill()

    def _tab(self, i):
        self.tabs.button(i).setChecked(True)
        self.stack.setCurrentIndex(i)
        self._fill()

    def _fill(self):
        for trash, (search, items) in enumerate(self.lists):
            items.clear()
            rows = self.store.rows(bool(trash), search.text())
            for case_id, name, text, created, _ in rows:
                first = " ".join((text or "").split())[:90]
                item = QtWidgets.QListWidgetItem(f"{time.strftime('%d.%m.%Y %H:%M', time.localtime(created))}   "
                                                 f"{name or 'ohne Bezeichnung'}   {first}")
                item.setData(Qt.UserRole, case_id)
                items.addItem(item)
            self.tabs.button(1 + trash).setText(("Fallliste", "Papierkorb")[trash] + (f" ({len(rows)})" if rows else ""))

    def _each(self, which, action):
        for item in self.lists[which][1].selectedItems() or ([self.lists[which][1].currentItem()] if self.lists[which][1].currentItem() else []):
            action(item.data(Qt.UserRole))
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
        if self.case is None and not self.text.toPlainText().strip() and not self.name.text().strip():
            return
        self.case = self.store.save(self.case, self.name.text().strip(), self.text.toPlainText())

    def _new(self):
        self.saver.stop()
        self._save()
        self.case, self.result = None, None
        for w in (self.name, self.text, self.out):
            w.blockSignals(True)
            w.clear()
            w.blockSignals(False)
        self.note.setText("")
        self._tab(0)

    def _open(self, case_id):
        self._new()
        row = self.store.get(case_id)
        if not row:
            return
        self.case = case_id
        self.name.setText(row[0] or "")
        self.text.blockSignals(True)
        self.text.setPlainText(row[1] or "")
        self.text.blockSignals(False)
        self._show(row[2])

    def _analyse(self):
        text = self.text.toPlainText().strip()
        if not text:
            return self.note.setText("Erst den Fall diktieren oder eintippen.")
        if not (self.ctl.cfg.get("llm") or {}).get("model"):
            restyle(self.note, "bad")
            return self.note.setText("Kein Sprachmodell eingestellt. Unter KI-Nachbearbeitung Server und Modell wählen.")
        self.saver.stop()
        self._save()
        self.go.setEnabled(False)
        restyle(self.note, "muted")
        self.note.setText("Das Sprachmodell wertet aus …")
        case, cfg = self.case, copy.deepcopy(self.ctl.cfg)

        def work():
            try:
                self.sig_done.emit(visite.analyse(cfg, text), "", case)
            except Exception as e:
                log.warning("Visite: Auswertung fehlgeschlagen: %s", type(e).__name__)
                self.sig_done.emit(None, str(e) or type(e).__name__, case)
        threading.Thread(target=work, daemon=True).start()

    def _done(self, result, error, case):
        self.go.setEnabled(True)
        if error:
            restyle(self.note, "bad")
            return self.note.setText(f"Das hat nicht geklappt: {error}")
        self.store.save(case, *self.store.get(case)[:2], result)
        if case == self.case:
            restyle(self.note, "ok")
            self.note.setText("Entwurf fertig. Bitte prüfen, bevor du etwas übernimmst.")
            self._show(result)
        self._fill()

    def _show(self, result):
        self.result, self.copy = result, {}
        if not result:
            return self.out.clear()
        esc = lambda t: html.escape(str(t or "")).replace("\n", "<br>")
        parts = []

        def block(key, title, body_html, plain):
            if plain.strip():
                self.copy[key] = plain
                parts.append(f"<h3>{title} &nbsp;<a href='{key}'>kopieren</a></h3>{body_html}")
        doc = result.get("documentation") or {}
        block("brief", "Arztbrief-Entwurf", "".join(f"<p><b>{t}:</b><br>{esc(doc.get(k))}</p>" for k, t in visite.SECTIONS
                                                    if str(doc.get(k) or "").strip()), visite.letter(result))
        alerts = [a for a in result.get("safetyAlerts") or [] if isinstance(a, dict)]
        block("netz", "Sicherheitsnetz", "".join(f"<p><span class='warn'><b>{esc(a.get('context'))}</b></span><br>{esc(a.get('suggestion'))}</p>"
                                                 for a in alerts), "\n".join(f"{a.get('context', '')}: {a.get('suggestion', '')}" for a in alerts))
        asks = [q for q in result.get("followUpQuestions") or [] if isinstance(q, dict)]
        block("fragen", "Gezielte Rückfragen", "".join(
            f"<p><b>{i}. {esc(q.get('question'))}</b> <span class='muted'>({self.PRIORITY.get(q.get('priority'), 'ergänzend')})</span>"
            f"<br><span class='muted'>{esc(q.get('rationale'))}</span></p>" for i, q in enumerate(asks, 1)),
            "\n".join(f"{i}. {q.get('question', '')}" for i, q in enumerate(asks, 1)))
        codes = [c for c in result.get("codes") or [] if isinstance(c, dict)]
        block("codes", "Kodierung (Vorschlag)", "<p>" + "<br>".join(f"<b>{esc(c.get('code'))}</b> {esc(c.get('description'))}" for c in codes) + "</p>",
              "\n".join(f"{c.get('code', '')} {c.get('description', '')}" for c in codes))
        info = result.get("patientHandout") or {}
        block("info", "Patienteninfo", f"<p><b>{esc(info.get('title'))}</b><br>{esc(info.get('content'))}</p>",
              f"{info.get('title', '')}\n{info.get('content', '')}" if info.get("content") else "")
        block("en", "Zusammenfassung (englisch)", f"<p>{esc(doc.get('case_summary_en'))}</p>", str(doc.get("case_summary_en") or ""))
        self.out.setHtml("".join(parts))

    def _copy(self, url):
        text = self.copy.get(url.toString())
        if text:
            QtGui.QGuiApplication.clipboard().setMimeData(private_mime(text))
            restyle(self.note, "ok")
            self.note.setText("Kopiert.")


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
        super().__init__("KI-Nachbearbeitung",
                         "Schickt das Transkript mit einem deiner Prompts an ein Sprachmodell und fügt "
                         "dessen Antwort ein. Funktioniert mit jedem Server, der die OpenAI-Schnittstelle "
                         "spricht – auf diesem Rechner oder bei einem Anbieter deiner Wahl.")
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
        self.hotkey = QtWidgets.QLineEdit(placeholderText="z. B. f8 oder ctrl+alt+g – leer = keine Taste")
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
                            "Ohne Namenserkennung greifen nur Regeln: Daten, Nummern, Anschriften und Namen hinter Anrede "
                            "oder Titel. Ein Name ohne Anrede rutscht durch.")

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
            self.hotkey.setText("+".join(p.get("hotkey") or []))
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
        self.hold = QtWidgets.QLineEdit()
        self.lock = QtWidgets.QLineEdit()
        self.paste = QtWidgets.QLineEdit()
        self.field = QtWidgets.QLineEdit()
        self.target = QtWidgets.QLineEdit()
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
            label("Mehrere Tasten mit + verbinden, zum Beispiel ctrl+win. Eine einzelne Taste wie ctrl startet "
                  "nach kurzem Halten; Strg+C, Strg+Klick und andere Kürzel funktionieren weiter wie gewohnt. "
                  "Esc bricht eine laufende Aufnahme ab.", "muted", wrap=True)))
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
        self.prompt = QtWidgets.QPlainTextEdit()
        self.prompt.setMinimumHeight(170)
        self.prompt_note = label("", "muted")
        self.body.addWidget(card(
            label("Visite & Übergabe: Anweisung an das Sprachmodell", "h2"),
            label("Bestimmt, was aus einem Fall erzeugt wird (Arztbrief-Entwurf, Sicherheitsnetz, Rückfragen, Kodierung, "
                  "Patienteninfo). Die Namen der Felder im JSON-Schema am Ende müssen bleiben, sonst kann LocalScribe das "
                  "Ergebnis nicht anzeigen.", "muted", wrap=True),
            self.prompt,
            hbox(button("Speichern", self._prompt_save, name="primary"),
                 button("Standard wiederherstellen", self._prompt_reset), None, self.prompt_note)))
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
        self.body.addWidget(card(
            label("Aktualisieren und entfernen", "h2"),
            label(f"Installiert ist Fassung {__version__}. Für ein Update die ZIP-Datei der neuen Fassung herunterladen "
                  "und hier auswählen; das kleine Paket genügt, das Sprachmodell bleibt erhalten. LocalScribe ersetzt "
                  "den Programmordner und startet neu. Einstellungen, Verlauf und Wörterbuch bleiben, wie sie sind.",
                  "muted", wrap=True),
            hbox(button("Aus ZIP-Datei aktualisieren …", self._update, name="primary"),
                 button("Neue Fassung suchen", lambda: QtGui.QDesktopServices.openUrl(
                     QtCore.QUrl("https://github.com/chunkyfire/LocalScribe/releases/latest"))),
                 button("LocalScribe entfernen …", self._remove), None),
            self.care_note))
        self.sig_unpacked.connect(self._unpacked)
        self.body.addStretch(1)

    sig_unpacked = Signal(str, str)      # Ordner der neuen Fassung, Fehlertext

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

    def _prompt_save(self):
        text = self.prompt.toPlainText().strip()
        self.ctl.cfg["visite_prompt"] = "" if text == visite.PROMPT.strip() else text
        self.ctl.apply_cfg()
        self.saved(self.prompt_note)

    def _prompt_reset(self):
        self.prompt.setPlainText(visite.PROMPT)
        self._prompt_save()

    def refresh(self):
        self.prompt.setPlainText(visite.prompt(self.ctl.cfg))
        cfg = self.ctl.cfg
        self.hold.setText("+".join(cfg["hotkey_hold"]))
        self.model.setCurrentIndex(max(0, self.model.findData(cfg.get("model_choice", "de"))))
        self.model_dir.setText(cfg.get("model_dir") or "")
        self.lock.setText(cfg.get("hotkey_lock") or "")
        self.paste.setText("+".join(cfg.get("hotkey_paste_last") or []))
        self.field.setText("+".join(cfg.get("hotkey_next_field") or []))
        self.target.setText("+".join(cfg.get("hotkey_target") or []))
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
        nav.addSpacing(18)

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
            ("KI-Nachbearbeitung", LlmPage(ctl)),
            ("Einstellungen", SettingsPage(ctl)),
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
