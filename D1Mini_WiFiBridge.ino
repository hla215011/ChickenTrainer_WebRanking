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
// 只連手機熱點（JIPX7）— 比賽現場開熱點即可
const char* WIFI_SSID_PHONE = "JIPX7";
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
  // 只連手機熱點
  if (tryWiFi(WIFI_SSID_PHONE, WIFI_PASS_PHONE)) return true;
  Serial.println("[WiFi] phone hotspot not found");
  return false;
}

// 從 server 抓當前時間，回傳 TIME:YYYY-MM-DD HH:MM
void fetchTime() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("TIME_FAIL");
    return;
  }
  WiFiClientSecure client;
  client.setInsecure();
  client.setTimeout(15000);
  HTTPClient http;
  http.setTimeout(15000);
  String url = String(SERVER) + "/api/time";
  if (!http.begin(client, url)) { Serial.println("TIME_FAIL"); return; }
  int code = http.GET();
  if (code == 200) {
    String resp = http.getString();
    int p = resp.indexOf("\"time\":");
    if (p >= 0) {
      int q = resp.indexOf("\"", p + 8);
      String t = resp.substring(p + 8, q);
      Serial.print("TIME:"); Serial.println(t);
    } else {
      Serial.println("TIME_FAIL");
    }
  } else {
    Serial.println("TIME_FAIL");
  }
  http.end();
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
    // 解析 rename_code & rename_pin
    // ⚠ Python json.dumps() 預設輸出 `"key": "value"` (冒號後有空格)，
    //   所以不能寫死 `"key":"value"` 找 — 改成「找 key → 跳到下一個 " → 讀到下個 "」
    //   這樣有沒有空白、tab、換行都不影響
    String rc = "", rp = "";
    auto extractStr = [&](const char* key) -> String {
      int p = resp.indexOf(key);
      if (p < 0) return "";
      int o = resp.indexOf('"', p + strlen(key));   // value 的開引號
      if (o < 0) return "";
      int c = resp.indexOf('"', o + 1);             // value 的關引號
      if (c <= o) return "";
      return resp.substring(o + 1, c);
    };
    rc = extractStr("\"rename_code\"");
    rp = extractStr("\"rename_pin\"");
    Serial.printf("SYNC_OK:RANK:%d:CODE:%s:PIN:%s\n", rank, rc.c_str(), rp.c_str());
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
  // 開機即發 heartbeat，讓 Mega 左上角圖示立刻反應
  Serial.println(WiFi.status() == WL_CONNECTED ? "WIFI:OK" : "WIFI:NO");
  Serial.println("READY");
}

void loop() {
  // Read line from Serial (Mega 送來的 SCORE:xx,SURV:xx,DUR:xx,DIFF:xx,NAME:xxx)
  while (Serial.available()) {
    char c = Serial.read();
    // [byte] 0xXX debug 已移除：每收一個 byte 都會回傳給 Mega 反而把 RX 灌爆
    if (c == '\n' || c == '\r') {
      if (linePos > 0) {
        lineBuf[linePos] = 0;
        Serial.print("[RX] "); Serial.println(lineBuf);
        // 處理時間查詢指令 TIME?
        if (strncmp(lineBuf, "TIME?", 5) == 0) {
          fetchTime();
        } else {
          int sc=0,sv=0,dr=0,df=1;
          char *p;
          if ((p=strstr(lineBuf,"SCORE:"))) sc=atoi(p+6);
          if ((p=strstr(lineBuf,"SURV:")))  sv=atoi(p+5);
          if ((p=strstr(lineBuf,"DUR:")))   dr=atoi(p+4);
          if ((p=strstr(lineBuf,"DIFF:")))  df=atoi(p+5);
          doUpload(sc, sv, dr, df);
        }
        linePos = 0;
      }
    } else if (linePos < sizeof(lineBuf) - 1) {
      lineBuf[linePos++] = c;
    }
  }
  // 健康檢查 + WiFi heartbeat（每 10 秒推送 WIFI:OK / WIFI:NO 給 Mega 顯示左上角圖示）
  static unsigned long lastWifiPing = 0;
  if (millis() - lastWifiPing > 10000) {
    lastWifiPing = millis();
    bool ok = (WiFi.status() == WL_CONNECTED);
    Serial.println(ok ? "WIFI:OK" : "WIFI:NO");
    // 順便：60 秒沒連 WiFi 就嘗試重連（從原本 60s 心跳改成這裡）
    static uint8_t reconnectCounter = 0;
    if (!ok) {
      reconnectCounter++;
      if (reconnectCounter >= 6) {  // 6 × 10s = 60s
        reconnectCounter = 0;
        connectWiFi();
      }
    } else {
      reconnectCounter = 0;
    }
  }
}
