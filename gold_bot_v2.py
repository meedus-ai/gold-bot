#!/usr/bin/env python3
"""
صفقات الذهب v2 - XAUUSD ICT Trading Bot
بيانات حقيقية من yfinance + تحليل ICT كامل
"""

import requests
import time
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# ============================================================
# ⚙️ الإعدادات
# ============================================================
TELEGRAM_TOKEN = "8860469291:AAFdhIhTmx1qfWfCSPA77xMvBaTIJ_2v4fw"
CHAT_ID = "1904585446"
SYMBOL_YF = "GC=F"       # رمز الذهب في Yahoo Finance
CHECK_INTERVAL = 300      # كل 5 دقائق

# ============================================================
# 📱 إرسال تيليجرام
# ============================================================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ خطأ تيليجرام: {e}")
        return False

# ============================================================
# 📊 جلب بيانات الكانديلز الحقيقية
# ============================================================
def get_candles(interval="5m", period="1d"):
    try:
        ticker = yf.Ticker(SYMBOL_YF)
        df = ticker.history(interval=interval, period=period)
        if df.empty:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        return df
    except Exception as e:
        print(f"❌ خطأ جلب البيانات: {e}")
        return None

# ============================================================
# 🧠 كشف Order Blocks
# ============================================================
def find_order_blocks(df, lookback=20):
    obs = []
    for i in range(2, min(lookback, len(df)-1)):
        idx = -(i+1)
        candle = df.iloc[idx]
        next_c = df.iloc[idx+1]
        next2  = df.iloc[idx+2] if idx+2 < 0 else df.iloc[-1]

        # Bullish OB: كانديلة هابطة تليها حركة صاعدة قوية
        if (candle['close'] < candle['open'] and
            next_c['close'] > next_c['open'] and
            next_c['close'] > candle['high']):
            obs.append({
                'type': 'bullish',
                'high': candle['high'],
                'low':  candle['low'],
                'mid':  (candle['high'] + candle['low']) / 2
            })

        # Bearish OB: كانديلة صاعدة تليها حركة هابطة قوية
        if (candle['close'] > candle['open'] and
            next_c['close'] < next_c['open'] and
            next_c['close'] < candle['low']):
            obs.append({
                'type': 'bearish',
                'high': candle['high'],
                'low':  candle['low'],
                'mid':  (candle['high'] + candle['low']) / 2
            })
    return obs

# ============================================================
# 🧠 كشف Fair Value Gaps
# ============================================================
def find_fvg(df, lookback=20):
    fvgs = []
    for i in range(2, min(lookback, len(df)-1)):
        idx = -(i+1)
        prev = df.iloc[idx-1]
        curr = df.iloc[idx]
        nxt  = df.iloc[idx+1]

        # Bullish FVG: فجوة صاعدة
        if prev['high'] < nxt['low']:
            fvgs.append({
                'type': 'bullish',
                'high': nxt['low'],
                'low':  prev['high'],
                'mid':  (nxt['low'] + prev['high']) / 2
            })

        # Bearish FVG: فجوة هابطة
        if prev['low'] > nxt['high']:
            fvgs.append({
                'type': 'bearish',
                'high': prev['low'],
                'low':  nxt['high'],
                'mid':  (prev['low'] + nxt['high']) / 2
            })
    return fvgs

# ============================================================
# 🧠 كشف BOS / CHoCH
# ============================================================
def find_bos(df, lookback=30):
    if len(df) < lookback:
        return None

    recent = df.tail(lookback)
    highs = recent['high'].values
    lows  = recent['low'].values

    prev_high = max(highs[:-5])
    prev_low  = min(lows[:-5])
    curr_high = highs[-1]
    curr_low  = lows[-1]

    if curr_high > prev_high:
        return 'bullish_bos'
    elif curr_low < prev_low:
        return 'bearish_bos'
    return None

# ============================================================
# 🧠 Premium / Discount Zone
# ============================================================
def get_pd_zone(df, lookback=50):
    recent = df.tail(lookback)
    high = recent['high'].max()
    low  = recent['low'].min()
    mid  = (high + low) / 2
    current = df.iloc[-1]['close']

    if current < mid:
        return 'discount', high, low, mid
    else:
        return 'premium', high, low, mid

