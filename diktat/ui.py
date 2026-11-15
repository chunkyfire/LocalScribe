"""Statusleiste, Tray-Symbol und Verlaufsspeicher."""
import sqlite3
import time

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QTimer

ACCENT = QtGui.QColor("#C6FF3D")
INK = QtGui.QColor(11, 11, 11, 238)
EDGE = QtGui.QColor(58, 58, 58)


class Store:
    """Verlauf in SQLite; wird nur aus dem Hauptthread benutzt."""

    def __init__(self, path):
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS verlauf (id INTEGER PRIMARY KEY, zeit REAL, text TEXT,"
                        " sekunden REAL, latenz REAL, fenster TEXT)")
        have = {row[1] for row in self.db.execute("PRAGMA table_info(verlauf)")}
        for col, kind in (("roh", "TEXT"), ("prompt", "TEXT"), ("woerter", "INTEGER")):
            if col not in have:
                self.db.execute(f"ALTER TABLE verlauf ADD COLUMN {col} {kind}")
        for ident, text in self.db.execute("SELECT id, text FROM verlauf WHERE woerter IS NULL").fetchall():
            self.db.execute("UPDATE verlauf SET woerter=? WHERE id=?", (len(text.split()), ident))
        self.db.commit()

    def add(self, text, seconds, latency, window, raw="", prompt=""):
        self.db.execute("INSERT INTO verlauf (zeit, text, sekunden, latenz, fenster, roh, prompt, woerter)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (time.time(), text, seconds, latency, window, raw, prompt, len(text.split())))
        self.db.commit()

    def recent(self, query="", limit=200):
        return self.db.execute("SELECT id, zeit, text, fenster, prompt FROM verlauf WHERE text LIKE ?"
                               " ORDER BY id DESC LIMIT ?", (f"%{query}%", limit)).fetchall()

    def last(self):
        row = self.db.execute("SELECT text FROM verlauf ORDER BY id DESC LIMIT 1").fetchone()
        return row[0] if row else ""

    def delete(self, ident):
        self.db.execute("DELETE FROM verlauf WHERE id=?", (ident,))
        self.db.commit()

    def clear(self):
        self.db.execute("DELETE FROM verlauf")
        self.db.commit()

    def prune(self, days):
        if days and days > 0:
            self.db.execute("DELETE FROM verlauf WHERE zeit < ?", (time.time() - days * 86400,))
            self.db.commit()

    def stats(self):
        """(Wörter gesamt, Wörter pro Minute, Wörter heute)"""
        total, spoken_words, spoken_secs = self.db.execute(
            "SELECT COALESCE(SUM(woerter),0), COALESCE(SUM(CASE WHEN sekunden>0 THEN woerter END),0),"
            " COALESCE(SUM(sekunden),0) FROM verlauf").fetchone()
        midnight = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
        today = self.db.execute("SELECT COALESCE(SUM(woerter),0) FROM verlauf WHERE zeit >= ?",
                                (midnight,)).fetchone()[0]
        wpm = round(spoken_words / spoken_secs * 60) if spoken_secs > 5 else 0
        return total, wpm, today


class Overlay(QtWidgets.QWidget):
    """Kleine Statusleiste unten in der Bildschirmmitte; nimmt nie den Fokus."""
    BARS = 26

    def __init__(self, recorder):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.recorder = recorder
        self.mode, self.text, self.phase, self.token = "idle", "", 0, 0
        self.levels = [0.0] * self.BARS
        self.timer = QTimer(self, interval=33, timeout=self._tick)
        self.resize(460, 44)
        self.place()
        self.show()

    def place(self):
        g = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        self.move(g.center().x() - self.width() // 2, g.bottom() - self.height() - 14)

    def set_mode(self, mode, text=""):
        self.token += 1
        if mode in ("recording", "locked") and self.mode not in ("recording", "locked"):
            self.levels = [0.0] * self.BARS
        self.mode, self.text = mode, text
        if mode == "idle":
            self.timer.stop()
        else:
            self.place()
            self.timer.start()
        self.update()

    def flash(self, text, ms=2200):
        self.set_mode("message", text)
        token = self.token
        QTimer.singleShot(ms, lambda: self.set_mode("idle") if self.token == token else None)

    def _tick(self):
        self.phase += 1
        if self.mode in ("recording", "locked"):
            self.levels.pop(0)
            self.levels.append(min(1.0, (self.recorder.level * 14) ** 0.6))
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        cx, bottom = self.width() / 2, self.height() - 2
        if self.mode == "idle":
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 60), 1))
            p.setBrush(QtGui.QColor(11, 11, 11, 170))
            p.drawRoundedRect(QtCore.QRectF(cx - 22, bottom - 8, 44, 8), 4, 4)
            return
        font = QtGui.QFont("Segoe UI", 9)
        font.setWeight(QtGui.QFont.DemiBold)
        p.setFont(font)
        if self.mode == "message":
            w = min(self.width() - 4, p.fontMetrics().horizontalAdvance(self.text) + 36)
        else:
            w = {"recording": 150, "locked": 176, "processing": 96}[self.mode]
        h = 34
        r = QtCore.QRectF(cx - w / 2, bottom - h, w, h)
        p.setPen(QtGui.QPen(EDGE, 1))
        p.setBrush(INK)
        p.drawRoundedRect(r, h / 2, h / 2)
        cy = r.center().y()
        if self.mode in ("recording", "locked"):
            left = r.left() + 22
            if self.mode == "locked":  # Punkt = Freihand aktiv
                p.setPen(Qt.NoPen)
                p.setBrush(ACCENT)
                p.drawEllipse(QtCore.QPointF(r.left() + 20, cy), 4, 4)
                left += 22
            step = (r.right() - 22 - left) / self.BARS
            p.setPen(Qt.NoPen)
            p.setBrush(ACCENT)
            for i, lv in enumerate(self.levels):
                bh = 3 + lv * 20
                p.drawRoundedRect(QtCore.QRectF(left + i * step, cy - bh / 2, max(2.0, step - 2), bh), 1.2, 1.2)
        elif self.mode == "processing":
            p.setPen(Qt.NoPen)
            for i in range(3):
                c = QtGui.QColor(ACCENT)
                c.setAlpha(90 + int(165 * (0.5 + 0.5 * np.sin(self.phase * 0.22 - i * 0.9))))
                p.setBrush(c)
                p.drawEllipse(QtCore.QPointF(cx + (i - 1) * 14, cy), 3.5, 3.5)
        else:
            p.setPen(QtGui.QColor(232, 232, 232))
            p.drawText(r, Qt.AlignCenter, self.text)


def make_pixmap(size=64) -> QtGui.QPixmap:
    pm = QtGui.QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.scale(size / 64, size / 64)
    p.setPen(Qt.NoPen)
    p.setBrush(QtGui.QColor(11, 11, 11))
    p.drawRoundedRect(2, 2, 60, 60, 14, 14)
    p.setBrush(ACCENT)
    for i, bh in enumerate((14, 30, 40, 22, 12)):
        p.drawRoundedRect(QtCore.QRectF(12 + i * 8.6, 32 - bh / 2, 5, bh), 2.5, 2.5)
    p.end()
    return pm


def make_icon() -> QtGui.QIcon:
    icon = QtGui.QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        icon.addPixmap(make_pixmap(size))
    return icon
