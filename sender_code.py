#2025年7月時点の実験で使用している送信用のスクリプトです。
"""
sender_auto.py  ―  by-id で GPS / LoRa を自動識別して送信
"""

import serial, time, socket, sys, os, traceback, glob

# ─── 設定 ─────────────────────────────
DEVICE_NAME   = "broad"          # 送信機名
BAUD_GPS      = 4800
BAUD_LORA     = 115200
SEND_INTERVAL = 1.0              # 送信間隔 [秒]
LOG_DIR       = "/home/kou/insect-tracking/sender"
# by-id でマッチさせる文字列（必要なら書き換え）
GPS_KEYWORD   = "Prolific"       # GPSドングル（BU-353 は Prolific）
LORA_KEYWORD  = "Silicon_Labs"   # ES920LR は CP2102 (Silicon Labs)
# ──────────────────────────────────

os.makedirs(LOG_DIR, exist_ok=True)
sys.stdout = open(f"{LOG_DIR}/output.log", "a", buffering=1)
sys.stderr = open(f"{LOG_DIR}/error.log", "a", buffering=1)

log  = lambda m: print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {m}", flush=True)
err  = lambda m: print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {m}", file=sys.stderr, flush=True)

def find_by_id(keyword: str):
    for link in glob.glob("/dev/serial/by-id/*"):
        if keyword in os.path.basename(link):
            return os.path.realpath(link)  # → /dev/ttyUSBx
    return None

# ─── ポート自動検出（最大30秒リトライ） ───────
gps_port = lora_port = None
for attempt in range(30):
    gps_port  = gps_port  or find_by_id(GPS_KEYWORD)
    lora_port = lora_port or find_by_id(LORA_KEYWORD)
    if gps_port and lora_port:
        break
    time.sleep(1)

if not (gps_port and lora_port):
    err(f"Port detect failed  gps={gps_port}  lora={lora_port}")
    sys.exit(1)

log(f"Detected  GPS={gps_port}  LoRa={lora_port}")

# ─── シリアルを開く ────────────────────
try:
    gps_ser   = serial.Serial(gps_port,  BAUD_GPS,  timeout=1)
    lora_ser  = serial.Serial(lora_port, BAUD_LORA, timeout=1)
    lora_ser.flush()
    log("Serial ports opened")
except Exception as e:
    err(f"Serial open error: {e}")
    sys.exit(1)

# ─── 位置取得ヘルパ ───────────────────
def to_dec(coord, direc):
    n = 2 if direc in "NS" else 3
    try:
        deg = float(coord[:n]); minute = float(coord[n:]) / 60
        return (-1 if direc in "SW" else 1) * (deg + minute)
    except: return None

def get_gps(timeout=2):
    t0 = time.time()
    while time.time() - t0 < timeout:
        line = gps_ser.readline().decode(errors="ignore").strip()
        if line.startswith("$GPGGA"):
            p = line.split(",")
            if len(p) > 5 and p[2] and p[4]:
                return to_dec(p[2], p[3]), to_dec(p[4], p[5])
    return None, None

# ─── メインループ ────────────────────
name = DEVICE_NAME or socket.gethostname()
log("送信開始")
seq = 0
try:
    while True:
        lat, lon = get_gps()
        if lat is not None:
            msg = f"{seq},{lat:.6f},{lon:.6f},{name}"
        else:
            msg = f"{seq},位置情報不明,{name}"
        try:
            lora_ser.write((msg + "\r\n").encode())
            lora_ser.flush()
            log(f"[送信] {msg}")
        except Exception as e:
            err(f"Send failed: {e}")
        seq += 1
        time.sleep(SEND_INTERVAL)
except KeyboardInterrupt:
    log("KeyboardInterrupt ― 終了")
except Exception:
    err("Unexpected:\n" + traceback.format_exc())
finally:
    try: gps_ser.close(); lora_ser.close()
    except: pass
    log("ポートを閉じて終了")
