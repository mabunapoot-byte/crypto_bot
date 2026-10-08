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
# 4. إرسال الواتساب وتيليجرام
# ---------------------------------------------------------
def send_whatsapp_message(message_body):
    phone_number = MY_PHONE_NUMBER.split('@')[0].replace('+', '').replace(' ', '').strip()
    api_key = CALLMEBOT_API_KEY.strip()

    if not phone_number or not api_key:
        return False

    try:
        encoded_text = urllib.parse.quote_plus(message_body)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone_number}&text={encoded_text}&apikey={api_key}"
        res = requests.get(url, timeout=15)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ خطأ واتساب: {e}", flush=True)
        return False

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage
