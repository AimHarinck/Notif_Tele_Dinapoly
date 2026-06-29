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

SMA_FAST   = 3
SMA_MID    = 7
SMA_SLOW   = 25
SHIFT_FAST = 3
SHIFT_MID  = 5
SHIFT_SLOW = 5

TIMEFRAMES = {
    "H1":  "1h",
    "M30": "30min"
}

last_cross = {tf: None for tf in TIMEFRAMES}
# ───────────────────────────────────────────────────────────

def kirim_telegram(pesan, chat_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id or CHAT_ID, "text": pesan, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print(f"[{datetime.now()}] Pesan terkirim")
    except Exception as e:
        print(f"[{datetime.now()}] Gagal kirim: {e}")

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
        print(f"Exception: {e}")
        return None

def hitung_sma(series, period):
    return series.rolling(period).mean()

def format_posisi_sma(s3, s7, s25):
    """Urutkan SMA dari nilai tertinggi ke terendah"""
    sma_dict = {"SMA3 (s3)": s3, "SMA7 (s5)": s7, "SMA25(s5)": s25}
    sorted_sma = sorted(sma_dict.items(), key=lambda x: x[1], reverse=True)
    hasil = ""
    for nama, nilai in sorted_sma:
        hasil += f"〰️ {nama} : {nilai:,.2f}\n"
    return hasil.strip()

def cek_signal(label, interval):
    global last_cross

    df = ambil_data(interval)
    if df is None or len(df) < 60:
        return

    df["sma3"]  = hitung_sma(df["close"], SMA_FAST)
    df["sma7"]  = hitung_sma(df["close"], SMA_MID)
    df["sma25"] = hitung_sma(df["close"], SMA_SLOW)

    df["sma3_shift"]  = df["sma3"].shift(SHIFT_FAST)
    df["sma7_shift"]  = df["sma7"].shift(SHIFT_MID)
    df["sma25_shift"] = df["sma25"].shift(SHIFT_SLOW)

    df = df.dropna().reset_index(drop=True)
    if len(df) < 3:
        return

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    buy_cross  = prev["sma3"] <= prev["sma7"] and curr["sma3"] > curr["sma7"]
    sell_cross = prev["sma3"] >= prev["sma7"] and curr["sma3"] < curr["sma7"]

    s3  = curr["sma3_shift"]
    s7  = curr["sma7_shift"]
    s25 = curr["sma25_shift"]

    posisi_sma = format_posisi_sma(s3, s7, s25)
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M")

    if buy_cross and last_cross[label] != "BUY":
        last_cross[label] = "BUY"

        if s3 > s25 and s7 > s25:
            tp = 5.0
            sl = 3.0
            kondisi = "BUY T (Searah Trend)"
        else:
            tp = 3.0
            sl = 5.0
            kondisi = "BUY C (Counter Trend)"

        entry    = curr["close"]
        tp_price = entry + tp
        sl_price = entry - sl

        pesan = (
            f"🟢 <b>{kondisi} — XAU/USD {label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📈 SMA 3 cross SMA 7 ke <b>ATAS</b>\n"
            f"💰 Entry : <b>${entry:,.2f}</b>\n"
            f"🎯 TP    : ${tp_price:,.2f} (+${tp})\n"
            f"🛑 SL    : ${sl_price:,.2f} (-${sl})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📐 Posisi SMA (atas→bawah):\n"
            f"{posisi_sma}\n"
            f"🕐 Waktu : {waktu}"
        )
        kirim_telegram(pesan)
        print(f"[{waktu}] BUY {label}")

    elif sell_cross and last_cross[label] != "SELL":
        last_cross[label] = "SELL"

        if s3 < s25 and s7 < s25:
            tp = 5.0
            sl = 3.0
            kondisi = "SELL T (Searah Trend)"
        else:
            tp = 3.0
            sl = 5.0
            kondisi = "SELL C (Counter Trend)"

        entry    = curr["close"]
        tp_price = entry - tp
        sl_price = entry + sl

        pesan = (
            f"🔴 <b>{kondisi} — XAU/USD {label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📉 SMA 3 cross SMA 7 ke <b>BAWAH</b>\n"
            f"💰 Entry : <b>${entry:,.2f}</b>\n"
            f"🎯 TP    : ${tp_price:,.2f} (-${tp})\n"
            f"🛑 SL    : ${sl_price:,.2f} (+${sl})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📐 Posisi SMA (atas→bawah):\n"
            f"{posisi_sma}\n"
            f"🕐 Waktu : {waktu}"
        )
        kirim_telegram(pesan)
        print(f"[{waktu}] SELL {label}")

    else:
        print(f"[{waktu}] {label} — Tidak ada sinyal baru")

def cek_semua():
    for label, interval in TIMEFRAMES.items():
        cek_signal(label, interval)
        time.sleep(2)

# ─── LISTENER COMMAND ─────────────────────────────────────
last_update_id = None

def handle_cek(chat_id):
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M")
    kirim_telegram(f"📊 <b>STATUS SMA — XAU/USD</b>\n🕐 {waktu}", chat_id)

    for label, interval in TIMEFRAMES.items():
        df = ambil_data(interval)
        if df is None:
            kirim_telegram(f"❌ {label}: Gagal ambil data", chat_id)
            continue

        df["sma3"]  = hitung_sma(df["close"], SMA_FAST)
        df["sma7"]  = hitung_sma(df["close"], SMA_MID)
        df["sma25"] = hitung_sma(df["close"], SMA_SLOW)
        df["sma3_shift"]  = df["sma3"].shift(SHIFT_FAST)
        df["sma7_shift"]  = df["sma7"].shift(SHIFT_MID)
        df["sma25_shift"] = df["sma25"].shift(SHIFT_SLOW)
        df = df.dropna().reset_index(drop=True)

        curr  = df.iloc[-1]
        harga = curr["close"]
        s3    = curr["sma3_shift"]
        s7    = curr["sma7_shift"]
        s25   = curr["sma25_shift"]

        posisi_sma = format_posisi_sma(s3, s7, s25)

        if s3 > s7:
            status = "🟢 SMA3 di ATAS SMA7"
        else:
            status = "🔴 SMA3 di BAWAH SMA7"

        kirim_telegram(
            f"━━━━ <b>{label}</b> ━━━━\n"
            f"💰 Harga : <b>${harga:,.2f}</b>\n"
            f"📐 Posisi SMA (atas→bawah):\n"
            f"{posisi_sma}\n"
            f"{status}",
            chat_id
        )
        time.sleep(3)

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
                msg  = update.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                if text.strip().lower() == "/cek" and chat_id:
                    threading.Thread(target=handle_cek, args=(chat_id,)).start()
                elif text.strip().lower() == "/start" and chat_id:
                    kirim_telegram(
                        "🤖 <b>Bot XAU/USD Aim Crossing aktif!</b>\n\n"
                        "📊 TF: H1 &amp; M30\n"
                        "📐 Logika: SMA 3/7/25 dengan Shift\n\n"
                        "Perintah:\n/cek — Status SMA terkini",
                        chat_id
                    )
        except Exception as e:
            print(f"[{datetime.now()}] Error listener: {e}")
            time.sleep(5)

# ─── SCHEDULER ─────────────────────────────────────────────
schedule.every().hour.at(":02").do(lambda: cek_signal("H1", "1h"))
schedule.every(30).minutes.do(lambda: cek_signal("M30", "30min"))

# ─── START ─────────────────────────────────────────────────
print("🤖 Bot XAU/USD Aim Crossing mulai berjalan...")
kirim_telegram(
    "🤖 <b>Bot XAU/USD Aim Crossing aktif!</b>\n"
    "📊 TF: H1 &amp; M30\n"
    "📐 Logika: SMA 3/7/25 dengan Shift\n\n"
    "Ketik /cek untuk status terkini!"
)

threading.Thread(target=dengarkan_command, daemon=True).start()
cek_semua()

while True:
    schedule.run_pending()
    time.sleep(30)
