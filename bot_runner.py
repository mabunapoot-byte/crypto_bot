# -*- coding: utf-8 -*-
"""
=====================================================================
🤖 Financial Market & Egypt Macro Analytics Bot — الإصدار 2.0 (منظم)
=====================================================================
التحسينات الجوهرية عن الإصدار الأول:
  1. تنظيم الكود إلى وحدات واضحة (Config / Data / Signals / Reporters).
  2. لا أسرار داخل الكود — كل المفاتيح من Environment Variables.
  3. قسم جديد بالكامل: المؤشرات الاقتصادية المصرية (تضخم، بطالة، سكان،
     سيولة الأفراد والبنوك M1/M2، الفائدة، الاحتياطي) مع أسهم اتجاه تلقائية.
  4. أسعار المعادن الآن مباشرة من Yahoo Finance (ذهب/فضة/بلاتين/بالاديوم)
     بدلاً من الأرقام الثابتة، مع قيم احتياطية عند الفشل.
  5. محرك إشارات تفاعلي: SMA + RSI + MACD مع نقاط قوة (0-100) +
     تنبيهات فورية عند تشبع شرائي/بيعي أو تقاطع MACD.
  6. توقيت القاهرة بدل UTC، وتقسيم رسائل تيليجرام الطويلة تلقائيًا.
  7. HTTP مع إعادة محاولة (Retry) لجميع الطلبات الخارجية.
  8. نقطة /health تعرض حالة البوت وآخر تحديث (للمراقبة على Render).

المتطلبات (requirements.txt):
    flask, pandas, requests
=====================================================================
"""

import os
import time
import urllib.parse
from datetime import datetime
from threading import Thread
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from flask import Flask, jsonify

# =====================================================================
# 1) الإعدادات والثوابت
# =====================================================================
APP_NAME = "Financial Market & Egypt Macro Analytics Bot"
CAIRO_TZ = ZoneInfo("Africa/Cairo")

# --- مفاتيح الواتساب والبريد (من Render Environment Variables فقط) ---
TELEGRAM_TOKEN      = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MY_PHONE_NUMBER     = os.environ.get("MY_PHONE_NUMBER", "").strip()
CALLMEBOT_API_KEY   = os.environ.get("CALLMEBOT_API_KEY", "").strip()
SENDER_EMAIL        = os.environ.get("SENDER_EMAIL", "").strip()
RECEIVER_EMAIL      = os.environ.get("RECEIVER_EMAIL", "").strip()
BREVO_API_KEY       = os.environ.get("BREVO_API_KEY", "").strip()

# --- الجدولة الزمنية (قابلة للتعديل من Environment Variables) ---
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default

CHECK_INTERVAL_MINUTES   = _env_int("CHECK_INTERVAL_MINUTES", 5)
WHATSAPP_INTERVAL_HOURS  = _env_int("WHATSAPP_INTERVAL_HOURS", 2)
EMAIL_INTERVAL_HOURS     = _env_int("EMAIL_INTERVAL_HOURS", 3)
TELEGRAM_INTERVAL_HOURS  = _env_int("TELEGRAM_INTERVAL_HOURS", 6)

# --- قيم احتياطية عند فشل الاتصال بالمصادر الحية ---
FALLBACK_USD_EGP = 52.30          # سعر السوق تقريبًا — أكتوبر 2026
FALLBACK_METALS_USD = {           # تُستخدم فقط إذا تعذر جلب Yahoo Finance
    "GC=F": 3800.0,               # الذهب (أونصة)
    "SI=F": 45.0,                 # الفضة (أونصة)
    "PL=F": 1150.0,               # البلاتين (أونصة)
    "PA=F": 1050.0,               # البالاديوم (أونصة)
}

HTTP_TIMEOUT = 12
MAX_RETRIES = 3

CRYPTO_PAIRS = {
    "Bitcoin (BTC)":  "BTC-USD",
    "Ethereum (ETH)": "ETH-USD",
    "Solana (SOL)":   "SOL-USD",
    "Ripple (XRP)":   "XRP-USD",
    "Dogecoin (DOGE)":"DOGE-USD",
}

