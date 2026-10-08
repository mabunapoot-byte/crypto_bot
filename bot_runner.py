import os
import time
from threading import Thread
import urllib.parse
from flask import Flask
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. خادم Flask لإبقاء الخدمة نشطة على Render
# ---------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "🤖 Financial Market & Analytics Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# ---------------------------------------------------------
# 2. الثوابت ومتغيرات البيئة
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8214213423:AAGifBdaeIxQLp3r8Ky0y0_Hvwedq2ia6Z4')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7727265173')

# بيانات الواتساب
MY_PHONE_NUMBER = os.environ.get('MY_PHONE_NUMBER', '201201211155')
CALLMEBOT_API_KEY = os.environ.get('CALLMEBOT_API_KEY', '3424442')

# إعدادات البريد الإلكتروني عبر Brevo API
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'mabunapoot@gmail.com')
RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL', 'mabunapoot@gmail.com')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '').strip()

# الجدولة الزمنية المعتمدة
CHECK_INTERVAL_MINUTES = 5
WHATSAPP_INTERVAL_HOURS = 2
EMAIL_INTERVAL_HOURS = 3
TELEGRAM_INTERVAL_HOURS = 6

# ---------------------------------------------------------
# 3. إرسال البريد الإلكتروني عبر Brevo HTTP API
# ---------------------------------------------------------
def send_email_report(subject, message_body):
    if not BREVO_API_KEY:
        print("⚠️ يرجى ضبط BREVO_API_KEY في إعدادات Render لإرسال البريد.", flush=True)
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

    payload = {
        "sender": {"name": "Financial Analytics Bot", "email": SENDER_EMAIL},
        "to": [{"email": RECEIVER_EMAIL}],
        "subject": subject,
        "textContent": message_body
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code in [200, 201]:
            print(f"📧 تم إرسال التقرير الشامل لـ {RECEIVER_EMAIL} بنجاح عبر Brevo API!", flush=True)
            return True
        else:
            print(f"❌ فشل إرسال البريد عبر API: {response.text}", flush=True)
            return False
    except Exception as e:
        print(f"❌ خطأ في إرسال البريد عبر API: {e}", flush=True)
        return False

# ---------------------------------------------------------
# 4. إرسال الواتساب وتيليجرام (مُحسن التنسيق)
# ---------------------------------------------------------
def send_whatsapp_message(message_body):
    phone_number = MY_PHONE_NUMBER.split('@')[0].replace('+', '').replace(' ', '').strip()
    api_key = CALLMEBOT_API_KEY.strip()

    if not phone_number or not api_key:
        return False

    try:
        # استخدام quote_plus لضمان التنسيق الصحيح للأسطر والرموز في الواتساب
        encoded_text = urllib.parse.quote_plus(message_body)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone_number}&text={encoded_text}&apikey={api_key}"
        res = requests.get(url, timeout=15)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ خطأ واتساب: {e}", flush=True)
        return False

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ خطأ تيليجرام: {e}", flush=True)
        return False

# ---------------------------------------------------------
# 5. البيانات المالية المتقدمة، المعادن، الأخبار والسيارات
# ---------------------------------------------------------
def get_forex_and_metals():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        res = requests.get(url, timeout=5)
        rates = res.json().get('rates', {})
        usd_egp = rates.get('EGP', 48.5)

        forex = {
            'USD': usd_egp,
            'EUR': (usd_egp / rates.get('EUR', 1.0)) if rates.get('EUR') else 0,
            'GBP': (usd_egp / rates.get('GBP', 1.0)) if rates.get('GBP') else 0,
            'SAR': (usd_egp / rates.get('SAR', 3.75)) if rates.get('SAR') else 0,
            'AED': (usd_egp / rates.get('AED', 3.67)) if rates.get('AED') else 0,
            'KWD': (usd_egp / rates.get('KWD', 0.30)) if rates.get('KWD') else 0,
        }
        
        gold_oz_usd = 2650.0
        silver_oz_usd = 31.5
        platinum_oz_usd = 980.0
        palladium_oz_usd = 1020.0
        
        gold_gram_24 = (gold_oz_usd / 31.1035) * usd_egp
        
        metals = {
            'الذهب (24)': gold_gram_24,
            'الذهب (21)': gold_gram_24 * (21 / 24),
            'الذهب (18)': gold_gram_24 * (18 / 24),
            'الجنيه الذهب': (gold_gram_24 * (21 / 24)) * 8,
            'الفضة (999)': (silver_oz_usd / 31.1035) * usd_egp,
            'الفضة (925)': ((silver_oz_usd / 31.1035) * usd_egp) * 0.925,
            'البلاتين (أونصة)': platinum_oz_usd * usd_egp,
            'البالاديوم (أونصة)': palladium_oz_usd * usd_egp
        }
        
        return forex, metals, usd_egp
    except Exception as e:
        print(f"⚠️ خطأ أسعار الصرف والمعادن: {e}", flush=True)
        return {'USD': 48.5}, {}, 48.5

