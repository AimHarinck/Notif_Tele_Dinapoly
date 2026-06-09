import requests
import pandas as pd
import schedule
import time
from datetime import datetime

# ─── KONFIGURASI ───────────────────────────────────────────
TELEGRAM_TOKEN = "8699687331:AAE8uBkFJt_syLYUDNY4HZdBxjE31Lo9GxI"
CHAT_ID        = "1469880541"
TWELVEDATA_KEY = "ae6a9018157e4bb2bc6f701a4e1cbd89"
SYMBOL         = "XAU/USD"

# SMA Settings
SMA_FAST_PERIOD  = 3
SMA_FAST_SHIFT   = 3
SMA_SLOW_PERIOD  = 7
SMA_SLOW_SHIFT   = 5
SMA_TREND_PERIOD = 25
SMA_TREND_SHIFT  = 5
# ───────────────────────────────────────────────────────────

def kirim_telegram(pesan):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print(f"[{datetime.now()}] Pesan terkirim ke Telegram")
    except Exception as e:
        print(f"[{datetime.now()}] Gagal kirim Telegram: {e}")

def ambil_data(interval, outputsize=100):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVEDATA_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "values" not in data:
            print(f"Error ambil data {interval}: {data}")
            return None
        df = pd.DataFrame(data["values"])
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col])
        df = df.iloc[::-1].reset_index(drop=True)  # lama ke baru
        return df
    except Exception as e:
        print(f"Exception ambil data {interval}: {e}")
        return None

def hitung_sma_shift(series, period, shift):
    """Hitung SMA lalu geser (shift) ke kanan sebanyak 'shift' candle"""
    sma = series.rolling(period).mean()
    sma_shifted = sma.shift(shift)
    return sma_shifted

def posisi_harga(harga, sma25):
    if harga > sma25:
        return "📈 Harga DI ATAS SMA 25 (Bullish Bias)"
    else:
        return "📉 Harga DI BAWAH SMA 25 (Bearish Bias)"

def cek_crossing_tf(interval, label):
    print(f"[{datetime.now()}] Mengecek crossing {label}...")
    df = ambil_data(interval)
    if df is None:
        return

    # Hitung SMA dengan shift
    df["sma_fast"]  = hitung_sma_shift(df["close"], SMA_FAST_PERIOD,  SMA_FAST_SHIFT)
    df["sma_slow"]  = hitung_sma_shift(df["close"], SMA_SLOW_PERIOD,  SMA_SLOW_SHIFT)
    df["sma_trend"] = hitung_sma_shift(df["close"], SMA_TREND_PERIOD, SMA_TREND_SHIFT)

    df = df.dropna().reset_index(drop=True)
    if len(df) < 3:
        print(f"Data {label} tidak cukup")
        return

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    prev_diff = prev["sma_fast"] - prev["sma_slow"]
    curr_diff = curr["sma_fast"] - curr["sma_slow"]

    harga     = curr["close"]
    sma3      = curr["sma_fast"]
    sma7      = curr["sma_slow"]
    sma25     = curr["sma_trend"]
    posisi    = posisi_harga(harga, sma25)
    waktu     = datetime.now().strftime("%Y-%m-%d %H:%M")

    if prev_diff < 0 and curr_diff > 0:
        pesan = (
            f"🟢 <b>GOLDEN CROSS — XAU/USD {label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📈 SMA 3 memotong SMA 7 ke <b>ATAS</b>\n"
            f"💰 Harga        : <b>${harga:,.2f}</b>\n"
            f"〰️ SMA 3 (s3)  : {sma3:,.2f}\n"
            f"〰️ SMA 7 (s5)  : {sma7:,.2f}\n"
            f"〰️ SMA 25 (s3) : {sma25:,.2f}\n"
            f"{posisi}\n"
            f"🕐 Waktu        : {waktu}"
        )
        kirim_telegram(pesan)
        print(f"[{waktu}] GOLDEN CROSS {label} terdeteksi!")

    elif prev_diff > 0 and curr_diff < 0:
        pesan = (
            f"🔴 <b>DEATH CROSS — XAU/USD {label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📉 SMA 3 memotong SMA 7 ke <b>BAWAH</b>\n"
            f"💰 Harga        : <b>${harga:,.2f}</b>\n"
            f"〰️ SMA 3 (s3)  : {sma3:,.2f}\n"
            f"〰️ SMA 7 (s5)  : {sma7:,.2f}\n"
            f"〰️ SMA 25 (s3) : {sma25:,.2f}\n"
            f"{posisi}\n"
            f"🕐 Waktu        : {waktu}"
        )
        kirim_telegram(pesan)
        print(f"[{waktu}] DEATH CROSS {label} terdeteksi!")

    else:
        print(f"[{waktu}] {label} — Tidak ada crossing. SMA3={sma3:.2f}, SMA7={sma7:.2f}")

def cek_semua():
    cek_crossing_tf("1h",  "H1")
    time.sleep(3)  # jeda sebentar agar tidak kena rate limit API
    cek_crossing_tf("15min", "M15")

# ─── SCHEDULER ─────────────────────────────────────────────
# H1  → cek tiap jam lebih 2 menit
schedule.every().hour.at(":02").do(lambda: cek_crossing_tf("1h", "H1"))

# M15 → cek tiap 15 menit lebih 1 menit
schedule.every(15).minutes.do(lambda: cek_crossing_tf("15min", "M15"))

# ─── START ─────────────────────────────────────────────────
print("🤖 Bot XAU/USD SMA Cross mulai berjalan...")
kirim_telegram(
    "🤖 <b>Bot XAU/USD SMA Cross aktif!</b>\n"
    "Memantau Golden/Death Cross SMA 3 & SMA 7\n"
    "📊 Timeframe: H1 &amp; M15\n"
    "📐 Filter: Posisi harga vs SMA 25"
)

# Cek langsung saat pertama start
cek_semua()

while True:
    schedule.run_pending()
    time.sleep(30)