# =====================================================================
# 2) خادم Flask (إبقاء الخدمة نشطة + مراقبة الحالة)
# =====================================================================
app = Flask(__name__)
STATE = {"started_at": None, "last_run": None, "last_alerts": []}

@app.route("/")
def home():
    return f"🤖 {APP_NAME} is alive and running!"

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "app": APP_NAME,
        "started_at": STATE["started_at"],
        "last_run": STATE["last_run"],
        "recent_alerts": STATE["last_alerts"][-10:],
    })

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# =====================================================================
# 3) أدوات مساعدة — HTTP مع إعادة محاولة
# =====================================================================
def http_get(url: str, headers: dict | None = None, retries: int = MAX_RETRIES):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            res = requests.get(url, headers=headers or {}, timeout=HTTP_TIMEOUT)
            res.raise_for_status()
            return res
        except Exception as e:
            last_err = e
            time.sleep(0.8 * attempt)
    print(f"⚠️ فشل GET بعد {retries} محاولات: {url} — {last_err}", flush=True)
    return None

def now_cairo() -> datetime:
    return datetime.now(CAIRO_TZ)

def now_str() -> str:
    return now_cairo().strftime("%Y-%m-%d %H:%M (%Z)")

# =====================================================================
# 4) المؤشرات الاقتصادية المصرية (بيانات CAPMAS / CBE 2026)
#    كل بند: value الحالي، prev القراءة السابقة، as_of تاريخ القراءة
#    lower_is_better=True تعني أن الانخفاض خبر إيجابي (مثل التضخم)
#    ⚠️ حدّث هذه القيم شهريًا عند صدور بيانات CAPMAS/CBE الجديدة
# =====================================================================
EGYPT_STATS = [
    dict(key="infl_urban", label="التضخم الأساسي الحضري (سنوي)", value=14.5, prev=14.9,
         unit="%", as_of="أغسطس 2026 — CAPMAS", lower_is_better=True,
         note="تباطؤ طفيف بعد قفزة يوليو"),
    dict(key="infl_headline", label="التضخم العام (سنوي)", value=12.7, prev=13.0,
         unit="%", as_of="أغسطس 2026 — CAPMAS", lower_is_better=True),
    dict(key="infl_core", label="التضخم الأساسي (CBE)", value=14.9, prev=14.7,
         unit="%", as_of="أغسطس 2026 — البنك المركزي", lower_is_better=True),
    dict(key="unemploy", label="معدل البطالة", value=5.8, prev=6.0,
         unit="%", as_of="الربع الثاني 2026 — CAPMAS", lower_is_better=True,
         note="أدنى مستوى مسجل تاريخيًا"),
    dict(key="labor", label="قوة العمل", value=35.64, prev=35.41,
         unit="مليون", as_of="الربع الثاني 2026 — CAPMAS", lower_is_better=False),
    dict(key="pop", label="عدد السكان", value=110.0, prev=109.0,
         unit="مليون", as_of="أكتوبر 2026 (تقدير)", lower_is_better=False),
    dict(key="m2", label="السيولة المحلية الكلية (M2)", value=15.330, prev=13.073,
         unit="تريليون ج.م", as_of="مايو 2026 — CBE", lower_is_better=False,
         note="نمو سنوي +17.3%"),
    dict(key="m1", label="عرض النقود (M1)", value=3.39, prev=2.55,
         unit="تريليون ج.م", as_of="مايو 2026 — CBE (تقدير من نمو +32.9%)",
         lower_is_better=False),
    dict(key="cash_out", label="النقد خارج البنوك (سيولة الأفراد)", value=1.39, prev=1.10,
         unit="تريليون ج.م", as_of="مايو 2026 — CBE (تقدير من نمو +25.8%)",
         lower_is_better=False, note="مؤشر مباشر على السيولة لدى الأفراد"),
    dict(key="deposits", label="إجمالي ودائع البنوك", value=17.145, prev=14.45,
         unit="تريليون ج.م", as_of="مايو 2026 — CBE", lower_is_better=False,
         note="نمو سنوي +18.6%"),
    dict(key="hh_share", label="حصة الأسر من الودائع", value=75.3, prev=75.0,
         unit="%", as_of="مايو 2026 — CBE", lower_is_better=False),
    dict(key="credit", label="التسهيلات الائتمانية", value=11.564, prev=9.32,
         unit="تريليون ج.م", as_of="مايو 2026 — CBE", lower_is_better=False,
         note="نمو سنوي +24% تقريبًا"),
    dict(key="reserve_money", label="النقد الاحتياطي", value=2.568, prev=2.32,
         unit="تريليون ج.م", as_of="مايو 2026 — CBE", lower_is_better=False),
    dict(key="cbe_dep", label="فائدة الإيداع لليلة واحدة", value=19.0, prev=19.0,
         unit="%", as_of="آخر قرار معلن — MPC", lower_is_better=None),
    dict(key="cbe_lend", label="فائدة الإقراض لليلة واحدة", value=20.0, prev=20.0,
         unit="%", as_of="آخر قرار معلن — MPC", lower_is_better=None),
]

