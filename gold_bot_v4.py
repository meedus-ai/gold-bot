#!/usr/bin/env python3
"""
صفقات الذهب v4 - XAUUSD ICT Bot
بيانات حية من Twelve Data + Scalping + Swing
"""

import requests
import time
import pandas as pd
import numpy as np
from datetime import datetime, timezone

TELEGRAM_TOKEN = "8860469291:AAFdhIhTmx1qfWfCSPA77xMvBaTIJ_2v4fw"
CHAT_ID = "1904585446"
TWELVE_API_KEY = "7be6753a3c6a4fe3a3423811c72810bf"
SYMBOL = "XAU/USD"
CHECK_INTERVAL = 60

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ خطأ تيليجرام: {e}")
        return False

def get_candles(interval="1min", outputsize=100):
    """جلب بيانات حية من Twelve Data"""
    try:
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": SYMBOL,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": TWELVE_API_KEY,
            "format": "JSON"
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()

        if "values" not in data:
            print(f"⚠️ خطأ API: {data.get('message', 'unknown')}")
            return None

        df = pd.DataFrame(data["values"])
        df = df.rename(columns={
            "open": "open", "high": "high",
            "low": "low", "close": "close",
            "volume": "volume"
        })
        df[['open','high','low','close']] = df[['open','high','low','close']].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)  # ترتيب تصاعدي
        return df

    except Exception as e:
        print(f"❌ خطأ جلب البيانات: {e}")
        return None

def get_price():
    """جلب السعر الحالي"""
    try:
        url = "https://api.twelvedata.com/price"
        params = {"symbol": SYMBOL, "apikey": TWELVE_API_KEY}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return float(data["price"])
    except:
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
    if highs[-1] > max(highs[:-5]):
        return 'bullish_bos'
    elif lows[-1] < min(lows[:-5]):
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

