"""Segmentação PCM mono int16 em memória; nenhum áudio é persistido."""
from array import array


def has_voice(audio):
    samples = array('h', audio)
    # shortcut: limiar fixo de energia; calibrar com corpus de headsets antes de trocar por VAD.
    return bool(samples) and sum(value * value for value in samples) / len(samples) >= 300 ** 2


class Capture:
    def __init__(self, samplerate):
        self.preroll_bytes = int(samplerate * .5) * 2
        self.tail_bytes = int(samplerate * .8) * 2
        self.maximum_bytes = int(samplerate * 15) * 2
        self.reset()

    def reset(self):
        self.before = bytearray()
        self.audio = bytearray()
        self.silence = 0
        self.exceeded = False
        self.discarding = False

    def feed(self, audio):
        voiced = has_voice(audio)
        if self.discarding:
            self.silence = 0 if voiced else self.silence + len(audio)
            if self.silence >= self.tail_bytes:
                self.reset()
            return None
        if not self.audio:
            if not voiced:
                self.before.extend(audio)
                del self.before[:-self.preroll_bytes]
                return None
            self.audio.extend(self.before)
            self.before.clear()
        self.audio.extend(audio)
        self.silence = 0 if voiced else self.silence + len(audio)
        if len(self.audio) >= self.maximum_bytes:
            self.audio.clear()
            self.exceeded = True
            self.discarding = True
            return None
        if self.silence >= self.tail_bytes:
            result = bytes(self.audio[:self.maximum_bytes])
            self.reset()
            return result
        return None
