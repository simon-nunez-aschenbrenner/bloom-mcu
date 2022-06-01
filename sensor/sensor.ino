// BLOOM Sensor
// For Adafruit Feather 32u4 LoRa (RFM9x)
// Author: Simon Aschenbrenner

// Using AirSpayce's RadioHead library by Mike McCauley
// http://www.airspayce.com/mikem/arduino/RadioHead/index.html
// (27.10.21, GNU GPL v2)

// Uncomment the following line for serial monitor output and comment it for battery operation
// #define DEBUG

#include <RH_RF95.h>
#include <RHReliableDatagram.h>

// Pin configuration
#define MOISTURE_IN 18
#define VBAT_IN A9

#define ADDRBIT_0_IN 2
#define ADDRBIT_0_OUT 3
#define ADDRBIT_1_IN 5
#define ADDRBIT_1_OUT 6
#define ADDRBIT_2_IN 10
#define ADDRBIT_2_OUT 11
#define ADDRBIT_3_IN 12
#define ADDRBIT_3_OUT 13 // Also LED pin

#define RF95_CS 8
#define RF95_INT 7
#define RF95_RST 4

#define RF95_FREQ 868.0
#define RF95_POW 23 // From 5 to 23 dBm

// Measurement configuration
#define MIN_RAW_MOISTURE_VALUE 380 // Submerged in tap water
#define MAX_RAW_MOISTURE_VALUE 900 // Dry in the air
#define MIN_RAW_BATTERY_VALUE 496  // 3.2V
#define MAX_RAW_BATTERY_VALUE 652  // 4.2V

// LoRa configuration
#define SENSOR_0_ADDRESS 240
#define BROADCAST_ADDRESS 255
#define PREAMBLE "BLOOM"
#define FLAG_MEASUREMENT 0b0000
#define FLAG_PAIRING_REQ 0b0001
#define FLAG_PAIRING_ACK 0b0010
#define FLAG_ADDRESS_AVL 0b0100
#define FLAG_SHUTDOWN_ORDER 0b1000
#define BIT_MASK 0b00001111

// Times
#define MAX_UNACK_MSGS 3
#define PAIRING_TIMEOUT 10000 // 10 seconds
#define ANSWER_TIMEOUT 1000   //  1 second
#define SLEEP_DELAY 2000      //  2 seconds TODO change

// Globals
RH_RF95 driver(RF95_CS, RF95_INT);
RHReliableDatagram manager(driver, BROADCAST_ADDRESS);
uint8_t sensorAddress = SENSOR_0_ADDRESS;
uint8_t hubAddress = BROADCAST_ADDRESS;
uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
uint8_t unacknowledgedMessageCounter = 0;