def stat_arrow(s: dict) -> str:
    """سهم اتجاه + تقييم جيد/سيئ تلقائيًا حسب طبيعة المؤشر."""
    d = round(s["value"] - s["prev"], 4)
    if abs(d) < 1e-9:
        return "➡️ مستقر"
    up = "📈" if d > 0 else "📉"
    good = s.get("lower_is_better")
    if good is None:
        verdict = ""
    elif (d < 0) == bool(good):
        verdict = " ✅ إيجابي"
    else:
        verdict = " ⚠️ سلبي"
    return f"{up} {'+' if d > 0 else ''}{d:g} {s['unit']}{verdict}"

def build_egypt_section() -> str:
    lines = ["🇪🇬 *المؤشرات الاقتصادية المصرية — أحدث القراءات:*", ""]
    for s in EGYPT_STATS:
        line = f"• {s['label']}: *{s['value']:g} {s['unit']}* — {stat_arrow(s)}"
        if s.get("note"):
            line += f"\n    ↳ _{s['note']}_"
        line += f"\n    ↳ بتاريخ: {s['as_of']}"
        lines.append(line)
    lines.append("\n💡 مؤشرات السيولة: نمو M2 والنقد خارج البنوك بوتيرة أعلى من التضخم = سيولة واسعة تدعم السوق.")
    return "\n".join(lines)

# =====================================================================
# 5) البيانات المالية الحية
# =====================================================================
def get_forex() -> dict:
    """أسعار العملات مقابل الدولار من open.er-api ثم تحويلها إلى EGP."""
    res = http_get("https://open.er-api.com/v6/latest/USD")
    rates = (res.json().get("rates", {}) if res else {}) or {}

    usd_egp = rates.get("EGP", FALLBACK_USD_EGP)
    def to_egp(code: str, fallback: float) -> float:
        r = rates.get(code)
        return (usd_egp / r) if r else fallback

    return {
        "USD": usd_egp,
        "EUR": to_egp("EUR", 58.7),
        "GBP": to_egp("GBP", 69.3),
        "SAR": to_egp("SAR", usd_egp / 3.75),
        "AED": to_egp("AED", usd_egp / 3.67),
        "KWD": to_egp("KWD", usd_egp / 0.30),
        "_live": bool(rates),
    }

def get_metals_usd() -> tuple[dict, bool]:
    """أسعار المعادن (دولار/أونصة) مباشرة من Yahoo Finance."""
    headers = {"User-Agent": "Mozilla/5.0"}
    prices, live = {}, True
    for symbol in ("GC=F", "SI=F", "PL=F", "PA=F"):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
        res = http_get(url, headers=headers)
        px = None
        try:
            if res:
                result = res.json()["chart"]["result"][0]
                closes = [c for c in result["indicators"]["quote"][0]["close"] if c]
                if closes:
                    px = closes[-1]
        except Exception:
            px = None
        if px is None:
            live = False
            px = FALLBACK_METALS_USD[symbol]
        prices[symbol] = px
    return prices, live

