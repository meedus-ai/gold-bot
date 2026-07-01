#!/usr/bin/env python3
"""
صفقات الذهب v3 - XAUUSD ICT Trading Bot
Killzone إلزامية + Liquidity Sweep + تحليل أقوى
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
CHECK_INTERVAL = 300

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ خطأ تيليجرام: {e}")
        return False

def get_candles(interval="5m", period="5d"):
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

def in_killzone():
    hour = datetime.now(timezone.utc).hour
    if 2 <= hour <= 5:
        return "🌏 Asia Killzone"
    elif 7 <= hour <= 10:
        return "🇬🇧 London Killzone"
    elif 12 <= hour <= 15:
        return "🇺🇸 New York Killzone"
    return None

def find_order_blocks(df, lookback=20):
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

def find_fvg(df, lookback=20):
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
    curr_high = highs[-1]
    curr_low  = lows[-1]
    if curr_high > prev_high:
        return 'bullish_bos'
    elif curr_low < prev_low:
        return 'bearish_bos'
    return None

def find_liquidity_sweep(df, lookback=20):
    """
    كشف Liquidity Sweep:
    السعر يخترق قمة/قاع سابق ثم يرجع بسرعة
    """
    if len(df) < lookback + 2:
        return None

    recent = df.tail(lookback + 2)
    prev   = recent.iloc[:-2]
    last2  = recent.iloc[-2:]

    prev_high = prev['high'].max()
    prev_low  = prev['low'].min()

    candle1 = last2.iloc[0]
    candle2 = last2.iloc[1]

    # Bearish sweep: اخترق القمة ثم أغلق تحتها
    if (candle1['high'] > prev_high and
        candle2['close'] < prev_high):
        return 'bearish_sweep'

    # Bullish sweep: اخترق القاع ثم أغلق فوقه
    if (candle1['low'] < prev_low and
        candle2['close'] > prev_low):
        return 'bullish_sweep'

    return None

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

def analyze(df):
    current_price = df.iloc[-1]['close']
    signal  = None
    reasons = []
    entry = sl = tp1 = tp2 = None

    # 1. Killzone — إلزامية
    kz = in_killzone()
    if kz:
        reasons.append(f"✅ {kz}")
    else:
        reasons.append("🚫 خارج Killzone — لا إشارة")
        return {
            "price": round(current_price, 2),
            "signal": None,
            "entry": None, "sl": None, "tp1": None, "tp2": None, "rr": None,
            "reasons": reasons,
            "buy_score": 0, "sell_score": 0,
            "no_kz": True
        }

    # 2. BOS
    bos = find_bos(df)
    if bos == 'bullish_bos':
        reasons.append("📈 BOS صاعد مؤكد")
    elif bos == 'bearish_bos':
        reasons.append("📉 BOS هابط مؤكد")

    # 3. Liquidity Sweep
    sweep = find_liquidity_sweep(df)
    if sweep == 'bearish_sweep':
        reasons.append("💧 Liquidity Sweep هابط")
    elif sweep == 'bullish_sweep':
        reasons.append("💧 Liquidity Sweep صاعد")

    # 4. Premium / Discount
    pd_zone, rng_high, rng_low, rng_mid = get_pd_zone(df)
    if pd_zone == 'discount':
        reasons.append("💚 منطقة Discount")
    else:
        reasons.append("🔴 منطقة Premium")

    # 5. Order Blocks
    obs = find_order_blocks(df)
    bullish_obs = [o for o in obs if o['type'] == 'bullish']
    bearish_obs = [o for o in obs if o['type'] == 'bearish']

    # 6. FVG
    fvgs = find_fvg(df)
    bullish_fvgs = [f for f in fvgs if f['type'] == 'bullish']
    bearish_fvgs = [f for f in fvgs if f['type'] == 'bearish']

    # Score الشراء
    buy_score = 0
    if bos == 'bullish_bos':    buy_score += 1
    if sweep == 'bullish_sweep': buy_score += 2  # مهم جداً
    if pd_zone == 'discount':   buy_score += 1

    for ob in bullish_obs:
        if ob['low'] <= current_price <= ob['high']:
            buy_score += 2
            reasons.append(f"📦 OB شراء ({ob['low']:.1f} - {ob['high']:.1f})")
            break
    for fvg in bullish_fvgs:
        if fvg['low'] <= current_price <= fvg['high']:
            buy_score += 1
            reasons.append(f"⚡ FVG شراء ({fvg['low']:.1f} - {fvg['high']:.1f})")
            break

    # Score البيع
    sell_score = 0
    if bos == 'bearish_bos':    sell_score += 1
    if sweep == 'bearish_sweep': sell_score += 2  # مهم جداً
    if pd_zone == 'premium':    sell_score += 1

    for ob in bearish_obs:
        if ob['low'] <= current_price <= ob['high']:
            sell_score += 2
            reasons.append(f"📦 OB بيع ({ob['low']:.1f} - {ob['high']:.1f})")
            break
    for fvg in bearish_fvgs:
        if fvg['low'] <= current_price <= fvg['high']:
            sell_score += 1
            reasons.append(f"⚡ FVG بيع ({fvg['low']:.1f} - {fvg['high']:.1f})")
            break

    # القرار — يحتاج 4+ مع Killzone
    atr = df['high'].tail(14).mean() - df['low'].tail(14).mean()

    if buy_score >= 4 and buy_score > sell_score:
        signal = "BUY 🟢"
        entry = round(current_price, 2)
        sl    = round(entry - atr * 1.5, 2)
        tp1   = round(entry + atr * 2.0, 2)
        tp2   = round(entry + atr * 3.5, 2)

    elif sell_score >= 4 and sell_score > buy_score:
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
        "price": round(current_price, 2),
        "signal": signal,
        "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr,
        "reasons": reasons,
        "buy_score": buy_score, "sell_score": sell_score,
        "no_kz": False
    }

def format_message(a):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    reasons_text = "\n".join(f"  {r}" for r in a['reasons'])

    if a.get('no_kz'):
        return None  # لا نرسل شيء خارج Killzone

    if not a['signal']:
        return (
            f"🔍 <b>تحليل XAUUSD</b> | {now}\n"
            f"💰 السعر: <b>{a['price']}</b>\n\n"
            f"📊 التحليل:\n{reasons_text}\n\n"
            f"📈 شراء: {a['buy_score']} | 📉 بيع: {a['sell_score']}\n\n"
            f"⏳ <i>Killzone نشطة لكن لا confluence كافي</i>"
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

def main():
    print("=" * 50)
    print("🤖 صفقات الذهب v3 - ICT Bot")
    print("=" * 50)

    send_telegram(
        "🤖 <b>بوت صفقات الذهب v3 شغّال!</b>\n\n"
        "✅ Killzone إلزامية\n"
        "💧 Liquidity Sweep فلتر\n"
        "📊 Confluence 4+ مطلوب\n"
        "🔕 صامت خارج Killzone\n\n"
        "⏰ Killzones:\n"
        "  🌏 Asia: 5-8 صباحاً\n"
        "  🇬🇧 London: 10-1 ظهراً\n"
        "  🇺🇸 NY: 3-6 مساءً\n"
        "(بتوقيت السعودية)"
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

        if result.get('no_kz'):
            print("🚫 خارج Killzone — صامت")
            last_signal = None
            time.sleep(CHECK_INTERVAL)
            continue

        signal = result['signal']
        print(f"📈 Buy: {result['buy_score']} | 📉 Sell: {result['sell_score']}")

        if signal and signal != last_signal:
            msg = format_message(result)
            if msg and send_telegram(msg):
                print(f"✅ إشارة أُرسلت: {signal}")
                last_signal = signal
        else:
            if not signal:
                print("⏳ Killzone نشطة — لا confluence كافي")
                last_signal = None
            else:
                print("⏸️ نفس الإشارة — لم أرسل")

        print(f"⏱️ انتظار {CHECK_INTERVAL//60} دقائق...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 البوت أُوقف")
        send_telegram("🛑 <b>البوت أُوقف</b>")
