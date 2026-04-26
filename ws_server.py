#!/usr/bin/env python3
"""
WebSocket + HTTP server for Rocket Attitude Visualizer.

Reads quaternion data (w,x,y,z CSV line) from serial port, converts to
Euler angles, and broadcasts to WebSocket clients at 50 Hz.
Auto-detects the serial port if --serial is not specified.
Falls back to synthetic data if no port is found or available.

Usage:
    python ws_server.py                          # auto-detect port
    python ws_server.py --serial /dev/ttyUSB0    # explicit port
    python ws_server.py --serial COM3 --baud 9600
"""

import asyncio
import websockets
import json
import time
import math
import threading
import argparse
import os
import re
import mimetypes
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

# Parses: [I] EKF: Quat, (w=1.0000, x=0.0000, y=0.0000, z=0.0000)
_QUAT_RE = re.compile(r'w=([+-]?\d+\.?\d*)[,\s]+x=([+-]?\d+\.?\d*)[,\s]+y=([+-]?\d+\.?\d*)[,\s]+z=([+-]?\d+\.?\d*)')

mimetypes.add_type('model/gltf-binary', '.glb')
mimetypes.add_type('model/gltf+json',   '.gltf')

# ── Arguments ─────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--serial', default=None,   help='Serial port (auto-detected if omitted)')
parser.add_argument('--baud',   default=115200, type=int)
parser.add_argument('--ws',     default=8765,   type=int)
parser.add_argument('--http',   default=8080,   type=int)
args = parser.parse_args()

# ── Shared state ───────────────────────────────────────────────────────────────
_lock     = threading.Lock()
_angles   = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0}
_use_real = False
_clients  = set()

# ── Auto-detect serial port ────────────────────────────────────────────────────
def find_serial_port():
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            return None
        # Prefer USB/ACM ports (Arduino, STM32, etc.)
        for p in ports:
            desc = (p.description or '').lower()
            name = p.device.lower()
            if any(k in desc or k in name for k in ('usb', 'acm', 'arduino', 'stm', 'ch340', 'cp210', 'ftdi')):
                return p.device
        return ports[0].device   # fallback: first available port
    except Exception:
        return None

# ── Serial reader (blocking, auto-reconnects) ──────────────────────────────────
def serial_reader(port, baud):
    global _use_real
    try:
        import serial
        from scipy.spatial.transform import Rotation as R
    except ImportError as e:
        print(f"[serial] Missing dependency ({e}). Install: pip install pyserial scipy")
        return

    while True:
        try:
            print(f"[serial] Connecting to {port} @ {baud}…")
            ser = serial.Serial(port, baud, timeout=1)
            print(f"[serial] Connected ✓")
            _use_real = True

            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                m = _QUAT_RE.search(line)
                if not m:
                    continue
                try:
                    w, x, y, z = map(float, m.groups())
                except ValueError:
                    continue
                norm = math.sqrt(w**2 + x**2 + y**2 + z**2)
                if norm < 0.001:
                    continue
                w, x, y, z = w/norm, x/norm, y/norm, z/norm
                euler = R.from_quat([x, y, z, w]).as_euler('xyz', degrees=True)
                with _lock:
                    _angles['roll']  = float(euler[0])
                    _angles['pitch'] = float(euler[1])
                    _angles['yaw']   = float(euler[2])

        except Exception as e:
            _use_real = False
            print(f"[serial] Lost connection ({e}). Retrying in 3s…")
            time.sleep(3)

# ── WebSocket handler ──────────────────────────────────────────────────────────
async def ws_handler(websocket):
    _clients.add(websocket)
    print(f"[ws] Client connected  ({len(_clients)} active)")
    try:
        await websocket.wait_closed()
    finally:
        _clients.discard(websocket)
        print(f"[ws] Client disconnected ({len(_clients)} active)")

# ── Broadcaster 225 Hz (matches sensor rate) ──────────────────────────────────
async def broadcaster():
    t0 = time.monotonic()
    while True:
        t = time.monotonic() - t0
        if _use_real:
            with _lock:
                data = dict(_angles)
        else:
            data = {
                'roll':  45 * math.sin(0.8 * t),
                'pitch': 30 * math.sin(0.5 * t + math.pi / 4),
                'yaw':   60 * math.sin(0.3 * t),
            }
        if _clients:
            msg  = json.dumps(data)
            dead = set()
            for ws in list(_clients):
                try:
                    await ws.send(msg)
                except Exception:
                    dead.add(ws)
            _clients.difference_update(dead)
        await asyncio.sleep(1 / 225)

# ── HTTP server ────────────────────────────────────────────────────────────────
def http_server(port):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    httpd = ThreadingHTTPServer(('', port), SimpleHTTPRequestHandler)
    print(f"[http] http://0.0.0.0:{port}")
    httpd.serve_forever()

# ── Main ───────────────────────────────────────────────────────────────────────
async def main():
    port = args.serial or find_serial_port()
    if port:
        print(f"[serial] Using port: {port}")
        threading.Thread(target=serial_reader, args=(port, args.baud),
                         daemon=True).start()
    else:
        print("[serial] No port found — using synthetic data")
        print("[serial] Plug in the device or run:  python ws_server.py --serial /dev/ttyUSB0")

    threading.Thread(target=http_server, args=(args.http,), daemon=True).start()

    async with websockets.serve(ws_handler, '0.0.0.0', args.ws):
        print(f"[ws]   ws://0.0.0.0:{args.ws}")
        await broadcaster()

if __name__ == '__main__':
    asyncio.run(main())
