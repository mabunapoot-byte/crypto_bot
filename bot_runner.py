import os
import time
from threading import Thread
import urllib.parse
from flask import Flask
import pandas as pd
import requests

# استيراد مكتبات البريد الإلكتروني القياسية في بايثون
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ---------------------------------------------------------
# 1. خادم Flask لإبقاء الخدمة نشطة على Render
# ---------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "🤖 Crypto & Forex Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# ---------------------------------------------------------
# 2. الثوابت والمتغيرات (محدثة بالبيانات الجديدة)
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8214213423:AAGifBdaeIxQLp3r8Ky0y0_Hvwedq2ia6Z4')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7727265173')

# بيانات الواتساب عبر CallMeBot الجديدة
MY_PHONE_NUMBER = os.environ.get('MY_PHONE_NUMBER', '201201211155')
CALLMEBOT_API_KEY = os.environ.get('CALLMEBOT_API_KEY', '3424442')

# بيانات البريد الإلكتروني (Gmail SMTP)
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', '')      # بريد إرسال التقارير
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD', '') # كلمة مرور التطبيقات App Password
RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL', '')  # البريد المستلم للتقرير

INTERVAL_MINUTES = 15

# ---------------------------------------------------------
# 3. إرسال التقرير عبر البريد الإلكتروني (SMTP)
# ---------------------------------------------------------
def send_email_message(subject, message_body):
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
        print("⚠️ بيانات البريد الإلكتروني غير مكتملة في Render، يتم تجاوز الإرسال.", flush=True)
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

        print("📧 تم إرسال تقرير البريد الإلكتروني بنجاح!", flush=True)
        return True
    except Exception as e:
        print(f"❌ خطأ في إرسال البريد الإلكتروني: {e}", flush=True)
        return False

# ---------------------------------------------------------
# 4. إرسال الواتساب عبر CallMeBot API
# ---------------------------------------------------------
def send_whatsapp_message(message_body):
    phone_number = MY_PHONE_NUMBER.split('@')[0].replace('+', '').replace(' ', '').strip()
    api_key = CALLMEBOT_API_KEY.strip()

    if not phone_number or not api_key:
        print("⚠️ بيانات CallMeBot غير مكتملة.", flush=True)
        return False

    try:
        encoded_text = urllib.parse.quote(message_body)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone_number}&text={encoded_text}&apikey={api_key}"
        response = requests.get(url, timeout=15)

        if response.status_code == 200 and "invalid" not in response.text.lower() and "incorrect" not in response.text.lower():
            print("💬 تم إرسال تقرير الواتساب بنجاح عبر CallMeBot!", flush=True)
            return True
        else:
            print(f"❌ فشل إرسال الواتساب: {response.text}", flush=True)
            return False
    except Exception as e:
        print(f"❌ خطأ في الاتصال بـ CallMeBot: {e}", flush=True)
        return False

# ---------------------------------------------------------
# 5. إرسال الرسائل عبر تيليجرام
# ---------------------------------------------------------
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ خطأ في إرسال تيليجرام: {e}", flush=True)
        return False

# ---------------------------------------------------------
# 6. جلب أسعار العملات والتحليل الفني
# ---------------------------------------------------------
def get_forex_rates():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        res = requests.get(url, timeout=5)
        data = res.json().get('rates', {})
        usd_egp = data.get('EGP', 48.5)

        currencies = {
            'USD (دولار أمريكي)': usd_egp,
            'EUR (يورو)': (usd_egp / data.get('EUR', 1.0)) if data.get('EUR') else 0,
            'GBP (جنيه إسترليني)': (usd_egp / data.get('GBP', 1.0)) if data.get('GBP') else 0,
            'SAR (ريال سعودي)': (usd_egp / data.get('SAR', 3.75)) if data.get('SAR') else 0,
            'AED (درهم إماراتي)': (usd_egp / data.get('AED', 3.67)) if data.get('AED') else 0,
            'KWD (دينار كويتي)': (usd_egp / data.get('KWD', 0.30)) if data.get('KWD') else 0
        }
        return currencies, usd_egp
    except Exception as e:
        print(f"⚠️ خطأ في جلب أسعار الصرف: {e}", flush=True)
        return {'USD (دولار أمريكي)': 48.5}, 48.5

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
        avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
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
        print(f"❌ خطأ في جلب {pair_symbol}: {e}", flush=True)
        return None

