/*
 * D1Mini_WiFiBridge.ino
 * WiFi bridge for Chicken Trainer ranking system.
 * Board: ESP8266 D1 Mini
 *
 * Reads score data from Arduino Mega over Serial,
 * POSTs to the ranking server, and optionally returns
 * the top leaderboard entries back over Serial.
 *
 * Dependencies (install via Arduino Library Manager):
 *   - ESP8266WiFi      (bundled with ESP8266 core)
 *   - ESP8266HTTPClient (bundled with ESP8266 core)
 *   - ArduinoJson v6.x  (by Benoit Blanchon)
 */

#include <ESP8266WiFi.h>
#include <ESP8266WiFiMulti.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>

// ============================================================
// === CONFIG (change these) ===
// ============================================================
// 多 WiFi 模式 — 開機自動掃描，連最強的那個
// 加新 WiFi 只要在 setup() 裡 wifiMulti.addAP(...) 多加一行
const char* WIFI_SSID_HOME = "Home XD4";
const char* WIFI_PASS_HOME = "0933997111213";

const char* WIFI_SSID_PHONE = "JIPXV";               // 比賽用手機熱點
const char* WIFI_PASS_PHONE = "88888888";

const char* SERVER_IP     = "192.168.89.32";        // Mac LAN IP（家裡用）
const int   SERVER_PORT   = 8080;
const char* DEVICE_KEY    = "CHICKEN_SECRET_2026";

ESP8266WiFiMulti wifiMulti;
// ============================================================

// Built-in LED pin for D1 Mini
#define LED_PIN LED_BUILTIN

// Serial baud rate (must match Arduino Mega)
#define SERIAL_BAUD 9600

// How long to try WiFi connection before giving up (ms)
#define WIFI_TIMEOUT_MS 20000

// Buffer for incoming serial line
static char lineBuf[256];
static uint8_t linePos = 0;

// ============================================================
// Helpers
// ============================================================

void blinkLED(int times, int delayMs = 100) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, LOW);   // active LOW on D1 Mini
    delay(delayMs);
    digitalWrite(LED_PIN, HIGH);
    delay(delayMs);
  }
}

String buildURL(const char* endpoint) {
  String url = "http://";
  url += SERVER_IP;
  url += ":";
  url += SERVER_PORT;
  url += endpoint;
  return url;
}

// Convert numeric difficulty to string
// 0 = EASY, 1 = NORMAL, 2 = HARD
String diffToStr(int diff) {
  if (diff == 0) return "EASY";
  if (diff == 2) return "HARD";
  return "NORMAL";
}

// ============================================================
// WiFi management
// ============================================================

bool connectWiFi() {
  Serial.println("[WiFi] Scanning known networks...");
  WiFi.mode(WIFI_STA);
  // 加入所有已知 WiFi（依信號強度自動選最強）
  wifiMulti.addAP(WIFI_SSID_HOME,  WIFI_PASS_HOME);
  wifiMulti.addAP(WIFI_SSID_PHONE, WIFI_PASS_PHONE);

  unsigned long start = millis();
  while (wifiMulti.run() != WL_CONNECTED) {
    if (millis() - start > WIFI_TIMEOUT_MS) {
      Serial.println("\n[WiFi] All networks unreachable!");
      return false;
    }
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("[WiFi] Connected to: ");
  Serial.println(WiFi.SSID());
  Serial.print("[WiFi] IP: ");
  Serial.println(WiFi.localIP());
  blinkLED(3, 150);
  return true;
}

void ensureWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Reconnecting via wifiMulti...");
    unsigned long start = millis();
    while (wifiMulti.run() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
      delay(500);
      Serial.print(".");
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("[WiFi] Reconnected to: ");
      Serial.println(WiFi.SSID());
    } else {
      Serial.println("[WiFi] Reconnect failed.");
    }
  }
}

// ============================================================
// Sync score to server
// Returns the global rank (1-based), or 0 on failure
// ============================================================

int syncScore(const String& name, int score, int survival, int duration, int diffNum) {
  ensureWiFi();
  if (WiFi.status() != WL_CONNECTED) return 0;

  WiFiClient client;
  HTTPClient http;

  String url = buildURL("/api/sync");
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");

  // Build JSON body
  StaticJsonDocument<256> doc;
  doc["name"]       = name;
  doc["score"]      = score;
  doc["survival"]   = survival;
  doc["duration"]   = duration;
  doc["difficulty"] = diffToStr(diffNum);
  doc["device_key"] = DEVICE_KEY;

  String body;
  serializeJson(doc, body);

  Serial.println("[HTTP] POST /api/sync  body: " + body);
  int httpCode = http.POST(body);

  int rank = 0;
  if (httpCode == 200 || httpCode == 201) {
    String response = http.getString();
    Serial.println("[HTTP] Response: " + response);

    StaticJsonDocument<256> resp;
    DeserializationError err = deserializeJson(resp, response);
    if (!err && resp["ok"]) {
      rank = resp["rank"] | 0;
      blinkLED(5, 80);  // success blink
      Serial.print("[SYNC] OK — rank: ");
      Serial.println(rank);
    }
  } else {
    Serial.print("[HTTP] Error code: ");
    Serial.println(httpCode);
    blinkLED(2, 400);  // error blink (slow)
  }
  http.end();
  return rank;
}