def fetch_technical_data(pair_symbol):
    url = f"https://api.exchange.coinbase.com/products/{pair_symbol}/candles?granularity=900"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=8)
        res.raise_for_status()
        data = res.json()
        if not data:
            return None

        df = pd.DataFrame(data, columns=['timestamp', 'low', 'high', 'open', 'Price', 'volume'])
        df['Date'] = pd.to_datetime(df['timestamp'], unit='s')
        df = df.sort_values('Date').reset_index(drop=True)

        df['SMA_10'] = df['Price'].rolling(window=10).mean()
        df['SMA_30'] = df['Price'].rolling(window=30).mean()

        delta = df['Price'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))

        last = df.dropna().iloc[-1]
        return {
            'Price': last['Price'],
            'RSI': last['RSI'],
            'SMA_10': last['SMA_10'],
            'SMA_30': last['SMA_30']
        }
    except Exception as e:
        print(f"❌ خطأ جلب {pair_symbol}: {e}", flush=True)
        return None

def get_detailed_global_news():
    news_sections = {
        "🇺🇸 أمريكا": [
            "الفيدرالي الأمريكي يُبقي السياسة النقدية تحت المراقبة مع ترقب بيانات التضخم.",
            "استمرار تدفق السيولة للأسهم الأمريكية وصناديق الذكاء الاصطناعي."
        ],
        "🇪🇺 أوروبا وروسيا": [
            "المركزي الأوروبي يدرس تعديل الفائدة لمواجهة تباطؤ النمو الإقليمي.",
            "المركزي الروسي يحافظ على احتياطيات الذهب لدعم الروبل."
        ],
        "🇨🇳 🇯🇵 آسيا": [
            "الصين تضخ حزم تحفيز جديدة لدعم قطاع العقارات والصادرات.",
            "بنك اليابان يُلمح لمراقبة مستويات الين ومعدلات الأجور."
        ],
        "🌍 الشرق الأوسط": [
            "متابعة التطورات الجيوسياسية وتأثيرها على النفط والملاحة.",
            "المركزي المصري يواصل استراتيجية استقرار سوق الصرف."
        ]
    }
    return news_sections

def get_detailed_auto_market():
    cars = {
        "🚗 اقتصادية": {
            "نيسان صني": "695,000 - 750,000 ج.م",
            "شيري أريزو 5": "650,000 - 710,000 ج.م",
            "سوزوكي سويفت": "620,000 - 680,000 ج.م"
        },
        "🚘 متوسطة": {
            "تويوتا كورولا": "1,300,000 - 1,450,000 ج.م",
            "هيونداي إلترا AD": "890,000 - 980,000 ج.م",
            "إم جي ZS": "975,000 - 1,050,000 ج.م",
            "كيا سبورتاج": "1,780,000 - 1,950,000 ج.م"
        },
        "🏎️ فاخرة وكهرباء": {
            "مرسيدس C200": "3,400,000 - 3,800,000 ج.م",
            "بي إم دبليو 320i": "3,200,000 - 3,600,000 ج.م",
            "فولكس ID.4": "1,650,000 - 1,850,000 ج.م"
        }
    }
    return cars

