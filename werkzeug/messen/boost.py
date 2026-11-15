"""Wort-Boosting im Modell: Fachbegriffe bekommen beim Dekodieren einen kleinen Vorsprung.

Das Modell wählt Silbe für Silbe (genauer: Wortstück für Wortstück) das wahrscheinlichste. Liegt es
zwischen zwei Stücken knapp, entscheidet hier das Lexikon: Ein Stück, das das gerade entstehende Wort
zu einem Anfang eines Fachbegriffs macht, bekommt einen Zuschlag. So wird aus „Hydrala|cin“
„Hydrala|zin“, ohne dass später etwas ersetzt werden muss.

Sicherungen: Der Zuschlag wirkt nur, wenn das Modell ohnehin ein Stück ausgeben will (nie statt
einer Pause), nur unter seinen eigenen besten Kandidaten und erst ab einem Wortanfang von
MIN_PREFIX Buchstaben. Er kann also kein Wort erfinden, das das Modell nicht selbst erwogen hat.

Stand 0.9: gemessen, nicht in der App. An eigenen Diktaten ein Prozentpunkt weniger Wortfehler, an den
unabhängigen Aufnahmen 0,1 Punkte mehr (ERGEBNIS.md). Mit dem genauer gekürzten Modell lohnt es nicht.
"""
import numpy as np

MIN_PREFIX = 4       # kürzere Wortanfänge passen auf zu viele Alltagswörter
TOP = 8              # nur unter den besten Kandidaten des Modells wird umsortiert


class Booster:
    def __init__(self, pieces, terms, weight=2.0, blank=None, ramp=3.0):
        """pieces: Wortstücke des Modells in der Reihenfolge ihrer Nummern (▁ = Wortanfang).
        terms: Fachbegriffe. weight: Zuschlag auf die Bewertung des Modells."""
        self.pieces = [p.replace("▁", " ") for p in pieces]
        self.weight = weight
        self.ramp = ramp
        self.blank = len(self.pieces) - 1 if blank is None else blank
        self.prefixes = set()
        self.terms = set()
        for term in terms:
            low = term.lower()
            self.terms.add(low)
            for n in range(MIN_PREFIX, len(low) + 1):
                self.prefixes.add(low[:n])
        self._seen, self._word = 0, ""

    def _partial(self, tokens) -> str:
        """Das Wort, das gerade entsteht (alles seit dem letzten Wortanfang), klein geschrieben."""
        if len(tokens) < self._seen:
            self._seen, self._word = 0, ""
        for t in tokens[self._seen:]:
            piece = self.pieces[t]
            self._word = piece[1:] if piece.startswith(" ") else self._word + piece
        self._seen = len(tokens)
        return self._word.lower()

    def adjust(self, tokens, logits):
        """Bewertungen des Modells für den nächsten Schritt anpassen (verändert logits nicht)."""
        vocab = logits[: len(self.pieces)]
        best = int(vocab.argmax())
        if best == self.blank or not self.weight:
            return logits
        word = self._partial(tokens)
        top = np.argpartition(vocab, -TOP)[-TOP:]
        out = None
        for i in top:
            if i == self.blank:
                continue
            piece = self.pieces[i]
            cand = (piece[1:] if piece.startswith(" ") else word + piece).lower()
            if " " in cand or len(cand) < MIN_PREFIX or cand not in self.prefixes:
                continue
            if out is None:
                out = logits.copy()
            # je länger der passende Wortanfang, desto sicherer ist der Begriff gemeint
            grow = min(1.0, (len(cand) - MIN_PREFIX + 1) / self.ramp)
            out[i] += self.weight * grow * (1.5 if cand in self.terms else 1.0)
        return logits if out is None else out


def install(model, terms, weight=2.0, ramp=3.0):
    """Hängt das Boosting in ein onnx-asr-Transducer-Modell ein. Gibt den Booster zurück (oder None)."""
    asr = model
    while not hasattr(asr, "_decode") and hasattr(asr, "asr"):
        asr = asr.asr
    if not hasattr(asr, "_decode") or not hasattr(asr, "_vocab"):
        return None
    vocab = asr._vocab
    pieces = [vocab[i] for i in range(len(vocab))]
    booster = Booster(pieces, terms, weight, blank=getattr(asr, "_blank_idx", None), ramp=ramp)
    inner = getattr(asr, "_decode_plain", None) or asr._decode
    asr._decode_plain = inner

    def decode(prev_tokens, prev_state, encoder_out):
        logits, step, state = inner(prev_tokens, prev_state, encoder_out)
        return booster.adjust(prev_tokens, logits), step, state
    asr._decode = decode
    return booster
