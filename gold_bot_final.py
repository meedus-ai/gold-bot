#!/usr/bin/env python3
"""
صفقات الذهب - XAUUSD ICT Bot (Scalping + Swing)
Killzone إلزامية | M1 Scalping + M5 Swing
"""

import requests
import time
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

TELEGRAM_TOKEN = "8860469291:AAFdhIhTmx1qfWfCSPA77xMvBaTIJ_2v4fw"
CHAT_ID = "1904585446"
SYMBOL_YF = "GC=F"
CHECK_INTERVAL = 60  # كل دقيقة داخل Killzone

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ خطأ تيليجرام: {e}")
        return False

def get_candles(interval="1m", period="1d"):
    try:
        ticker = yf.Ticker(SYMBOL_YF)
        df = ticker.history(interval=interval, period=period)
        if df.empty:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        return df
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return None

def in_killzone():
    hour = datetime.now(timezone.utc).hour
    if 2 <= hour <= 5:
        return "🌏 Asia"
    elif 7 <= hour <= 10:
        return "🇬🇧 London"
    elif 12 <= hour <= 15:
        return "🇺🇸 New York"
    return None

def find_ob(df, lookback=15):
    obs = []
    for i in range(2, min(lookback, len(df)-1)):
        idx = -(i+1)
        candle = df.iloc[idx]
        next_c = df.iloc[idx+1]
        if (candle['close'] < candle['open'] and
            next_c['close'] > next_c['open'] and
            next_c['close'] > candle['high']):
            obs.append({'type': 'bullish', 'high': candle['high'], 'low': candle['low']})
        if (candle['close'] > candle['open'] and
            next_c['close'] < next_c['open'] and
            next_c['close'] < candle['low']):
            obs.append({'type': 'bearish', 'high': candle['high'], 'low': candle['low']})
    return obs

def find_fvg(df, lookback=15):
    fvgs = []
    for i in range(2, min(lookback, len(df)-1)):
        idx = -(i+1)
        prev = df.iloc[idx-1]
        nxt  = df.iloc[idx+1]
        if prev['high'] < nxt['low']:
            fvgs.append({'type': 'bullish', 'high': nxt['low'], 'low': prev['high']})
        if prev['low'] > nxt['high']:
            fvgs.append({'type': 'bearish', 'high': prev['low'], 'low': nxt['high']})
    return fvgs

def find_bos(df, lookback=30):
    if len(df) < lookback:
        return None
    recent = df.tail(lookback)
    highs = recent['high'].values
    lows  = recent['low'].values
    prev_high = max(highs[:-5])
    prev_low  = min(lows[:-5])
    if highs[-1] > prev_high:
        return 'bullish_bos'
    elif lows[-1] < prev_low:
        return 'bearish_bos'
    return None

def find_sweep(df, lookback=15):
    if len(df) < lookback + 2:
        return None
    recent = df.tail(lookback + 2)
    prev   = recent.iloc[:-2]
    last2  = recent.iloc[-2:]
    prev_high = prev['high'].max()
    prev_low  = prev['low'].min()
    c1 = last2.iloc[0]
    c2 = last2.iloc[1]
    if c1['high'] > prev_high and c2['close'] < prev_high:
        return 'bearish_sweep'
    if c1['low'] < prev_low and c2['close'] > prev_low:
        return 'bullish_sweep'
    return None

def judas_swing(df):
    if df is None or len(df) < 20:
        return None
    recent = df.tail(15)
    first_5 = recent.head(5)
    last_5  = recent.tail(5)
    first_high = first_5['high'].max()
    first_low  = first_5['low'].min()
    last_close = last_5.iloc[-1]['close']
    last_high  = last_5['high'].max()
    last_low   = last_5['low'].min()
    if last_high > first_high and last_close < first_high:
        return 'bearish_judas'
    if last_low < first_low and last_close > first_low:
        return 'bullish_judas'
    return None

def get_pd_zone(df, lookback=50):
    recent = df.tail(lookback)
    high = recent['high'].max()
    low  = recent['low'].min()
    mid  = (high + low) / 2
    current = df.iloc[-1]['close']
    return 'discount' if current < mid else 'premium'

