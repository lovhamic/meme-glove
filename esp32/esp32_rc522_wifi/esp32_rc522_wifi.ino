/*
 * ESP32 RC522 NFC/RFID Tag Reader with Wi-Fi HTTP Transmitter
 * -------------------------------------------------------------
 * Hardware Wiring (RC522 to ESP32):
 *   RC522 3.3V  -> ESP32 3.3V  (DO NOT connect to 5V!)
 *   RC522 RST   -> ESP32 GPIO 22
 *   RC522 GND   -> ESP32 GND
 *   RC522 MISO  -> ESP32 GPIO 19
 *   RC522 MOSI  -> ESP32 GPIO 23
 *   RC522 SCK   -> ESP32 GPIO 18
 *   RC522 SDA/SS-> ESP32 GPIO 5
 *
 * Required Arduino Libraries:
 *   1. "MFRC522" by GithubCommunity / Miguel Balboa (Install via Library Manager)
 *   2. "WiFi" (Built into ESP32 board package)
 *   3. "HTTPClient" (Built into ESP32 board package)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>

// ================= USER CONFIGURATION =================
const char* WIFI_SSID     = "(TinkerSpace)";       // Replace with your Wi-Fi Name (2.4GHz)
const char* WIFI_PASSWORD = "123tinkerspace";   // Replace with your Wi-Fi Password

// Replace with your PC's IP address (shown when you run run_server.bat)
const char* SERVER_IP     = "192.168.1.138";
const int   SERVER_PORT   = 5000;

// Server endpoint path
const char* SERVER_PATH   = "/tag";
// ======================================================

// RC522 Pin Definitions
#define SS_PIN    5   // SDA / SS Pin
#define RST_PIN   22  // Reset Pin

MFRC522 mfrc522(SS_PIN, RST_PIN);

// Debounce variables to avoid repeated triggers while card is held on reader
String lastUID = "";
unsigned long lastReadTime = 0;
const unsigned long DEBOUNCE_DELAY_MS = 2500; // 2.5 seconds between reading the same card

// Function prototypes
void connectToWiFi();
void sendTagToServer(String uid);

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println();
  Serial.println("==========================================");
  Serial.println(" ESP32 RC522 NFC/RFID Wi-Fi Music Player ");
  Serial.println("==========================================");

  // Initialize SPI bus and RC522 reader
  SPI.begin(); // Standard ESP32 SPI: SCK=18, MISO=19, MOSI=23, SS=5
  mfrc522.PCD_Init();
  delay(50);
  
  // Verify RC522 communication
  byte version = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
  Serial.print("RC522 Firmware Version: 0x");
  Serial.println(version, HEX);
  if (version == 0x00 || version == 0xFF) {
    Serial.println("[WARNING] RC522 not detected! Please check your wiring connections.");
  } else {
    Serial.println("[OK] RC522 Reader initialized successfully.");
  }

  // Connect to Wi-Fi
  connectToWiFi();

  Serial.println("\n[READY] Tap an NFC/RFID card on the RC522 reader...\n");
}

void loop() {
  // Ensure Wi-Fi stays connected
  if (WiFi.status() != WL_CONNECTED) {
    connectToWiFi();
  }

  // Look for new cards
  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }

  // Select one of the cards
  if (!mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // Extract UID in hex format (e.g., "A1B2C3D4")
  String currentUID = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) {
      currentUID += "0";
    }
    currentUID += String(mfrc522.uid.uidByte[i], HEX);
  }
  currentUID.toUpperCase();

  unsigned long currentTime = millis();

  // Debounce check: ignore if same card was scanned very recently
  if (currentUID != lastUID || (currentTime - lastReadTime > DEBOUNCE_DELAY_MS)) {
    lastUID = currentUID;
    lastReadTime = currentTime;

    Serial.println("------------------------------------------");
    Serial.print("[CARD DETECTED] UID: ");
    Serial.println(currentUID);
    
    // Send UID to Python music server over Wi-Fi
    sendTagToServer(currentUID);
    Serial.println("------------------------------------------");
  }

  // Halt PICC and stop encryption on PCD
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  
  delay(100);
}

void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("Connecting to Wi-Fi '");
  Serial.print(WIFI_SSID);
  Serial.print("'");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[Wi-Fi CONNECTED]");
    Serial.print("ESP32 IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Target Music Server: http://");
    Serial.print(SERVER_IP);
    Serial.print(":");
    Serial.print(SERVER_PORT);
    Serial.println(SERVER_PATH);
  } else {
    Serial.println("\n[ERROR] Wi-Fi Connection failed! Please verify credentials.");
  }
}

void sendTagToServer(String uid) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP ERROR] Cannot send: Wi-Fi not connected.");
    return;
  }

  HTTPClient http;
  String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + String(SERVER_PATH);

  Serial.print("Sending POST request to: ");
  Serial.println(url);

  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  // Create JSON payload
  String jsonPayload = "{\"uid\":\"" + uid + "\"}";

  int httpResponseCode = http.POST(jsonPayload);

  if (httpResponseCode > 0) {
    Serial.print("[HTTP SUCCESS] Response Code: ");
    Serial.println(httpResponseCode);
    String response = http.getString();
    Serial.print("[SERVER RESPONSE] ");
    Serial.println(response);
  } else {
    Serial.print("[HTTP ERROR] Request failed, error code: ");
    Serial.println(httpResponseCode);
    Serial.println("Hint: Make sure the Python server is running and Windows Firewall allows port " + String(SERVER_PORT));
  }

  http.end();
}
