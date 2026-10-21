"""
api.audio - звук: свои файлы и синтезированные сигналы (без файлов!).

    api.audio.tone(880, 90, wave="square")                 # писк
    api.audio.tone(600, 200, slide=-400)                   # «лазер»: частота падает
    api.audio.noise(250)                                   # «взрыв»
    api.audio.play(r"C:\\sounds\\ding.wav", volume=0.6)      # wav / mp3 / ogg
    api.audio.stop_all()

Если звукового устройства нет (или нет QtMultimedia) - методы тихо ничего не делают
и возвращают False.
"""

import os
import math
import wave
import struct
import random
import hashlib
import tempfile

_RATE = 22050


def _synth(freq, ms, volume, wave_kind, slide, noise=False):
    n = int(_RATE * ms / 1000)
    frames = bytearray()
    phase = 0.0
    rnd = random.Random(5)
    for i in range(n):
        t = i / max(1, n)
        env = (1 - t) ** 1.5 if t > 0.05 else t / 0.05       # быстрая атака, плавное затухание
        f = freq + slide * t
        phase += 2 * math.pi * max(20.0, f) / _RATE
        if noise:
            s = rnd.uniform(-1, 1)
        elif wave_kind == "square":
            s = 1.0 if math.sin(phase) >= 0 else -1.0
        elif wave_kind == "saw":
            s = ((phase / math.pi) % 2) - 1
        elif wave_kind == "triangle":
            s = 2 * abs(((phase / math.pi) % 2) - 1) - 1
        else:
            s = math.sin(phase)
        frames += struct.pack("<h", int(max(-1, min(1, s * env * volume)) * 32000))
    return bytes(frames)


class AudioAPI:
    def __init__(self, api):
        self._api = api
        self._live = []
        self._dir = os.path.join(tempfile.gettempdir(), "gor_addon_audio")
        os.makedirs(self._dir, exist_ok=True)
        api._resources.add(self.stop_all)

    def _wav(self, freq, ms, volume, wave_kind, slide, noise=False):
        key = hashlib.md5(f"{freq}|{ms}|{volume}|{wave_kind}|{slide}|{noise}".encode()).hexdigest()[:16]
        path = os.path.join(self._dir, key + ".wav")
        if not os.path.exists(path):
            data = _synth(freq, ms, volume, wave_kind, slide, noise)
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(_RATE)
                w.writeframes(data)
        return path

    def _effect(self, path, volume, loop=False):
        try:
            from PyQt6.QtMultimedia import QSoundEffect
            from PyQt6.QtCore import QUrl
        except Exception:
            return False
        e = QSoundEffect(self._api.launcher)
        e.setSource(QUrl.fromLocalFile(path))
        e.setVolume(max(0.0, min(1.0, volume)))
        if loop:
            e.setLoopCount(-2)       # QSoundEffect.Infinite
        e.play()
        self._live.append(e)
        if len(self._live) > 24:
            old = self._live.pop(0)
            old.stop()
            old.deleteLater()
        return True

    def tone(self, freq=440, ms=120, volume=0.5, wave="square", slide=0):
        """Синтезированный сигнал. wave: sine | square | saw | triangle; slide - изменение частоты (Гц)."""
        return self._effect(self._wav(freq, ms, volume, wave, slide), 1.0)

    def noise(self, ms=200, volume=0.5):
        """Шум («взрыв», «выстрел»)."""
        return self._effect(self._wav(0, ms, volume, "noise", 0, noise=True), 1.0)

    def play(self, path, volume=1.0, loop=False):
        """Проиграть файл. wav - мгновенно; mp3/ogg/flac - через медиаплеер."""
        if not os.path.exists(path):
            return False
        if path.lower().endswith(".wav"):
            return self._effect(path, volume, loop)
        try:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PyQt6.QtCore import QUrl
        except Exception:
            return False
        player = QMediaPlayer(self._api.launcher)
        out = QAudioOutput(self._api.launcher)
        out.setVolume(max(0.0, min(1.0, volume)))
        player.setAudioOutput(out)
        player.setSource(QUrl.fromLocalFile(path))
        if loop:
            player.setLoops(QMediaPlayer.Loops.Infinite)
        player.play()
        self._live.append((player, out))
        return True

    def beep(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.beep()

    def stop_all(self):
        for item in self._live:
            try:
                if isinstance(item, tuple):
                    item[0].stop()
                    item[0].deleteLater()
                    item[1].deleteLater()
                else:
                    item.stop()
                    item.deleteLater()
            except Exception:
                pass
        self._live.clear()