def metals_in_egp(metals_usd: dict, usd_egp: float) -> dict:
    """تحويل أسعار المعادن إلى الجرام بالجنيه المصري."""
    ozt = 31.1035
    g24 = (metals_usd["GC=F"] / ozt) * usd_egp
    sil = (metals_usd["SI=F"] / ozt) * usd_egp
    return {
        "الذهب (24)":        g24,
        "الذهب (21)":        g24 * 21 / 24,
        "الذهب (18)":        g24 * 18 / 24,
        "الجنيه الذهب":      g24 * 21 / 24 * 8,
        "الفضة (999)":       sil,
        "الفضة (925)":       sil * 0.925,
        "البلاتين (أونصة)":  metals_usd["PL=F"] * usd_egp,
        "البالاديوم (أونصة)":metals_usd["PA=F"] * usd_egp,
    }

def gold_trend() -> str:
    """اتجاه الذهب خلال آخر 5 جلسات (إشارة تفاعلية)."""
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1d&range=1mo"
    res = http_get(url, headers=headers)
    try:
        if not res:
            raise ValueError("no response")
        result = res.json()["chart"]["result"][0]
        closes = [c for c in result["indicators"]["quote"][0]["close"] if c]
        week_change = (closes[-1] / closes[-6] - 1) * 100 if len(closes) >= 6 else 0
        month_change = (closes[-1] / closes[0] - 1) * 100
        arrow_w = "📈" if week_change > 0 else "📉"
        arrow_m = "📈" if month_change > 0 else "📉"
        return (f"{arrow_w} أسبوعي: {week_change:+.1f}% | "
                f"{arrow_m} شهري: {month_change:+.1f}%")
    except Exception:
        return "➡️ تعذر حساب الاتجاه حاليًا"