# ---------------------------------------------------------
# 6. الحلقة الرئيسية والجدولة
# ---------------------------------------------------------
def main_loop():
    print("🤖 بدأ تشغيل البوت المطور مع التنسيق المحسن للواتساب...", flush=True)

    crypto_pairs = {
        'Bitcoin (BTC)': 'BTC-USD',
        'Ethereum (ETH)': 'ETH-USD',
        'Solana (SOL)': 'SOL-USD',
        'Ripple (XRP)': 'XRP-USD',
        'Dogecoin (DOGE)': 'DOGE-USD'
    }

    last_whatsapp_time = 0
    last_email_time = 0
    last_telegram_time = 0

    while True:
        try:
            current_time = time.time()
            forex_rates, metals, usd_egp = get_forex_and_metals()
            current_time_str = time.strftime('%Y-%m-%d %H:%M UTC')

            # --- بناء التحليل الفني للعملات الرقمية ---
            crypto_msg_tg = "\n📊 التحليل الفني للعملات الرقمية:\n===================================\n"
            wa_crypto_details = ""

            for name, pair in crypto_pairs.items():
                cdata = fetch_technical_data(pair)
                if cdata:
                    price_usd = cdata['Price']
                    price_egp = price_usd * usd_egp
                    rsi = cdata['RSI']
                    sma10 = cdata['SMA_10']
                    sma30 = cdata['SMA_30']

                    if sma10 > sma30 and 30 < rsi < 70:
                        status_short = "Buy"
                        status_desc_tg = "🟢 إشارة شراء (Buy)\n  الاتجاه صاعد ومؤشر RSI في منطقة استقرار آمنة."
                    elif rsi >= 70:
                        status_short = "Overbought"
                        status_desc_tg = "⚠️ تنبيه تشبع شرائي (Overbought)\n  السعر مرتفع جداً، يُنصح بتجنب الشراء."
                    elif rsi <= 30:
                        status_short = "Oversold"
                        status_desc_tg = "ℹ️ تنبيه تشبع بيعي (Oversold)\n  السعر منخفض جداً، ترقب ارتداد صاعد محتمل."
                    elif sma10 < sma30:
                        status_short = "Sell"
                        status_desc_tg = "🔴 إشارة بيع (Sell)\n  الاتجاه هابط والمتوسط السريع أدنى من البطيء."
                    else:
                        status_short = "Hold"
                        status_desc_tg = "⚪ احتفاظ (Hold)\n  لا توجد إشارة اتجاه قوية واضحة."

                    crypto_msg_tg += (
                        f"🪙 {name}\n"
                        f"• السعر: ${price_usd:,.2f} ({price_egp:,.0f} ج.م)\n"
                        f"📈 المؤشرات الفنية:\n"
                        f"  - المتوسط السريع (SMA 10): ${sma10:,.2f}\n"
                        f"  - المتوسط البطيء (SMA 30): ${sma30:,.2f}\n"
                        f"  - مؤشر القوة النسبية (RSI): {rsi:.1f}\n"
                        f"🚦 القرار الاستثماري:\n{status_desc_tg}\n"
                        f"-----------------------------------\n"
                    )

                    short_name = name.split(' ')[0]
                    wa_crypto_details += f"• {short_name}: ${price_usd:,.2f} | RSI:{rsi:.1f} ({status_short})\n"

                time.sleep(0.2)

            # --- 1. إرسال تيليجرام (كل 6 ساعات) ---
            if current_time - last_telegram_time >= (TELEGRAM_INTERVAL_HOURS * 3600) or last_telegram_time == 0:
                forex_msg_tg = "💵 أسعار العملات الأجنبية بالجنيه المصري (EGP):\n"
                for curr_name, rate in forex_rates.items():
                    forex_msg_tg += f"• {curr_name}: {rate:,.2f} ج.م\n"

                full_tg_report = f"""📊 تقرير السوق الشامل والتحليل الكمي (كل 6 ساعات)
⏱ التوقيت: {current_time_str}
===================================
{forex_msg_tg}===================================
{crypto_msg_tg}⚙️ إرسال تلقائي عبر السحابة"""

                if send_telegram_message(full_tg_report):
                    last_telegram_time = current_time

            # --- 2. إرسال الواتساب المنظم والأنيق (كل ساعتين) ---
            if current_time - last_whatsapp_time >= (WHATSAPP_INTERVAL_HOURS * 3600) or last_whatsapp_time == 0:
                wa_msg = (
                    f"📊 *تقرير السوق التفصيلي*\n"
                    f"⏱ {current_time_str}\n"
                    f"-----------------------------------\n"
                    f"💵 *أسعار العملات (EGP):*\n"
                    f"• USD: {usd_egp:.2f} | EUR: {forex_rates.get('EUR', 0):.2f}\n"
                    f"• GBP: {forex_rates.get('GBP', 0):.2f} | SAR: {forex_rates.get('SAR', 0):.2f}\n"
                    f"• AED: {forex_rates.get('AED', 0):.2f} | KWD: {forex_rates.get('KWD', 0):.2f}\n"
                    f"-----------------------------------\n"
                    f"👑 *أسعار المعادن (الجرام):*\n"
                    f"• الذهب (21): {metals.get('الذهب (21)', 0):,.0f} ج.م\n"
                    f"• الذهب (24): {metals.get('الذهب (24)', 0):,.0f} ج.م\n"
                    f"• الفضة (999): {metals.get('الفضة (999)', 0):,.2f} ج.م\n"
                    f"-----------------------------------\n"
                    f"🪙 *تحليل العملات الرقمية:*\n"
                    f"{wa_crypto_details}"
                    f"-----------------------------------\n"
                    f"⚙️ التحديث القادم بعد ساعتين"
                )

                if send_whatsapp_message(wa_msg):
                    last_whatsapp_time = current_time

            # --- 3. إرسال البريد الإلكتروني الموسع الشامل (كل 3 ساعات) ---
            if current_time - last_email_time >= (EMAIL_INTERVAL_HOURS * 3600) or last_email_time == 0:
                global_news = get_detailed_global_news()
                auto_data = get_detailed_auto_market()

                news_str = ""
                for region, headlines in global_news.items():
                    news_str += f"\n{region}:\n"
                    for h in headlines:
                        news_str += f"  • {h}\n"

                metals_str = "\n".join([f"• {k}: {v:,.2f} ج.م" for k, v in metals.items()])

                auto_str = ""
                for cat_name, models in auto_data.items():
                    auto_str += f"\n{cat_name}:\n"
                    for model_name, price_range in models.items():
                        auto_str += f"  • {model_name}: {price_range}\n"

                email_report = f"""📊 التقرير المالي والإقتصادي الشامل المطور
⏱ التوقيت: {current_time_str}
المستلم: {RECEIVER_EMAIL}
==================================================

1️⃣ النشرة الاقتصادية العالمية والأخبار الإقليمية:
--------------------------------------------------{news_str}

2️⃣ أسعار العملات الأجنبية بالجنيه المصري:
--------------------------------------------------
• USD (دولار أمريكي): {usd_egp:.2f} ج.م
• EUR (يورو): {forex_rates.get('EUR', 0):.2f} ج.م
• GBP (جنيه إسترليني): {forex_rates.get('GBP', 0):.2f} ج.م
• SAR (ريال سعودي): {forex_rates.get('SAR', 0):.2f} ج.م
• AED (درهم إماراتي): {forex_rates.get('AED', 0):.2f} ج.م
• KWD (دينار كويتي): {forex_rates.get('KWD', 0):.2f} ج.م

3️⃣ موسوعة أسعار المعادن النفيسة والصناعية:
--------------------------------------------------
{metals_str}

4️⃣ مؤشرات وتحليل العملات الرقمية:
--------------------------------------------------
{crypto_msg_tg}

5️⃣ دليل أسعار سوق السيارات في مصر:
--------------------------------------------------{auto_str}

==================================================
⚙️ يُولد هذا التقرير التفصيلي تلقائياً كل 3 ساعات عبر خوادم السحابة.
"""
                email_subject = f"📈 التقرير المالي والإقتصادي الشامل - {current_time_str}"

                if send_email_report(email_subject, email_report):
                    last_email_time = current_time

        except Exception as e:
            print(f"❌ خطأ في الحلقة الرئيسية: {e}", flush=True)

        time.sleep(CHECK_INTERVAL_MINUTES * 60)

# ---------------------------------------------------------
# 7. نقطة الانطلاق
# ---------------------------------------------------------
if __name__ == '__main__':
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()

    main_loop()
