import os
import time
from threading import Thread
from flask import Flask
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. خادم Flask لإعلام منصة Render أن الخدمة تعمل على المنفذ المطلوب
# ---------------------------------------------------------
app = Flask('')


@app.route('/')
def home():
  return "🤖 Crypto Bot is alive and running!"


def run_web_server():
  # يقرأ المنفذ المخصص من Render تلقائياً
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)


# ---------------------------------------------------------
# 2. البيانات الثابتة والمتغيرات
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get(
    'TELEGRAM_TOKEN', '8214213423:AAGifBdaeIxQLp3r8Ky0y0_Hvwedq2ia6Z4'
)
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7727265173')
COIN_ID = 'bitcoin'
COIN_NAME = 'Bitcoin'
INTERVAL_MINUTES = 15


# ---------------------------------------------------------
# 3. جلب وتحليل البيانات الفنية
# ---------------------------------------------------------
def fetch_technical_data(coin_id, days=30):
  url = f'https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart'
  params = {'vs_currency': 'usd', 'days': days}
  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      )
  }

  try:
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    prices = response.json().get('prices', [])

    if not prices:
      return pd.DataFrame()

    df = pd.DataFrame(prices, columns=['timestamp', 'Price'])
    df['Date'] = pd.to_datetime(df['timestamp'], unit='ms')

    df['SMA_10'] = df['Price'].rolling(window=10).mean()
    df['SMA_30'] = df['Price'].rolling(window=30).mean()

    delta = df['Price'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()

    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    return df.dropna()
  except Exception as e:
    print(f'❌ خطأ في جلب البيانات: {e}')
    return pd.DataFrame()


# ---------------------------------------------------------
# 4. إرسال الرسائل عبر تيليجرام
# ---------------------------------------------------------
def send_telegram_message(message):
  url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
  payload = {
      'chat_id': TELEGRAM_CHAT_ID,
      'text': message,
      'parse_mode': 'Markdown',
  }
  try:
    response = requests.post(url, json=payload, timeout=10)
    return response.status_code == 200
  except Exception as e:
    print(f'❌ خطأ في إرسال التيليجرام: {e}')
    return False


# ---------------------------------------------------------
# 5. حلقة التداول والتحليل الرئيسية
# ---------------------------------------------------------
def main_loop():
  print('🤖 بدأ تشغيل بوت التحليل الفني بنجاح...')
  while True:
    try:
      df_tech = fetch_technical_data(COIN_ID, days=30)
      if not df_tech.empty:
        last_row = df_tech.iloc[-1]
        current_price = last_row['Price']
        current_rsi = last_row['RSI']
        sma_10 = last_row['SMA_10']
        sma_30 = last_row['SMA_30']
        signal_date = last_row['Date'].strftime('%Y-%m-%d %H:%M UTC')

        if sma_10 > sma_30 and 30 < current_rsi < 70:
          status_desc = (
              '🟢 *إشارة شراء (Buy)*\nالاتجاه صاعد ومؤشر RSI في منطقة استقرار'
              ' آمنة.'
          )
        elif current_rsi >= 70:
          status_desc = (
              '⚠️ *تنبيه تشبع شرائي (Overbought)*\nالسعر مرتفع جداً، يُنصح'
              ' بتجنب الشراء حالياً.'
          )
        elif current_rsi <= 30:
          status_desc = (
              'ℹ️ *تنبيه تشبع بيعي (Oversold)*\nالسعر منخفض جداً، ترقب ارتداد'
              ' صاعد محتمل.'
          )
        elif sma_10 < sma_30:
          status_desc = (
              '🔴 *إشارة بيع (Sell)*\nالاتجاه هابط والمتوسط السريع أدنى من'
              ' البطيء.'
          )
        else:
          status_desc = (
              '⚪ *احتفاظ (Hold)*\nلا توجد إشارة اتجاه قوية واضحة حالياً.'
          )

        msg = f"""🤖 *تقرير دوري مجدول تلقائياً (السحابة)*
-----------------------------------
🪙 *العملة:* {COIN_NAME}
💰 *السعر الحالي:* ${current_price:,.2f}
⏱ *التوقيت:* {signal_date}
-----------------------------------
📈 *المؤشرات الفنية:*
• المتوسط السريع (SMA 10): ${sma_10:,.2f}
• المتوسط البطيء (SMA 30): ${sma_30:,.2f}
• مؤشر القوة النسبية (RSI): {current_rsi:.1f}
-----------------------------------
🚦 *القرار الاستثماري والتنبيه:*
{status_desc}
-----------------------------------
⚙️ *إرسال تلقائي كل {INTERVAL_MINUTES} دقيقة*"""

        send_telegram_message(msg)

    except Exception as e:
      print(f'❌ خطأ في الحلقة الرئيسية: {e}')

    time.sleep(INTERVAL_MINUTES * 60)


# ---------------------------------------------------------
# 6. نقطة الانطلاق
# ---------------------------------------------------------
if __name__ == '__main__':
  # تشغيل خادم Flask أولاً فوراً حتى يكتشف Render المنفذ (Port)
  web_thread = Thread(target=run_web_server)
  web_thread.daemon = True
  web_thread.start()

  # تشغيل البوت
  main_loop()
