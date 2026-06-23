from machine import Pin, PWM
import select
import sys
import time


PWM_FREQ_HZ = 20_000
PWM_MIN = 0
PWM_MAX = 65_535
NEUTRAL = 32_768
FAILSAFE_MS = 1_000

AXIS_PINS = {
    "THROTTLE": 16,
    "YAW": 17,
    "PITCH": 18,
    "ROLL": 19,
}

AXIS_DETAILS = {
    "THROTTLE": {
        "motion": "Z-axis altitude",
        "low": "hold/lower altitude",
        "high": "increase altitude",
    },
    "YAW": {
        "motion": "rotation around Z-axis",
        "low": "counter-clockwise",
        "high": "clockwise",
    },
    "PITCH": {
        "motion": "forward/backward",
        "low": "backward",
        "high": "forward",
    },
    "ROLL": {
        "motion": "left/right lateral",
        "low": "left",
        "high": "right",
    },
}

ALIASES = {
    "T": "THROTTLE",
    "THR": "THROTTLE",
    "THROTTLE": "THROTTLE",
    "Y": "YAW",
    "YAW": "YAW",
    "P": "PITCH",
    "PIT": "PITCH",
    "PITCH": "PITCH",
    "R": "ROLL",
    "ROL": "ROLL",
    "ROLL": "ROLL",
}

DIRECTION_ALIASES = {
    "UP": ("THROTTLE", PWM_MAX),
    "CLIMB": ("THROTTLE", PWM_MAX),
    "DOWN": ("THROTTLE", PWM_MIN),
    "DESCEND": ("THROTTLE", PWM_MIN),
    "CLOCKWISE": ("YAW", PWM_MAX),
    "CW": ("YAW", PWM_MAX),
    "COUNTERCLOCKWISE": ("YAW", PWM_MIN),
    "COUNTER-CLOCKWISE": ("YAW", PWM_MIN),
    "CCW": ("YAW", PWM_MIN),
    "FORWARD": ("PITCH", PWM_MAX),
    "BACK": ("PITCH", PWM_MIN),
    "BACKWARD": ("PITCH", PWM_MIN),
    "RIGHT": ("ROLL", PWM_MAX),
    "LEFT": ("ROLL", PWM_MIN),
}


class AxisOutput:
    def __init__(self, name, pin_number):
        self.name = name
        self.pin_number = pin_number
        self.pwm = PWM(Pin(pin_number))
        self.pwm.freq(PWM_FREQ_HZ)
        self.value = NEUTRAL
        self.write(NEUTRAL)

    def write(self, value):
        value = int(value)
        if value < PWM_MIN:
            value = PWM_MIN
        elif value > PWM_MAX:
            value = PWM_MAX
        self.value = value
        self.pwm.duty_u16(value)

    def remap_pin(self, pin_number):
        self.pwm.deinit()
        self.pin_number = int(pin_number)
        self.pwm = PWM(Pin(self.pin_number))
        self.pwm.freq(PWM_FREQ_HZ)
        self.write(self.value)


axes = {name: AxisOutput(name, pin) for name, pin in AXIS_PINS.items()}
poller = select.poll()
poller.register(sys.stdin, select.POLLIN)
buffer = ""
armed = False
last_command_ms = time.ticks_ms()


def axis_name(token):
    return ALIASES.get(token.strip().upper())


def center_all():
    for axis in axes.values():
        axis.write(NEUTRAL)


def status():
    parts = ["OK STATUS", "ARMED" if armed else "DISARMED"]
    for name in ("THROTTLE", "YAW", "PITCH", "ROLL"):
        axis = axes[name]
        detail = AXIS_DETAILS[name]
        parts.append(
            "{}={}@GP{}[{};low={};high={}]".format(
                name,
                axis.value,
                axis.pin_number,
                detail["motion"],
                detail["low"],
                detail["high"],
            )
        )
    print(" ".join(parts))


def set_axis(name, value):
    if not armed:
        print("ERR DISARMED")
        return
    axes[name].write(value)
    print("OK {} {}".format(name, axes[name].value))


def parse_assignment(command):
    if ":" in command:
        axis_text, value_text = command.split(":", 1)
    elif "=" in command:
        axis_text, value_text = command.split("=", 1)
    else:
        return False
    name = axis_name(axis_text)
    if name is None:
        return False
    set_axis(name, int(value_text.strip()))
    return True


def set_direction(direction, value_text=None):
    direction = direction.strip().upper()
    if direction not in DIRECTION_ALIASES:
        return False
    name, default_value = DIRECTION_ALIASES[direction]
    value = default_value if value_text is None else int(value_text.strip())
    set_axis(name, value)
    return True


def handle_line(line):
    global armed
    line = line.strip()
    if not line:
        return

    upper = line.upper()
    if upper == "ARM":
        armed = True
        center_all()
        print("OK ARMED")
    elif upper in ("DISARM", "K", "STOP"):
        armed = False
        center_all()
        print("OK DISARMED")
    elif upper in ("CENTER", "NEUTRAL"):
        center_all()
        print("OK CENTER")
    elif upper == "STATUS":
        status()
    elif upper == "HELP":
        print(
            "OK HELP ARM DISARM STOP CENTER STATUS "
            "THROTTLE/YAW/PITCH/ROLL 0..65535 "
            "MOVE FORWARD/BACKWARD/LEFT/RIGHT/UP/DOWN/CW/CCW [value]"
        )
    elif upper.startswith("MAP "):
        parts = upper.split()
        if len(parts) != 3:
            print("ERR MAP_FORMAT")
            return
        name = axis_name(parts[1])
        if name is None:
            print("ERR AXIS")
            return
        axes[name].remap_pin(int(parts[2]))
        print("OK MAP {} GP{}".format(name, axes[name].pin_number))
    elif parse_assignment(upper):
        return
    else:
        parts = upper.split()
        if len(parts) in (2, 3) and parts[0] == "MOVE":
            if not set_direction(parts[1], parts[2] if len(parts) == 3 else None):
                print("ERR DIRECTION")
        elif len(parts) == 3 and parts[0] == "SET":
            name = axis_name(parts[1])
            if name is None:
                print("ERR AXIS")
                return
            set_axis(name, int(parts[2]))
        elif len(parts) == 2:
            name = axis_name(parts[0])
            if name is None:
                print("ERR AXIS")
                return
            set_axis(name, int(parts[1]))
        else:
            print("ERR COMMAND")


def read_available_input():
    global buffer, last_command_ms
    while poller.poll(0):
        chunk = sys.stdin.read(1)
        if not chunk:
            return
        if chunk in ("\n", "\r"):
            if buffer:
                last_command_ms = time.ticks_ms()
                handle_line(buffer)
                buffer = ""
        elif len(buffer) < 96:
            buffer += chunk
        else:
            buffer = ""
            print("ERR LINE_TOO_LONG")


center_all()
print("OK PICO DRONE CONTROLLER READY")

while True:
    read_available_input()
    if armed and time.ticks_diff(time.ticks_ms(), last_command_ms) > FAILSAFE_MS:
        armed = False
        center_all()
        print("OK FAILSAFE DISARMED")
    time.sleep_ms(5)
