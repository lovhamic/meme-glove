# 🎵 ESP32 RC522 NFC Wi-Fi Music Player

Trigger and play songs on your PC wirelessly whenever an NFC or RFID card is scanned by your ESP32.

---

## 📁 Project Structure

```
├── esp32/
│   └── esp32_rc522_wifi.ino     # Arduino code for ESP32 & RC522 RFID module
│
├── server/                      # 🐍 PYTHON SERVER OPTION
│   ├── server.py                # Python HTTP server & Pygame audio player
│   ├── config.json              # Tag UID -> Song / Action mapping
│   ├── requirements.txt         # Flask & Pygame dependencies
│   ├── generate_samples.py      # Generates test audio files
│   └── music/                   # Place your .mp3 / .wav songs here
│
├── server_node/                 # ⚡ NODE.JS SERVER OPTION
│   ├── server.js                # Node.js Express HTTP server & Windows audio player
│   ├── config.json              # Tag UID -> Song / Action mapping
│   ├── package.json             # Express dependencies
│   └── music/                   # Place your .mp3 / .wav songs here
│
├── run_server.bat               # 1-Click launcher for Python Server
├── run_node_server.bat          # 1-Click launcher for Node.js Server
└── README.md
```

---

## ⚡ 1. Hardware Setup (RC522 $\leftrightarrow$ ESP32)

Connect the **MFRC522** RFID/NFC module to your **ESP32** using standard SPI pins:

| RC522 Pin | ESP32 Pin | Notes |
| :--- | :--- | :--- |
| **3.3V / VCC** | **3.3V** | ⚠️ **DO NOT connect to 5V!** |
| **RST** | **GPIO 22** | Reset Pin |
| **GND** | **GND** | Ground |
| **MISO** | **GPIO 19** | SPI Master In Slave Out |
| **MOSI** | **GPIO 23** | SPI Master Out Slave In |
| **SCK** | **GPIO 18** | SPI Clock |
| **SDA / SS** | **GPIO 5** | SPI Chip Select |

---

## 💻 2. Step-by-Step Setup

### Step A: Start the Python Music Server on PC
1. Double-click **`run_server.bat`**.
2. The script will automatically:
   - Create a Python virtual environment.
   - Install required packages (`flask`, `pygame`).
   - Display your PC's Wi-Fi IP address on the screen (e.g., `192.168.1.15`).
   - Start the server on port `5000`.
3. Open your browser and visit **`http://localhost:5000`** to view the live dashboard!

---

### Step B: Configure and Flash ESP32
1. Open **Arduino IDE**.
2. Install the **MFRC522** library:
   - Go to **Sketch** $\rightarrow$ **Include Library** $\rightarrow$ **Manage Libraries...**
   - Search for **`MFRC522`** (by GithubCommunity / Miguel Balboa) and click **Install**.
3. Open [`esp32/esp32_rc522_wifi.ino`](esp32/esp32_rc522_wifi.ino).
4. Update your Wi-Fi credentials and PC IP address at the top:
   ```cpp
   const char* WIFI_SSID     = "Your_WiFi_Name";
   const char* WIFI_PASSWORD = "Your_WiFi_Password";
   const char* SERVER_IP     = "192.168.1.15"; // PC IP from Step A
   const int   SERVER_PORT   = 5000;
   ```
5. Select your ESP32 board and COM port, then click **Upload**.
6. Open **Serial Monitor** at **115200 baud** to see connection logs.

---

## 🎛️ 3. Mapping Cards to Songs

### How to Map New Cards:
1. Tap any NFC card or RFID keychain on the reader.
2. The server console and web dashboard will highlight the scanned UID:
   ```text
   [!] NEW / UNMAPPED CARD DETECTED: 83A1290B
   ```
3. Open [`server/config.json`](server/config.json) and add your card:
   ```json
   {
     "settings": {
       "music_folder": "music",
       "default_volume": 0.8
     },
     "tags": {
       "83A1290B": "my_favorite_song.mp3",
       "04A1B2C3": "song2.wav",
       "E5F6G7H8": "ACTION:STOP",
       "11223344": "ACTION:PAUSE_RESUME"
     }
   }
   ```
4. Place your `.mp3` or `.wav` files into the `server/music/` folder.
5. **No need to restart the server!** `config.json` is reloaded live on every scan.

---

## 🎵 Special Action Commands
You can map a card UID to control commands instead of a song:
- `"ACTION:STOP"`: Stops the current music.
- `"ACTION:PAUSE_RESUME"`: Toggles play/pause.
- `"ACTION:VOL_UP"`: Increases volume by 10%.
- `"ACTION:VOL_DOWN"`: Decreases volume by 10%.
