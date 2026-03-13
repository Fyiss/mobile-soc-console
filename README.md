# 📱 Mobile SOC Console — Phone-Controlled Intrusion Response System

A real-time cybersecurity project that detects security incidents on a Linux host and lets you authorize and execute response actions directly from your smartphone.

---

## Architecture

```
Linux Agent ←→ Mosquitto MQTT (localhost:1883) ←→ FastAPI Broker ←→ Flutter Mobile App
                                                          ↓
                                              Block IP / Kill Process / Isolate / Dismiss
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Host OS | Arch Linux (Hyprland, Wayland) |
| Hardware | HP Pavilion Gaming — AMD Ryzen 5, GTX 1650 |
| Agent | Python 3.14 (asyncio, psutil, systemd-journald) |
| Message Broker | Mosquitto MQTT |
| Backend | FastAPI + uvicorn |
| Mobile App | Flutter 3.27.4 |
| Phone | iQOO Neo 10 (Android) |

---

## Project Structure

```
~/soc-agent/
└── agent.py              # Linux agent — detection + response dispatcher

~/soc-broker/
├── main.py               # FastAPI app — MQTT bridge, WebSocket manager, JWT auth
└── api/
    ├── auth.py           # POST /auth/login — JWT token issuance
    ├── websocket.py      # GET /ws/{device_id}?token= — real-time alert stream
    └── commands.py       # POST /commands/send — response action dispatcher

~/soc_mobile/
└── lib/
    └── main.dart         # Flutter app — login, WebSocket alerts, action sheet
```

---

## Features

### Detection (Linux Agent)
- **SSH Brute Force** — monitors systemd-journald for repeated failed auth attempts
- **Suspicious Process** — psutil-based process monitor for anomalous activity
- **Network Anomaly** — monitors for unusual network connections
- **Log Monitor** — watches system logs for security events

### Response Actions (from Phone)
- **Block IP** — adds `iptables DROP` rule for the source IP
- **Kill Process** — terminates the suspicious process by PID
- **Isolate Host** — network isolation response
- **Dismiss** — acknowledge and close the alert

### Mobile App
- JWT-authenticated login
- Live WebSocket alert feed
- Per-alert action sheet with severity colors (HIGH / MEDIUM / LOW)
- Auto-reconnects every 3 seconds if connection drops

---

## Setup & Running

### Prerequisites

#### 1. System packages
```bash
# Mosquitto MQTT broker + ADB
sudo pacman -S mosquitto android-tools nodejs npm
```

#### 2. Python dependencies
```bash
pip install fastapi 'uvicorn[standard]' paho-mqtt psutil --break-system-packages
```

#### 3. Flutter installation (Arch Linux)
```bash
# Install Flutter via AUR
yay -S flutter

# Or manually:
git clone https://github.com/flutter/flutter.git ~/flutter --depth 1 -b stable
echo 'export PATH="$PATH:$HOME/flutter/bin"' >> ~/.zshrc
source ~/.zshrc

# Verify installation
flutter doctor
```

> Make sure `flutter doctor` shows no critical errors. Android SDK and ADB must be available.

#### 4. Android SDK / ADB setup
```bash
# Install Android SDK tools
yay -S android-sdk-cmdline-tools-latest

# Accept licenses
flutter doctor --android-licenses

# Verify ADB sees your phone (with USB debugging enabled on phone)
adb devices
# Expected: <device_id>    device
```

> On your iQOO Neo 10: go to **Settings → About Phone → tap Build Number 7 times** to enable Developer Options, then **Settings → Developer Options → enable USB Debugging**.

---

### Installing the Flutter App on Phone

#### Option A — Run directly via ADB (development, no APK needed)
```bash
# Connect phone via USB first
cd ~/soc_mobile
flutter run
```
> This builds and installs the app directly to your connected phone. Takes ~1 min on first run.

#### Option B — Build APK and install manually
```bash
cd ~/soc_mobile

# Build release APK
flutter build apk --release

# APK will be at:
# build/app/outputs/flutter-apk/app-release.apk

