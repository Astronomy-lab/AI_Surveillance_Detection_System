#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

const char* ssid     = "Redmi Note 13 Pro 5G";
const char* password = "aditya06";

#define BUZZER_PIN 13
#define LED_PIN    14

// AI-Thinker ESP32-CAM pins
#define PWDN_GPIO_NUM  32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM   0
#define SIOD_GPIO_NUM  26
#define SIOC_GPIO_NUM  27
#define Y9_GPIO_NUM    35
#define Y8_GPIO_NUM    34
#define Y7_GPIO_NUM    39
#define Y6_GPIO_NUM    36
#define Y5_GPIO_NUM    21
#define Y4_GPIO_NUM    19
#define Y3_GPIO_NUM    18
#define Y2_GPIO_NUM     5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM  23
#define PCLK_GPIO_NUM  22

httpd_handle_t stream_httpd = NULL;
httpd_handle_t ctrl_httpd   = NULL;

// ---------- live video: http://IP:81/stream ----------
static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t *fb = NULL;
  char part[96];
  esp_err_t res = httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=frame");
  if (res != ESP_OK) return res;

  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) { res = ESP_FAIL; break; }
    res = httpd_resp_send_chunk(req, "--frame\r\n", 9);
    if (res == ESP_OK) {
      size_t n = snprintf(part, sizeof(part),
        "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
      res = httpd_resp_send_chunk(req, part, n);
    }
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
    if (res == ESP_OK) res = httpd_resp_send_chunk(req, "\r\n", 2);
    esp_camera_fb_return(fb);
    if (res != ESP_OK) break;
  }
  return res;
}

// ---------- alarm: http://IP/alarm?state=1 (or 0) ----------
static esp_err_t alarm_handler(httpd_req_t *req) {
  char query[32], val[4];
  if (httpd_req_get_url_query_str(req, query, sizeof(query)) == ESP_OK &&
      httpd_query_key_value(query, "state", val, sizeof(val)) == ESP_OK) {
    int on = atoi(val);
    digitalWrite(LED_PIN, on ? HIGH : LOW);
    digitalWrite(BUZZER_PIN, on ? HIGH : LOW);
  }
  httpd_resp_send(req, "OK", 2);
  return ESP_OK;
}

void startServers() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();

  config.server_port = 80;
  httpd_uri_t alarm_uri = {"/alarm", HTTP_GET, alarm_handler, NULL};
  if (httpd_start(&ctrl_httpd, &config) == ESP_OK)
    httpd_register_uri_handler(ctrl_httpd, &alarm_uri);

  config.server_port = 81;
  config.ctrl_port  += 1;
  httpd_uri_t stream_uri = {"/stream", HTTP_GET, stream_handler, NULL};
  if (httpd_start(&stream_httpd, &config) == ESP_OK)
    httpd_register_uri_handler(stream_httpd, &stream_uri);
}

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  camera_config_t c;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer   = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM; c.pin_d4 = Y6_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sscb_sda = SIOD_GPIO_NUM;   // if compile error, rename to pin_sccb_sda
  c.pin_sscb_scl = SIOC_GPIO_NUM;   // if compile error, rename to pin_sccb_scl
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size   = FRAMESIZE_VGA;   // 640x480
  c.jpeg_quality = 12;
  c.fb_count     = 2;
  c.grab_mode    = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&c) != ESP_OK) {
    Serial.println("Camera init failed");
    return;
  }

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi connected");
  startServers();
  Serial.print("Stream : http://"); Serial.print(WiFi.localIP()); Serial.println(":81/stream");
  Serial.print("Alarm  : http://"); Serial.print(WiFi.localIP()); Serial.println("/alarm?state=1");
}

void loop() { delay(1000); }
