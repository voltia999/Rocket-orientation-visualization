# Rocket Attitude Visualizer

Real-time 3D rocket attitude visualization using quaternion data from a serial device (e.g. ESP32 with EKF). Falls back to synthetic data when no device is connected.

## Architecture

```
Arduino/ESP32
  └─ Serial (115200 baud, 225 Hz)
       └─ ws_server.py  (Python)
            ├─ Parses quaternion → Euler angles
            ├─ HTTP server  :8080  (serves the web files)
            └─ WebSocket    :8765  (broadcasts at 225 Hz)
                  └─ index.html  (Three.js + Chart.js)
                        ├─ 3D rocket rendered at 60 fps (screen refresh)
                        └─ Roll / Pitch / Yaw live charts
```

## Serial data format

The firmware sends one line per sample:

```
[I] EKF: Quat, (w=1.0000, x=0.0000, y=0.0000, z=0.0000)
```

The parser ignores everything outside the `w=`, `x=`, `y=`, `z=` fields.

---

## Requirements

- Python 3.8+
- pip packages: `websockets`, `pyserial`, `scipy`

```bash
pip install websockets pyserial scipy
```

---

## Linux

### 1 — Run the server

```bash
python ws_server.py
```

The serial port is auto-detected. To force a specific port:

```bash
python ws_server.py --serial /dev/ttyUSB0 --baud 115200
```

### 2 — Open the visualizer

Same machine: [http://localhost:8080](http://localhost:8080)

From another device on the same network, find your IP first:

```bash
ip addr show | grep "inet " | grep -v 127
```

Then open `http://192.168.x.x:8080` on the other device.

### 3 — Firewall (if other devices can't connect)

```bash
sudo firewall-cmd --add-port=8080/tcp --add-port=8765/tcp          # until reboot
sudo firewall-cmd --permanent --add-port=8080/tcp --add-port=8765/tcp  # permanent
sudo firewall-cmd --reload
```

---

## Windows

### 1 — Install Python

Download from [python.org](https://www.python.org/downloads/). During installation check **"Add Python to PATH"**.

### 2 — Install dependencies

Open **Command Prompt** or **PowerShell**:

```bat
pip install websockets pyserial scipy
```

### 3 — Run the server

```bat
python ws_server.py
```

Auto-detection works on Windows too (detects CH340, CP210x, FTDI, etc.). To force a COM port:

```bat
python ws_server.py --serial COM3 --baud 115200
```

### 4 — Open the visualizer

Same machine: [http://localhost:8080](http://localhost:8080)

From another device, find your IP:

```bat
ipconfig
# look for "IPv4 Address" under your Wi-Fi or Ethernet adapter
```

Then open `http://192.168.x.x:8080`.

### 5 — Firewall (if other devices can't connect)

Run **PowerShell as Administrator**:

```powershell
New-NetFirewallRule -DisplayName "RocketViz HTTP" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
New-NetFirewallRule -DisplayName "RocketViz WS"   -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow
```

---

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--serial` | auto | Serial port (`/dev/ttyUSB0`, `COM3`, …) |
| `--baud` | 115200 | Baud rate |
| `--http` | 8080 | HTTP server port |
| `--ws` | 8765 | WebSocket port |

---

## Broadcast rate

The server broadcasts at **225 Hz** to match the sensor output rate, ensuring no samples are dropped. The browser renders at 60 fps (screen refresh limit) and always uses the latest received value.

---

## Files

| File | Description |
|------|-------------|
| `index.html` | Main visualizer (procedural wireframe rocket) |
| `ws_server.py` | Python backend: serial reader + HTTP + WebSocket |
| `Solaris_Insignia_ConFondo.svg` | Logo |
