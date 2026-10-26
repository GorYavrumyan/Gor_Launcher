"""
Геймпад для режима Big Picture (XInput на Windows, /dev/input/js* на Linux; без внешних зависимостей).

Qt6 убрал QtGamepad, поэтому опрашиваем XInput напрямую (Windows: Xbox-совместимые
контроллеры, в том числе большинство геймпадов через Steam Input / DS4Windows).
На других системах считыватель просто неактивен - режим управляется клавиатурой.

Устройство модуля:
  decode_state()    - сырые данные XInput -> множество логических кнопок
  ButtonRepeater    - "нажатие" + автоповтор для направлений (чистая логика, без Qt)
  XInputBackend     - обращение к xinput*.dll
  GamepadReader     - QObject: опрос по таймеру, сигнал pressed(str)

Логические имена кнопок: up down left right a b x y lb rb start back lt rt
"""
import ctypes
import os
import platform
import re
import struct
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# --- XInput: маски кнопок (wButtons) ---
_BUTTON_MASKS = (
    (0x0001, "up"), (0x0002, "down"), (0x0004, "left"), (0x0008, "right"),
    (0x0010, "start"), (0x0020, "back"),
    (0x0100, "lb"), (0x0200, "rb"),
    (0x1000, "a"), (0x2000, "b"), (0x4000, "x"), (0x8000, "y"),
)

STICK_THRESHOLD = 16000   # из диапазона +-32767; ~50% отклонения стика = "нажатие"
TRIGGER_THRESHOLD = 128   # из диапазона 0..255

REPEATABLE = frozenset({"up", "down", "left", "right"})
REPEAT_DELAY = 0.40       # сек до первого автоповтора
REPEAT_INTERVAL = 0.11    # сек между повторами


def decode_state(buttons, lx=0, ly=0, lt=0, rt=0):
    """Сырое состояние одного контроллера -> frozenset логических кнопок."""
    held = {name for mask, name in _BUTTON_MASKS if buttons & mask}
    # левый стик работает как крестовина
    if lx > STICK_THRESHOLD:
        held.add("right")
    elif lx < -STICK_THRESHOLD:
        held.add("left")
    if ly > STICK_THRESHOLD:
        held.add("up")
    elif ly < -STICK_THRESHOLD:
        held.add("down")
    if lt > TRIGGER_THRESHOLD:
        held.add("lt")
    if rt > TRIGGER_THRESHOLD:
        held.add("rt")
    return frozenset(held)


class ButtonRepeater:
    """Превращает "что зажато сейчас" в события нажатия.

    update(held, now) -> список имён кнопок, которые надо обработать:
      * только что нажатая кнопка - сразу;
      * зажатое направление - повторяется через REPEAT_DELAY, затем каждые REPEAT_INTERVAL.
    Если зажаты противоположные направления (стик + крестовина), повтор идёт для последнего нажатого.
    """

    def __init__(self):
        self._prev = frozenset()
        self._next_repeat = {}

    def update(self, held, now):
        events = []
        for name in sorted(held - self._prev):          # новые нажатия
            events.append(name)
            if name in REPEATABLE:
                self._next_repeat[name] = now + REPEAT_DELAY
        for name in list(self._next_repeat):
            if name not in held:                         # отпустили - повтор сбрасывается
                del self._next_repeat[name]
        for name, when in list(self._next_repeat.items()):
            if name in held and name not in events and now >= when:
                events.append(name)
                # шаг по времени, а не "now + interval": не копим задержку при редких опросах
                self._next_repeat[name] = max(when + REPEAT_INTERVAL, now)
        self._prev = held
        return events

    def swallow(self, held):
        """Считать все сейчас зажатые кнопки уже обработанными: событий не будет,
        пока их не отпустят (нужно после возврата из игры, где A мог остаться зажатым)."""
        self._prev = frozenset(held)
        self._next_repeat.clear()


# --- Windows XInput ---
class _XInputGamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class _XInputState(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_ulong), ("Gamepad", _XInputGamepad)]


class XInputBackend:
    """Опрос до 4 контроллеров. poll() -> список (buttons, lx, ly, lt, rt) подключённых.
    Пустые слоты XInput опрашивает медленно, поэтому их проверяем редко (раз в секунду)."""

    RESCAN_INTERVAL = 1.0

    def __init__(self):
        self._dll = None
        for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                self._dll = ctypes.WinDLL(name)
                break
            except (OSError, AttributeError):
                continue
        if self._dll is None:
            raise OSError("XInput недоступен")
        self._dll.XInputGetState.argtypes = [ctypes.c_ulong, ctypes.POINTER(_XInputState)]
        self._dll.XInputGetState.restype = ctypes.c_ulong
        self._connected = set()
        self._last_scan = 0.0

    def poll(self):
        now = time.monotonic()
        if now - self._last_scan >= self.RESCAN_INTERVAL:
            self._last_scan = now
            slots = range(4)
        else:
            slots = sorted(self._connected)
        result = []
        for slot in slots:
            state = _XInputState()
            if self._dll.XInputGetState(slot, ctypes.byref(state)) == 0:
                self._connected.add(slot)
                g = state.Gamepad
                result.append((g.wButtons, g.sThumbLX, g.sThumbLY, g.bLeftTrigger, g.bRightTrigger))
            else:
                self._connected.discard(slot)
        return result


