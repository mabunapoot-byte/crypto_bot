import os
import time
from threading import Thread
from flask import Flask
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. خادم Flask لفتح المنفذ وتلبية شرط Render
# ---------------------------------------------------------
app = Flask('')


@app.route('/')
def home():
  return "🤖 Crypto Bot is alive and running!"


def run_web_server():
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)


# ---------------------------------------------------------
# 2. الثوابت والمتغيرات
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
COIN_NAME = 'Bitcoin'
INTERVAL_MINUTES = 15


# ---------------------------------------------------------
# 3. جلب البيانات عبر Coinbase API (مفتوح ولا يحظر Render)
# ---------------------------------------------------------
def fetch_technical_data():
  # جلب الشموع اليابانية للإطار الزمني 15 دقيقة (900 ثانية)
  url = 'https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=900'
  headers = {'User-Agent': 'Mozilla/5.0'}

  try:
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    if not data:
      print('⚠️ لم يتم استرجاع بيانات من Coinbase', flush=True)
      return pd.DataFrame()

    # Coinbase ترجع ترتيب العناصر: [timestamp, low, high, open, close, volume]
    df = pd.DataFrame(
        data, columns=['timestamp', 'low', 'high', 'open', 'Price', 'volume']
    )
    df['Date'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('Date').reset_index(drop=True)

    # المتوسطات المتحركة
    df['SMA_10'] = df['Price'].rolling(window=10).mean()
    df['SMA_30'] = df['Price'].rolling(window=30).mean()

    # حساب RSI بالنعومة الأسية الاحترافية
    delta = df['Price'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()

    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    return df.dropna()
  except Exception as e:
    print(f'❌ خطأ في جلب البيانات من Coinbase: {e}', flush=True)
    return pd.DataFrame()


# ---------------------------------------------------------
# 4. إرسال الرسائل عبر تيليجرام
# ---------------------------------------------------------
def send_telegram_message(message):
  if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print('⚠️ متغيرات البيئة للتيليجرام غير مضبوطة بشكل صحيح!', flush=True)
    return False

  url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
  payload = {
      'chat_id': TELEGRAM_CHAT_ID,
      'text': message,
      'parse_mode': 'Markdown',
  }
  try:
    response = requests.post(url, json=payload, timeout=10)
    if response.status_code == 200:
      print('✅ تم إرسال التقرير إلى تيليجرام بنجاح!', flush=True)
      return True
    else:
      print(f'❌ فشل إرسال تيليجرام: {response.text}', flush=True)
      return False
  except Exception as e:
    print(f'❌ خطأ في الاتصال بتيليجرام: {e}', flush=True)
    return False


# ---------------------------------------------------------
# 5. الحلقة الرئيسية
# ---------------------------------------------------------
def main_loop():
  print('🤖 بدأ تشغيل البوت مع Coinbase API...', flush=True)

  # إرسال تنبيه تأكيد فوري عند بداية تشغيل السيرفر
  send_telegram_message(
      '🚀 *تم تحديث البوت والربط مع Coinbase API بنجاح! جاري التوصيل...*'
  )

  while True:
    try:
      df_tech = fetch_technical_data()
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
      print(f'❌ خطأ في الحلقة الرئيسية: {e}', flush=True)

    print(
        f'😴 جاري الانتظار {INTERVAL_MINUTES} دقيقة حتى التقرير القادم...',
        flush=True,
    )
    time.sleep(INTERVAL_MINUTES * 60)


# ---------------------------------------------------------
# 6. نقطة الانطلاق
# ---------------------------------------------------------
if __name__ == '__main__':
  web_thread = Thread(target=run_web_server)
  web_thread.daemon = True
  web_thread.start()

  main_loop()