# ============================================================
# تحليل SCALPING على M1
# ============================================================
def analyze_scalping(df_m1):
    current = df_m1.iloc[-1]['close']
    reasons = []
    buy_score = sell_score = 0

    judas = judas_swing(df_m1)
    sweep = find_sweep(df_m1, lookback=10)
    obs   = find_ob(df_m1, lookback=10)
    fvgs  = find_fvg(df_m1, lookback=10)

    if judas == 'bullish_judas':
        reasons.append("🃏 Judas Swing صاعد")
        buy_score += 2
    elif judas == 'bearish_judas':
        reasons.append("🃏 Judas Swing هابط")
        sell_score += 2

    if sweep == 'bullish_sweep':
        reasons.append("💧 Sweep صاعد M1")
        buy_score += 2
    elif sweep == 'bearish_sweep':
        reasons.append("💧 Sweep هابط M1")
        sell_score += 2

    for ob in [o for o in obs if o['type'] == 'bullish']:
        if ob['low'] <= current <= ob['high']:
            reasons.append(f"📦 Micro OB شراء")
            buy_score += 2
            break
    for ob in [o for o in obs if o['type'] == 'bearish']:
        if ob['low'] <= current <= ob['high']:
            reasons.append(f"📦 Micro OB بيع")
            sell_score += 2
            break
    for fvg in [f for f in fvgs if f['type'] == 'bullish']:
        if fvg['low'] <= current <= fvg['high']:
            reasons.append(f"⚡ Micro FVG شراء")
            buy_score += 1
            break
    for fvg in [f for f in fvgs if f['type'] == 'bearish']:
        if fvg['low'] <= current <= fvg['high']:
            reasons.append(f"⚡ Micro FVG بيع")
            sell_score += 1
            break

    atr = max(df_m1['high'].tail(10).mean() - df_m1['low'].tail(10).mean(), 0.5)
    signal = entry = sl = tp1 = tp2 = rr = None

    if buy_score >= 4 and buy_score > sell_score:
        signal = "BUY 🟢"
        entry  = round(current, 2)
        sl     = round(entry - atr * 1.0, 2)
        tp1    = round(entry + atr * 1.5, 2)
        tp2    = round(entry + atr * 2.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"
    elif sell_score >= 4 and sell_score > buy_score:
        signal = "SELL 🔴"
        entry  = round(current, 2)
        sl     = round(entry + atr * 1.0, 2)
        tp1    = round(entry - atr * 1.5, 2)
        tp2    = round(entry - atr * 2.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"

    return {"signal": signal, "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
            "rr": rr, "reasons": reasons, "buy": buy_score, "sell": sell_score}

# ============================================================
# تحليل SWING على M5
# ============================================================
def analyze_swing(df_m5):
    current = df_m5.iloc[-1]['close']
    reasons = []
    buy_score = sell_score = 0

    bos   = find_bos(df_m5)
    sweep = find_sweep(df_m5, lookback=20)
    pd_z  = get_pd_zone(df_m5)
    obs   = find_ob(df_m5, lookback=20)
    fvgs  = find_fvg(df_m5, lookback=20)

    if bos == 'bullish_bos':
        reasons.append("📈 BOS صاعد M5")
        buy_score += 1
    elif bos == 'bearish_bos':
        reasons.append("📉 BOS هابط M5")
        sell_score += 1

    if sweep == 'bullish_sweep':
        reasons.append("💧 Sweep صاعد M5")
        buy_score += 2
    elif sweep == 'bearish_sweep':
        reasons.append("💧 Sweep هابط M5")
        sell_score += 2

    if pd_z == 'discount':
        reasons.append("💚 منطقة Discount")
        buy_score += 1
    else:
        reasons.append("🔴 منطقة Premium")
        sell_score += 1

    for ob in [o for o in obs if o['type'] == 'bullish']:
        if ob['low'] <= current <= ob['high']:
            reasons.append(f"📦 OB شراء M5")
            buy_score += 2
            break
    for ob in [o for o in obs if o['type'] == 'bearish']:
        if ob['low'] <= current <= ob['high']:
            reasons.append(f"📦 OB بيع M5")
            sell_score += 2
            break
    for fvg in [f for f in fvgs if f['type'] == 'bullish']:
        if fvg['low'] <= current <= fvg['high']:
            reasons.append(f"⚡ FVG شراء M5")
            buy_score += 1
            break
    for fvg in [f for f in fvgs if f['type'] == 'bearish']:
        if fvg['low'] <= current <= fvg['high']:
            reasons.append(f"⚡ FVG بيع M5")
            sell_score += 1
            break

    atr = max(df_m5['high'].tail(14).mean() - df_m5['low'].tail(14).mean(), 1.0)
    signal = entry = sl = tp1 = tp2 = rr = None

    if buy_score >= 4 and buy_score > sell_score:
        signal = "BUY 🟢"
        entry  = round(current, 2)
        sl     = round(entry - atr * 1.5, 2)
        tp1    = round(entry + atr * 2.0, 2)
        tp2    = round(entry + atr * 3.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"
    elif sell_score >= 4 and sell_score > buy_score:
        signal = "SELL 🔴"
        entry  = round(current, 2)
        sl     = round(entry + atr * 1.5, 2)
        tp1    = round(entry - atr * 2.0, 2)
        tp2    = round(entry - atr * 3.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"

    return {"signal": signal, "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
            "rr": rr, "reasons": reasons, "buy": buy_score, "sell": sell_score}

# ============================================================
# تنسيق الرسائل
# ============================================================
def format_scalping(a, kz, price):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    reasons = "\n".join(f"  {r}" for r in a['reasons'])
    return (
        f"⚡ <b>إشارة SCALPING {a['signal']}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💹 <b>XAUUSD M1</b> | {now}\n"
        f"📍 {kz} Killzone\n\n"
        f"📌 <b>الدخول</b>       {a['entry']}\n"
        f"🛑 <b>وقف الخسارة</b>  {a['sl']}\n"
        f"🎯 <b>الهدف 1</b>      {a['tp1']}\n"
        f"🎯 <b>الهدف 2</b>      {a['tp2']}\n"
        f"⚖️ <b>نسبة RR</b>      {a['rr']}\n\n"
        f"📋 <b>الأسباب:</b>\n{reasons}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>SCALPING — هدف سريع 3-5$</b>\n"
        f"⚠️ <i>القرار النهائي لك</i>"
    )

def format_swing(a, kz, price):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    reasons = "\n".join(f"  {r}" for r in a['reasons'])
    return (
        f"📊 <b>إشارة SWING {a['signal']}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💹 <b>XAUUSD M5</b> | {now}\n"
        f"📍 {kz} Killzone\n\n"
        f"📌 <b>الدخول</b>       {a['entry']}\n"
        f"🛑 <b>وقف الخسارة</b>  {a['sl']}\n"
        f"🎯 <b>الهدف 1</b>      {a['tp1']}\n"
        f"🎯 <b>الهدف 2</b>      {a['tp2']}\n"
        f"⚖️ <b>نسبة RR</b>      {a['rr']}\n\n"
        f"📋 <b>الأسباب:</b>\n{reasons}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📊 <b>SWING — هدف 10-20$</b>\n"
        f"⚠️ <i>القرار النهائي لك</i>"
    )

# ============================================================
# الحلقة الرئيسية
# ============================================================
def main():
    print("=" * 50)
    print("🤖 صفقات الذهب - Scalping + Swing Bot")
    print("=" * 50)

    send_telegram(
        "🤖 <b>بوت صفقات الذهب النهائي شغّال!</b>\n\n"
        "⚡ <b>Scalping M1:</b>\n"
        "  • Judas Swing\n"
        "  • Micro OB + FVG\n"
        "  • هدف: 3-5$\n\n"
        "📊 <b>Swing M5:</b>\n"
        "  • BOS + Sweep\n"
        "  • OB + FVG + Premium/Discount\n"
        "  • هدف: 10-20$\n\n"
        "⏰ Killzones (بتوقيت السعودية):\n"
        "  🌏 Asia: 5-8 صباحاً\n"
        "  🇬🇧 London: 10ص-1ظ\n"
        "  🇺🇸 NY: 3-6 مساءً\n\n"
        "🔕 صامت خارج Killzone"
    )

    last_scalp_signal = None
    last_swing_signal = None
    last_scalp_time   = None
    last_swing_time   = None
    check_count = 0

    while True:
        check_count += 1
        now_str = datetime.now().strftime('%H:%M:%S')
        kz = in_killzone()

        if not kz:
            if check_count % 10 == 0:
                print(f"🚫 {now_str} — خارج Killzone")
            last_scalp_signal = None
            last_swing_signal = None
            time.sleep(CHECK_INTERVAL)
            continue

        print(f"\n🔍 فحص #{check_count} - {now_str} | {kz}")

        df_m1 = get_candles(interval="1m", period="1d")
        df_m5 = get_candles(interval="5m", period="5d")

        if df_m1 is None or df_m5 is None:
            print("⚠️ بيانات غير كافية")
            time.sleep(30)
            continue

        current = round(df_m1.iloc[-1]['close'], 2)
        print(f"💰 السعر: ${current}")

        now_time = datetime.now(timezone.utc)

        # --- Scalping ---
        scalp = analyze_scalping(df_m1)
        print(f"⚡ Scalp — Buy:{scalp['buy']} Sell:{scalp['sell']}")

        scalp_time_ok = True
        if last_scalp_time:
            scalp_time_ok = (now_time - last_scalp_time).seconds / 60 > 15

        if scalp['signal'] and (scalp['signal'] != last_scalp_signal or scalp_time_ok):
            msg = format_scalping(scalp, kz, current)
            if send_telegram(msg):
                print(f"✅ Scalping: {scalp['signal']}")
                last_scalp_signal = scalp['signal']
                last_scalp_time   = now_time
        else:
            if not scalp['signal']:
                last_scalp_signal = None

        # --- Swing ---
        swing = analyze_swing(df_m5)
        print(f"📊 Swing  — Buy:{swing['buy']} Sell:{swing['sell']}")

        swing_time_ok = True
        if last_swing_time:
            swing_time_ok = (now_time - last_swing_time).seconds / 60 > 30

        if swing['signal'] and (swing['signal'] != last_swing_signal or swing_time_ok):
            msg = format_swing(swing, kz, current)
            if send_telegram(msg):
                print(f"✅ Swing: {swing['signal']}")
                last_swing_signal = swing['signal']
                last_swing_time   = now_time
        else:
            if not swing['signal']:
                last_swing_signal = None

        print(f"⏱️ انتظار دقيقة...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 البوت أُوقف")
        send_telegram("🛑 <b>البوت أُوقف</b>")
