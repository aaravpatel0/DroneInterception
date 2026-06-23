#include <Arduino.h>

const uint8_t PIN_THROTTLE = 16;
const uint8_t PIN_YAW = 17;
const uint8_t PIN_PITCH = 18;
const uint8_t PIN_ROLL = 19;

const uint32_t PWM_FREQ_HZ = 20000;
const uint8_t PWM_RESOLUTION_BITS = 16;
const uint32_t PWM_MIN = 0;
const uint32_t PWM_MAX = 65535;
const uint32_t NEUTRAL = 32768;
const size_t MAX_LINE_LENGTH = 64;

String inputLine;
uint32_t throttleValue = NEUTRAL;
uint32_t yawValue = NEUTRAL;
uint32_t pitchValue = NEUTRAL;
uint32_t rollValue = NEUTRAL;

uint32_t clampDuty(long value) {
  if (value < static_cast<long>(PWM_MIN)) {
    return PWM_MIN;
  }
  if (value > static_cast<long>(PWM_MAX)) {
    return PWM_MAX;
  }
  return static_cast<uint32_t>(value);
}

void writeAxis(uint8_t pin, uint32_t value, const char *axisName, uint32_t &storedValue) {
  storedValue = value;
  analogWrite(pin, value);
  Serial.print("OK ");
  Serial.print(axisName);
  Serial.print(" ");
  Serial.println(value);
}

void centerAll() {
  throttleValue = NEUTRAL;
  yawValue = NEUTRAL;
  pitchValue = NEUTRAL;
  rollValue = NEUTRAL;
  analogWrite(PIN_THROTTLE, throttleValue);
  analogWrite(PIN_YAW, yawValue);
  analogWrite(PIN_PITCH, pitchValue);
  analogWrite(PIN_ROLL, rollValue);
}

void printStatus() {
  Serial.print("OK STATUS throttle=");
  Serial.print(throttleValue);
  Serial.print("@GP16 yaw=");
  Serial.print(yawValue);
  Serial.print("@GP17 pitch=");
  Serial.print(pitchValue);
  Serial.print("@GP18 roll=");
  Serial.print(rollValue);
  Serial.println("@GP19");
}

bool parseAssignment(const String &line, String &axis, uint32_t &value) {
  int delimiter = line.indexOf(':');
  if (delimiter < 0) {
    delimiter = line.indexOf('=');
  }
  if (delimiter <= 0 || delimiter == static_cast<int>(line.length()) - 1) {
    return false;
  }

  axis = line.substring(0, delimiter);
  String valueText = line.substring(delimiter + 1);
  axis.trim();
  valueText.trim();
  axis.toLowerCase();

  if (axis.length() == 0 || valueText.length() == 0) {
    return false;
  }

  value = clampDuty(valueText.toInt());
  return true;
}

void handleLine(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }

  String command = line;
  command.toLowerCase();
  if (command == "center" || command == "neutral") {
    centerAll();
    Serial.println("OK CENTER");
    return;
  }
  if (command == "status") {
    printStatus();
    return;
  }

  String axis;
  uint32_t value = NEUTRAL;
  if (!parseAssignment(line, axis, value)) {
    Serial.println("ERR FORMAT");
    return;
  }

  if (axis == "throttle" || axis == "t" || axis == "thr") {
    writeAxis(PIN_THROTTLE, value, "throttle", throttleValue);
  } else if (axis == "yaw" || axis == "y") {
    writeAxis(PIN_YAW, value, "yaw", yawValue);
  } else if (axis == "pitch" || axis == "p") {
    writeAxis(PIN_PITCH, value, "pitch", pitchValue);
  } else if (axis == "roll" || axis == "r") {
    writeAxis(PIN_ROLL, value, "roll", rollValue);
  } else {
    Serial.println("ERR AXIS");
  }
}

void setup() {
  Serial.begin(115200);

  analogWriteFreq(PWM_FREQ_HZ);
  analogWriteResolution(PWM_RESOLUTION_BITS);

  pinMode(PIN_THROTTLE, OUTPUT);
  pinMode(PIN_YAW, OUTPUT);
  pinMode(PIN_PITCH, OUTPUT);
  pinMode(PIN_ROLL, OUTPUT);
  centerAll();

  Serial.println("OK PICO DRONE PWM READY");
}

void loop() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\n' || c == '\r') {
      if (inputLine.length() > 0) {
        handleLine(inputLine);
        inputLine = "";
      }
    } else if (inputLine.length() < MAX_LINE_LENGTH) {
      inputLine += c;
    } else {
      inputLine = "";
      Serial.println("ERR LINE_TOO_LONG");
    }
  }
}