// ============================================================
// Fetch leaderboard and send back to Mega
// Format: RANK1:Name:Score\n  RANK2:Name:Score\n  ...
// ============================================================

void fetchAndSendLeaderboard(int limit = 5) {
  ensureWiFi();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("LEADERBOARD_FAIL");
    return;
  }

  WiFiClient client;
  HTTPClient http;

  String url = buildURL("/api/leaderboard");
  url += "?limit=";
  url += limit;

  http.begin(client, url);
  int httpCode = http.GET();

  if (httpCode == 200) {
    String response = http.getString();
    Serial.println("[HTTP] Leaderboard: " + response);

    // Parse array
    StaticJsonDocument<1024> doc;
    DeserializationError err = deserializeJson(doc, response);
    if (!err && doc.is<JsonArray>()) {
      JsonArray arr = doc.as<JsonArray>();
      for (JsonObject entry : arr) {
        int    r    = entry["rank"]  | 0;
        String n    = entry["name"].as<String>();
        int    s    = entry["score"] | 0;
        // Send to Mega via Serial
        // Format: RANK1:PlayerName:95
        Serial.print("RANK");
        Serial.print(r);
        Serial.print(":");
        Serial.print(n);
        Serial.print(":");
        Serial.println(s);
      }
    }
  } else {
    Serial.print("[HTTP] Leaderboard error: ");
    Serial.println(httpCode);
  }
  http.end();
}

// ============================================================
// Parse incoming serial line from Mega
//
// Expected format (newline-terminated):
//   SCORE:95,SURV:88,DUR:72,DIFF:1,NAME:Johnny
//
// Fields:
//   SCORE  — integer 0-100
//   SURV   — survival rate 0-100
//   DUR    — duration in seconds
//   DIFF   — 0=EASY 1=NORMAL 2=HARD
//   NAME   — player name string
// ============================================================

bool parseLine(const char* line, String& nameOut, int& scoreOut, int& survOut, int& durOut, int& diffOut) {
  // Make a mutable copy
  char buf[256];
  strncpy(buf, line, sizeof(buf) - 1);
  buf[sizeof(buf)-1] = '\0';

  nameOut  = "Player";
  scoreOut = 0;
  survOut  = 0;
  durOut   = 0;
  diffOut  = 1;

  bool hasScore = false;

  char* token = strtok(buf, ",");
  while (token != nullptr) {
    String tok = String(token);
    tok.trim();

    int colonIdx = tok.indexOf(':');
    if (colonIdx < 0) { token = strtok(nullptr, ","); continue; }

    String key = tok.substring(0, colonIdx);
    String val = tok.substring(colonIdx + 1);
    key.trim(); val.trim();
    key.toUpperCase();

    if (key == "SCORE") { scoreOut = val.toInt(); hasScore = true; }
    else if (key == "SURV")  survOut  = val.toInt();
    else if (key == "DUR")   durOut   = val.toInt();
    else if (key == "DIFF")  diffOut  = val.toInt();
    else if (key == "NAME")  nameOut  = val;

    token = strtok(nullptr, ",");
  }
  return hasScore;
}

// ============================================================
// Setup
// ============================================================

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);  // LED off (active LOW)

  Serial.begin(SERIAL_BAUD);
  delay(500);
  Serial.println();
  Serial.println("=== Chicken Trainer WiFi Bridge ===");
  Serial.print("Firmware built: ");
  Serial.println(__DATE__ " " __TIME__);

  // Initial WiFi connection
  if (!connectWiFi()) {
    Serial.println("[WARN] Starting without WiFi. Will retry on first sync.");
  }

  Serial.println("[READY] Waiting for data from Mega...");
  Serial.println("[FORMAT] SCORE:95,SURV:88,DUR:72,DIFF:1,NAME:Johnny");
}

// ============================================================
// Loop
// ============================================================

void loop() {
  // Read bytes from Serial (from Mega)
  while (Serial.available()) {
    char c = (char)Serial.read();

    if (c == '\n' || c == '\r') {
      if (linePos > 0) {
        lineBuf[linePos] = '\0';
        linePos = 0;

        String line = String(lineBuf);
        line.trim();

        if (line.length() == 0) continue;

        Serial.println("[RX] " + line);

        // Special command: request leaderboard
        if (line.equalsIgnoreCase("LEADERBOARD")) {
          fetchAndSendLeaderboard(5);
          continue;
        }

        // Parse score data
        String name;
        int score, surv, dur, diff;
        if (parseLine(lineBuf, name, score, surv, dur, diff)) {
          int rank = syncScore(name, score, surv, dur, diff);
          if (rank > 0) {
            // Send result back to Mega
            Serial.print("SYNC_OK:RANK:");
            Serial.print(rank);
            Serial.print(":NAME:");
            Serial.print(name);
            Serial.print(":SCORE:");
            Serial.println(score);
          } else {
            Serial.println("SYNC_FAIL");
          }
        } else {
          Serial.println("[WARN] Could not parse line: " + line);
        }
      }
    } else {
      if (linePos < sizeof(lineBuf) - 1) {
        lineBuf[linePos++] = c;
      }
    }
  }

  // Periodic WiFi health check (every 30 seconds)
  static unsigned long lastCheck = 0;
  if (millis() - lastCheck > 30000) {
    lastCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WiFi] Lost connection, reconnecting...");
      ensureWiFi();
    }
  }

  delay(10);
}
