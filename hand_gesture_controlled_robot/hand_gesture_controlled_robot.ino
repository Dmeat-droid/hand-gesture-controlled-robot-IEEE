#include <WiFi.h>
#include <WiFiUdp.h>

// ================= KONFIGURASI =================
// Konfigurasi WiFi
const char* ssid = "calon maba itb";
const char* password = "kanjutngapungg";

// Konfigurasi UDP
WiFiUDP udp;
const unsigned int localUdpPort = 4210;
char incomingPacket[255];

// Pin L298N (Sesuai konfigurasi kamu)
const int ENA = 14;
const int IN1 = 27;
const int IN2 = 26;

const int IN3 = 25;
const int IN4 = 33;
const int ENB = 32;

// Safety Watchdog (Mobil berhenti jika hilang sinyal > 0.5 detik)
unsigned long lastPacketTime = 0;
const unsigned long TIMEOUT_MS = 500; 
// ===============================================

void setup() {
  Serial.begin(115200);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);

  stopMotors();

  WiFi.begin(ssid, password);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP()); // <-- Pastikan IP di Python sama dengan ini

  udp.begin(localUdpPort);
}

// Fungsi Low Level Motor (Logika kamu tetap dipakai)
void setMotorA(int speed) {
  if (speed > 0) {
    digitalWrite(IN1, HIGH);
    digitalWrite(IN2, LOW);
    analogWrite(ENA, speed);
  } else if (speed < 0) {
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, HIGH);
    analogWrite(ENA, abs(speed));
  } else {
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, LOW);
    analogWrite(ENA, 0);
  }
}

void setMotorB(int speed) {
  if (speed > 0) {
    digitalWrite(IN3, HIGH);
    digitalWrite(IN4, LOW);
    analogWrite(ENB, speed);
  } else if (speed < 0) {
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, HIGH);
    analogWrite(ENB, abs(speed));
  } else {
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, LOW);
    analogWrite(ENB, 0);
  }
}

void stopMotors() {
  setMotorA(0);
  setMotorB(0);
}

// --- FUNGSI GERAK (Sekarang menerima input 'pwm') ---

void moveForward(int pwm) {
  setMotorA(pwm);
  setMotorB(pwm);
}

void moveBackward(int pwm) {
  // Beri nilai negatif agar fungsi setMotor membalik arah
  setMotorA(-pwm);
  setMotorB(-pwm);
}

void turnLeft(int pwm) {
  // Roda Kiri pelan/berhenti, Roda Kanan jalan (Pivot)
  // Atau kamu bisa pakai logika: setMotorA(pwm/2); setMotorB(pwm);
  setMotorA(pwm / 4); // Kurangi speed roda dalam
  setMotorB(pwm);
}

void turnRight(int pwm) {
  setMotorA(pwm);
  setMotorB(pwm / 4); // Kurangi speed roda dalam
}

void loop() {
  int packetSize = udp.parsePacket();
  
  if (packetSize) {
    int len = udp.read(incomingPacket, 255);
    if (len > 0) incomingPacket[len] = '\0';
    
    String data = String(incomingPacket);
    lastPacketTime = millis(); // Reset timer watchdog

    // --- PARSING DATA (Format: "CMD:SPEED") ---
    char cmd = data.charAt(0); // Ambil karakter pertama (F, B, L, R, S)
    int speed = 0;

    // Cek apakah ada tanda ':'
    int separatorIndex = data.indexOf(':');
    if (separatorIndex != -1) {
       // Ambil angka di belakang titik dua
      //  speed = data.substring(separatorIndex + 1).toInt();
      speed = 255;
    } else {
       // Jika Python lama (cuma kirim karakter), pakai speed default
       speed = 255; 
    }

    // aktifkan program dibawah bila ingin mengaktifkan pengatur kecepatan
    // Limit speed 0-255
    // speed = constrain(speed, 0, 255);

    // Debugging (Bisa dihapus kalau menuhin serial monitor)
    // Serial.print(cmd); Serial.print(" -> "); Serial.println(speed);

    // Eksekusi
    if (cmd == 'S' || cmd == 's') stopMotors();
    else if (cmd == 'F' || cmd == 'f') moveForward(speed);
    else if (cmd == 'B' || cmd == 'b') moveBackward(speed);
    else if (cmd == 'L' || cmd == 'l') turnLeft(speed);
    else if (cmd == 'R' || cmd == 'r') turnRight(speed);
  }

  // --- SAFETY WATCHDOG ---
  // Jika tidak ada data masuk selama 500ms (Python crash/WiFi putus), motor stop
  if (millis() - lastPacketTime > TIMEOUT_MS) {
    stopMotors();
  }
  
  // Delay kecil agar ESP tidak panas/hang
  delay(1); 
}