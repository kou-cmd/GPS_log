#2025年7月時点の実験で使用している受信用のスクリプトです。

import os, csv, serial, sqlite3, socket
from datetime import datetime

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE    = 115200
TIMEOUT_S   = 1

BASE_DIR = os.path.dirname(__file__)
HOSTNAME = socket.gethostname()

DB_FILE  = os.path.join(BASE_DIR, f"gps_data_{HOSTNAME}.db")
CSV_FILE = os.path.join(BASE_DIR, f"gps_log_seq_{HOSTNAME}.csv")

DDL = """CREATE TABLE IF NOT EXISTS gps_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    seq INTEGER,
    latitude REAL,
    longitude REAL,
    rssi REAL,
    antenna TEXT,
    sender TEXT
);"""

def init_db():
    conn = sqlite3.connect(DB_FILE)
    with conn:
        conn.execute(DDL)
    return conn

def init_csv():
    new = not os.path.exists(CSV_FILE)
    f = open(CSV_FILE, "a", newline="")
    w = csv.writer(f)
    if new:
        w.writerow(["timestamp","seq","latitude","longitude","rssi","antenna","sender"])
    return f, w

def parse_line(raw: str):
    try:
        rssi_part, data_part = raw.split("):Receive Data(")
        rssi = float(rssi_part.split("RSSI(")[1].replace("dBm", ""))
        parts = data_part.rstrip(")").split(",")
        seq      = int(parts[0])
        latitude = float(parts[1])
        longitude= float(parts[2])
        sender   = parts[3].strip()
        return seq, latitude, longitude, rssi, sender
    except Exception:
        return None, None, None, None, None

def main():
    antenna = input(f"アンテナ名（デフォルト: {HOSTNAME}）: ").strip() or HOSTNAME
    conn = init_db()
    csv_f, csv_w = init_csv()

    print("[Serial] open...")
    try:
        with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=TIMEOUT_S) as ser:
            while True:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue

                seq, lat, lon, rssi, sender = parse_line(raw)
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # DB に NULLを含んでも記録
                with conn:
                    conn.execute(
                        "INSERT INTO gps_log(timestamp,seq,latitude,longitude,rssi,antenna,sender) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (ts, seq, lat, lon, rssi, antenna, sender)
                    )

                # CSVにも記録
                csv_w.writerow([ts, seq, lat, lon, rssi, antenna, sender])
                csv_f.flush()

                print(f"[保存] ts={ts} seq={seq} lat={lat} lon={lon} rssi={rssi} sender={sender}")

    except KeyboardInterrupt:
        print("\n終了します")
    finally:
        conn.close(); csv_f.close()

if __name__ == "__main__":
    main()
