import os
import re
import time
from threading import Thread
import urllib.parse
import xml.etree.ElementTree as ET
from flask import Flask
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. خادم Flask لإبقاء الخدمة نشطة على Render
# ---------------------------------------------------------
app = Flask('')


@app.route('/')
def home():
  return '🤖 Realtime Financial & Official Economic Data Bot is running!'


def run_web_server():
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)


# ---------------------------------------------------------
# 2. الثوابت ومتغيرات البيئة
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get(
    'TELEGRAM_TOKEN', '8214213423:AAGifBdaeIxQLp3r8Ky0y0_Hvwedq2ia6Z4'
)
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7727265173')

MY_PHONE_NUMBER = os.environ.get('MY_PHONE_NUMBER', '201201211155')
CALLMEBOT_API_KEY = os.environ.get('CALLMEBOT_API_KEY', '3424442')

SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'mabunapoot@gmail.com')
RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL', 'mabunapoot@gmail.com')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '').strip()

# تعديل فترات التحديث (بالساعات) لتصبح عملية ومباشرة
CHECK_INTERVAL_MINUTES = 5
WHATSAPP_INTERVAL_HOURS = 1  # إرسال كل ساعة
EMAIL_INTERVAL_HOURS = 2  # إرسال كل ساعتين
TELEGRAM_INTERVAL_HOURS = 1  # إرسال كل ساعة


# ---------------------------------------------------------
# 3. إرسال البريد الإلكتروني عبر Brevo HTTP API
# ---------------------------------------------------------
def send_email_report(subject, message_body):
  if not BREVO_API_KEY:
    print('⚠️ BREVO_API_KEY غير مضبوط في متغيرات البيئة.', flush=True)
    return False

  url = 'https://api.brevo.com/v3/smtp/email'
  headers = {
      'accept': 'application/json',
      'api-key': BREVO_API_KEY,
      'content-type': 'application/json',
  }

  payload = {
      'sender': {'name': 'Realtime Financial Bot', 'email': SENDER_EMAIL},
      'to': [{'email': RECEIVER_EMAIL}],
      'subject': subject,
      'textContent': message_body,
  }

  try:
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    return response.status_code in [200, 201]
  except Exception as e:
    print(f'❌ خطأ في إرسال البريد: {e}', flush=True)
    return False


# ---------------------------------------------------------
# 4. إرسال الواتساب وتيليجرام
# ---------------------------------------------------------
def send_whatsapp_message(message_body):
  phone_number = (
      MY_PHONE_NUMBER.split('@')[0]
      .replace('+', '')
      .replace(' ', '')
      .strip()
  )
  api_key = CALLMEBOT_API_KEY.strip()

  if not phone_number or not api_key:
    return False

  try:
    encoded_text = urllib.parse.quote(message_body, safe='')
    url = f'https://api.callmebot.com/whatsapp.php?phone={phone_number}&text={encoded_text}&apikey={api_key}'
    res = requests.get(url, timeout=15)
    return res.status_code == 200
  except Exception as e:
    print(f'❌ خطأ واتساب: {e}', flush=True)
    return False


def send_telegram_message(message):
  url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
  payload = {
      'chat_id': TELEGRAM_CHAT_ID,
      'text': message,
      'parse_mode': 'Markdown',
  }
  try:
    res = requests.post(url, json=payload, timeout=10)
    return res.status_code == 200
  except Exception as e:
    print(f'❌ خطأ تيليجرام: {e}', flush=True)
    return False


