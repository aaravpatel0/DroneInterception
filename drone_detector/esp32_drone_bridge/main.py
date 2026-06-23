import json
import socket
import time

try:
    from machine import I2C, Pin
    import network
except ImportError:
    I2C = None
    Pin = None
    network = None


WIFI_SSID = "CHANGE_ME"
WIFI_PASSWORD = "CHANGE_ME"
UDP_PORT = 4210
FAILSAFE_MS = 500
NEUTRAL = 32768
PWM_MIN = 0
PWM_MAX = 65535
I2C_BUS_ID = 0
BMI160_SDA_PIN = 8
BMI160_SCL_PIN = 9
BMI160_ADDRESS = 0x68
BMI160_ALT_ADDRESS = 0x69
BMI160_CHIP_ID_REG = 0x00
BMI160_EXPECTED_CHIP_ID = 0xD1
BMI160_CMD_REG = 0x7E
BMI160_ACCEL_NORMAL_CMD = 0x11
BMI160_GYRO_NORMAL_CMD = 0x15
BMI160_GYRO_DATA_REG = 0x0C
BMI160_ACCEL_DATA_REG = 0x12

AXIS_ORDER = ("throttle", "yaw", "pitch", "roll")

controls = {
    "throttle": NEUTRAL,
    "yaw": NEUTRAL,
    "pitch": NEUTRAL,
    "roll": NEUTRAL,
}
armed = False
last_packet_ms = time.ticks_ms()
imu = None
imu_address = None


def clamp_u16(value):
    value = int(value)
    if value < PWM_MIN:
        return PWM_MIN
    if value > PWM_MAX:
        return PWM_MAX
    return value


def center_controls():
    for axis in AXIS_ORDER:
        controls[axis] = NEUTRAL


def connect_wifi():
    if network is None:
        print("ERR network module unavailable; run this on MicroPython ESP32 firmware")
        return None

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("wifi connecting...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > 15000:
                raise RuntimeError("WiFi connection timed out")
            time.sleep_ms(250)

    print("wifi connected {}".format(wlan.ifconfig()[0]))
    return wlan


def write_reg(i2c, address, register, value):
    i2c.writeto_mem(address, register, bytes([value]))


def read_reg(i2c, address, register, length=1):
    return i2c.readfrom_mem(address, register, length)


def detect_bmi160(i2c):
    for address in (BMI160_ADDRESS, BMI160_ALT_ADDRESS):
        try:
            chip_id = read_reg(i2c, address, BMI160_CHIP_ID_REG)[0]
        except OSError:
            continue
        if chip_id == BMI160_EXPECTED_CHIP_ID:
            return address
        raise RuntimeError(
            "BMI160 chip id mismatch at 0x{:02X}: expected 0x{:02X}, got 0x{:02X}".format(
                address,
                BMI160_EXPECTED_CHIP_ID,
                chip_id,
            )
        )
    raise RuntimeError("BMI160 not found at 0x68 or 0x69")


def init_imu():
    if I2C is None or Pin is None:
        print("ERR machine.I2C unavailable; run this on MicroPython ESP32-C3 firmware")
        return None, None

    i2c = I2C(
        I2C_BUS_ID,
        scl=Pin(BMI160_SCL_PIN),
        sda=Pin(BMI160_SDA_PIN),
        freq=400000,
    )
    address = detect_bmi160(i2c)
    write_reg(i2c, address, BMI160_CMD_REG, BMI160_ACCEL_NORMAL_CMD)
    time.sleep_ms(50)
    write_reg(i2c, address, BMI160_CMD_REG, BMI160_GYRO_NORMAL_CMD)
    time.sleep_ms(100)
    print("BMI160 ready at 0x{:02X}".format(address))
    return i2c, address


def int16_le(low, high):
    value = low | (high << 8)
    if value & 0x8000:
        value -= 0x10000
    return value


def read_xyz_raw(i2c, address, register):
    data = read_reg(i2c, address, register, 6)
    return {
        "x": int16_le(data[0], data[1]),
        "y": int16_le(data[2], data[3]),
        "z": int16_le(data[4], data[5]),
    }


def parse_packet(data):
    text = data.decode("utf-8").strip()
    if not text:
        return None

    if text[0] == "{":
        payload = json.loads(text)
        return {
            axis: clamp_u16(payload.get(axis, controls[axis]))
            for axis in AXIS_ORDER
        }

    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 4:
        raise ValueError("expected JSON or throttle,yaw,pitch,roll CSV")
    return {axis: clamp_u16(parts[index]) for index, axis in enumerate(AXIS_ORDER)}


def read_imu():
    if imu is None or imu_address is None:
        return {"ok": False, "error": "BMI160 unavailable"}
    try:
        return {
            "ok": True,
            "chip": "BMI160",
            "address": "0x{:02X}".format(imu_address),
            "accel_raw": read_xyz_raw(imu, imu_address, BMI160_ACCEL_DATA_REG),
            "gyro_raw": read_xyz_raw(imu, imu_address, BMI160_GYRO_DATA_REG),
        }
    except OSError as exc:
        return {"ok": False, "chip": "BMI160", "error": str(exc)}


def apply_controls(next_controls):
    controls.update(next_controls)
    print(
        "CTRL throttle={throttle} yaw={yaw} pitch={pitch} roll={roll}".format(
            **controls
        )
    )


def telemetry_packet():
    payload = {
        "armed": armed,
        "controls": controls,
        "imu": read_imu(),
    }
    return json.dumps(payload)


def main():
    global armed, last_packet_ms, imu, imu_address

    try:
        imu, imu_address = init_imu()
    except Exception as exc:
        imu = None
        imu_address = None
        print("ERR BMI160 {}".format(exc))

    try:
        connect_wifi()
    except Exception as exc:
        print("ERR WIFI {}".format(exc))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", UDP_PORT))
    sock.settimeout(0.05)
    center_controls()
    print("OK ESP32 DRONE BRIDGE UDP {}".format(UDP_PORT))

    while True:
        try:
            data, address = sock.recvfrom(512)
        except OSError:
            data = None
            address = None

        if data:
            command = data.decode("utf-8", "ignore").strip().upper()
            if command == "ARM":
                armed = True
                center_controls()
                last_packet_ms = time.ticks_ms()
                sock.sendto(b'{"ok":"armed"}', address)
            elif command in ("DISARM", "STOP", "K"):
                armed = False
                center_controls()
                sock.sendto(b'{"ok":"disarmed"}', address)
            elif command == "STATUS":
                sock.sendto(telemetry_packet().encode("utf-8"), address)
            elif armed:
                try:
                    apply_controls(parse_packet(data))
                    last_packet_ms = time.ticks_ms()
                    sock.sendto(telemetry_packet().encode("utf-8"), address)
                except Exception as exc:
                    sock.sendto(json.dumps({"error": str(exc)}).encode("utf-8"), address)
            else:
                sock.sendto(b'{"error":"disarmed"}', address)

        if armed and time.ticks_diff(time.ticks_ms(), last_packet_ms) > FAILSAFE_MS:
            armed = False
            center_controls()
            print("OK FAILSAFE DISARMED")

        time.sleep_ms(5)


main()
