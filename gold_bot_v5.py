#!/usr/bin/env python3
"""
صفقات الذهب v5 - HTF Bias + Weekly Profile + Scalping + Swing
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
        df[['open','high','low','close']] = df[['open','high','low','close']].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)
        return df
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return None

def get_price():
    try:
        url = "https://api.twelvedata.com/price"
        params = {"symbol": SYMBOL, "apikey": TWELVE_API_KEY}
        r = requests.get(url, params=params, timeout=10)
        return float(r.json()["price"])
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

# ============================================================
# 🧠 HTF Bias — تحليل D1 و H4
# ============================================================
def get_htf_bias():
    """
    يحلل D1 و H4 ويحدد الاتجاه العام
    Returns: 'bullish', 'bearish', 'neutral'
    """
    try:
        df_d1 = get_candles(interval="1day", outputsize=30)
        df_h4 = get_candles(interval="4h", outputsize=30)

        if df_d1 is None or df_h4 is None:
            return 'neutral', 'neutral', 'neutral'

        # D1 Bias
        d1_highs = df_d1['high'].tail(10).values
        d1_lows  = df_d1['low'].tail(10).values
        d1_close = df_d1['close'].iloc[-1]
        d1_ema   = df_d1['close'].tail(10).mean()

        # Higher Highs & Higher Lows = Bullish
        d1_bias = 'neutral'
        if d1_highs[-1] > d1_highs[-3] and d1_lows[-1] > d1_lows[-3]:
            d1_bias = 'bullish'
        elif d1_highs[-1] < d1_highs[-3] and d1_lows[-1] < d1_lows[-3]:
            d1_bias = 'bearish'

        # H4 Bias
        h4_highs = df_h4['high'].tail(10).values
        h4_lows  = df_h4['low'].tail(10).values

        h4_bias = 'neutral'
        if h4_highs[-1] > h4_highs[-3] and h4_lows[-1] > h4_lows[-3]:
            h4_bias = 'bullish'
        elif h4_highs[-1] < h4_highs[-3] and h4_lows[-1] < h4_lows[-3]:
            h4_bias = 'bearish'

        # Overall Bias
        if d1_bias == 'bullish' and h4_bias == 'bullish':
            overall = 'bullish'
        elif d1_bias == 'bearish' and h4_bias == 'bearish':
            overall = 'bearish'
        else:
            overall = 'neutral'

        return overall, d1_bias, h4_bias

    except Exception as e:
        print(f"❌ خطأ HTF: {e}")
        return 'neutral', 'neutral', 'neutral'

# ============================================================
# 📅 Weekly Profile
# ============================================================
def get_weekly_profile():
    """
    يحدد طابع الأسبوع:
    - أين السيولة الأسبوعية؟
    - هل الأسبوع صاعد أم هابط؟
    """
    try:
        df_d1 = get_candles(interval="1day", outputsize=10)
        if df_d1 is None:
            return None

        # آخر 5 أيام = أسبوع تداول
        week = df_d1.tail(5)
        week_high = week['high'].max()
        week_low  = week['low'].min()
        week_open = week['open'].iloc[0]
        week_close = week['close'].iloc[-1]

        # اتجاه الأسبوع
        week_bias = 'bullish' if week_close > week_open else 'bearish'

        # مستويات السيولة
        buy_side_liq  = round(week_high, 2)  # سيولة فوق القمة
        sell_side_liq = round(week_low, 2)   # سيولة تحت القاع

        return {
            'bias': week_bias,
            'high': week_high,
            'low': week_low,
            'buy_liq': buy_side_liq,
            'sell_liq': sell_side_liq
        }
    except Exception as e:
        print(f"❌ خطأ Weekly: {e}")
        return None

# ============================================================
# تحليل ICT (نفس v4)
# ============================================================
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

# ============================================================
# تحليل Scalping مع HTF Filter
# ============================================================
def analyze_scalping(df_m1, price, htf_bias):
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
            reasons.append("📦 Micro OB شراء")
            buy_score += 2
            break
    for ob in [o for o in obs if o['type'] == 'bearish']:
        if ob['low'] <= price <= ob['high']:
            reasons.append("📦 Micro OB بيع")
            sell_score += 2
            break
    for fvg in [f for f in fvgs if f['type'] == 'bullish']:
        if fvg['low'] <= price <= fvg['high']:
            reasons.append("⚡ Micro FVG شراء")
            buy_score += 1
            break
    for fvg in [f for f in fvgs if f['type'] == 'bearish']:
        if fvg['low'] <= price <= fvg['high']:
            reasons.append("⚡ Micro FVG بيع")
            sell_score += 1
            break

    # HTF Filter — أهم جزء
    if htf_bias == 'bullish':
        sell_score = 0  # نلغي إشارات البيع إذا HTF صاعد
        reasons.append("✅ HTF Bias صاعد — BUY فقط")
    elif htf_bias == 'bearish':
        buy_score = 0   # نلغي إشارات الشراء إذا HTF هابط
        reasons.append("✅ HTF Bias هابط — SELL فقط")
    else:
        reasons.append("⚠️ HTF Neutral — حذر")

    atr = max(df_m1['high'].tail(10).mean() - df_m1['low'].tail(10).mean(), 0.5)
    signal = entry = sl = tp1 = tp2 = rr = None

    if buy_score >= 4 and buy_score > sell_score:
        signal = "BUY 🟢"
        entry  = round(price, 2)
        raw_sl = atr * 1.5
        sl_dist = max(raw_sl, 3.0)  # حد أدنى 3$
        sl     = round(entry - sl_dist, 2)
        tp1    = round(entry + sl_dist * 2.0, 2)
        tp2    = round(entry + sl_dist * 3.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"
    elif sell_score >= 4 and sell_score > buy_score:
        signal = "SELL 🔴"
        entry  = round(price, 2)
        raw_sl = atr * 1.5
        sl_dist = max(raw_sl, 3.0)  # حد أدنى 3$
        sl     = round(entry + sl_dist, 2)
        tp1    = round(entry - sl_dist * 2.0, 2)
        tp2    = round(entry - sl_dist * 3.5, 2)
        rr     = f"1:{round(abs(tp2-entry)/abs(entry-sl), 1)}"

    return {"signal": signal, "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
            "rr": rr, "reasons": reasons, "buy": buy_score, "sell": sell_score}

# ============================================================
# تحليل Swing مع HTF Filter
# ============================================================
def analyze_swing(df_m5, price, htf_bias, weekly):
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
            reasons.append("📦 OB شراء M5")
            buy_score += 2
            break
    for ob in [o for o in obs if o['type'] == 'bearish']:
        if ob['low'] <= price <= ob['high']:
            reasons.append("📦 OB بيع M5")
            sell_score += 2
            break
    for fvg in [f for f in fvgs if f['type'] == 'bullish']:
        if fvg['low'] <= price <= fvg['high']:
            reasons.append("⚡ FVG شراء M5")
            buy_score += 1
            break
    for fvg in [f for f in fvgs if f['type'] == 'bearish']:
        if fvg['low'] <= price <= fvg['high']:
            reasons.append("⚡ FVG بيع M5")
            sell_score += 1
            break

    # Weekly Profile
    if weekly:
        if weekly['bias'] == 'bullish':
            reasons.append(f"📅 Weekly صاعد | سيولة فوق {weekly['buy_liq']}")
            buy_score += 1
        else:
            reasons.append(f"📅 Weekly هابط | سيولة تحت {weekly['sell_liq']}")
            sell_score += 1

    # HTF Filter
    if htf_bias == 'bullish':
        sell_score = 0
        reasons.append("✅ HTF Bias صاعد — BUY فقط")
    elif htf_bias == 'bearish':
        buy_score = 0
        reasons.append("✅ HTF Bias هابط — SELL فقط")
    else:
        reasons.append("⚠️ HTF Neutral — حذر")

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

# ============================================================
# تنسيق الرسائل
# ============================================================
def htf_emoji(bias):
    if bias == 'bullish': return "📈 صاعد"
    if bias == 'bearish': return "📉 هابط"
    return "➡️ محايد"

def format_scalping(a, kz, price, htf, d1, h4):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    reasons = "\n".join(f"  {r}" for r in a['reasons'])
    return (
        f"⚡ <b>إشارة SCALPING {a['signal']}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💹 <b>XAUUSD M1</b> | {now}\n"
        f"📍 {kz} Killzone\n"
        f"💰 السعر: {price}\n\n"
        f"🔭 <b>HTF Bias:</b>\n"
        f"  D1: {htf_emoji(d1)}\n"
        f"  H4: {htf_emoji(h4)}\n"
        f"  الاتجاه العام: {htf_emoji(htf)}\n\n"
        f"📌 <b>الدخول</b>       {a['entry']}\n"
        f"🛑 <b>وقف الخسارة</b>  {a['sl']}\n"
        f"🎯 <b>الهدف 1</b>      {a['tp1']}\n"
        f"🎯 <b>الهدف 2</b>      {a['tp2']}\n"
        f"⚖️ <b>نسبة RR</b>      {a['rr']}\n\n"
        f"📋 <b>الأسباب:</b>\n{reasons}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>SCALPING — هدف 3-5$</b>\n"
        f"⚠️ <i>القرار النهائي لك</i>"
    )

def format_swing(a, kz, price, htf, d1, h4, weekly):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    reasons = "\n".join(f"  {r}" for r in a['reasons'])
    weekly_text = ""
    if weekly:
        weekly_text = (
            f"📅 <b>Weekly Profile:</b>\n"
            f"  اتجاه: {htf_emoji(weekly['bias'])}\n"
            f"  سيولة فوق: {weekly['buy_liq']}\n"
            f"  سيولة تحت: {weekly['sell_liq']}\n\n"
        )
    return (
        f"📊 <b>إشارة SWING {a['signal']}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💹 <b>XAUUSD M5</b> | {now}\n"
        f"📍 {kz} Killzone\n"
        f"💰 السعر: {price}\n\n"
        f"🔭 <b>HTF Bias:</b>\n"
        f"  D1: {htf_emoji(d1)}\n"
        f"  H4: {htf_emoji(h4)}\n"
        f"  الاتجاه العام: {htf_emoji(htf)}\n\n"
        f"{weekly_text}"
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
    print("🤖 صفقات الذهب v5 - HTF Bias + Weekly")
    print("=" * 50)

    send_telegram(
        "🤖 <b>بوت صفقات الذهب v5 شغّال!</b>\n\n"
        "🔭 <b>HTF Bias:</b> يحلل D1 + H4 أولاً\n"
        "📅 <b>Weekly Profile:</b> طابع الأسبوع\n"
        "⚡ Scalping M1 + 📊 Swing M5\n"
        "📡 بيانات حية Twelve Data\n"
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
    last_htf_update = None
    htf_bias = 'neutral'
    d1_bias = 'neutral'
    h4_bias = 'neutral'
    weekly = None
    check_count = 0

    while True:
        check_count += 1
        now_str = datetime.now().strftime('%H:%M:%S')
        now_time = datetime.now(timezone.utc)
        kz = in_killzone()

        # تحديث HTF كل ساعة
        if last_htf_update is None or (now_time - last_htf_update).seconds > 3600:
            print("🔭 تحديث HTF Bias...")
            htf_bias, d1_bias, h4_bias = get_htf_bias()
            weekly = get_weekly_profile()
            last_htf_update = now_time
            print(f"  D1: {d1_bias} | H4: {h4_bias} | Overall: {htf_bias}")
            if weekly:
                print(f"  Weekly: {weekly['bias']} | High: {weekly['high']} | Low: {weekly['low']}")

        if not kz:
            if check_count % 10 == 0:
                print(f"🚫 {now_str} — خارج Killzone | HTF: {htf_bias}")
            last_scalp = None
            last_swing = None
            time.sleep(CHECK_INTERVAL)
            continue

        print(f"\n⚡ فحص #{check_count} - {now_str} | {kz} | HTF: {htf_bias}")

        price = get_price()
        if not price:
            print("⚠️ تعذر جلب السعر")
            time.sleep(30)
            continue

        print(f"💰 السعر: ${price}")

        df_m1 = get_candles(interval="1min", outputsize=50)
        df_m5 = get_candles(interval="5min", outputsize=100)

        if df_m1 is None or df_m5 is None:
            print("⚠️ بيانات غير كافية")
            time.sleep(30)
            continue

        # Scalping
        scalp = analyze_scalping(df_m1, price, htf_bias)
        print(f"⚡ Scalp — Buy:{scalp['buy']} Sell:{scalp['sell']}")

        scalp_ok = True
        if last_scalp_time:
            scalp_ok = (now_time - last_scalp_time).seconds / 60 > 15

        if scalp['signal'] and (scalp['signal'] != last_scalp or scalp_ok):
            msg = format_scalping(scalp, kz, price, htf_bias, d1_bias, h4_bias)
            if send_telegram(msg):
                print(f"✅ Scalping: {scalp['signal']}")
                last_scalp = scalp['signal']
                last_scalp_time = now_time
        elif not scalp['signal']:
            last_scalp = None

        # Swing
        swing = analyze_swing(df_m5, price, htf_bias, weekly)
        print(f"📊 Swing  — Buy:{swing['buy']} Sell:{swing['sell']}")

        swing_ok = True
        if last_swing_time:
            swing_ok = (now_time - last_swing_time).seconds / 60 > 30

        if swing['signal'] and (swing['signal'] != last_swing or swing_ok):
            msg = format_swing(swing, kz, price, htf_bias, d1_bias, h4_bias, weekly)
            if send_telegram(msg):
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