# ============================================================
# ⏰ Killzone Check
# ============================================================
def in_killzone():
    hour = datetime.now(timezone.utc).hour
    minute = datetime.now(timezone.utc).minute

    if 2 <= hour <= 5:
        return "🌏 Asia Killzone"
    elif 7 <= hour <= 10:
        return "🇬🇧 London Killzone"
    elif 12 <= hour <= 15:
        return "🇺🇸 New York Killzone"
    return None

# ============================================================
# 🎯 التحليل الكامل وتحديد الإشارة
# ============================================================
def analyze(df):
    current_price = df.iloc[-1]['close']
    signal = None
    reasons = []
    entry = sl = tp1 = tp2 = None

    # 1. Killzone
    kz = in_killzone()
    if kz:
        reasons.append(f"✅ {kz}")
    else:
        reasons.append("⏰ خارج Killzone")

    # 2. BOS
    bos = find_bos(df)
    if bos == 'bullish_bos':
        reasons.append("📈 BOS صاعد مؤكد")
    elif bos == 'bearish_bos':
        reasons.append("📉 BOS هابط مؤكد")

    # 3. Premium / Discount
    pd_zone, rng_high, rng_low, rng_mid = get_pd_zone(df)
    if pd_zone == 'discount':
        reasons.append("💚 منطقة Discount — يفضل الشراء")
    else:
        reasons.append("🔴 منطقة Premium — يفضل البيع")

    # 4. Order Blocks
    obs = find_order_blocks(df)
    bullish_obs = [o for o in obs if o['type'] == 'bullish']
    bearish_obs = [o for o in obs if o['type'] == 'bearish']

    # 5. FVG
    fvgs = find_fvg(df)
    bullish_fvgs = [f for f in fvgs if f['type'] == 'bullish']
    bearish_fvgs = [f for f in fvgs if f['type'] == 'bearish']

    # ============================================================
    # منطق الإشارة — شراء
    # ============================================================
    buy_confluence = 0

    if bos == 'bullish_bos': buy_confluence += 1
    if pd_zone == 'discount': buy_confluence += 1
    if kz: buy_confluence += 1

    # السعر في OB صاعد
    for ob in bullish_obs:
        if ob['low'] <= current_price <= ob['high']:
            buy_confluence += 2
            reasons.append(f"📦 داخل Order Block شراء ({ob['low']:.2f} - {ob['high']:.2f})")
            break

    # السعر في FVG صاعد
    for fvg in bullish_fvgs:
        if fvg['low'] <= current_price <= fvg['high']:
            buy_confluence += 1
            reasons.append(f"⚡ داخل FVG شراء ({fvg['low']:.2f} - {fvg['high']:.2f})")
            break

    # ============================================================
    # منطق الإشارة — بيع
    # ============================================================
    sell_confluence = 0

    if bos == 'bearish_bos': sell_confluence += 1
    if pd_zone == 'premium': sell_confluence += 1
    if kz: sell_confluence += 1

    for ob in bearish_obs:
        if ob['low'] <= current_price <= ob['high']:
            sell_confluence += 2
            reasons.append(f"📦 داخل Order Block بيع ({ob['low']:.2f} - {ob['high']:.2f})")
            break

    for fvg in bearish_fvgs:
        if fvg['low'] <= current_price <= fvg['high']:
            sell_confluence += 1
            reasons.append(f"⚡ داخل FVG بيع ({fvg['low']:.2f} - {fvg['high']:.2f})")
            break

    # ============================================================
    # القرار النهائي — يحتاج 3+ confluence
    # ============================================================
    atr = df['high'].tail(14).mean() - df['low'].tail(14).mean()

    if buy_confluence >= 3 and buy_confluence > sell_confluence:
        signal = "BUY 🟢"
        entry = round(current_price, 2)
        sl    = round(entry - atr * 1.5, 2)
        tp1   = round(entry + atr * 2.0, 2)
        tp2   = round(entry + atr * 3.5, 2)

    elif sell_confluence >= 3 and sell_confluence > buy_confluence:
        signal = "SELL 🔴"
        entry = round(current_price, 2)
        sl    = round(entry + atr * 1.5, 2)
        tp1   = round(entry - atr * 2.0, 2)
        tp2   = round(entry - atr * 3.5, 2)

    rr = None
    if signal and entry and sl and tp2:
        risk   = abs(entry - sl)
        reward = abs(tp2 - entry)
        rr = f"1:{round(reward/risk, 1)}" if risk > 0 else "N/A"

    return {
        "price":   round(current_price, 2),
        "signal":  signal,
        "entry":   entry,
        "sl":      sl,
        "tp1":     tp1,
        "tp2":     tp2,
        "rr":      rr,
        "reasons": reasons,
        "buy_score":  buy_confluence,
        "sell_score": sell_confluence
    }

