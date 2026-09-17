
// Standalone Ultrasonic Sensor Test
// Pins based on Andino Hardware Config
const int trigPin = 8;
const int echoPin = 7;

void setup() {
  Serial.begin(9600); // Standard baud rate for simple testing
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  Serial.println("Ultrasonic Sensor Test Started");
}

void loop() {
  // Clear trigger
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  
  // Send 10us pulse
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  // Read echo (Timeout 30ms ~ 5m)
  long duration = pulseIn(echoPin, HIGH, 30000);
  
  if (duration == 0) {
    Serial.println("No Echo (Timeout) - Check Wiring!");
  } else {
    // Calculate distance in cm
    // Speed of sound = 343 m/s = 0.0343 cm/us
    float distance = duration * 0.0343 / 2;
    Serial.print("Distance: ");
    Serial.print(distance);
    Serial.println(" cm");
  }
  
  delay(500);
}
