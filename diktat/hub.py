"""Das App-Fenster: Verlauf, Wörterbuch, Textbausteine, KI-Nachbearbeitung, Einstellungen."""
import copy
import os
import threading
import time

from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import Qt, QTimer, Signal

from . import llm
from .longform import LongJob
from .ui import make_icon, make_pixmap

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
    def __init__(self, page, ident, zeit, text, window, prompt):
        super().__init__(objectName="row")
        self.page, self.ident, self.text = page, ident, text
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Klicken kopiert" + (f"  ·  diktiert in: {window}" if window else ""))
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
            QtGui.QGuiApplication.clipboard().setText(self.text)
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
        for ident, zeit, text, window, prompt in rows:
            day = self._day(zeit)
            if day != last_day:
                self.list.addWidget(label(day, "day"))
                last_day = day
            self.list.addWidget(Row(self, ident, zeit, text, window, prompt))
        if not rows:
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
        self.text.setReadOnly(busy)
        has = bool(self.text.toPlainText().strip())
        for b in (self.copy, self.save, self.ki):
            b.setEnabled(has and not busy)

    def set_text(self, text):
        self.text.setPlainText(text)
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())

    def _copy(self):
        QtGui.QGuiApplication.clipboard().setText(self.text.toPlainText())
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

    def __init__(self, ctl, title, subtitle, source):
        super().__init__(title, subtitle, scroll=False)
        self.ctl, self.source = ctl, source
        self.job = LongJob(ctl)
        self.job.part.connect(self.on_part)
        self.job.finished.connect(self.on_finished)
        self.started = 0.0
        self.out = Transcript(ctl)

    def refresh(self):
        self.out.refresh()

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
            self.ctl.store.add(text, seconds, time.time() - self.started, self.source)


