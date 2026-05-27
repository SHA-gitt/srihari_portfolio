#include <Wire.h>

// ==========================================
// 1. HARDWARE PINOUTS
// ==========================================
// Left Motor
const int PIN_ENA = 10;
const int PIN_IN1 = 4;
const int PIN_IN2 = 2;

// Right Motor
const int PIN_ENB = 9;
const int PIN_IN3 = 8;
const int PIN_IN4 = 7;

// ==========================================
// 2. FLIGHT SETTINGS (12V DC SAFE)
// ==========================================
const int BASE_THROTTLE = 95;   // ~3.7V effective (Safe hover power)
const int MIN_PWM = 20;         // Minimum power to keep motors spinning
const int MAX_PWM = 255;        // ~5.9V effective (Absolute max safety limit)

// PID Tuning Baseline
float Kp = 3.0;
float Ki = 0.0;
float Kd = 1.2;

// ==========================================
// 3. SYSTEM VARIABLES
// ==========================================
const int MPU = 0x68;
float angle_roll = 0.0;
unsigned long loop_timer;

// Sensor calibration
long gyro_x_cal = 0;
long accel_y_cal = 0;
long accel_z_cal = 0;

// PID Variables
float pid_error = 0.0;
float pid_i = 0.0;
float pid_last_error = 0.0;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  // Note: Standard 100kHz I2C speed used here for maximum stability

  // Configure Motor Pins
  pinMode(PIN_ENA, OUTPUT); pinMode(PIN_IN1, OUTPUT); pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_ENB, OUTPUT); pinMode(PIN_IN3, OUTPUT); pinMode(PIN_IN4, OUTPUT);
  
  // Set motors to push air DOWN
  digitalWrite(PIN_IN1, HIGH); digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, HIGH); digitalWrite(PIN_IN4, LOW);
  
  // Ensure motors are OFF
  analogWrite(PIN_ENA, 0);
  analogWrite(PIN_ENB, 0);

  Serial.println(F("\n=================================="));
  Serial.println(F("    FLIGHT CONTROLLER BOOTING     "));
  Serial.println(F("=================================="));
  
  // Initialize MPU6050
  Wire.beginTransmission(MPU);
  Wire.write(0x6B); 
  Wire.write(0x00); // Wake up
  Wire.endTransmission();
  
  delay(100); // <-- MAGIC DELAY: Gives the MPU6050 time to wake up!
  
  // Configure Gyro to +/- 500 deg/s
  Wire.beginTransmission(MPU); Wire.write(0x1B); Wire.write(0x08); Wire.endTransmission();
  
  // Configure Accel to +/- 8g
  Wire.beginTransmission(MPU); Wire.write(0x1C); Wire.write(0x10); Wire.endTransmission();

  Serial.println(F("Calibrating IMU... DO NOT MOVE!"));
  delay(1000);

  // Take 1000 samples for high-precision zeroing
  for (int i = 0; i < 1000; i++) {
    Wire.beginTransmission(MPU);
    Wire.write(0x3B);
    Wire.endTransmission();
    Wire.requestFrom(MPU, 6);
    
    // Read only the axes we need for Roll
    Wire.read(); Wire.read(); // Skip Accel X
    int16_t acc_y = Wire.read() << 8 | Wire.read(); // Read Accel Y
    int16_t acc_z = Wire.read() << 8 | Wire.read(); // Read Accel Z
    
    Wire.beginTransmission(MPU);
    Wire.write(0x43);
    Wire.endTransmission();
    Wire.requestFrom(MPU, 2);
    int16_t gyro_x = Wire.read() << 8 | Wire.read(); // Read Gyro X
    
    accel_y_cal += acc_y;
    accel_z_cal += acc_z;
    gyro_x_cal += gyro_x;
    delay(3);
  }
  
  accel_y_cal /= 1000;
  accel_z_cal /= 1000;
  gyro_x_cal /= 1000;

  Serial.println(F("Calibration Complete. Starting Balancer."));
  Serial.println(F("Use Spacebar for Random PID, or format 'P:3.5 I:0.0 D:1.5'"));
  Serial.println(F("==================================\n"));
  delay(1000);
  
  // Start the strict loop timer 
  loop_timer = micros(); 
}

