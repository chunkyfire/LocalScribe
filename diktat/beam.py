"""Dekodieren mit mehreren Kandidaten und Wortschatz-Bonus.

Das Modell schreibt Wortstück für Wortstück. Beim einfachen Dekodieren zählt an jeder Stelle nur das
wahrscheinlichste Stück; ein früher Irrtum („Ami“ + „no“ als zwei Wörter statt „Aminophenazon“) ist dann nicht
mehr zu retten, und die Nachbearbeitung findet aus den Trümmern oft nicht zum Begriff zurück. Hier laufen mehrere
Kandidaten nebeneinander her. Ein Kandidat, dessen entstehendes Wort der Anfang eines Begriffs aus dem Wortschatz
ist, bekommt je Wortstück einen Bonus. Wird doch kein Begriff daraus, wird der Bonus wieder abgezogen; er bleibt
nur, wenn am Wortende ein ganzer Begriff dasteht (auch gebeugt). Der
Wortschatz kann also kein Wort durchdrücken, das dem Ton deutlich widerspricht; er entscheidet zwischen ähnlich
klingenden Lesarten.

Gemessen an neun echten ärztlichen Diktaten (Corti Med-Dictate, werkzeug/messen/ERGEBNIS.md): Stehen die
Fachwörter im Wortschatz, sinkt die Wortfehlerrate von 14,2 % (Wortschatz nur in der Nachbearbeitung) auf 10,8 %.
Ohne passenden Wortschatz bringt das Verfahren nichts; ein sehr großes allgemeines Lexikon schadet sogar. Deshalb
gilt der Bonus nur für die Kernbegriffe und den eigenen Wortschatz.
"""
import numpy as np

MIN_WORD = 4        # kürzere Wörter passen auf zu viele Alltagswörter
GAMMA = 2.3         # eine Pause kommt nur infrage, wenn das Modell sie selbst ernsthaft erwägt
ENDINGS = ("e", "en", "er", "es", "em", "n", "s", "ern", "nen", "se", "sen")


class Bias:
    def __init__(self, vocab, terms, weight=2.0):
        """vocab: Nummer -> Wortstück (Leerzeichen am Anfang = Wortanfang). terms: Begriffe des Wortschatzes."""
        self.pieces = vocab
        self.weight = weight
        self.terms, self.prefixes = set(), set()
        for term in terms:
            for word in term.lower().replace("-", " ").split():
                word = word.strip(".,;:()[]\"'")
                if len(word) < MIN_WORD or not word[0].isalpha():
                    continue
                self.terms.add(word)
                for n in range(1, len(word) + 1):
                    self.prefixes.add(word[:n])
        # Zustand eines Kandidaten: Wort bisher, Beginn des laufenden Wortteils (-1: wird kein Begriff mehr),
        # Zahl der Wortstücke, gutgeschriebener Bonus
        self.start = ("", 0, 0, 0.0)

    def _term(self, word):
        if word in self.terms:
            return True
        return any((word.endswith(e) and word[:-len(e)] in self.terms) or word + e in self.terms for e in ENDINGS)

    def step(self, st, token):
        """Ein Wortstück anhängen. Gibt (neuer Zustand, Änderung der Bewertung) zurück."""
        word, seg0, ntok, pend = st
        piece = self.pieces[token]
        first = piece.strip()[:1]
        delta = 0.0
        if piece.startswith(" ") or not first.isalpha():
            delta = self.close(st)
            if not first.isalpha():
                return self.start, delta
            word, seg0, ntok, pend = "", 0, 0, 0.0
            piece = piece.strip()
        if seg0 < 0:
            return (word, -1, ntok, 0.0), delta
        low = piece.lower()
        new = word + low
        ntok += 1
        seg = new[seg0:]
        if not seg0 and seg in self.prefixes:                          # Anfang eines Begriffs: Bonus je Wortstück
            target = self.weight * ntok if len(new) >= MIN_WORD else 0.0
            return (new, 0, ntok, target), delta + target - pend
        if seg in self.prefixes or self._term(seg):                    # gebeugte Form: Bonus bleibt stehen
            return (new, seg0, ntok, pend), delta
        return (new, -1, ntok, 0.0), delta - pend

    def close(self, st):
        """Wortende: Der Bonus bleibt nur, wenn ein ganzer Begriff dasteht."""
        word, seg0, ntok, pend = st
        if seg0 >= 0 and len(word) >= MIN_WORD and self._term(word[seg0:]):
            return 0.0
        return -pend


class Hyp:
    __slots__ = ("tokens", "times", "state", "score", "t", "emitted", "st")

    def __init__(self, tokens, times, state, score, t, emitted, st):
        self.tokens, self.times, self.state, self.score = tokens, times, state, score
        self.t, self.emitted, self.st = t, emitted, st


def _log_softmax(x):
    m = x.max(axis=-1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=-1, keepdims=True))


