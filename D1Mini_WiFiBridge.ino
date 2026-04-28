/*
 * D1Mini_WiFiBridge.ino — production
 * Mega Serial1 → D1 Mini Serial → POST 到 Render 雲端
 */
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClientSecure.h>

// ============================================================
// CONFIG
// ============================================================
const char* WIFI_SSID_HOME  = "Home XD4";
const char* WIFI_PASS_HOME  = "0933997111213";
const char* WIFI_SSID_PHONE = "JIPXV";
const char* WIFI_PASS_PHONE = "88888888";
const char* SERVER     = "https://chickentrainer-webranking.onrender.com";
const char* DEVICE_KEY = "CHICKEN_SECRET_2026";
#define WIFI_TIMEOUT_MS 20000
// ============================================================

#define LED LED_BUILTIN
char lineBuf[200];
uint8_t linePos = 0;

void blinkLED(int n, int ms) {
  for (int i = 0; i < n; i++) {
    digitalWrite(LED, LOW); delay(ms);
    digitalWrite(LED, HIGH); delay(ms);
  }
}

bool tryWiFi(const char* ssid, const char* pass) {
  Serial.print("[WiFi] try "); Serial.print(ssid); Serial.print(" ");
  WiFi.disconnect();
  delay(100);
  WiFi.begin(ssid, pass);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > WIFI_TIMEOUT_MS) {
      Serial.println(" [TIMEOUT]");
      return false;
    }
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("[WiFi] connected: "); Serial.println(WiFi.SSID());
  Serial.print("[IP] ");              Serial.println(WiFi.localIP());
  blinkLED(3, 150);
  return true;
}

bool connectWiFi() {
  WiFi.mode(WIFI_STA);
  // 先試家裡，連不上再試手機熱點
  if (tryWiFi(WIFI_SSID_HOME, WIFI_PASS_HOME)) return true;
  if (tryWiFi(WIFI_SSID_PHONE, WIFI_PASS_PHONE)) return true;
  Serial.println("[WiFi] all failed");
  return false;
}

void doUpload(int sc, int sv, int dr, int df) {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("SYNC_FAIL");
    return;
  }
  WiFiClientSecure client;
  client.setInsecure();
  client.setTimeout(45000);
  HTTPClient http;
  http.setTimeout(45000);
  String url = String(SERVER) + "/api/sync";
  if (!http.begin(client, url)) {
    Serial.println("SYNC_FAIL");
    return;
  }
  http.addHeader("Content-Type", "application/json");
  String body = "{\"name\":\"Device\",\"score\":";
  body += sc; body += ",\"survival\":"; body += sv;
  body += ",\"duration\":"; body += dr;
  body += ",\"difficulty\":\"";
  body += (df == 0 ? "EASY" : (df == 2 ? "HARD" : "NORMAL"));
  body += "\",\"device_key\":\""; body += DEVICE_KEY; body += "\"}";
  Serial.println("[POST] " + body);
  int code = http.POST(body);
  Serial.printf("[POST] code=%d\n", code);
  if (code == 200 || code == 201) {
    String resp = http.getString();
    Serial.println("[RESP] " + resp);
    int p = resp.indexOf("\"rank\":");
    int rank = (p >= 0) ? resp.substring(p + 7).toInt() : 0;
    Serial.printf("SYNC_OK:RANK:%d:NAME:Device:SCORE:%d\n", rank, sc);
    blinkLED(5, 80);
  } else {
    Serial.printf("[POST] err: %s\n", http.errorToString(code).c_str());
    Serial.println("SYNC_FAIL");
    blinkLED(2, 400);
  }
  http.end();
}

void setup() {
  pinMode(LED, OUTPUT);
  digitalWrite(LED, HIGH);
  Serial.begin(9600);
  delay(2000);
  Serial.println();
  Serial.println("=== Chicken WiFi Bridge ===");
  Serial.printf("Heap: %d\n", ESP.getFreeHeap());
  connectWiFi();
  Serial.println("READY");
}

void loop() {
  // Read line from Serial (Mega 送來的 SCORE:xx,SURV:xx,DUR:xx,DIFF:xx,NAME:xxx)
  while (Serial.available()) {
    char c = Serial.read();
    Serial.printf("[byte] 0x%02X '%c'\n", (uint8_t)c, (c >= 32 && c < 127) ? c : '?');
    if (c == '\n' || c == '\r') {
      if (linePos > 0) {
        lineBuf[linePos] = 0;
        Serial.print("[RX] "); Serial.println(lineBuf);
        int sc=0,sv=0,dr=0,df=1;
        char *p;
        if ((p=strstr(lineBuf,"SCORE:"))) sc=atoi(p+6);
        if ((p=strstr(lineBuf,"SURV:")))  sv=atoi(p+5);
        if ((p=strstr(lineBuf,"DUR:")))   dr=atoi(p+4);
        if ((p=strstr(lineBuf,"DIFF:")))  df=atoi(p+5);
        doUpload(sc, sv, dr, df);
        linePos = 0;
      }
    } else if (linePos < sizeof(lineBuf) - 1) {
      lineBuf[linePos++] = c;
    }
  }
  // 健康檢查
  static unsigned long lastCheck = 0;
  if (millis() - lastCheck > 60000) {
    lastCheck = millis();
    if (WiFi.status() != WL_CONNECTED) connectWiFi();
  }
}
