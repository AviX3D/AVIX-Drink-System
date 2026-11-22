/*
  AVIX Drink System — firmware V2 (Arduino Nano)
  AVIX 3D — avix3d.com

  Pompe péristaltique via L298N mini + bouton du capot + LED WS2812B (capot V2).
  Compatible avec l'appli Windows "AVIX Drink System" (115200 bauds) :
    '1' = pompe ON   '0' = pompe OFF   '2' = pompe inversée (purge)
  Commandes texte (Moniteur série, fin de ligne "Nouvelle ligne") :
    ON:200  OFF  REV:200  SPD:150  PING  STATUS

  Bibliothèque à installer : Adafruit NeoPixel (Gestionnaire de bibliothèques).
  Carte : Arduino Nano (ATmega328P). Pour un clone CH340 : processeur
  "ATmega328P (Old Bootloader)" si le téléversement échoue.
*/

#include <Adafruit_NeoPixel.h>

// ---------------- CONFIG ----------------
// Capot V2 avec bouton + LED : laisser à 1.  Capot V2 simple : mettre les deux à 0.
#define HAS_BUTTON 1
#define HAS_LED    1

const uint8_t PIN_IN1    = 3;   // D3 -> L298N mini IN1 (PWM : vitesse)
const uint8_t PIN_IN2    = 4;   // D4 -> L298N mini IN2 (tout ou rien : sens)
const uint8_t PIN_BUTTON = 2;   // D2 -> bouton 12x12 du capot -> GND (pull-up interne)
const uint8_t PIN_LED    = 6;   // D6 -> résistance 330 ohms -> DIN de la WS2812B

const long     BAUD         = 115200;
uint8_t        pumpSpeed    = 255;     // vitesse par défaut (0-255)
const uint8_t  PURGE_SPEED  = 255;
const uint32_t MAX_RUN_MS   = 20000;   // sécurité : coupure auto après 20 s en continu
const uint32_t DEBOUNCE_MS  = 25;
const uint8_t  LED_BRIGHT   = 80;      // luminosité max de la LED (0-255)
// ----------------------------------------

enum PumpState : uint8_t { PUMP_OFF, PUMP_ON, PUMP_REV };
PumpState pumpState = PUMP_OFF;
uint32_t  pumpStartMs = 0;
uint32_t  faultUntilMs = 0;            // clignotement rouge après coupure de sécurité
bool      buttonHeld = false;          // la pompe tourne parce que le bouton du capot est appuyé

Adafruit_NeoPixel led(1, PIN_LED, NEO_GRB + NEO_KHZ800);

// ---------- pompe ----------
void pumpApply() {
  switch (pumpState) {
    case PUMP_ON:  analogWrite(PIN_IN1, pumpSpeed);   digitalWrite(PIN_IN2, LOW);  break;
    case PUMP_REV:                                   // IN2 n'est pas PWM : IN2 haut + PWM inversé sur IN1
      digitalWrite(PIN_IN2, HIGH);
      if (PURGE_SPEED >= 255) digitalWrite(PIN_IN1, LOW); else analogWrite(PIN_IN1, 255 - PURGE_SPEED);
      break;
    default:       digitalWrite(PIN_IN1, LOW);        digitalWrite(PIN_IN2, LOW);  break;
  }
}

void pumpSet(PumpState s, const char *src) {
  if (s == pumpState) return;
  pumpState = s;
  pumpStartMs = millis();
  pumpApply();
  Serial.print(F("PUMP:"));
  Serial.print(s == PUMP_ON ? F("ON") : s == PUMP_REV ? F("REV") : F("OFF"));
  Serial.print(F(" ("));
  Serial.print(src);
  Serial.println(F(")"));
}

// ---------- LED ----------
void ledColor(uint8_t r, uint8_t g, uint8_t b) {
#if HAS_LED
  led.setPixelColor(0, led.Color(r, g, b));
  led.show();
#endif
}

void ledUpdate() {
#if HAS_LED
  static uint32_t last = 0;
  uint32_t now = millis();
  if (now - last < 20) return;          // 50 Hz suffit
  last = now;
  if ((int32_t)(faultUntilMs - now) > 0) {             // défaut : rouge clignotant
    bool on = (now / 150) % 2;
    ledColor(on ? LED_BRIGHT : 0, 0, 0);
  } else if (pumpState == PUMP_ON) {
    ledColor(0, LED_BRIGHT, 0);                         // vert : ça coule
  } else if (pumpState == PUMP_REV) {
    ledColor(0, LED_BRIGHT / 2, LED_BRIGHT);            // cyan : purge
  } else {                                              // repos : jaune AVIX qui respire
    uint16_t t = (now / 8) % 512;
    uint8_t k = t < 256 ? t : 511 - t;
    uint8_t lvl = 6 + (uint16_t)k * (LED_BRIGHT / 3) / 255;
    ledColor(lvl, lvl, 0);                              // #C1C107 : jaune AVIX
  }
#endif
}