def decode(asr, enc, beam=8, bias=None, nbest=1):
    """enc: (T, Breite) Ausgabe des Encoders für ein Stück Ton. Gibt die besten Kandidaten zurück:
    Liste aus (Wortstück-Nummern, Zeitpunkte, Bewertung), beste zuerst."""
    T = enc.shape[0]
    if T == 0:
        return [([], [], 0.0)]
    blank, V = asr._blank_idx, asr._vocab_size
    max_sym = asr._max_tokens_per_step
    s1, s2 = asr._create_state()
    hyps = [Hyp((), (), (s1[:, 0], s2[:, 0]), 0.0, 0, 0, bias.start if bias else None)]
    done = []
    run = asr._decoder_joint.run
    while hyps:
        tmin = min(h.t for h in hyps)
        active = [h for h in hyps if h.t == tmin]
        rest = [h for h in hyps if h.t != tmin]
        out, a, b = run(["outputs", "output_states_1", "output_states_2"], {
            "encoder_outputs": np.repeat(enc[tmin][None, :, None], len(active), axis=0),
            "targets": np.array([[h.tokens[-1] if h.tokens else blank] for h in active], dtype=np.int32),
            "target_length": np.ones(len(active), dtype=np.int32),
            "input_states_1": np.stack([h.state[0] for h in active], axis=1),
            "input_states_2": np.stack([h.state[1] for h in active], axis=1)})
        out = out.reshape(len(active), -1)
        lp = _log_softmax(out[:, :V])
        new = []
        for i, h in enumerate(active):
            d = int(out[i, V:].argmax())                # wie weit es im Ton weitergeht, sagt das Modell selbst
            if lp[i, blank] >= lp[i].max() - GAMMA or h.emitted >= max_sym:
                new.append(Hyp(h.tokens, h.times, h.state, h.score + float(lp[i, blank]), h.t + max(d, 1), 0, h.st))
            if h.emitted >= max_sym:
                continue
            state = (a[:, i], b[:, i])
            for tok in np.argpartition(lp[i], -(beam + 1))[-(beam + 1):]:
                tok = int(tok)
                if tok == blank:
                    continue
                score, st = h.score + float(lp[i, tok]), h.st
                if bias is not None:
                    st, delta = bias.step(st, tok)
                    score += delta
                new.append(Hyp(h.tokens + (tok,), h.times + (h.t,), state, score, h.t + d,
                               h.emitted + 1 if d == 0 else 0, st))
        # gleiche Texte am selben Zeitpunkt zusammenlegen, dann die besten behalten. Fertige Kandidaten
        # (am Ende des Tons angekommen) bleiben im Rennen und belegen ihren Platz.
        best = {}
        for h in rest + new + done:
            k = (h.tokens, min(h.t, T))
            if k not in best or h.score > best[k].score:
                best[k] = h
        hyps, done = [], []
        for h in sorted(best.values(), key=lambda h: h.score, reverse=True)[:beam]:
            if h.t >= T:
                if bias is not None and h.st is not bias.start:
                    h.score += bias.close(h.st)
                    h.st = bias.start
                done.append(h)
            else:
                hyps.append(h)
    done.sort(key=lambda h: h.score, reverse=True)
    return [(list(h.tokens), list(h.times), h.score) for h in done[:nbest]]


def _inner(model):
    asr = model
    while not hasattr(asr, "_decoding") and hasattr(asr, "asr"):
        asr = asr.asr
    return asr if hasattr(asr, "_decoder_joint") and hasattr(asr, "_decode_tokens") else None


def install(model, terms, beam=8, weight=2.0):
    """Hängt das Verfahren in ein onnx-asr-Modell ein; ohne Begriffe (oder beam < 2) gilt wieder das einfache
    Dekodieren. Gibt True zurück, wenn es aktiv ist."""
    asr = _inner(model)
    if asr is None:
        return False
    plain = getattr(asr, "_decoding_plain", None) or asr._decoding
    asr._decoding_plain = plain
    if not terms or beam < 2:
        asr._decoding = plain
        return False
    bias = Bias(asr._vocab, terms, weight)

    def words(tokens):
        return len(asr._decode_tokens(tokens, None, None).text.split())

    def decoding(encoder_out, encoder_out_lens, /, **kwargs):
        simple = list(plain(encoder_out, encoder_out_lens, **kwargs))
        for e, n, (tokens, times, logprobs) in zip(encoder_out, encoder_out_lens, simple):
            found, at, _ = decode(asr, e[: int(n)], beam, bias)[0]
            # Die Suche überspringt selten eine unsichere Passage ganz: dann gilt die einfache Lesart.
            if kwargs.get("need_logprobs") or words(found) < words(list(tokens)) - 2:
                yield tokens, times, logprobs
            else:
                yield found, at, None
    asr._decoding = decoding
    return True
