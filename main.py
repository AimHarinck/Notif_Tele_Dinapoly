import requests
import pandas as pd
import schedule
import time
import threading
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

def kirim_telegram(pesan, chat_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id or CHAT_ID, "text": pesan, "parse_mode": "HTML"}
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
        df = df.iloc[::-1].reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Exception ambil data {interval}: {e}")
        return None

def hitung_sma_shift(series, period, shift):
    sma = series.rolling(period).mean()
    return sma.shift(shift)

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

    df["sma_fast"]  = hitung_sma_shift(df["close"], SMA_FAST_PERIOD,  SMA_FAST_SHIFT)
    df["sma_slow"]  = hitung_sma_shift(df["close"], SMA_SLOW_PERIOD,  SMA_SLOW_SHIFT)
    df["sma_trend"] = hitung_sma_shift(df["close"], SMA_TREND_PERIOD, SMA_TREND_SHIFT)

    df = df.dropna().reset_index(drop=True)
    if len(df) < 3:
        return

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    prev_diff = prev["sma_fast"] - prev["sma_slow"]
    curr_diff = curr["sma_fast"] - curr["sma_slow"]

    harga  = curr["close"]
    sma3   = curr["sma_fast"]
    sma7   = curr["sma_slow"]
    sma25  = curr["sma_trend"]
    posisi = posisi_harga(harga, sma25)
    waktu  = datetime.now().strftime("%Y-%m-%d %H:%M")

    if prev_diff < 0 and curr_diff > 0:
        pesan = (
            f"🟢 <b>GOLDEN CROSS — XAU/USD {label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📈 SMA 3 memotong SMA 7 ke <b>ATAS</b>\n"
            f"💰 Harga        : <b>${harga:,.2f}</b>\n"
            f"〰️ SMA 3 (s3)  : {sma3:,.2f}\n"
            f"〰️ SMA 7 (s5)  : {sma7:,.2f}\n"
            f"〰️ SMA 25 (s5) : {sma25:,.2f}\n"
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
            f"〰️ SMA 25 (s5) : {sma25:,.2f}\n"
            f"{posisi}\n"
            f"🕐 Waktu        : {waktu}"
        )
        kirim_telegram(pesan)
        print(f"[{waktu}] DEATH CROSS {label} terdeteksi!")

    else:
        print(f"[{waktu}] {label} — Tidak ada crossing. SMA3={sma3:.2f}, SMA7={sma7:.2f}")

def handle_cek(chat_id):
    """Balas command /cek dengan nilai SMA terkini H1 dan M15"""
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M")
    pesan = f"📊 <b>STATUS SMA — XAU/USD</b>\n🕐 {waktu}\n"

    for interval, label in [("1h", "H1"), ("15min", "M15"), ("5min", "M5")]:
        df = ambil_data(interval)
        if df is None:
            pesan += f"\n❌ {label}: Gagal ambil data\n"
            continue

        df["sma_fast"]  = hitung_sma_shift(df["close"], SMA_FAST_PERIOD,  SMA_FAST_SHIFT)
        df["sma_slow"]  = hitung_sma_shift(df["close"], SMA_SLOW_PERIOD,  SMA_SLOW_SHIFT)
        df["sma_trend"] = hitung_sma_shift(df["close"], SMA_TREND_PERIOD, SMA_TREND_SHIFT)
        df = df.dropna().reset_index(drop=True)

        curr  = df.iloc[-1]
        harga = curr["close"]
        sma3  = curr["sma_fast"]
        sma7  = curr["sma_slow"]
        sma25 = curr["sma_trend"]

        if sma3 > sma7:
            status = "🟢 SMA3 di ATAS SMA7"
        else:
            status = "🔴 SMA3 di BAWAH SMA7"

        posisi = "📈 Harga > SMA25" if harga > sma25 else "📉 Harga < SMA25"

        pesan += (
            f"\n━━━━ <b>{label}</b> ━━━━\n"
            f"💰 Harga        : <b>${harga:,.2f}</b>\n"
            f"〰️ SMA 3 (s3)  : {sma3:,.2f}\n"
            f"〰️ SMA 7 (s5)  : {sma7:,.2f}\n"
            f"〰️ SMA 25 (s5) : {sma25:,.2f}\n"
            f"{status}\n"
            f"{posisi}\n"
        )
        time.sleep(2)

    kirim_telegram(pesan, chat_id)

def cek_semua():
    cek_crossing_tf("1h", "H1")
    time.sleep(2)
    cek_crossing_tf("15min", "M15")
    time.sleep(2)
    cek_crossing_tf("5min", "M5")

# ─── LISTENER COMMAND TELEGRAM ────────────────────────────
last_update_id = None

def dengarkan_command():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    while True:
        try:
            params = {"timeout": 30, "offset": last_update_id}
            r = requests.get(url, params=params, timeout=35)
            data = r.json()
            for update in data.get("result", []):
                last_update_id = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                if text.strip().lower() == "/cek" and chat_id:
                    print(f"[{datetime.now()}] Command /cek diterima")
                    threading.Thread(target=handle_cek, args=(chat_id,)).start()
                elif text.strip().lower() == "/start" and chat_id:
                    kirim_telegram(
                        "🤖 <b>Bot XAU/USD SMA Cross aktif!</b>\n\n"
                        "Perintah yang tersedia:\n"
                        "/cek — Lihat nilai SMA terkini H1 &amp; M15",
                        chat_id
                    )
        except Exception as e:
            print(f"[{datetime.now()}] Error listener: {e}")
            time.sleep(5)

# ─── SCHEDULER ─────────────────────────────────────────────
schedule.every().hour.at(":02").do(lambda: cek_crossing_tf("1h", "H1"))
schedule.every(15).minutes.do(lambda: cek_crossing_tf("15min", "M15"))
schedule.every(5).minutes.do(lambda: cek_crossing_tf("5min", "M5"))

# ─── START ─────────────────────────────────────────────────
print("🤖 Bot XAU/USD SMA Cross mulai berjalan...")
kirim_telegram(
    "🤖 <b>Bot XAU/USD SMA Cross aktif!</b>\n"
    "Memantau Golden/Death Cross SMA 3 &amp; SMA 7\n"
    "📊 Timeframe: H1, M15 &amp; M5\n"
    "📐 Filter: Posisi harga vs SMA 25\n\n"
    "Ketik /cek untuk lihat nilai SMA terkini!"
)

# Jalankan listener command di thread terpisah
threading.Thread(target=dengarkan_command, daemon=True).start()

# Cek langsung saat pertama start
cek_semua()

while True:
    schedule.run_pending()
    time.sleep(30)