# ---------------------------------------------------------
# 5. جلب الأخبار الاقتصادية الحية
# ---------------------------------------------------------
def fetch_live_arabic_news():
  news_data = {}
  sources = {
      '🇺🇸 أمريكا والفيدرالي': (
          'https://news.google.com/rss/search?q=الفيدرالي+الأمريكي+الاقتصاد&hl=ar&gl=EG&ceid=EG:ar'
      ),
      '🇪🇺 أوروبا وروسيا': (
          'https://news.google.com/rss/search?q=المركزي+الأوروبي+روسيا+تضخم&hl=ar&gl=EG&ceid=EG:ar'
      ),
      '🇨🇳 🇯🇵 أسواق آسيا': (
          'https://news.google.com/rss/search?q=اقتصاد+الصين+اليابان+أسواق&hl=ar&gl=EG&ceid=EG:ar'
      ),
      '🌍 مصر والشرق الأوسط': (
          'https://news.google.com/rss/search?q=اقتصاد+مصر+البنك+المركزي&hl=ar&gl=EG&ceid=EG:ar'
      ),
  }

  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
          ' (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
      )
  }

  for region, url in sources.items():
    try:
      res = requests.get(url, headers=headers, timeout=8)
      if res.status_code == 200:
        root = ET.fromstring(res.content)
        items = root.findall('.//item/title')[:2]
        headlines = [
            item.text.rsplit(' - ', 1)[0]
            for item in items
            if item.text is not None
        ]
        news_data[region] = (
            headlines if headlines else ['لا توجد عناوين جديدة حالياً.']
        )
      else:
        news_data[region] = ['تعذر جلب الأخبار من المصدر.']
    except Exception as e:
      print(f'❌ خطأ جلب أخبار {region}: {e}', flush=True)
      news_data[region] = ['خطأ في الاتصال بمصدر الأخبار.']
  return news_data


def get_egypt_macro_indicators():
  return {
      'سعر الفائدة الرئيسي (البنك المركزي CBE)': '19.50%',
      'معدل التضخم السنوي (CAPMAS / CBE)': '14.5%',
      'معدل البطالة (CAPMAS)': '6.0%',
      'توقعات نمو الاقتصاد (IMF)': '4.7% - 5.1%',
      'احتياطي النقد الأجنبي المباشر (CBE)': '57.34 مليار دولار',
  }


# ---------------------------------------------------------
# 6. جلب الأسعار والبيانات المالية
# ---------------------------------------------------------
def fetch_egypt_local_gold_prices(usd_egp, gold_oz_usd):
  g24_est = (gold_oz_usd / 31.1035) * usd_egp
  return {
      'الذهب (24)': g24_est,
      'الذهب (21)': g24_est * (21 / 24),
      'الذهب (18)': g24_est * (18 / 24),
      'الجنيه الذهب': (g24_est * (21 / 24)) * 8,
  }


def get_live_forex_and_metals():
  try:
    url = 'https://open.er-api.com/v6/latest/USD'
    res = requests.get(url, timeout=5)
    rates = res.json().get('rates', {})
    usd_egp = rates.get('EGP', 47.4)

    forex = {
        'USD': usd_egp,
        'EUR': (usd_egp / rates.get('EUR', 1.0)) if rates.get('EUR') else 0,
        'GBP': (usd_egp / rates.get('GBP', 1.0)) if rates.get('GBP') else 0,
        'SAR': (usd_egp / rates.get('SAR', 3.75)) if rates.get('SAR') else 0,
    }

    gold_oz_usd = 2650.0
    metals = fetch_egypt_local_gold_prices(usd_egp, gold_oz_usd)

    return forex, metals, usd_egp, gold_oz_usd
  except Exception as e:
    print(f'⚠️ خطأ جلب البيانات المالية: {e}', flush=True)
    return {'USD': 47.4}, {}, 47.4, 2650.0