def analyze_scalping(df_m1, price):
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
        if ob['low'] <= price <= ob['high']:
            reasons.append(f"📦 Micro OB شراء")
            buy_score += 2
            break
    for ob in [o for o in obs if o['type'] == 'bearish']:
        if ob['low'] <= price <= ob['high']:
            reasons.append(f"📦 Micro OB بيع")
            sell_score += 2
            break
    for fvg in [f for f in fvgs if f['type'] == 'bullish']:
        if fvg['low'] <= price <= fvg['high']:
            reasons.append(f"⚡ Micro FVG شراء")
            buy_score += 1
            break
    for fvg in [f for f in fvgs if f['type'] == 'bearish']:
        if fvg['low'] <= price <= fvg['high']:
            reasons.append(f"⚡ Micro FVG بيع")
            sell_score += 1
            break

    atr = max(df_m1['high'].tail(10).mean() - df_m1['low'].tail(10).mean(), 0.5)
    signal = entry = sl = tp1 = tp2 = rr = None

    if buy_score >= 4 and buy_score > sell_score:
        signal = "BUY 🟢"
        entry  = round(price, 2)
        sl     = round(entry - atr * 1.0, 2)
        tp1    = round(entry + atr * 1.5, 2)
        tp2    = round(entry + atr * 2.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"
    elif sell_score >= 4 and sell_score > buy_score:
        signal = "SELL 🔴"
        entry  = round(price, 2)
        sl     = round(entry + atr * 1.0, 2)
        tp1    = round(entry - atr * 1.5, 2)
        tp2    = round(entry - atr * 2.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"

    return {"signal": signal, "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
            "rr": rr, "reasons": reasons, "buy": buy_score, "sell": sell_score}

def analyze_swing(df_m5, price):
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
        if ob['low'] <= price <= ob['high']:
            reasons.append(f"📦 OB شراء M5")
            buy_score += 2
            break
    for ob in [o for o in obs if o['type'] == 'bearish']:
        if ob['low'] <= price <= ob['high']:
            reasons.append(f"📦 OB بيع M5")
            sell_score += 2
            break
    for fvg in [f for f in fvgs if f['type'] == 'bullish']:
        if fvg['low'] <= price <= fvg['high']:
            reasons.append(f"⚡ FVG شراء M5")
            buy_score += 1
            break
    for fvg in [f for f in fvgs if f['type'] == 'bearish']:
        if fvg['low'] <= price <= fvg['high']:
            reasons.append(f"⚡ FVG بيع M5")
            sell_score += 1
            break

    atr = max(df_m5['high'].tail(14).mean() - df_m5['low'].tail(14).mean(), 1.0)
    signal = entry = sl = tp1 = tp2 = rr = None

    if buy_score >= 4 and buy_score > sell_score:
        signal = "BUY 🟢"
        entry  = round(price, 2)
        sl     = round(entry - atr * 1.5, 2)
        tp1    = round(entry + atr * 2.0, 2)
        tp2    = round(entry + atr * 3.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"
    elif sell_score >= 4 and sell_score > buy_score:
        signal = "SELL 🔴"
        entry  = round(price, 2)
        sl     = round(entry + atr * 1.5, 2)
        tp1    = round(entry - atr * 2.0, 2)
        tp2    = round(entry - atr * 3.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"

    return {"signal": signal, "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
            "rr": rr, "reasons": reasons, "buy": buy_score, "sell": sell_score}

def format_scalping(a, kz, price):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    reasons = "\n".join(f"  {r}" for r in a['reasons'])
    return (
        f"⚡ <b>إشارة SCALPING {a['signal']}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💹 <b>XAUUSD M1</b> | {now}\n"
        f"📍 {kz} Killzone\n"
        f"💰 السعر: {price}\n\n"
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
        f"📍 {kz} Killzone\n"
        f"💰 السعر: {price}\n\n"
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

def main():
    print("=" * 50)
    print("🤖 صفقات الذهب v4 - Twelve Data")
    print("=" * 50)

    send_telegram(
        "🤖 <b>بوت صفقات الذهب v4 شغّال!</b>\n\n"
        "📡 <b>بيانات حية من Twelve Data</b>\n\n"
        "⚡ Scalping M1 + 📊 Swing M5\n"
        "🔕 صامت خارج Killzone\n\n"
        "⏰ Killzones (بتوقيت السعودية):\n"
        "  🌏 Asia: 5-8 صباحاً\n"
        "  🇬🇧 London: 10ص-1ظ\n"
        "  🇺🇸 NY: 3-6 مساءً"
    )

    last_scalp = None
    last_swing = None
    last_scalp_time = None
    last_swing_time = None
    check_count = 0

    while True:
        check_count += 1
        now_str = datetime.now().strftime('%H:%M:%S')
        kz = in_killzone()

        if not kz:
            if check_count % 10 == 0:
                print(f"🚫 {now_str} — خارج Killzone")
            last_scalp = None
            last_swing = None
            time.sleep(CHECK_INTERVAL)
            continue

        print(f"\n⚡ فحص #{check_count} - {now_str} | {kz}")

        # جلب السعر الحالي
        price = get_price()
        if not price:
            print("⚠️ تعذر جلب السعر")
            time.sleep(30)
            continue

        print(f"💰 السعر الحي: ${price}")

        # جلب الكانديلز
        df_m1 = get_candles(interval="1min", outputsize=50)
        df_m5 = get_candles(interval="5min", outputsize=100)

        if df_m1 is None or df_m5 is None:
            print("⚠️ بيانات غير كافية")
            time.sleep(30)
            continue

        now_time = datetime.now(timezone.utc)

        # Scalping
        scalp = analyze_scalping(df_m1, price)
        print(f"⚡ Scalp — Buy:{scalp['buy']} Sell:{scalp['sell']}")

        scalp_ok = True
        if last_scalp_time:
            scalp_ok = (now_time - last_scalp_time).seconds / 60 > 15

        if scalp['signal'] and (scalp['signal'] != last_scalp or scalp_ok):
            if send_telegram(format_scalping(scalp, kz, price)):
                print(f"✅ Scalping: {scalp['signal']}")
                last_scalp = scalp['signal']
                last_scalp_time = now_time
        elif not scalp['signal']:
            last_scalp = None

        # Swing
        swing = analyze_swing(df_m5, price)
        print(f"📊 Swing  — Buy:{swing['buy']} Sell:{swing['sell']}")

        swing_ok = True
        if last_swing_time:
            swing_ok = (now_time - last_swing_time).seconds / 60 > 30

        if swing['signal'] and (swing['signal'] != last_swing or swing_ok):
            if send_telegram(format_swing(swing, kz, price)):
                print(f"✅ Swing: {swing['signal']}")
                last_swing = swing['signal']
                last_swing_time = now_time
        elif not swing['signal']:
            last_swing = None

        print(f"⏱️ انتظار دقيقة...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 البوت أُوقف")
        send_telegram("🛑 <b>البوت أُوقف</b>")
