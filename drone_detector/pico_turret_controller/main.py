from machine import Pin, PWM
import select
import sys
import time


STEP_PIN = 3
DIR_PIN = 4
EN_PIN = 5
SERVO_PIN = 9

TILT_MIN = 85
TILT_MAX = 130
TILT_HOME = 90
MAX_PAN_STEPS_PER_COMMAND = 200
PAN_LIMIT_STEPS = 250
STEP_PULSE_US = 2_000
SERVO_FREQ_HZ = 50

SERVO_MIN_US = 500
SERVO_MAX_US = 2_500
PWM_MAX = 65_535


step_pin = Pin(STEP_PIN, Pin.OUT, value=0)
dir_pin = Pin(DIR_PIN, Pin.OUT, value=0)
en_pin = Pin(EN_PIN, Pin.OUT, value=1)
servo_pwm = None
pan_position = 0
tilt_angle = TILT_HOME
input_buffer = ""
poller = select.poll()
poller.register(sys.stdin, select.POLLIN)


def clamp(value, low, high):
    return max(low, min(high, value))


def servo_duty_for_angle(angle):
    pulse_us = SERVO_MIN_US + (SERVO_MAX_US - SERVO_MIN_US) * angle / 180
    return int(PWM_MAX * pulse_us / 20_000)


def enable_stepper(enabled):
    en_pin.value(0 if enabled else 1)


def attach_servo():
    global servo_pwm
    if servo_pwm is None:
        servo_pwm = PWM(Pin(SERVO_PIN))
        servo_pwm.freq(SERVO_FREQ_HZ)


def detach_servo():
    global servo_pwm
    if servo_pwm is not None:
        servo_pwm.deinit()
        servo_pwm = None


def set_tilt(requested_angle):
    global tilt_angle
    tilt_angle = clamp(int(requested_angle), TILT_MIN, TILT_MAX)
    attach_servo()
    servo_pwm.duty_u16(servo_duty_for_angle(tilt_angle))
    print("OK TILT {}".format(tilt_angle))


def move_pan(requested_steps):
    global pan_position
    steps = clamp(int(requested_steps), -MAX_PAN_STEPS_PER_COMMAND, MAX_PAN_STEPS_PER_COMMAND)
    target_position = pan_position + steps
    if target_position > PAN_LIMIT_STEPS:
        steps = PAN_LIMIT_STEPS - pan_position
    elif target_position < -PAN_LIMIT_STEPS:
        steps = -PAN_LIMIT_STEPS - pan_position
    if steps == 0:
        print("OK PAN 0")
        return

    dir_pin.value(1 if steps >= 0 else 0)
    enable_stepper(True)
    for _ in range(abs(steps)):
        step_pin.value(1)
        time.sleep_us(STEP_PULSE_US)
        step_pin.value(0)
        time.sleep_us(STEP_PULSE_US)
    enable_stepper(False)
    pan_position += steps
    print("OK PAN {}".format(steps))


def stop_turret():
    enable_stepper(False)
    detach_servo()
    print("OK STOP")


def home_turret():
    global pan_position
    pan_position = 0
    set_tilt(TILT_HOME)
    print("OK HOME")


def zero_pan_only():
    global pan_position
    pan_position = 0
    print("OK PANZERO")


def set_stepper_power(enabled):
    enable_stepper(enabled)
    print("OK MOTOR {}".format("ON" if enabled else "OFF"))


def status():
    print("OK STATUS PAN {} TILT {}".format(pan_position, tilt_angle))


def parse_value(line, prefix):
    if not line.startswith(prefix):
        return None
    value_text = line[len(prefix):].strip()
    if not value_text:
        return None
    return int(value_text)


def handle_command(line):
    line = line.strip().upper()
    if not line:
        return

    try:
        pan_value = parse_value(line, "PAN ")
        tilt_value = parse_value(line, "TILT ")
        if pan_value is not None:
            move_pan(pan_value)
        elif tilt_value is not None:
            set_tilt(tilt_value)
        elif line == "HOME":
            home_turret()
        elif line in ("STOP", "K"):
            stop_turret()
        elif line == "PANZERO":
            zero_pan_only()
        elif line == "MOTOR ON":
            set_stepper_power(True)
        elif line == "MOTOR OFF":
            set_stepper_power(False)
        elif line == "STATUS":
            status()
        else:
            print("ERR UNKNOWN_COMMAND {}".format(line))
    except ValueError:
        print("ERR BAD_VALUE")


def read_serial():
    global input_buffer
    while poller.poll(0):
        char = sys.stdin.read(1)
        if not char:
            return
        if char in ("\n", "\r"):
            if input_buffer:
                handle_command(input_buffer)
                input_buffer = ""
        elif len(input_buffer) < 64:
            input_buffer += char
        else:
            input_buffer = ""
            print("ERR COMMAND_TOO_LONG")


enable_stepper(False)
detach_servo()
print("OK READY")

while True:
    read_serial()
    time.sleep_ms(2)