void loop() {
  
  // ==========================================
  // 1. STRICT 250Hz TIMING (4000 microseconds)
  // ==========================================
  while (micros() - loop_timer < 4000);
  loop_timer = micros();

  // ==========================================
  // 2. READ IMU & CALCULATE ANGLE
  // ==========================================
  Wire.beginTransmission(MPU);
  Wire.write(0x3B);
  Wire.endTransmission();
  Wire.requestFrom(MPU, 14);
  
  Wire.read(); Wire.read(); // Skip Accel X
  int16_t acc_y = Wire.read() << 8 | Wire.read(); 
  int16_t acc_z = Wire.read() << 8 | Wire.read(); 
  Wire.read(); Wire.read(); // Skip Temp
  int16_t gyro_x = Wire.read() << 8 | Wire.read(); 
  
  // Apply calibration offsets
  gyro_x -= gyro_x_cal;
  acc_y -= accel_y_cal;
  
  float gyro_rate = gyro_x / 65.5;
  float acc_angle = atan2(acc_y, acc_z) * 180.0 / PI;

  // Optimized Complementary Filter (0.004 dt is baked in)
  angle_roll = 0.996 * (angle_roll + gyro_rate * 0.004) + 0.004 * acc_angle;

  // ==========================================
  // 3. PID CALCULATION
  // ==========================================
  pid_error = 0.0 - angle_roll; // Target is 0.0 degrees perfectly flat
  
  float pid_p = Kp * pid_error;
  
  // Integral with anti-windup (only applies when close to level)
  if (pid_error > -10 && pid_error < 10) {
    pid_i += Ki * pid_error;
  }
  pid_i = constrain(pid_i, -50.0, 50.0);
  
  // Derivative (Calculated over exactly 0.004 seconds)
  float pid_d = Kd * ((pid_error - pid_last_error) / 0.004); 
  pid_last_error = pid_error;
  
  float pid_output = pid_p + pid_i + pid_d;
  pid_output = constrain(pid_output, -100.0, 100.0); 

  // ==========================================
  // 4. MOTOR MIXER
  // ==========================================
  // LOGIC VERIFIED: Positive Angle = Left Motor Increases.
  // If angle is POSITIVE, error (0 - angle) is NEGATIVE.
  // This makes pid_output NEGATIVE.
  // Base - (-Output) = Base + Output (LEFT INCREASES)
  // Base + (-Output) = Base - Output (RIGHT DECREASES)
  
  int pwm_left  = BASE_THROTTLE - pid_output; 
  int pwm_right = BASE_THROTTLE + pid_output; 

  // Apply safety limits
  pwm_left = constrain(pwm_left, MIN_PWM, MAX_PWM);
  pwm_right = constrain(pwm_right, MIN_PWM, MAX_PWM);

  // Write to hardware
  analogWrite(PIN_ENA, pwm_left);
  analogWrite(PIN_ENB, pwm_right);

  // ==========================================
  // 5. SERIAL COMMUNICATION (Non-blocking)
  // ==========================================
  static int print_counter = 0;
  if (print_counter++ >= 25) { // Print at 10Hz to prevent loop lag
    print_counter = 0;
    
    Serial.print(F("Ang:")); Serial.print(angle_roll, 1);
    Serial.print(F("\tL:")); Serial.print(pwm_left);
    Serial.print(F("\tR:")); Serial.print(pwm_right);
    Serial.print(F("\tP:")); Serial.print(Kp, 1);
    Serial.print(F("\tD:")); Serial.println(Kd, 1);
    
    // Check for tuning commands
    if (Serial.available() > 0) {
      String input = Serial.readStringUntil('\n');
      input.trim();
      
      // Spacebar (Randomizer)
      if (input == "") {
        Kp = random(10, 50) / 10.0; // Random P between 1.0 and 5.0
        Kd = random(5, 20) / 10.0;  // Random D between 0.5 and 2.0
        Ki = 0.0; 
        pid_i = 0; // Reset integral
        Serial.print(F("\n>>> RANDOM PID - Kp: ")); Serial.print(Kp, 1);
        Serial.print(F(" Kd: ")); Serial.println(Kd, 1);
      } 
      // Manual Tuning
      else if (input.indexOf("P:") >= 0) {
        int p_idx = input.indexOf("P:") + 2;
        int i_idx = input.indexOf("I:");
        int d_idx = input.indexOf("D:");
        
        if (i_idx > 0 && d_idx > 0) {
          Kp = input.substring(p_idx, i_idx).toFloat();
          Ki = input.substring(i_idx + 2, d_idx).toFloat();
          Kd = input.substring(d_idx + 2).toFloat();
          pid_i = 0; // Reset integral on tune
          Serial.println(F("\n>>> PID UPDATED <<<"));
        }
      }
    }
  }
}