def fetch_technical_data(pair_symbol):
  url = f'https://api.exchange.coinbase.com/products/{pair_symbol}/candles?granularity=900'
  headers = {'User-Agent': 'Mozilla/5.0'}
  try:
    res = requests.get(url, headers=headers, timeout=8)
    data = res.json()
    if not data or not isinstance(data, list):
      return None

    df = pd.DataFrame(
        data, columns=['timestamp', 'low', 'high', 'open', 'Price', 'volume']
    )
    df['Date'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('Date').reset_index(drop=True)

    df['SMA_10'] = df['Price'].rolling(window=10).mean()
    df['SMA_30'] = df['Price'].rolling(window=30).mean()

    delta = df['Price'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    last = df.dropna().iloc[-1]
    return {
        'Price': last['Price'],
        'RSI': last['RSI'],
        'SMA_10': last['SMA_10'],
        'SMA_30': last['SMA_30'],
    }
  except Exception as e:
    return None


# ---------------------------------------------------------
# 7. الحلقة الرئيسية والجدولة
# ---------------------------------------------------------
def main_loop():
  print('🤖 بدأ تشغيل البوت المحدث مع إرسال الأخبار الحية...', flush=True)

  crypto_pairs = {'Bitcoin (BTC)': 'BTC-USD', 'Ethereum (ETH)': 'ETH-USD'}

  last_whatsapp_time = 0
  last_email_time = 0
  last_telegram_time = 0

  while True:
    try:
      current_time = time.time()
      forex_rates, metals, usd_egp, gold_oz = get_live_forex_and_metals()
      egypt_macro = get_egypt_macro_indicators()
      current_time_str = time.strftime('%Y-%m-%d %H:%M UTC')

      # جلب الأخبار الحية لاستخدامها في جميع القنوات
      arabic_news = fetch_live_arabic_news()
      news_formatted_text = ''
      for region, headlines in arabic_news.items():
        news_formatted_text += f'\n*{region}:*\n'
        for h in headlines:
          news_formatted_text += f'• {h}\n'

      # --- 1. إرسال تيليجرام ---
      if (
          current_time - last_telegram_time >= (TELEGRAM_INTERVAL_HOURS * 3600)
          or last_telegram_time == 0
      ):
        full_tg_report = f"""📰 *تحديث الأخبار الاقتصادية والأسواق*
⏱ التوقيت: {current_time_str}
===================================
{news_formatted_text}
===================================
💵 *العملات:* USD: {usd_egp:.2f} ج.م | EUR: {forex_rates.get('EUR', 0):.2f} ج.م
👑 *الذهب:* عيار 21: {metals.get('الذهب (21)', 0):,.0f} ج.م
===================================
⚙️ إرسال تلقائي عبر السحابة"""

        if send_telegram_message(full_tg_report):
          print('✅ تم إرسال تحديث تيليجرام بنجاح.', flush=True)
          last_telegram_time = current_time

      # --- 2. إرسال الواتساب ---
      if (
          current_time - last_whatsapp_time >= (WHATSAPP_INTERVAL_HOURS * 3600)
          or last_whatsapp_time == 0
      ):
        wa_msg = f"""📊 *تحديث الأخبار والأسواق (WhatsApp)*
⏱ {current_time_str}
-----------------------------------
{news_formatted_text}
-----------------------------------
💵 *الدولار:* {usd_egp:.2f} ج.م
👑 *ذهب عيار 21:* {metals.get('الذهب (21)', 0):,.0f} ج.م
-----------------------------------
⚙️ التحديث القادم بعد ساعة"""

        if send_whatsapp_message(wa_msg):
          print('✅ تم إرسال تحديث الواتساب بنجاح.', flush=True)
          last_whatsapp_time = current_time

      # --- 3. إرسال البريد الإلكتروني ---
      if (
          current_time - last_email_time >= (EMAIL_INTERVAL_HOURS * 3600)
          or last_email_time == 0
      ):
        email_report = f"""📊 التقرير المالي والإقتصادي الشامل
⏱ التوقيت: {current_time_str}
==================================================

1️⃣ النشرة الاقتصادية العاجلة:
--------------------------------------------------
{news_formatted_text}

2️⃣ أسعار العملات والمعادن:
--------------------------------------------------
• USD: {usd_egp:.2f} ج.م
• الذهب عيار 21: {metals.get('الذهب (21)', 0):,.2f} ج.م
"""
        email_subject = (
            f'📈 التقرير المالي والإقتصادي الشامل - {current_time_str}'
        )

        if send_email_report(email_subject, email_report):
          print('✅ تم إرسال الإيميل بنجاح.', flush=True)
          last_email_time = current_time

    except Exception as e:
      print(f'❌ خطأ في الحلقة الرئيسية: {e}', flush=True)

    time.sleep(CHECK_INTERVAL_MINUTES * 60)


# ---------------------------------------------------------
# 8. نقطة الانطلاق
# ---------------------------------------------------------
if __name__ == '__main__':
  web_thread = Thread(target=run_web_server)
  web_thread.daemon = True
  web_thread.start()

  main_loop()
