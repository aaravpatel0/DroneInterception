#include <Arduino.h>
#include <Servo.h>

const uint8_t STEP_PIN = 3;
const uint8_t DIR_PIN = 16;
const uint8_t EN_PIN = 5;
const uint8_t SERVO_PIN = 9;

const int TILT_MIN = 80;
const int TILT_MAX = 130;
const int TILT_HOME = 85;
const int MAX_PAN_STEPS_PER_COMMAND = 70;
const long PAN_LIMIT_STEPS = 5000;
const unsigned int FAST_STEP_PULSE_US = 100;
const unsigned int SLOW_STEP_PULSE_US = 450;
const int RAMP_STEPS = 24;
const unsigned int DIR_SETUP_US = 50;
const bool ACK_MOVEMENT_COMMANDS = false;

Servo tiltServo;
long panPosition = 0;
int tiltAngle = TILT_HOME;
String inputLine;

int clampInt(int value, int low, int high) {
  if (value < low) {
    return low;
  }
  if (value > high) {
    return high;
  }
  return value;
}

void enableStepper(bool enabled) {
  digitalWrite(EN_PIN, enabled ? LOW : HIGH);
}

unsigned int rampDelayForStep(int index, int totalSteps) {
  int edgeSteps = min(min(index, totalSteps - 1 - index), RAMP_STEPS);
  if (edgeSteps >= RAMP_STEPS) {
    return FAST_STEP_PULSE_US;
  }
  float progress = edgeSteps / float(RAMP_STEPS);
  return SLOW_STEP_PULSE_US - (unsigned int)((SLOW_STEP_PULSE_US - FAST_STEP_PULSE_US) * progress);
}

void movePan(int requestedSteps) {
  int steps = clampInt(requestedSteps, -MAX_PAN_STEPS_PER_COMMAND, MAX_PAN_STEPS_PER_COMMAND);
  long targetPosition = panPosition + steps;

  if (targetPosition > PAN_LIMIT_STEPS) {
    steps = PAN_LIMIT_STEPS - panPosition;
  } else if (targetPosition < -PAN_LIMIT_STEPS) {
    steps = -PAN_LIMIT_STEPS - panPosition;
  }

  if (steps == 0) {
    Serial.println("OK PAN 0");
    return;
  }

  digitalWrite(DIR_PIN, steps >= 0 ? HIGH : LOW);
  delayMicroseconds(DIR_SETUP_US);
  enableStepper(true);

  int count = abs(steps);
  for (int i = 0; i < count; i++) {
    unsigned int pulseDelay = rampDelayForStep(i, count);
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(pulseDelay);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(pulseDelay);
  }

  panPosition += steps;
  if (ACK_MOVEMENT_COMMANDS) {
    Serial.print("OK PAN ");
    Serial.println(steps);
  }
}

void setTilt(int requestedAngle) {
  tiltAngle = clampInt(requestedAngle, TILT_MIN, TILT_MAX);
  if (!tiltServo.attached()) {
    tiltServo.attach(SERVO_PIN);
  }
  tiltServo.write(tiltAngle);
  if (ACK_MOVEMENT_COMMANDS) {
    Serial.print("OK TILT ");
    Serial.println(tiltAngle);
  }
}

void stopTurret() {
  enableStepper(false);
  if (tiltServo.attached()) {
    tiltServo.detach();
  }
  Serial.println("OK STOP");
}

void homeTurret() {
  panPosition = 0;
  setTilt(TILT_HOME);
  Serial.println("OK HOME");
}

void printStatus() {
  Serial.print("OK STATUS PAN ");
  Serial.print(panPosition);
  Serial.print(" TILT ");
  Serial.println(tiltAngle);
}

void zeroPanOnly() {
  panPosition = 0;
  Serial.println("OK PANZERO");
}

void setStepperPower(bool enabled) {
  enableStepper(enabled);
  Serial.println(enabled ? "OK MOTOR ON" : "OK MOTOR OFF");
}

void setPinLevel(uint8_t pin, bool high, const char *name) {
  digitalWrite(pin, high ? HIGH : LOW);
  Serial.print("OK ");
  Serial.print(name);
  Serial.println(high ? " HIGH" : " LOW");
}

void pulseStepSlowly() {
  enableStepper(true);
  for (int i = 0; i < 10; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delay(250);
    digitalWrite(STEP_PIN, LOW);
    delay(250);
  }
  enableStepper(false);
  Serial.println("OK STEP PULSE");
}

bool parseCommandValue(const String &line, const String &prefix, int &value) {
  if (!line.startsWith(prefix)) {
    return false;
  }

  String valueText = line.substring(prefix.length());
  valueText.trim();
  if (valueText.length() == 0) {
    return false;
  }

  value = valueText.toInt();
  return true;
}

void handleCommand(String line) {
  line.trim();
  line.toUpperCase();
  if (line.length() == 0) {
    return;
  }

  int value = 0;
  if (parseCommandValue(line, "PAN ", value)) {
    movePan(value);
  } else if (parseCommandValue(line, "TILT ", value)) {
    setTilt(value);
  } else if (line == "HOME") {
    homeTurret();
  } else if (line == "STOP" || line == "K") {
    stopTurret();
  } else if (line == "PANZERO") {
    zeroPanOnly();
  } else if (line == "MOTOR ON") {
    setStepperPower(true);
  } else if (line == "MOTOR OFF") {
    setStepperPower(false);
  } else if (line == "STEP HIGH") {
    setPinLevel(STEP_PIN, true, "STEP");
  } else if (line == "STEP LOW") {
    setPinLevel(STEP_PIN, false, "STEP");
  } else if (line == "DIR HIGH") {
    setPinLevel(DIR_PIN, true, "DIR");
  } else if (line == "DIR LOW") {
    setPinLevel(DIR_PIN, false, "DIR");
  } else if (line == "EN LOW") {
    setPinLevel(EN_PIN, false, "EN");
  } else if (line == "EN HIGH") {
    setPinLevel(EN_PIN, true, "EN");
  } else if (line == "STEP PULSE") {
    pulseStepSlowly();
  } else if (line == "STATUS") {
    printStatus();
  } else {
    Serial.print("ERR UNKNOWN_COMMAND ");
    Serial.println(line);
  }
}

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  enableStepper(false);

  Serial.begin(115200);
  delay(1200);
  Serial.println("OK READY");
}

void loop() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\n' || c == '\r') {
      if (inputLine.length() > 0) {
        handleCommand(inputLine);
        inputLine = "";
      }
    } else if (inputLine.length() < 64) {
      inputLine += c;
    } else {
      inputLine = "";
      Serial.println("ERR COMMAND_TOO_LONG");
    }
  }
}