void setup() {

    // SERIAL SETUP
    #ifdef DEBUG
    Serial.begin(115200);
    while (!Serial) {
        delay(1);
    }
    Serial.println("SENSOR SETUP");
    #endif

    
    // RADIO SETUP
    #ifdef DEBUG
    Serial.println("LoRa radio reset");
    #endif
    // cmp. datasheet page 110f, 7.2.1. POR and 7.2.2. ManualReset
    pinMode(RF95_RST, OUTPUT);
    digitalWrite(RF95_RST, HIGH);
    delay(10);
    digitalWrite(RF95_RST, LOW);
    delay(1);
    digitalWrite(RF95_RST, HIGH);
    delay(5);

    #ifdef DEBUG
    Serial.println("LoRa radio initialization");
    #endif
    if (!manager.init()) {
        #ifdef DEBUG
        Serial.println("ERROR: LoRa radio initialization failed");
        Serial.println("Rebooting");
        #endif
        while(true); // TODO autoreset
    }
    // Default parameters after initialization are:
    // Frequency: 434.0MHz
    // Modulation: GFSK_Rb250Fd250
    // Power: 13dBm
    // Bandwith: 125kHz
    // CRC: 4/5 (CRC on)
    // Spreading Factor: 7 (128 chips/symbol)
    // _thisAddress (sensorAddress): 255 (Broadcast address)

    #ifdef DEBUG
    Serial.println("LoRa radio initialized, setting parameters");
    #endif
    if (!driver.setFrequency(RF95_FREQ)) {
        #ifdef DEBUG
        Serial.println("ERROR: LoRa radio frequency set failed");
        Serial.println("Rebooting");
        #endif
        while(true); // TODO autoreset
    }
    #ifdef DEBUG
    Serial.print("LoRa radio frequency set to: "); Serial.println(RF95_FREQ);
    #endif
    driver.setTxPower(RF95_POW, false);
    #ifdef DEBUG
    Serial.print("LoRa radio power set to: "); Serial.println(RF95_POW);
    Serial.println("RADIO SETUP COMPLETE");
    #endif
    
    // ADDRESS SETUP
    #ifdef DEBUG
    Serial.println("Reading sensor ID");
    #endif
    bool bit0;
    pinMode(ADDRBIT_0_OUT, OUTPUT);
    digitalWrite(ADDRBIT_0_OUT, LOW);
    pinMode(ADDRBIT_0_IN, INPUT_PULLUP);
    bit0 = !digitalRead(ADDRBIT_0_IN);
    bool bit1;
    pinMode(ADDRBIT_1_OUT, OUTPUT);
    digitalWrite(ADDRBIT_1_OUT, LOW);
    pinMode(ADDRBIT_1_IN, INPUT_PULLUP);
    bit1 = !digitalRead(ADDRBIT_1_IN);
    bool bit2;
    pinMode(ADDRBIT_2_OUT, OUTPUT);
    digitalWrite(ADDRBIT_2_OUT, LOW);
    pinMode(ADDRBIT_2_IN, INPUT_PULLUP);
    bit2 = !digitalRead(ADDRBIT_2_IN);
    bool bit3;
    pinMode(ADDRBIT_3_OUT, OUTPUT);
    digitalWrite(ADDRBIT_3_OUT, LOW); // This will also turn on the LED
    pinMode(ADDRBIT_3_IN, INPUT_PULLUP);
    bit3 = !digitalRead(ADDRBIT_3_IN);

    sensorAddress |= (bit3 << 3) | (bit2 << 2) | (bit1 << 1) | bit0;
    #ifdef DEBUG
    Serial.print("Initial sensor address: "); Serial.print(sensorAddress, BIN);
    Serial.print(" (Sensor ID "); Serial.print(sensorAddress - SENSOR_0_ADDRESS, DEC); Serial.println(")");
    #endif
    
    if (sensorAddress == hubAddress) {
        #ifdef DEBUG
        Serial.println("FATAL ERROR: sensorAddress == hubAddress");
        Serial.println("Entering eternal deepsleep");
        #endif
        while(true); // TODO eternal deepsleep
    }
    #ifdef DEBUG
    Serial.println("Setting LoRa address");
    #endif
    manager.setThisAddress(sensorAddress);
    #ifdef DEBUG
    Serial.println("ADDRESS SETUP COMPLETE");
    #endif


    // NETWORK SETUP
    #ifdef DEBUG
    Serial.println("Sending pairing requests");
    #endif
    bool isPaired = false;
    uint8_t pairingRequestCounter = 0;
    char data[] = PREAMBLE;
    manager.setHeaderFlags(FLAG_PAIRING_REQ, BIT_MASK);

    long deadline = millis() + PAIRING_TIMEOUT;
    while(!isPaired && millis() < deadline) {
        pairingRequestCounter++;
        #ifdef DEBUG
        Serial.print("Pairing request #"); Serial.println(pairingRequestCounter, DEC);
        #endif
        manager.sendtoWait(data, sizeof(data)-1, BROADCAST_ADDRESS);  // Don't wait for ack on broadcast
        uint8_t len = sizeof(buf);
        uint8_t from, to, id, flags;
        if (manager.recvfromAckTimeout(buf, &len, ANSWER_TIMEOUT, &from, &to, &id, &flags)) {
            // TODO full log
            // Serial.print("Received reply from node with address: "); Serial.println(from, BIN);
            if ((flags & BIT_MASK) == FLAG_PAIRING_ACK) { // TODO check preamble
                #ifdef DEBUG
                Serial.println("Received PAIRING_ACK");
                #endif
                hubAddress = from;
                #ifdef DEBUG
                Serial.print("Assigned hub address: "); Serial.print(hubAddress, BIN);
                Serial.print(" (Hub #"); Serial.print(from >> 4, DEC); Serial.println(")");
                #endif
                sensorAddress = from & sensorAddress;
                #ifdef DEBUG
                Serial.print("Assigned sensor address: "); Serial.print(sensorAddress, BIN);
                Serial.print(" (Sensor #"); Serial.print(sensorAddress & BIT_MASK); Serial.println(")");
                Serial.println("Setting LoRa address");
                #endif
                manager.setThisAddress(sensorAddress);
                #ifdef DEBUG
                Serial.println("Sensor successfully paired to hub");
                #endif
                isPaired = true;
            } else {
                Serial.println("Invalid PAIRING_ACK, will be ignored");
            }
        }
    }
    if (!isPaired) {
        #ifdef DEBUG
        Serial.println("FATAL ERROR: Sensor could not be paired");
        Serial.println("Entering eternal deepsleep");
        #endif
        while(true); // TODO eternal deepsleep
    }
    #ifdef DEBUG
    Serial.println("NETWORK SETUP COMPLETE");
    Serial.println("SETUP FINISHED, ENTERING MAIN LOOP");
    #endif
}