class RecordPage(LongPage):
    def __init__(self, ctl):
        super().__init__(ctl, "Aufnahme",
                         "Einmal drücken startet, noch einmal drücken beendet – auch nach einer Stunde. "
                         "Der Text entsteht schon während du sprichst und bleibt auf diesem Rechner.",
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
        self.body.addWidget(card(hbox(self.btn, (self._wrap(col), 1), spacing=22)))
        self.body.addWidget(self.out, 1)
        self.recording = False
        self.tick = QTimer(self, interval=250, timeout=self._tick)

    @staticmethod
    def _wrap(layout):
        w = QtWidgets.QWidget()
        layout.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        return w

    def info(self, text):
        self.state.setText(text)

    def toggle(self):
        if self.recording:
            self.recording = False
            self.tick.stop()
            self.job.stop_recording()
            self.btn.setEnabled(False)
            restyle(self.btn, "rec")
            self.btn.setText("Start")
            self.state.setText("Schreibe den Rest fertig …")
            return
        if self.job.running or not self.model_ready():
            return
        try:
            self.job.start_recording()
        except Exception as e:
            return self.info(f"Mikrofon nicht verfügbar: {e}")
        self.recording, self.started = True, time.time()
        self.out.set_text("")
        self.out.set_busy(True)
        restyle(self.btn, "recOn")
        self.btn.setText("Stopp")
        self.state.setText("Nimmt auf …")
        self.tick.start()

    def _tick(self):
        self.clock.setText(clock(time.time() - self.started))
        loud = self.job.level > 0.01
        self.state.setText("Nimmt auf …" if loud or time.time() - self.started < 3
                           else "Nimmt auf – gerade ist nichts zu hören")

    def on_finished(self, text, seconds, error):
        super().on_finished(text, seconds, error)
        self.btn.setEnabled(True)
        if error:
            keep = f" Die Tonaufnahme liegt unter {self.job.wav_path}." if self.job.wav_path else ""
            self.state.setText(f"Fehler: {error}.{keep}")
        elif text.strip():
            self.state.setText(f"Fertig – {clock(seconds)} aufgenommen, {len(text.split())} Wörter. "
                               "Der Text steht auch im Verlauf.")
        else:
            self.state.setText("Kein Text erkannt.")


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
        if error:
            self.state.setText(f"Das hat nicht geklappt: {error}")
        elif text.strip():
            self.state.setText(f"Fertig – {clock(seconds)} Audio in {clock(took)}, {len(text.split())} Wörter. "
                               "Der Text steht auch im Verlauf.")
        else:
            self.state.setText("Kein Text erkannt.")


# ---------------------------------------------------------------- Wörterbuch / Textbausteine
class MapPage(Page):
    """Tabelle für ein Wörterbuch in der Konfiguration (Schlüssel -> Wert)."""

    def __init__(self, ctl, title, subtitle, key, headers):
        super().__init__(title, subtitle, scroll=False)
        self.ctl, self.key, self.loading = ctl, key, False
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
        self.body.addWidget(self.table, 1)
        self.body.addLayout(hbox(button("Hinzufügen", self.add, "primary"),
                                 button("Entfernen", self.remove), None))

    def refresh(self):
        self.loading = True
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


# ---------------------------------------------------------------- KI
class LlmPage(Page):
    sig_models = Signal(object, str)
    sig_test = Signal(str, str, float)

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
        self.enabled = QtWidgets.QCheckBox("KI-Nachbearbeitung einschalten")
        self.preset = QtWidgets.QComboBox()
        for name, _ in PRESETS:
            self.preset.addItem(name)
        self.preset.activated.connect(self._preset)
        self.url = QtWidgets.QLineEdit(placeholderText="https://…/v1")
        self.url.textEdited.connect(lambda: self.preset.setCurrentIndex(len(PRESETS) - 1))
        self.key = QtWidgets.QLineEdit()
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.model = QtWidgets.QComboBox(editable=True)
        self.model.lineEdit().setPlaceholderText("Modellname")
        self.status = label("", "muted", wrap=True)
        self.status.hide()
        self.fetch = button("Modelle abrufen", self.load_models)
        self.body.addWidget(card(
            self.enabled,
            form(("Server", hbox(self.preset, (self.url, 1))),
                 ("API-Schlüssel", hbox((self.key, 1), button("Entfernen", self.drop_key, "ghost"))),
                 ("Modell", hbox((self.model, 1), self.fetch))),
            self.status))

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

    @staticmethod
    def _wrap(layout):
        w = QtWidgets.QWidget()
        layout.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        return w

    # ----- Laden / Speichern
    def refresh(self):
        cfg = self.ctl.cfg
        l = cfg["llm"]
        self.enabled.setChecked(bool(l.get("enabled")))
        self.url.setText(l.get("base_url") or "")
        urls = [u for _, u in PRESETS]
        self.preset.setCurrentIndex(urls.index(self.url.text()) if self.url.text() in urls[:-1] else len(urls) - 1)
        self.key.clear()
        self.key.setPlaceholderText("gespeichert – zum Ändern neu eingeben" if llm.get_key()
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
                 model=self.model.currentText().strip(), auto_prompt=self.auto.currentData() or "")
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
                llm.set_key(self.typed_key())
            except Exception as e:
                return self.saved(self.note, f"Schlüssel nicht speicherbar: {e}", ok=False)
        self.ctl.cfg["llm"] = self.llm_cfg()
        self.ctl.cfg["prompts"] = copy.deepcopy(self.prompts)
        self.ctl.apply_cfg()
        selected = self.current
        self.refresh()
        self.list.setCurrentRow(selected)
        self.saved(self.note)

    def drop_key(self):
        llm.set_key("")
        self.key.clear()
        self.key.setPlaceholderText("bei lokalen Servern meist leer")

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
        self.mic = QtWidgets.QComboBox()
        self.sounds = QtWidgets.QCheckBox("Töne bei Start und Ende der Aufnahme")
        self.clip = QtWidgets.QCheckBox("Zwischenablage nach dem Einfügen wiederherstellen")
        self.auto = QtWidgets.QCheckBox("Mit Windows starten")
        self.days = QtWidgets.QSpinBox(minimum=0, maximum=3650, suffix=" Tage", specialValueText="nie löschen")
        self.days.setFixedWidth(150)
        self.body.addWidget(card(
            label("Tasten", "h2"),
            form(("Diktieren (halten)", self.hold), ("Freihand (dazu drücken)", self.lock),
                 ("Letzten Text einfügen", self.paste)),
            label("Mehrere Tasten mit + verbinden, zum Beispiel ctrl+win. "
                  "Esc bricht eine laufende Aufnahme ab.", "muted", wrap=True)))
        self.body.addWidget(card(label("Aufnahme", "h2"), form(("Mikrofon", self.mic)),
                                 self.sounds, self.clip))
        self.body.addWidget(card(label("Verlauf und Start", "h2"),
                                 form(("Einträge löschen nach", hbox(self.days, None))), self.auto,
                                 hbox(button("Verknüpfungen auf Desktop und im Startmenü anlegen", self.shortcuts),
                                      None)))
        self.body.addStretch(1)

    def refresh(self):
        cfg = self.ctl.cfg
        self.hold.setText("+".join(cfg["hotkey_hold"]))
        self.lock.setText(cfg.get("hotkey_lock") or "")
        self.paste.setText("+".join(cfg.get("hotkey_paste_last") or []))
        self.mic.clear()
        self.mic.addItem("Standardgerät", None)
        for name in self.ctl.input_devices():
            self.mic.addItem(name, name)
        self.mic.setCurrentIndex(max(0, self.mic.findData(cfg.get("microphone"))))
        self.sounds.setChecked(bool(cfg.get("sounds")))
        self.clip.setChecked(bool(cfg.get("restore_clipboard", True)))
        self.days.setValue(int(cfg.get("history_days") or 0))
        self.auto.setChecked(self.ctl.autostart_enabled())

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
        if not hold or lock is None or paste is None or len(lock) > 1:
            return self.saved(self.note, "Eine Taste ist unbekannt oder das Diktier-Kürzel fehlt.", ok=False)
        self.ctl.cfg.update(hotkey_hold=hold, hotkey_lock=lock[0] if lock else "", hotkey_paste_last=paste,
                            microphone=self.mic.currentData(), sounds=self.sounds.isChecked(),
                            restore_clipboard=self.clip.isChecked(), history_days=self.days.value())
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
                                   "dictionary", ["Erkannt wird", "Ersetzen durch"])),
            ("Textbausteine", MapPage(ctl, "Textbausteine",
                                      "Ein gesprochenes Stichwort wird durch den hinterlegten Text ersetzt. "
                                      "Für einen Zeilenumbruch \\n schreiben.",
                                      "snippets", ["Stichwort", "Text"])),
            ("KI-Nachbearbeitung", LlmPage(ctl)),
            ("Einstellungen", SettingsPage(ctl)),
        ]
        self.buttons = QtWidgets.QButtonGroup(self)
        for i, (name, page) in enumerate(self.pages):
            b = QtWidgets.QPushButton(name, checkable=True)
            b.setCursor(Qt.PointingHandCursor)
            self.buttons.addButton(b, i)
            nav.addWidget(b)
            self.stack.addWidget(page)
        self.buttons.idClicked.connect(self.show_page)
        nav.addStretch(1)
        self.status = label("", "muted", wrap=True)
        nav.addWidget(self.status)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side)
        lay.addWidget(self.stack, 1)
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

    def open(self):
        self.pages[self.stack.currentIndex()][1].refresh()
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        e.ignore()  # läuft im Infobereich weiter
        self.hide()