# ============================================================
# 📨 تنسيق الرسالة
# ============================================================
def format_message(a):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    reasons_text = "\n".join(f"  {r}" for r in a['reasons'])

    if not a['signal']:
        return (
            f"🔍 <b>تحليل XAUUSD</b> | {now}\n"
            f"💰 السعر: <b>{a['price']}</b>\n\n"
            f"📊 التحليل:\n{reasons_text}\n\n"
            f"📈 درجة الشراء: {a['buy_score']} | 📉 درجة البيع: {a['sell_score']}\n\n"
            f"⏳ <i>لا إشارة كافية — أنتظر confluence أقوى</i>"
        )

    return (
        f"🚨 <b>إشارة {a['signal']}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💹 <b>XAUUSD</b> | {now}\n\n"
        f"📌 <b>الدخول</b>       {a['entry']}\n"
        f"🛑 <b>وقف الخسارة</b>  {a['sl']}\n"
        f"🎯 <b>الهدف 1</b>      {a['tp1']}\n"
        f"🎯 <b>الهدف 2</b>      {a['tp2']}\n"
        f"⚖️ <b>نسبة RR</b>      {a['rr']}\n\n"
        f"📋 <b>الأسباب:</b>\n{reasons_text}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>القرار النهائي لك</i>"
    )

# ============================================================
# 🚀 الحلقة الرئيسية
# ============================================================
def main():
    print("=" * 50)
    print("🤖 صفقات الذهب v2 - ICT Bot")
    print("=" * 50)

    send_telegram(
        "🤖 <b>بوت صفقات الذهب v2 شغّال!</b>\n\n"
        "📊 بيانات حقيقية من السوق\n"
        "🧠 تحليل ICT كامل:\n"
        "  • Order Blocks حقيقية\n"
        "  • Fair Value Gaps\n"
        "  • BOS / CHoCH\n"
        "  • Premium & Discount\n"
        "  • Killzones\n\n"
        "⏰ فحص كل 5 دقائق"
    )

    last_signal = None
    check_count = 0

    while True:
        check_count += 1
        now = datetime.now().strftime('%H:%M:%S')
        print(f"\n🔍 فحص #{check_count} - {now}")

        df = get_candles(interval="5m", period="5d")

        if df is None or len(df) < 30:
            print("⚠️ بيانات غير كافية")
            time.sleep(60)
            continue

        current = round(df.iloc[-1]['close'], 2)
        print(f"💰 السعر: ${current}")

        result = analyze(df)
        signal = result['signal']

        print(f"📈 Buy Score: {result['buy_score']} | 📉 Sell Score: {result['sell_score']}")

        if signal and signal != last_signal:
            msg = format_message(result)
            if send_telegram(msg):
                print(f"✅ إشارة أُرسلت: {signal}")
                last_signal = signal
        else:
            if not signal:
                print(f"⏳ لا إشارة كافية")
                last_signal = None
            else:
                print(f"⏸️ نفس الإشارة السابقة — لم أرسل")

        print(f"⏱️ انتظار {CHECK_INTERVAL//60} دقائق...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 البوت أُوقف")
        send_telegram("🛑 <b>البوت أُوقف</b>\nتم إيقاف المراقبة يدوياً")