# =====================================================================
# 6) التحليل الفني والإشارات التفاعلية
# =====================================================================
def fetch_technical_data(pair_symbol: str) -> dict | None:
    """شموع 15 دقيقة من Coinbase + SMA10/30 + RSI14 + MACD(12,26,9)."""
    url = f"https://api.exchange.coinbase.com/products/{pair_symbol}/candles?granularity=900"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = http_get(url, headers=headers)
    if not res:
        return None
    try:
        data = res.json()
        if not data:
            return None
        df = pd.DataFrame(data, columns=["timestamp", "low", "high", "open", "Price", "volume"])
        df["Date"] = pd.to_datetime(df["timestamp"], unit="s")
        df = df.sort_values("Date").reset_index(drop=True)

        df["SMA_10"] = df["Price"].rolling(window=10).mean()
        df["SMA_30"] = df["Price"].rolling(window=30).mean()

        delta = df["Price"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        df["RSI"] = 100 - (100 / (1 + avg_gain / avg_loss))

        ema12 = df["Price"].ewm(span=12, adjust=False).mean()
        ema26 = df["Price"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

        row = df.dropna()
        if len(row) < 2:
            return None
        last, prev = row.iloc[-1], row.iloc[-2]
        return {
            "Price": last["Price"],
            "RSI": last["RSI"],
            "SMA_10": last["SMA_10"],
            "SMA_30": last["SMA_30"],
            "MACD": last["MACD"],
            "MACD_SIGNAL": last["MACD_SIGNAL"],
            "prev_rsi": prev["RSI"],
            "prev_macd_above": bool(prev["MACD"] > prev["MACD_SIGNAL"]),
        }
    except Exception as e:
        print(f"❌ خطأ تحليل {pair_symbol}: {e}", flush=True)
        return None

def compute_signal(c: dict) -> tuple[int, str, str]:
    """درجة قوة الإشارة 0-100 + وصف عربي مختصر."""
    score = 50
    reasons = []

    if c["SMA_10"] > c["SMA_30"]:
        score += 15; reasons.append("تقاطع إيجابي للمتوسطات")
    else:
        score -= 15; reasons.append("تقاطع سلبي للمتوسطات")

    macd_above = c["MACD"] > c["MACD_SIGNAL"]
    if macd_above:
        score += 15; reasons.append("MACD فوق خط الإشارة")
    else:
        score -= 15; reasons.append("MACD تحت خط الإشارة")

    rsi = c["RSI"]
    if rsi >= 70:
        score -= 20; reasons.append("تشبع شرائي")
    elif rsi <= 30:
        score += 5; reasons.append("تشبع بيعي (مراقبة ارتداد)")
    elif 45 <= rsi <= 65:
        score += 10; reasons.append("RSI في منطقة صحية")
    elif 30 < rsi < 45:
        score += 5; reasons.append("زخم هابط يضعف")

    score = max(0, min(100, score))
    if score >= 70:
        label = "🟢 شراء قوي"
    elif score >= 55:
        label = "🟢 ميل شرائي"
    elif score >= 45:
        label = "⚪ حياد"
    elif score >= 30:
        label = "🟠 ميل بيعي"
    else:
        label = "🔴 بيع قوي"
    return score, label, "، ".join(reasons[:3])

def detect_alert(name: str, c: dict) -> str | None:
    """إشارات تفاعلية فورية: دخول مناطق التشبع أو تقاطع MACD."""
    alerts = []
    if c["prev_rsi"] < 70 <= c["RSI"]:
        alerts.append("⚠️ دخول منطقة تشبع شرائي")
    if c["prev_rsi"] > 30 >= c["RSI"]:
        alerts.append("💡 دخول منطقة تشبع بيعي — فرصة ارتداد محتملة")
    macd_now = c["MACD"] > c["MACD_SIGNAL"]
    if macd_now and not c["prev_macd_above"]:
        alerts.append("✨ تقاطع MACD صاعد (إشارة شراء)")
    if not macd_now and c["prev_macd_above"]:
        alerts.append("🔻 تقاطع MACD هابط (إشارة بيع)")
    if not alerts:
        return None
    short = name.split(" ")[0]
    return f"🚨 {short} (${c['Price']:,.2f}):\n" + "\n".join(f"  {a}" for a in alerts)

# =====================================================================
# 7) الإرسال — Telegram / WhatsApp / Email
# =====================================================================
def send_telegram(message: str, parse_mode: str = "Markdown") -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_TOKEN/CHAT_ID غير مضبوطة.", flush=True)
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # تقسيم الرسائل الطويلة (حد تيليجرام 4096 حرف)
    chunks = [message[i:i+3800] for i in range(0, len(message), 3800)] or [message]
    ok = True
    for chunk in chunks:
        try:
            res = requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": parse_mode,
            }, timeout=HTTP_TIMEOUT)
            ok = ok and res.status_code == 200
            time.sleep(0.4)
        except Exception as e:
            print(f"❌ خطأ تيليجرام: {e}", flush=True)
            ok = False
    return ok

def send_whatsapp(message_body: str) -> bool:
    phone = MY_PHONE_NUMBER.split("@")[0].replace("+", "").replace(" ", "").strip()
    api_key = CALLMEBOT_API_KEY.strip()
    if not phone or not api_key:
        print("⚠️ بيانات CallMeBot غير مضبوطة.", flush=True)
        return False
    try:
        encoded = urllib.parse.quote_plus(message_body)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded}&apikey={api_key}"
        res = requests.get(url, timeout=HTTP_TIMEOUT)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ خطأ واتساب: {e}", flush=True)
        return False