void loop() {
  
    // MEASURE MOISTURE
    float measuredMoisture = analogRead(MOISTURE_IN);
    if (measuredMoisture < MIN_RAW_MOISTURE_VALUE) {
        measuredMoisture = MIN_RAW_MOISTURE_VALUE;
    }
    if (measuredMoisture > MAX_RAW_MOISTURE_VALUE) {
        measuredMoisture = MAX_RAW_MOISTURE_VALUE;
    }
    float transformedMoisture;
    transformedMoisture = 1.0 - static_cast<float>(measuredMoisture - MIN_RAW_MOISTURE_VALUE) / static_cast<float>(MAX_RAW_MOISTURE_VALUE - MIN_RAW_MOISTURE_VALUE);
    #ifdef DEBUG
    Serial.print("Measured moisture: "); Serial.println(measuredMoisture, 0);
    Serial.print("Transformed moisture: "); Serial.println(transformedMoisture, 2);
    #endif

    // MEASURE BATTERY
    float measuredBattery = analogRead(VBAT_IN);
    if (measuredBattery < MIN_RAW_BATTERY_VALUE) {
        measuredBattery = MIN_RAW_BATTERY_VALUE;
    }
    if (measuredBattery > MAX_RAW_BATTERY_VALUE) {
        measuredBattery = MAX_RAW_BATTERY_VALUE;
    }
    float transformedBattery;
    transformedBattery = static_cast<float>(measuredBattery - MIN_RAW_BATTERY_VALUE) / static_cast<float>(MAX_RAW_BATTERY_VALUE - MIN_RAW_BATTERY_VALUE);
    #ifdef DEBUG
    Serial.print("Measured battery: "); Serial.println(measuredBattery, 0);
    Serial.print("Transformed battery: "); Serial.println(transformedBattery, 2);
    #endif


    // TRANSMIT AND RECEIVE
    String message = String(PREAMBLE) + " " + transformedMoisture + " " + transformedBattery;
    char data[16];
    message.toCharArray(data, 16);
    manager.setHeaderFlags(FLAG_MEASUREMENT, BIT_MASK);
    #ifdef DEBUG
    Serial.print("Sending measurement data: "); Serial.print("'"); Serial.print(data); Serial.println("'");
    #endif
    if (manager.sendtoWait(data, sizeof(data)-1, hubAddress)) {
        #ifdef DEBUG
        Serial.println("Hub acknowledged message, listening for reply");
        #endif
        unacknowledgedMessageCounter = 0;
        uint8_t len = sizeof(buf);
        uint8_t from, to, id, flags;
        if (manager.recvfromAckTimeout(buf, &len, ANSWER_TIMEOUT, &from, &to, &id, &flags)) {
            // TODO full log
            // Serial.print("Received reply from node with address: "); Serial.println(from, BIN);
            if ((flags & BIT_MASK) == FLAG_SHUTDOWN_ORDER) { // TODO check preamble and hubAddress
                #ifdef DEBUG
                Serial.print("Received SHUTDOWN_ORDER (from Hub #"); Serial.print(from >> 4, DEC); Serial.println(")");
                Serial.println("Entering eternal deepsleep");
                #endif
                while(true); // TODO eternal deepsleep
            } else {
                #ifdef DEBUG
                Serial.println("Invalid SHUTDOWN_ORDER, will be ignored");
                #endif
            }
        } else {
            #ifdef DEBUG
            Serial.println("No reply from hub");
            #endif
        }
    } else {
        unacknowledgedMessageCounter++;
        #ifdef DEBUG
        Serial.print("Sending data failed: Unacknowledged message #"); Serial.println(unacknowledgedMessageCounter, DEC);
        #endif
    }


    // CHECK UNACKNOWLEDGED
    if (unacknowledgedMessageCounter > MAX_UNACK_MSGS) {
        #ifdef DEBUG
        Serial.print("FATAL ERROR: More than "); Serial.print(MAX_UNACK_MSGS, DEC); Serial.println(" messages unacknowledged");
        Serial.println("Entering eternal deepsleep");
        #endif
        while(true); // TODO eternal deepsleep
    }

    // ENTER DEEPSLEEP
    delay(SLEEP_DELAY); // TODO deepsleep
}