class LinuxJoystickBackend:
    """Геймпады на Linux через legacy joystick API (/dev/input/js*), без зависимостей.

    Отдаёт то же, что XInputBackend.poll(): [(buttons, lx, ly, lt, rt), ...],
    где buttons - битовая маска в раскладке XInput. Поддержаны Xbox-совместимые
    контроллеры (драйвер xpad) и PlayStation (hid-playstation / hid-sony);
    устройства подхватываются и на лету (переподключение).
    """

    _EVENT = struct.Struct("<IhBB")          # time, value, type, number
    _XBOX_BTN = {0: 0x1000, 1: 0x2000, 2: 0x4000, 3: 0x8000, 4: 0x0100, 5: 0x0200, 6: 0x0020, 7: 0x0010}
    _PS_BTN = {0: 0x1000, 1: 0x2000, 3: 0x4000, 2: 0x8000, 4: 0x0100, 5: 0x0200, 8: 0x0020, 9: 0x0010}
    _RESCAN_SEC = 2.0

    def __init__(self, dev_dir="/dev/input", max_slots=4):
        self._dir = dev_dir
        self._max = max_slots
        self._devs = {}                      # путь -> состояние устройства
        self._last_scan = 0.0
        if not os.path.isdir(dev_dir):
            raise OSError("нет " + dev_dir)

    @staticmethod
    def _is_playstation(path):
        try:
            node = os.path.basename(path)
            with open(f"/sys/class/input/{node}/device/name", "r", errors="ignore") as f:
                name = f.read().lower()
            return any(k in name for k in ("dualshock", "dualsense", "wireless controller", "sony", "playstation"))
        except OSError:
            return False

    def _scan(self):
        self._last_scan = time.monotonic()
        try:
            names = sorted(n for n in os.listdir(self._dir) if re.fullmatch(r"js\d+", n))
        except OSError:
            return
        for n in names[: self._max]:
            path = os.path.join(self._dir, n)
            if path in self._devs:
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            ps = self._is_playstation(path)
            self._devs[path] = {"fd": fd, "ps": ps, "btn": 0, "axes": {}, "hat": [0, 0]}

    def _close(self, path):
        d = self._devs.pop(path, None)
        if d:
            try:
                os.close(d["fd"])
            except OSError:
                pass

    def _drain(self, path, d):
        size = self._EVENT.size
        while True:
            try:
                data = os.read(d["fd"], size * 32)
            except BlockingIOError:
                return True
            except OSError:
                return False                 # устройство отключили
            if not data:
                return False
            for i in range(0, len(data) - size + 1, size):
                _t, value, etype, number = self._EVENT.unpack_from(data, i)
                etype &= 0x7F                # старший бит - "синтетическое" начальное событие
                if etype == 1:
                    bit = (self._PS_BTN if d["ps"] else self._XBOX_BTN).get(number)
                    if bit:
                        d["btn"] = (d["btn"] | bit) if value else (d["btn"] & ~bit)
                elif etype == 2:
                    if number == 6:
                        d["hat"][0] = value
                    elif number == 7:
                        d["hat"][1] = value
                    else:
                        d["axes"][number] = value

    def poll(self):
        if time.monotonic() - self._last_scan > self._RESCAN_SEC:
            self._scan()
        result = []
        for path in list(self._devs):
            d = self._devs[path]
            if not self._drain(path, d):
                self._close(path)
                continue
            btn = d["btn"]
            hx, hy = d["hat"]
            if hy < 0:
                btn |= 0x0001                # up
            elif hy > 0:
                btn |= 0x0002                # down
            if hx < 0:
                btn |= 0x0004                # left
            elif hx > 0:
                btn |= 0x0008                # right
            ax = d["axes"]
            lx = ax.get(0, 0)
            ly = -ax.get(1, 0)               # в joystick API "вверх" отрицательно, в XInput - положительно
            lt_axis, rt_axis = (4, 5) if d["ps"] else (2, 5)
            lt = max(0, min(255, (ax.get(lt_axis, -32767) + 32767) // 257))
            rt = max(0, min(255, (ax.get(rt_axis, -32767) + 32767) // 257))
            result.append((btn, lx, ly, lt, rt))
        return result


def default_backend():
    """XInput на Windows, joystick API на Linux, иначе None (остаётся клавиатура)."""
    system = platform.system()
    try:
        if system == "Windows":
            return XInputBackend()
        if system == "Linux":
            return LinuxJoystickBackend()
    except Exception:
        pass
    return None


class GamepadReader(QObject):
    """Опрашивает геймпад по таймеру и испускает pressed("a") и т.п.

    backend - любой объект с методом poll() -> [(buttons, lx, ly, lt, rt), ...];
    по умолчанию XInput. Подмена backend позволяет тестировать без железа.
    """

    pressed = pyqtSignal(str)
    connectionChanged = pyqtSignal(bool)

    def __init__(self, backend="auto", parent=None, interval_ms=16):
        super().__init__(parent)
        self._backend = default_backend() if backend == "auto" else backend
        self._repeater = ButtonRepeater()
        self._connected = False
        self._paused = False
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.poll)

    @property
    def available(self):
        return self._backend is not None

    @property
    def connected(self):
        return self._connected

    def start(self):
        if self._backend is not None:
            self._timer.start()

    def stop(self):
        self._timer.stop()

    def set_paused(self, paused):
        """На паузе ввод игнорируется (игра/стрим на переднем плане), но состояние
        кнопок отслеживается - после снятия паузы зажатое не превращается в нажатие."""
        self._paused = paused
        if not paused:
            self.resync()

    def resync(self):
        self._repeater.swallow(self._read_held())

    def _read_held(self):
        held = set()
        try:
            states = self._backend.poll() if self._backend else []
        except Exception:
            states = []
        self._update_connection(bool(states))
        for st in states:
            held |= decode_state(*st)
        return frozenset(held)

    def _update_connection(self, connected):
        if connected != self._connected:
            self._connected = connected
            self.connectionChanged.emit(connected)

    def poll(self, now=None):
        held = self._read_held()
        events = self._repeater.update(held, time.monotonic() if now is None else now)
        if self._paused:
            return
        for name in events:
            self.pressed.emit(name)
