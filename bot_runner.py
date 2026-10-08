import os
import time
from threading import Thread
from flask import Flask
import pandas as pd
import requests

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
# 2. الثوابت والمتغيرات
# ---------------------------------------------------------
TELEGRAM_TOKEN = os.environ.get(
    'TELEGRAM_TOKEN', '8214213423:AAGifBdaeIxQLp3r8Ky0y0_Hvwedq2ia6Z4'
)
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7727265173')
INTERVAL_MINUTES = 15


# ---------------------------------------------------------
# 3. جلب أسعار العملات الأجنبية مقابل الجنيه المصري
# ---------------------------------------------------------
def get_forex_rates():
  try:
    url = 'https://open.er-api.com/v6/latest/USD'
    res = requests.get(url, timeout=5)
    data = res.json().get('rates', {})
    usd_egp = data.get('EGP', 48.5)

    currencies = {
        '🇺🇸 USD (دولار أمريكي)': usd_egp,
        '🇪🇺 EUR (يورو)': (
            (usd_egp / data.get('EUR', 1.0)) if data.get('EUR') else 0
        ),
        '🇬🇧 GBP (جنيه إسترليني)': (
            (usd_egp / data.get('GBP', 1.0)) if data.get('GBP') else 0
        ),
        '🇸🇦 SAR (ريال سعودي)': (
            (usd_egp / data.get('SAR', 3.75)) if data.get('SAR') else 0
        ),
        '🇦🇪 AED (درهم إماراتي)': (
            (usd_egp / data.get('AED', 3.67)) if data.get('AED') else 0
        ),
        '🇰🇼 KWD (دينار كويتي)': (
            (usd_egp / data.get('KWD', 0.30)) if data.get('KWD') else 0
        ),
    }
    return currencies, usd_egp
  except Exception as e:
    print(f'⚠️ خطأ في جلب أسعار الصرف: {e}', flush=True)
    return {'🇺🇸 USD (دولار أمريكي)': 48.5}, 48.5


# ---------------------------------------------------------
# 4. جلب وتحليل البيانات الفنية للعملات الرقمية
# ---------------------------------------------------------
def fetch_crypto_data(pair_symbol):
  url = f'https://api.exchange.coinbase.com/products/{pair_symbol}/candles?granularity=900'
  headers = {'User-Agent': 'Mozilla/5.0'}
  try:
    res = requests.get(url, headers=headers, timeout=8)
    res.raise_for_status()
    data = res.json()
    if not data:
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
    print(f'❌ خطأ في جلب {pair_symbol}: {e}', flush=True)
    return None


# ---------------------------------------------------------
# 5. إرسال الرسائل عبر تيليجرام
# ---------------------------------------------------------
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
    print(f'❌ خطأ في إرسال تيليجرام: {e}', flush=True)
    return False


# ---------------------------------------------------------
# 6. الحلقة الرئيسية للبوت
# ---------------------------------------------------------
def main_loop():
  print('🤖 بدأ تشغيل بوت العملات الشامل وسعر الصرف...', flush=True)

  # قائمة أهم العملات الرقمية
  crypto_pairs = {
      'Bitcoin (BTC)': 'BTC-USD',
      'Ethereum (ETH)': 'ETH-USD',
      'Solana (SOL)': 'SOL-USD',
      'Ripple (XRP)': 'XRP-USD',
      'Cardano (ADA)': 'ADA-USD',
      'Binance Coin (BNB)': 'BNB-USD',
      'Dogecoin (DOGE)': 'DOGE-USD',
  }

  while True:
    try:
      forex_rates, usd_egp = get_forex_rates()

      # 1. بناء قسم أسعار العملات الأجنبية
      forex_msg = '💵 *أسعار العملات الأجنبية بالجنيه المصري (EGP):*\n'
      for curr_name, rate in forex_rates.items():
        forex_msg += f'• {curr_name}: *{rate:,.2f} ج.م*\n'

      # 2. بناء قسم العملات الرقمية
      crypto_msg = '\n🪙 *تحليل أبرز العملات الرقمية:*\n'
      crypto_msg += '-----------------------------------\n'

      for name, pair in crypto_pairs.items():
        cdata = fetch_crypto_data(pair)
        if cdata:
          price_usd = cdata['Price']
          price_egp = price_usd * usd_egp
          rsi = cdata['RSI']
          sma10 = cdata['SMA_10']
          sma30 = cdata['SMA_30']

          if sma10 > sma30 and 30 < rsi < 70:
            signal = '🟢 شراء'
          elif rsi >= 70:
            signal = '⚠️ تشبع شرائي'
          elif rsi <= 30:
            signal = 'ℹ️ تشبع بيعي'
          elif sma10 < sma30:
            signal = '🔴 بيع'
          else:
            signal = '⚪ احتفاظ'

          crypto_msg += (
              f'📌 *{name}*\n'
              f'• السعر: *${price_usd:,.2f}* ({price_egp:,.0f} ج.م)\n'
              f'• RSI: *{rsi:.1f}* | الإشارة: *{signal}*\n'
              '-----------------------------------\n'
          )
        time.sleep(0.3)

      # 3. تجميع التقرير النهائي
      current_time_str = time.strftime('%Y-%m-%d %H:%M UTC')
      full_report = f"""📊 *التقرير الشامل للعملات وسعر الصرف*
⏱ *التوقيت:* {current_time_str}
===================================
{forex_msg}===================================
{crypto_msg}⚙️ *تحديث تلقائي كل {INTERVAL_MINUTES} دقيقة عبر السحابة*"""

      send_telegram_message(full_report)

    except Exception as e:
      print(f'❌ خطأ في الحلقة الرئيسية: {e}', flush=True)

    time.sleep(INTERVAL_MINUTES * 60)


# ---------------------------------------------------------
# 7. نقطة الانطلاق
# ---------------------------------------------------------
if __name__ == '__main__':
  web_thread = Thread(target=run_web_server)
  web_thread.daemon = True
  web_thread.start()

  main_loop()