# Install via ADB
adb install build/app/outputs/flutter-apk/app-release.apk
```

> After installing the APK, you can disconnect the cable and use the app wirelessly via hotspot.

#### Updating the app after code changes
```bash
cd ~/soc_mobile
flutter run          # re-runs with latest code (press 'r' for hot reload)
# or for a fresh install:
flutter build apk --release && adb install -r build/app/outputs/flutter-apk/app-release.apk
```

### Start the Stack (3 terminals)

Open 3 separate terminal windows and run one command per terminal. **Order matters — start them top to bottom.**

**Terminal 1 — Mosquitto MQTT Broker:**
```bash
sudo systemctl start mosquitto
sudo systemctl status mosquitto   # confirm: active (running)
```
> Keep this terminal open. Mosquitto runs as a background service so no live output is expected.

**Terminal 2 — FastAPI Broker:**
```bash
cd ~/soc-broker
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
> Watch this terminal — it shows all HTTP requests, WebSocket connections, and MQTT bridge logs in real time. You should see:
> ```
> INFO: Uvicorn running on http://0.0.0.0:8000
> INFO: Application startup complete.
> ```
> When phone connects:
> ```
> Device connected: mobile-phone (1 total)
> WebSocket open: mobile-phone (user=admin)
> ```

**Terminal 3 — Linux Agent:**
```bash
cd ~/soc-agent
sudo python agent.py
```
> Watch this terminal — it shows detections and response action execution logs. When an action fires you should see:
> ```
> [INFO] dispatcher: Executing: block_ip on '1.2.3.4'
> [INFO] dispatcher: Blocked IP: 1.2.3.4
> ```

**Terminal 4 — ADB (wired only, skip if using hotspot):**
```bash
adb reverse tcp:8000 tcp:8000
adb reverse --list   # confirm: UsbFfs tcp:8000 tcp:8000
```
> Can close this terminal after confirming — the reverse tunnel stays active.

---

## Connecting the Mobile App

### Option A — USB Cable (ADB Reverse Forwarding)

```bash
# Forward port over USB
adb reverse tcp:8000 tcp:8000

# Verify
adb reverse --list
# Expected: UsbFfs tcp:8000 tcp:8000
```

In the Flutter app, set Broker URL to:
```
http://127.0.0.1:8000
```

### Option B — Wireless (Phone Hotspot) ⭐ Recommended

> **Note:** Direct WiFi won't work if your router has AP Isolation enabled (most home routers do). Use your phone's hotspot instead.

1. Enable hotspot on your iQOO Neo 10
2. Connect your PC to the phone's hotspot
3. Find your PC's new IP:
```bash
ip addr show wlan0 | grep "inet "
# Example output: inet 10.144.212.232/24
```
4. In the Flutter app, set Broker URL to:
```
http://10.144.212.232:8000
```

> The hotspot IP may change on reconnect. Always verify with `ip addr show wlan0 | grep inet` if connection fails.

---

## Authentication

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `soc-password-123` |
| Endpoint | `POST /auth/login` |

Get a token manually:
```bash
curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"soc-password-123"}'
```

---

## Testing the Pipeline

### Fire a test alert via MQTT:
```bash
mosquitto_pub -h localhost -p 1883 -t "soc/alerts" -m '{
  "id": "test-001",
  "type": "ssh_brute_force",
  "severity": "high",
  "message": "SSH brute force detected from 192.168.1.100",
  "source_ip": "192.168.1.100",
  "timestamp": "2026-03-13T17:41:00"
}'
```

### Test WebSocket directly:
```bash
# Install wscat
sudo npm install -g wscat

# Get token first, then:
wscat -c "ws://127.0.0.1:8000/ws/myphone?token=YOUR_JWT_TOKEN"
# Expected: Connected (press CTRL+C to quit)
```

### Verify Block IP action fired:
```bash
sudo iptables -L INPUT -n | grep 192.168.1.100
# Expected: DROP all -- 192.168.1.100  0.0.0.0/0

# Clean up test rule:
sudo iptables -D INPUT -s 192.168.1.100 -j DROP
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Get JWT token |
| WebSocket | `/ws/{device_id}?token=` | Real-time alert stream |
| POST | `/commands/send` | Execute response action |
| GET | `/docs` | Swagger UI — all routes |

---

## Roadmap

- [ ] Alert deduplication — prevent alert spam for repeated events
- [ ] SQLite persistence — alert history survives restarts
- [ ] Real journald SSH detection — live brute force detection from system logs
- [ ] FCM push notifications — alerts when app is in background
- [ ] Alert history dashboard in Flutter UI
- [ ] Blocked IPs management screen
- [ ] Token refresh / expiry handling

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| WebSocket 403 | URL missing `/{device_id}` — use `/ws/mobile-phone?token=...` |
| Auth 404 | Endpoint is `/auth/login` not `/auth/token` |
| Phone can't reach broker on WiFi | Router has AP isolation — use phone hotspot instead |
| Hotspot IP changed | Run `ip addr show wlan0 \| grep inet` and update app URL |
| uvicorn WS fails | Run `pip install 'uvicorn[standard]' --break-system-packages` |