def send_email_report(subject: str, body: str) -> bool:
    if not BREVO_API_KEY or not SENDER_EMAIL or not RECEIVER_EMAIL:
        print("⚠️ إعدادات Brevo غير مكتملة.", flush=True)
        return False
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY,
               "content-type": "application/json"}
    payload = {
        "sender": {"name": "Financial Analytics Bot", "email": SENDER_EMAIL},
        "to": [{"email": RECEIVER_EMAIL}],
        "subject": subject,
        "textContent": body,
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code in (200, 201):
            print(f"📧 تم إرسال البريد إلى {RECEIVER_EMAIL}", flush=True)
            return True
        print(f"❌ فشل Brevo: {res.text}", flush=True)
        return False
    except Exception as e:
        print(f"❌ خطأ Brevo: {e}", flush=True)
        return False

# =====================================================================
# 8) بناء التقارير
# =====================================================================
def build_forex_text(forex: dict) -> str:
    src = "مباشر" if forex.get("_live") else "احتياطي"
    lines = [f"💵 أسعار العملات (ج.م) — [{src}]:", ""]
    for k in ("USD", "EUR", "GBP", "SAR", "AED", "KWD"):
        lines.append(f"• {k}: {forex[k]:,.2f}")
    return "\n".join(lines)

def build_metals_text(metals: dict, trend: str, live: bool) -> str:
    src = "مباشر" if live else "احتياطي"
    lines = [f"👑 أسعار المعادن (ج.م) — [{src}]:", f"📊 اتجاه الذهب: {trend}", ""]
    for k, v in metals.items():
        dec = 2 if v < 100 else 0
        lines.append(f"• {k}: {v:,.{dec}f}")
    return "\n".join(lines)

def build_crypto_sections(usd_egp: float):
    """يرجع (نص_تفصيلي_طويل, نص_مختصر_واتساب, قائمة_التنبيهات)."""
    detailed = ["🪙 *التحليل الفني للعملات الرقمية:*", ""]
    wa_lines, alerts = [], []
    for name, pair in CRYPTO_PAIRS.items():
        c = fetch_technical_data(pair)
        time.sleep(0.2)
        if not c:
            continue
        price_egp = c["Price"] * usd_egp
        score, label, reasons = compute_signal(c)
        alert = detect_alert(name, c)
        if alert:
            alerts.append(alert)

        detailed.append(
            f"*{name}* — {label} (قوة الإشارة: {score}/100)\n"
            f"• السعر: ${c['Price']:,.2f} ≈ {price_egp:,.0f} ج.م\n"
            f"• RSI: {c['RSI']:.1f} | SMA10: ${c['SMA_10']:,.2f} | SMA30: ${c['SMA_30']:,.2f}\n"
            f"• MACD: {c['MACD']:,.4f} / إشارة: {c['MACD_SIGNAL']:,.4f}\n"
            f"↳ _{reasons}_\n"
        )
        short = name.split(" ")[0]
        wa_lines.append(f"• {short}: ${c['Price']:,.2f} | RSI {c['RSI']:.0f} | {score}/100 {label}")
    return "\n".join(detailed), "\n".join(wa_lines), alerts

def build_auto_section() -> str:
    cars = {
        "🚗 اقتصادية": {
            "نيسان صني": "695,000 - 750,000 ج.م",
            "شيري أريزو 5": "650,000 - 710,000 ج.م",
            "سوزوكي سويفت": "620,000 - 680,000 ج.م",
        },
        "🚘 متوسطة": {
            "تويوتا كورولا": "1,300,000 - 1,450,000 ج.م",
            "هيونداي إلنترا AD": "890,000 - 980,000 ج.م",
            "إم جي ZS": "975,000 - 1,050,000 ج.م",
            "كيا سبورتاج": "1,780,000 - 1,950,000 ج.م",
        },
        "🏎️ فاخرة وكهرباء": {
            "مرسيدس C200": "3,400,000 - 3,800,000 ج.م",
            "بي إم دبليو 320i": "3,200,000 - 3,600,000 ج.م",
            "فولكس ID.4": "1,650,000 - 1,850,000 ج.م",
        },
    }
    lines = ["🚙 *دليل أسعار السيارات في مصر:*", ""]
    for cat, models in cars.items():
        lines.append(f"*{cat}:*")
        for m, p in models.items():
            lines.append(f"  • {m}: {p}")
        lines.append("")
    return "\n".join(lines)

# =====================================================================
# 9) الحلقة الرئيسية
# =====================================================================
def main_loop():
    print(f"🤖 بدء تشغيل {APP_NAME} ...", flush=True)
    STATE["started_at"] = now_str()
    last_whatsapp = last_email = last_telegram = 0.0

    while True:
        try:
            now = time.time()
            STATE["last_run"] = now_str()

            forex = get_forex()
            usd_egp = forex["USD"]
            metals_usd, metals_live = get_metals_usd()
            metals = metals_in_egp(metals_usd, usd_egp)
            gold_tr = gold_trend()
            crypto_detail, crypto_wa, alerts = build_crypto_sections(usd_egp)

            # --- تنبيهات تفاعلية فورية (تيليجرام فورًا عند حدوثها) ---
            if alerts:
                for a in alerts:
                    send_telegram(f"🔔 *تنبيه سوق فوري*\n{a}\n⏱ {now_str()}")
                    STATE["last_alerts"].append(f"{now_str()} — {a.splitlines()[0]}")
                STATE["last_alerts"] = STATE["last_alerts"][-20:]

            # --- تيليجرام: التقرير الشامل (كل 6 ساعات) ---
            if now - last_telegram >= TELEGRAM_INTERVAL_HOURS * 3600 or last_telegram == 0:
                report = (
                    f"📊 *تقرير السوق الشامل — {now_str()}*\n\n"
                    f"{build_egypt_section()}\n\n"
                    f"{build_forex_text(forex)}\n\n"
                    f"{build_metals_text(metals, gold_tr, metals_live)}\n\n"
                    f"{crypto_detail}\n\n"
                    f"⚙️ إرسال آلي من Render — التقرير القادم بعد {TELEGRAM_INTERVAL_HOURS} ساعات"
                )
                if send_telegram(report):
                    last_telegram = now

            # --- واتساب: الملخص السريع (كل ساعتين) ---
            if now - last_whatsapp >= WHATSAPP_INTERVAL_HOURS * 3600 or last_whatsapp == 0:
                wa_msg = (
                    f"📊 *ملخص السوق السريع*\n⏱ {now_str()}\n\n"
                    f"💵 الدولار: {usd_egp:.2f} ج.م | اليورو: {forex['EUR']:.2f}\n"
                    f"👑 ذهب 21: {metals['الذهب (21)']:,.0f} ج.م | ذهب 24: {metals['الذهب (24)']:,.0f} ج.م\n"
                    f"📊 الذهب: {gold_tr}\n\n"
                    f"🪙 العملات الرقمية:\n{crypto_wa}\n\n"
                    f"📈 التضخم الحضري: 14.5% | البطالة: 5.8% (أدنى مستوى تاريخي)\n"
                    f"⚙️ التحديث القادم بعد ساعتين"
                )
                if send_whatsapp(wa_msg):
                    last_whatsapp = now

            # --- البريد: التقرير الموسع (كل 3 ساعات) ---
            if now - last_email >= EMAIL_INTERVAL_HOURS * 3600 or last_email == 0:
                email_body = (
                    f"📊 التقرير المالي والاقتصادي الشامل\n"
                    f"⏱ {now_str()}\nالمستلم: {RECEIVER_EMAIL}\n"
                    f"{'='*50}\n\n"
                    f"1️⃣ المؤشرات الاقتصادية المصرية\n{'-'*50}\n"
                    f"{build_egypt_section()}\n\n"
                    f"2️⃣ أسعار العملات\n{'-'*50}\n"
                    f"{build_forex_text(forex)}\n\n"
                    f"3️⃣ المعادن النفيسة\n{'-'*50}\n"
                    f"{build_metals_text(metals, gold_tr, metals_live)}\n\n"
                    f"4️⃣ العملات الرقمية\n{'-'*50}\n"
                    f"{crypto_detail}\n\n"
                    f"5️⃣ سوق السيارات\n{'-'*50}\n"
                    f"{build_auto_section()}\n\n"
                    f"{'='*50}\n⚙️ يُولد تلقائيًا كل {EMAIL_INTERVAL_HOURS} ساعات."
                )
                subject = f"📈 التقرير الشامل — {now_str()}"
                if send_email_report(subject, email_body):
                    last_email = now

        except Exception as e:
            print(f"❌ خطأ في الحلقة الرئيسية: {e}", flush=True)

        time.sleep(CHECK_INTERVAL_MINUTES * 60)

# =====================================================================
# 10) نقطة الانطلاق
# =====================================================================
if __name__ == "__main__":
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    main_loop()