void ledBoot() {
#if HAS_LED
  led.begin();
  led.setBrightness(255);
  const uint8_t seq[3][3] = {{LED_BRIGHT, 0, 0}, {0, LED_BRIGHT, 0}, {0, 0, LED_BRIGHT}};
  for (uint8_t i = 0; i < 3; i++) { ledColor(seq[i][0], seq[i][1], seq[i][2]); delay(150); }
  ledColor(0, 0, 0);
#endif
}

// ---------- bouton du capot ----------
void buttonUpdate() {
#if HAS_BUTTON
  static bool stable = HIGH, lastRead = HIGH;
  static uint32_t tChange = 0;
  bool r = digitalRead(PIN_BUTTON);
  if (r != lastRead) { lastRead = r; tChange = millis(); }
  if (millis() - tChange < DEBOUNCE_MS || r == stable) return;
  stable = r;
  if (stable == LOW) {                       // appui : la pompe tourne tant qu'on maintient
    Serial.println(F("BTN:1"));
    if (pumpState == PUMP_OFF) { buttonHeld = true; pumpSet(PUMP_ON, "bouton"); }
  } else {                                   // relâché
    Serial.println(F("BTN:0"));
    if (buttonHeld) { buttonHeld = false; pumpSet(PUMP_OFF, "bouton"); }
  }
#endif
}

// ---------- série ----------
char line[24];
uint8_t lineLen = 0;

void handleLine(char *s) {
  for (char *p = s; *p; p++) if (*p >= 'a' && *p <= 'z') *p -= 32;   // majuscules
  if (!strcmp(s, "OFF")) { buttonHeld = false; pumpSet(PUMP_OFF, "serie"); }
  else if (!strncmp(s, "ON", 2)) {
    if (s[2] == ':') pumpSpeed = constrain(atoi(s + 3), 0, 255);
    buttonHeld = false; pumpSet(PUMP_ON, "serie");
    if (pumpState == PUMP_ON) pumpApply();             // prend la nouvelle vitesse
  }
  else if (!strncmp(s, "REV", 3)) { buttonHeld = false; pumpSet(PUMP_REV, "serie"); }
  else if (!strncmp(s, "SPD:", 4)) { pumpSpeed = constrain(atoi(s + 4), 0, 255); pumpApply(); Serial.println(F("OK:SPD")); }
  else if (!strcmp(s, "PING")) Serial.println(F("PONG"));
  else if (!strcmp(s, "STATUS")) {
    Serial.print(F("STATUS pompe=")); Serial.print(pumpState);
    Serial.print(F(" vitesse=")); Serial.println(pumpSpeed);
  }
  else if (*s) { Serial.print(F("ERR:")); Serial.println(s); }
}

void serialUpdate() {
  while (Serial.available()) {
    char c = Serial.read();
    if (lineLen == 0) {                       // protocole 1 caractère de l'appli Windows
      if (c == '1') { buttonHeld = false; pumpSet(PUMP_ON, "appli"); continue; }
      if (c == '0') { buttonHeld = false; pumpSet(PUMP_OFF, "appli"); continue; }
      if (c == '2') { buttonHeld = false; pumpSet(PUMP_REV, "appli"); continue; }
    }
    if (c == '\n' || c == '\r') {
      if (lineLen) { line[lineLen] = 0; handleLine(line); lineLen = 0; }
    } else if (lineLen < sizeof(line) - 1) {
      line[lineLen++] = c;
    }
  }
}

// ---------- sécurité ----------
void safetyUpdate() {
  if (pumpState != PUMP_OFF && millis() - pumpStartMs > MAX_RUN_MS) {
    buttonHeld = false;
    pumpSet(PUMP_OFF, "securite");
    Serial.println(F("WARN:coupure securite (20 s en continu)"));
    faultUntilMs = millis() + 3000;
  }
}

void setup() {
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pumpApply();                                // pompe arrêtée dès le démarrage
#if HAS_BUTTON
  pinMode(PIN_BUTTON, INPUT_PULLUP);
#endif
  Serial.begin(BAUD);
  ledBoot();
  Serial.println(F("=== AVIX DRINK SYSTEM V2 - pret ==="));
}

void loop() {
  serialUpdate();
  buttonUpdate();
  safetyUpdate();
  ledUpdate();
}