# ---------------------------------------------------------
# 7. الحلقة الرئيسية للبوت
# ---------------------------------------------------------
def main_loop():
    print("🤖 بدأ تشغيل البوت المحدث بالأرقام الجديدة...", flush=True)

    crypto_pairs = {
        'Bitcoin (BTC)': 'BTC-USD',
        'Ethereum (ETH)': 'ETH-USD',
        'Solana (SOL)': 'SOL-USD',
        'Ripple (XRP)': 'XRP-USD',
        'Dogecoin (DOGE)': 'DOGE-USD'
    }

    while True:
        try:
            forex_rates, usd_egp = get_forex_rates()
            current_time_str = time.strftime('%Y-%m-%d %H:%M UTC')

            # 1. التقرير التفصيلي الكامل
            forex_msg = "💵 أسعار العملات الأجنبية بالجنيه المصري (EGP):\n"
            for curr_name, rate in forex_rates.items():
                forex_msg += f"• {curr_name}: {rate:,.2f} ج.م\n"

            crypto_msg = "\n📊 التحليل الفني والقرارات الاستثمارية للعملات الرقمية:\n===================================\n"

            # 2. التقرير المختصر للواتساب
            wa_msg = f"Market Summary ({current_time_str}):\n"
            wa_msg += f"USD: {usd_egp:.2f} EGP | EUR: {forex_rates.get('EUR (يورو)', 0):.2f} EGP\n"
            wa_msg += f"SAR: {forex_rates.get('SAR (ريال سعودي)', 0):.2f} EGP | AED: {forex_rates.get('AED (درهم إماراتي)', 0):.2f} EGP\n"
            wa_msg += "-------------------\nCrypto Rates:\n"

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
                        status_desc = "🟢 إشارة شراء (Buy)\n  الاتجاه صاعد ومؤشر RSI في منطقة استقرار آمنة."
                    elif rsi >= 70:
                        status_short = "Overbought"
                        status_desc = "⚠️ تنبيه تشبع شرائي (Overbought)\n  السعر مرتفع جداً، يُنصح بتجنب الشراء."
                    elif rsi <= 30:
                        status_short = "Oversold"
                        status_desc = "ℹ️ تنبيه تشبع بيعي (Oversold)\n  السعر منخفض جداً، ترقب ارتداد صاعد محتمل."
                    elif sma10 < sma30:
                        status_short = "Sell"
                        status_desc = "🔴 إشارة بيع (Sell)\n  الاتجاه هابط والمتوسط السريع أدنى من البطيء."
                    else:
                        status_short = "Hold"
                        status_desc = "⚪ احتفاظ (Hold)\n  لا توجد إشارة اتجاه قوية واضحة."

                    crypto_msg += (
                        f"🪙 {name}\n"
                        f"• السعر: ${price_usd:,.2f} ({price_egp:,.0f} ج.م)\n"
                        f"📈 المؤشرات الفنية:\n"
                        f"  - المتوسط السريع (SMA 10): ${sma10:,.2f}\n"
                        f"  - المتوسط البطيء (SMA 30): ${sma30:,.2f}\n"
                        f"  - مؤشر القوة النسبية (RSI): {rsi:.1f}\n"
                        f"🚦 القرار الاستثماري:\n{status_desc}\n"
                        f"-----------------------------------\n"
                    )

                    wa_msg += f"- {name.split(' ')[0]}: ${price_usd:,.2f} ({status_short})\n"

                time.sleep(0.3)

            full_report = f"""📊 تقرير السوق الشامل والتحليل الكمي
⏱ التوقيت: {current_time_str}
===================================
{forex_msg}===================================
{crypto_msg}⚙️ إرسال تلقائي كل {INTERVAL_MINUTES} دقيقة عبر السحابة"""

            # إرسال التقرير لـ تيليجرام
            send_telegram_message(full_report)

            # إرسال التقرير لـ الواتساب
            send_whatsapp_message(wa_msg)

            # إرسال التقرير لـ البريد الإلكتروني
            email_subject = f"📊 تقرير أسعار العملات والتحليل الفني - {current_time_str}"
            send_email_message(email_subject, full_report)

        except Exception as e:
            print(f"❌ خطأ في الحلقة الرئيسية: {e}", flush=True)

        time.sleep(INTERVAL_MINUTES * 60)

# ---------------------------------------------------------
# 8. نقطة الانطلاق
# ---------------------------------------------------------
if __name__ == '__main__':
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()

    main_loop()
