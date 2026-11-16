"""Sprungmarken: Platzhalter in eingefügtem Text nacheinander ansteuern.

Ein Textbaustein kann Marken in eckigen Klammern enthalten: „Anamnese: [ ] Befund: [ ]“. Nach dem Einfügen
steht der Cursor am Ende. Die Taste „Nächstes Feld“ bewegt ihn zur nächsten Marke und löscht sie, sodass man
dort weiterdiktiert. Gerechnet wird in Zeichen ab der Stelle, an der der Cursor zuletzt stand; wer zwischendurch
mit der Maus woanders hinklickt, bringt die Rechnung durcheinander.
"""
import re

MARK = re.compile(r"\[[^\[\]\n]{0,40}\]|_{3,}")     # [ ], [Befund] oder ___


class Fields:
    def __init__(self):
        self.marks, self.caret = [], 0

    def pasted(self, text: str):
        """Nach jedem Einfügen aufrufen. Text mit Marken beginnt eine neue Runde; Text ohne Marken (ein Diktat
        in ein Feld) lässt die laufende Runde unberührt: Der Cursor steht danach dort, wo die Marke endete."""
        found = [(m.start(), m.end()) for m in MARK.finditer(text)]
        if found:
            self.marks, self.caret = found, len(text.replace("\r\n", "\n"))
        return len(found)

    def active(self) -> bool:
        return bool(self.marks)

    def next(self):
        """(Schritte, Länge): Schritte nach rechts (negativ: nach links) bis zur Marke, dann so viele Zeichen löschen.
        None, wenn keine Marke mehr offen ist."""
        if not self.marks:
            return None
        start, end = self.marks.pop(0)
        move = start - self.caret
        self.caret = end
        return move, end - start
