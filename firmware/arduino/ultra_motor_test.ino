/*
  Motor and Ultrasonic Sensor Test for Arduino

  Pin Configuration:
  - Motor (via MOSFET): pin 23
  - Ultrasonic Echo: pin 25
  - Ultrasonic Trig: pin 16

  Controls through Serial Monitor:
  - Send 's' to start motor
  - Send 'x' to stop motor
  - Send 'q' to print quit message (Arduino keeps running unless reset)
*/

const int MOTOR_PIN = 23;
const int ULTRASONIC_TRIG = 16;
const int ULTRASONIC_ECHO = 25;

bool motorRunning = false;

void setup() {
  Serial.begin(9600);

  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, LOW);

  pinMode(ULTRASONIC_TRIG, OUTPUT);
  pinMode(ULTRASONIC_ECHO, INPUT);

  Serial.println("==================================================");
  Serial.println("Motor & Ultrasonic Sensor Test - Arduino");
  Serial.println("==================================================");
  Serial.println();
  Serial.println("Controls:");
  Serial.println("  's' - Start motor");
  Serial.println("  'x' - Stop motor");
  Serial.println("  'q' - Print quit message");
  Serial.println();

  delay(100); // sensor settle time
}

void startMotor() {
  digitalWrite(MOTOR_PIN, HIGH);
  motorRunning = true;
  Serial.println("Motor STARTED");
}

void stopMotor() {
  digitalWrite(MOTOR_PIN, LOW);
  motorRunning = false;
  Serial.println("Motor STOPPED");
}

const char* getMotorStatus() {
  return motorRunning ? "Running" : "Stopped";
}

float getDistanceCm() {
  // Ensure trigger is low
  digitalWrite(ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);

  // Send 10 us pulse
  digitalWrite(ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG, LOW);

  // Read pulse width with timeout (100000 us = 100 ms)
  unsigned long duration = pulseIn(ULTRASONIC_ECHO, HIGH, 100000);

  // If timeout happened
  if (duration == 0) {
    return -1;
  }

  // Speed of sound: 0.0343 cm/us
  // Distance = (duration * speed) / 2
  float distance = (duration * 0.0343) / 2.0;

  return distance;
}

void loop() {
  // Check for serial input
  if (Serial.available() > 0) {
    char key = Serial.read();

    if (key == 's' || key == 'S') {
      startMotor();
    } 
    else if (key == 'x' || key == 'X') {
      stopMotor();
    } 
    else if (key == 'q' || key == 'Q') {
      Serial.println("Quit requested. Reset Arduino to fully stop.");
      stopMotor();
    }
  }

  // Read ultrasonic distance
  float distance = getDistanceCm();

  if (distance >= 0) {
    Serial.print("Distance: ");
    Serial.print(distance, 2);
    Serial.print(" cm | Motor: ");
    Serial.println(getMotorStatus());
  } else {
    Serial.print("Distance: TIMEOUT | Motor: ");
    Serial.println(getMotorStatus());
  }

  delay(100);
}