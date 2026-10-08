import os
import time
from threading import Thread
import urllib.parse
from flask import Flask
import pandas as pd
import requests

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
# 2. الثوابت والمتغيرات
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8214213423:AAGifBdaeIxQLp3r8Ky0y0_Hvwedq2ia6Z4')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7727265173')

MY_PHONE_NUMBER = os.environ.get('MY_PHONE_NUMBER', '201201211155')
CALLMEBOT_API_KEY = os.environ.get('CALLMEBOT_API_KEY', '3424442')

# إعدادات البريد الإلكتروني
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', '')
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD', '')
RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL', 'mabunapoot@gmail.com')

SHORT_INTERVAL_MINUTES = 15
EMAIL_INTERVAL_HOURS = 3

# ---------------------------------------------------------
# 3. إرسال البريد الإلكتروني (SMTP)
# ---------------------------------------------------------
def send_email_report(subject, message_body):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("⚠️ يرجى ضبط SENDER_EMAIL و SENDER_PASSWORD في Render لإرسال البريد.", flush=True)
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = subject

        msg.attach(MIMEText(message_body, 'plain', 'utf-8'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f"📧 تم إرسال التقرير الشامل لـ {RECEIVER_EMAIL} بنجاح!", flush=True)
        return True
    except Exception as e:
        print(f"❌ خطأ في إرسال البريد الإلكتروني: {e}", flush=True)
        return False

# ---------------------------------------------------------
# 4. إرسال الواتساب وتيليجرام
# ---------------------------------------------------------
def send_whatsapp_message(message_body):
    phone_number = MY_PHONE_NUMBER.split('@')[0].replace('+', '').replace(' ', '').strip()
    api_key = CALLMEBOT_API_KEY.strip()

    if not phone_number or not api_key:
        return False

    try:
        encoded_text = urllib.parse.quote(message_body)
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
# 5. جلب أسعار العملات والمعادن والأخبار
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
        
        # أسعار التقريبية للأونصة بالدولار والجرام بالجنيه
        gold_oz_usd = 2650.0  # سعر الأونصة العالمي الفعلي
        silver_oz_usd = 31.5
        
        metals = {
            'الذهب (عيار 24)': (gold_oz_usd / 31.1035) * usd_egp,
            'الذهب (عيار 21)': ((gold_oz_usd / 31.1035) * usd_egp) * (21/24),
            'الفضة (عيار 999)': (silver_oz_usd / 31.1035) * usd_egp,
            'البلاتين (الأونصة)': 980.0 * usd_egp
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
        return {'Price': last['Price'], 'RSI': last['RSI'], 'SMA_10': last['SMA_10'], 'SMA_30': last['SMA_30']}
    except Exception as e:
        print(f"❌ خطأ جلب {pair_symbol}: {e}", flush=True)
        return None

def get_crypto_and_local_news():
    news = [
        "🌐 البيتكوين يحافظ على استقراره أعلا مستويات الدعم الرئيسية مع ترقب قرارات الفائدة الأمريكية.",
        "🌐 نمو الممتلكات المؤسسية في صناديق ETF للعملات الرقمية بقيادة بلاك روك.",
        "🇪🇬 البنك المركزي المصري يواصل تعزيز التدفقت النقدية واستقرار سوق الصرف الرسمي.",
        "🚗 سوق السيارات المصري يشهد استقراراً نسبيًا في أسعار الفئات الاقتصادية مع توفر الموديلات التجميع المحلي."
    ]
    return news

def get_auto_market_prices(usd_egp):
    # متوسط أسعار تقريبية لقطاع السيارات بالسوق المصري
    cars = {
        "نيسان صني (تجميع محلي)": "695,000 - 750,000 ج.م",
        "شيري أريزو 5": "650,000 - 710,000 ج.م",
        "هيونداي إلترا AD": "890,000 - 980,000 ج.م",
        "تويوتا كورولا (1.6L)": "1,300,000 - 1,450,000 ج.م",
        "إم جي ZS": "975,000 - 1,050,000 ج.م"
    }
    return cars

# ---------------------------------------------------------
# 6. الحلقة الرئيسية والجدولة
# ---------------------------------------------------------
def main_loop():
    print("🤖 بدأ تشغيل البوت المطور (تيليجرام + واتساب + بريد إلكتروني كل 3 ساعات)...", flush=True)

    crypto_pairs = {
        'Bitcoin (BTC)': 'BTC-USD',
        'Ethereum (ETH)': 'ETH-USD',
        'Solana (SOL)': 'SOL-USD',
        'Ripple (XRP)': 'XRP-USD',
        'Dogecoin (DOGE)': 'DOGE-USD'
    }

    last_email_time = 0

    while True:
        try:
            current_time = time.time()
            forex_rates, metals, usd_egp = get_forex_and_metals()
            current_time_str = time.strftime('%Y-%m-%d %H:%M UTC')

            # --- بناء تقرير العملات الرقمية ---
            crypto_msg = ""
            wa_crypto_msg = ""
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
                        status_desc = "🟢 إشارة شراء (Buy)"
                    elif rsi >= 70:
                        status_short = "Overbought"
                        status_desc = "⚠️ تنبيه تشبع شرائي (Overbought)"
                    elif rsi <= 30:
                        status_short = "Oversold"
                        status_desc = "ℹ️ تنبيه تشبع بيعي (Oversold)"
                    elif sma10 < sma30:
                        status_short = "Sell"
                        status_desc = "🔴 إشارة بيع (Sell)"
                    else:
                        status_short = "Hold"
                        status_desc = "⚪ احتفاظ (Hold)"

                    crypto_msg += (
                        f"🪙 {name}\n"
                        f"• السعر: ${price_usd:,.2f} ({price_egp:,.0f} ج.م)\n"
                        f"• RSI: {rsi:.1f} | القرار: {status_desc}\n"
                        f"-----------------------------------\n"
                    )
                    wa_crypto_msg += f"- {name.split(' ')[0]}: ${price_usd:,.2f} ({status_short})\n"
                time.sleep(0.2)

            # --- 1. إرسال الواتساب وتيليجرام المعتاد (كل 15 دقيقة) ---
            wa_msg = f"Market Summary ({current_time_str}):\n"
            wa_msg += f"USD: {usd_egp:.2f} EGP | EUR: {forex_rates.get('EUR', 0):.2f} EGP\n"
            wa_msg += f"-------------------\nCrypto Rates:\n{wa_crypto_msg}"
            
            send_whatsapp_message(wa_msg)
            
            tg_report = f"📊 تقرير السوق والسعر المباشر\n⏱ {current_time_str}\n===================\n💵 الدولار: {usd_egp:.2f} ج.م\n===================\n{crypto_msg}"
            send_telegram_message(tg_report)

            # --- 2. إرسال البريد الإلكتروني الشامل (كل 3 ساعات) ---
            if current_time - last_email_time >= (EMAIL_INTERVAL_HOURS * 3600) or last_email_time == 0:
                news_list = get_crypto_and_local_news()
                auto_list = get_auto_market_prices(usd_egp)

                news_str = "\n".join([f"• {item}" for item in news_list])
                metals_str = "\n".join([f"• {k}: {v:,.2f} ج.م" for k, v in metals.items()])
                auto_str = "\n".join([f"• {k}: {v}" for k, v in auto_list.items()])

                email_report = f"""📊 التقرير الشامل للأسواق والتحليل المالي
⏱ التوقيت: {current_time_str}
المستلم: {RECEIVER_EMAIL}
==================================================

1️⃣ الأخبار الاقتصادية والعملات الرقمية (عالمياً ومحلياً):
--------------------------------------------------
{news_str}

2️⃣ أسعار العملات الأجنبية بالجنيه المصري:
--------------------------------------------------
• USD (دولار أمريكي): {usd_egp:.2f} ج.م
• EUR (يورو): {forex_rates.get('EUR', 0):.2f} ج.م
• GBP (جنيه إسترليني): {forex_rates.get('GBP', 0):.2f} ج.م
• SAR (ريال سعودي): {forex_rates.get('SAR', 0):.2f} ج.م
• AED (درهم إماراتي): {forex_rates.get('AED', 0):.2f} EGP

3️⃣ بورصة المعادن النفيسة (سعر الجرام بالجنيه):
--------------------------------------------------
{metals_str}

4️⃣ مؤشرات وتحليل العملات الرقمية:
--------------------------------------------------
{crypto_msg}

5️⃣ مؤشر أسعار قطاع السيارات في مصر (تحديث دروري):
--------------------------------------------------
{auto_str}

==================================================
⚙️ هذا التقرير يُولد تلقائياً كل 3 ساعات لخدمة التحليل المالي والمتابعة.
"""
                email_subject = f"📈 التقرير الشامل للأسواق والمعادن والسيارات - {current_time_str}"
                
                if send_email_report(email_subject, email_report):
                    last_email_time = current_time

        except Exception as e:
            print(f"❌ خطأ في الحلقة الرئيسية: {e}", flush=True)

        time.sleep(SHORT_INTERVAL_MINUTES * 60)

# ---------------------------------------------------------
# 7. نقطة الانطلاق
# ---------------------------------------------------------
if __name__ == '__main__':
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()

    main_loop()
