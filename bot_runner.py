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

CHECK_INTERVAL_MINUTES = 5
WHATSAPP_INTERVAL_HOURS = 2
EMAIL_INTERVAL_HOURS = 3
TELEGRAM_INTERVAL_HOURS = 6


# ---------------------------------------------------------
# 3. إرسال البريد الإلكتروني عبر Brevo HTTP API
# ---------------------------------------------------------
def send_email_report(subject, message_body):
  if not BREVO_API_KEY:
    print(
        '⚠️ يرجى ضبط BREVO_API_KEY في إعدادات Render لإرسال البريد.', flush=True
    )
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
    encoded_text = urllib.parse.quote_plus(message_body)
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
# 5. البيانات الكلية الرسمية (البنك المركزي + CAPMAS + صندوق النقد)
# ---------------------------------------------------------
def get_egypt_macro_indicators():
  return {
      'سعر الفائدة الرئيسي (البنك المركزي CBE)': '19.50%',
      'سعر فائدة الإقراض لليلة واحدة (CBE)': '20.00%',
      'سعر فائدة الإيداع لليلة واحدة (CBE)': '18.50%',
      'معدل التضخم السنوي (CAPMAS / CBE)': '14.5%',
      'معدل التضخم الأساسي السنوي (CBE)': '14.9%',
      'معدل البطالة (الجهاز المركزي للإحصاء CAPMAS)': '6.0%',
      'توقعات نمو الاقتصاد (صندوق النقد الدولي IMF)': '4.7% - 5.1%',
      'إجمالي المعروض النقدي والسيولة المحلية (M2)': '15.66 تريليون ج.م',
      'السيولة والودائع بالجهاز المصرفي': '27.49 تريليون ج.م',
      'احتياطي النقد الأجنبي المباشر (CBE)': '57.34 مليار دولار',
      'عدد السكان الرسمي بالداخل (CAPMAS)': '107.5 مليون نسمة',
  }


def fetch_live_arabic_news():
  """جلب أحدث الأخبار الاقتصادية باللغة العربية بالكامل عبر خلاصات Google News"""
  news_data = {}
  sources = {
      '🇺🇸 الاقتصاد الأمريكي والسياسة النقدية': (
          'https://news.google.com/rss/search?q=الفيدرالي+الأمريكي+الاقتصاد&hl=ar&gl=EG&ceid=EG:ar'
      ),
      '🇪🇺 أوروبا وروسيا والطاقة': (
          'https://news.google.com/rss/search?q=المركزي+الأوروبي+روسيا+تضخم&hl=ar&gl=EG&ceid=EG:ar'
      ),
      '🇨🇳 🇯🇵 أسواق آسيا والصين': (
          'https://news.google.com/rss/search?q=اقتصاد+الصين+اليابان+أسواق&hl=ar&gl=EG&ceid=EG:ar'
      ),
      '🌍 الشرق الأوسط ومصر': (
          'https://news.google.com/rss/search?q=اقتصاد+مصر+البنك+المركزي&hl=ar&gl=EG&ceid=EG:ar'
      ),
  }

  for region, url in sources.items():
    try:
      res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=6)
      root = ET.fromstring(res.text)
      items = root.findall('.//item/title')[:2]
      headlines = [
          item.text.rsplit(' - ', 1)[0]
          for item in items
          if item.text is not None
      ]
      news_data[region] = (
          headlines
          if headlines
          else ['متابعة تحركات الأسواق العالمية والمحلية مباشرة.']
      )
    except Exception:
      news_data[region] = ['تغطية إخبارية اقتصادية مستمرة باللغة العربية.']
  return news_data


# ---------------------------------------------------------
# 6. جلب أسعار العملات والمعادن والسيارات
# ---------------------------------------------------------
def fetch_egypt_local_gold_prices(usd_egp, gold_oz_usd):
  headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

  try:
    url = 'https://api.gold-era.com/api/prices/gold'
    res = requests.get(url, headers=headers, timeout=5)
    if res.status_code == 200:
      data = res.json()
      g21 = float(data.get('gram21', 0))
      g24 = float(data.get('gram24', 0))
      if g21 > 2000:
        return {
            'الذهب (24)': g24 if g24 > 0 else g21 * (24 / 21),
            'الذهب (21)': g21,
            'الذهب (18)': g21 * (18 / 21),
            'الجنيه الذهب': g21 * 8,
        }
  except Exception:
    pass

  try:
    url = 'https://www.goldpriceegypt.com/'
    res = requests.get(url, headers=headers, timeout=5)
    if res.status_code == 200:
      match_21 = re.search(r'عيار 21.*?(\d[\d,]{3,})', res.text)
      if match_21:
        g21 = float(match_21.group(1).replace(',', ''))
        if g21 > 2000:
          return {
              'الذهب (24)': g21 * (24 / 21),
              'الذهب (21)': g21,
              'الذهب (18)': g21 * (18 / 21),
              'الجنيه الذهب': g21 * 8,
          }
  except Exception:
    pass

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
        'AED': (usd_egp / rates.get('AED', 3.67)) if rates.get('AED') else 0,
        'KWD': (usd_egp / rates.get('KWD', 0.30)) if rates.get('KWD') else 0,
    }

    try:
      r_gold = requests.get(
          'https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT',
          timeout=5,
      )
      gold_oz_usd = float(r_gold.json().get('price', 2650.0))
    except Exception:
      gold_oz_usd = 2650.0

    try:
      r_silver = requests.get(
          'https://api.exchange.coinbase.com/products/XAG-USD/ticker', timeout=5
      )
      silver_oz_usd = float(r_silver.json().get('price', 31.5))
    except Exception:
      silver_oz_usd = 31.5

    metals = fetch_egypt_local_gold_prices(usd_egp, gold_oz_usd)
    metals['الفضة (999)'] = (silver_oz_usd / 31.1035) * usd_egp
    metals['الفضة (925)'] = ((silver_oz_usd / 31.1035) * usd_egp) * 0.925
    metals['البلاتين (أونصة)'] = gold_oz_usd * 0.37 * usd_egp
    metals['البالاديوم (أونصة)'] = gold_oz_usd * 0.39 * usd_egp

    return forex, metals, usd_egp, gold_oz_usd
  except Exception as e:
    print(f'⚠️ خطأ جلب البيانات المالية: {e}', flush=True)
    return {'USD': 47.4}, {}, 47.4, 2650.0


def get_dynamic_auto_market(usd_egp):
  factor = usd_egp / 47.4
  cars = {
      '🚗 اقتصادية': {
          'نيسان صني': f'{int(695000*factor):,} - {int(750000*factor):,} ج.م',
          'شيري أريزو 5': f'{int(650000*factor):,} - {int(710000*factor):,} ج.م',
          'سوزوكي سويفت': f'{int(620000*factor):,} - {int(680000*factor):,} ج.م',
      },
      '🚘 متوسطة': {
          'تويوتا كورولا': (
              f'{int(1300000*factor):,} - {int(1450000*factor):,} ج.م'
          ),
          'هيونداي إلترا AD': (
              f'{int(890000*factor):,} - {int(980000*factor):,} ج.م'
          ),
          'إم جي ZS': f'{int(975000*factor):,} - {int(1050000*factor):,} ج.م',
          'كيا سبورتاج': (
              f'{int(1780000*factor):,} - {int(1950000*factor):,} ج.م'
          ),
      },
      '🏎️ فاخرة وكهرباء': {
          'مرسيدس C200': (
              f'{int(3400000*factor):,} - {int(3800000*factor):,} ج.م'
          ),
          'بي إم دبليو 320i': (
              f'{int(3200000*factor):,} - {int(3600000*factor):,} ج.م'
          ),
          'فولكس ID.4': (
              f'{int(1650000*factor):,} - {int(1850000*factor):,} ج.م'
          ),
      },
  }
  return cars


def fetch_technical_data(pair_symbol):
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
    print(f'❌ خطأ جلب {pair_symbol}: {e}', flush=True)
    return None


# ---------------------------------------------------------
# 7. الحلقة الرئيسية والجدولة
# ---------------------------------------------------------
def main_loop():
  print(
      '🤖 بدأ تشغيل البوت المحدث بالمؤشرات الرسمية والأخبار العربية...',
      flush=True,
  )

  crypto_pairs = {
      'Bitcoin (BTC)': 'BTC-USD',
      'Ethereum (ETH)': 'ETH-USD',
      'Solana (SOL)': 'SOL-USD',
      'Ripple (XRP)': 'XRP-USD',
      'Dogecoin (DOGE)': 'DOGE-USD',
  }

  last_whatsapp_time = 0
  last_email_time = 0
  last_telegram_time = 0

  while True:
    try:
      current_time = time.time()
      forex_rates, metals, usd_egp, gold_oz = get_live_forex_and_metals()
      egypt_macro = get_egypt_macro_indicators()
      current_time_str = time.strftime('%Y-%m-%d %H:%M UTC')

      crypto_msg_tg = '\n📊 التحليل الفني للعملات الرقمية:\n===================================\n'
      wa_crypto_details = ''

      for name, pair in crypto_pairs.items():
        cdata = fetch_technical_data(pair)
        if cdata:
          price_usd = cdata['Price']
          price_egp = price_usd * usd_egp
          rsi = cdata['RSI']
          sma10 = cdata['SMA_10']
          sma30 = cdata['SMA_30']

          if sma10 > sma30 and 30 < rsi < 70:
            status_short = 'Buy'
            status_desc_tg = (
                '🟢 إشارة شراء (Buy)\n  الاتجاه صاعد ومؤشر RSI في منطقة'
                ' استقرار آمنة.'
            )
          elif rsi >= 70:
            status_short = 'Overbought'
            status_desc_tg = (
                '⚠️ تنبيه تشبع شرائي (Overbought)\n  السعر مرتفع جداً، يُنصح'
                ' بتجنب الشراء.'
            )
          elif rsi <= 30:
            status_short = 'Oversold'
            status_desc_tg = (
                'ℹ️ تنبيه تشبع بيعي (Oversold)\n  السعر منخفض جداً، ترقب ارتداد'
                ' صاعد محتمل.'
            )
          elif sma10 < sma30:
            status_short = 'Sell'
            status_desc_tg = (
                '🔴 إشارة بيع (Sell)\n  الاتجاه هابط والمتوسط السريع أدنى من'
                ' البطيء.'
            )
          else:
            status_short = 'Hold'
            status_desc_tg = '⚪ احتفاظ (Hold)\n  لا توجد إشارة اتجاه قوية واضحة.'

          crypto_msg_tg += (
              f'🪙 {name}\n'
              f'• السعر: ${price_usd:,.2f} ({price_egp:,.0f} ج.م)\n'
              f'📈 المؤشرات الفنية:\n'
              f'  - المتوسط السريع (SMA 10): ${sma10:,.2f}\n'
              f'  - المتوسط البطيء (SMA 30): ${sma30:,.2f}\n'
              f'  - مؤشر القوة النسبية (RSI): {rsi:.1f}\n'
              f'🚦 القرار الاستثماري:\n{status_desc_tg}\n'
              '-----------------------------------\n'
          )

          short_name = name.split(' ')[0]
          wa_crypto_details += f'• {short_name}: ${price_usd:,.2f} | RSI:{rsi:.1f} ({status_short})\n'

        time.sleep(0.2)

      # --- 1. إرسال تيليجرام (كل 6 ساعات) ---
      if (
          current_time - last_telegram_time >= (TELEGRAM_INTERVAL_HOURS * 3600)
          or last_telegram_time == 0
      ):
        forex_msg_tg = '💵 أسعار العملات الأجنبية بالجنيه المصري (EGP):\n'
        for curr_name, rate in forex_rates.items():
          forex_msg_tg += f'• {curr_name}: {rate:,.2f} ج.م\n'

        macro_tg = '\n🇪🇬 بيانات البنك المركزي وCAPMAS والنمو (IMF):\n'
        macro_tg += (
            f"• الفائدة الرئيسية (CBE):"
            f" {egypt_macro.get('سعر الفائدة الرئيسي (البنك المركزي CBE)')}\n"
        )
        macro_tg += (
            f"• التضخم السنوي:"
            f" {egypt_macro.get('معدل التضخم السنوي (CAPMAS / CBE)')} |"
            f" البطالة:"
            f" {egypt_macro.get('معدل البطالة (الجهاز المركزي للإحصاء CAPMAS)')}\n"
        )
        macro_tg += (
            f"• توقعات النمو (IMF):"
            f" {egypt_macro.get('توقعات نمو الاقتصاد (صندوق النقد الدولي IMF)')}\n"
        )
        macro_tg += (
            f"• الاحتياطي النقدي:"
            f" {egypt_macro.get('احتياطي النقد الأجنبي المباشر (CBE)')}\n"
        )

        full_tg_report = f"""📊 تقرير السوق الشامل والمؤشرات الرسمية (كل 6 ساعات)
⏱ التوقيت: {current_time_str}
===================================
{forex_msg_tg}{macro_tg}===================================
{crypto_msg_tg}⚙️ إرسال تلقائي عبر السحابة"""

        if send_telegram_message(full_tg_report):
          last_telegram_time = current_time

      # --- 2. إرسال الواتساب (كل ساعتين) ---
      if (
          current_time - last_whatsapp_time >= (WHATSAPP_INTERVAL_HOURS * 3600)
          or last_whatsapp_time == 0
      ):
        wa_msg = (
            f'📊 *تقرير السوق والمؤشرات الرسمية*\n⏱'
            f' {current_time_str}\n-----------------------------------\n💵'
            f' *أسعار العملات (EGP):*\n• USD: {usd_egp:.2f} | EUR:'
            f" {forex_rates.get('EUR', 0):.2f}\n• GBP:"
            f" {forex_rates.get('GBP', 0):.2f} | SAR:"
            f" {forex_rates.get('SAR', 0):.2f}\n• AED:"
            f" {forex_rates.get('AED', 0):.2f} | KWD:"
            f" {forex_rates.get('KWD', 0):.2f}\n-----------------------------------\n🇪🇬"
            ' *بيانات CBE / CAPMAS / IMF:*\n• الفائدة الرئيسية:'
            f" {egypt_macro.get('سعر الفائدة الرئيسي (البنك المركزي CBE)')}\n•"
            ' التضخم السنوي:'
            f" {egypt_macro.get('معدل التضخم السنوي (CAPMAS / CBE)')} |"
            ' البطالة:'
            f" {egypt_macro.get('معدل البطالة (الجهاز المركزي للإحصاء CAPMAS)')}\n•"
            ' نمو IMF:'
            f" {egypt_macro.get('توقعات نمو الاقتصاد (صندوق النقد الدولي IMF)')}\n-----------------------------------\n👑"
            ' *أسعار الصاغة المصرية (الجرام):*\n• الذهب (21):'
            f" {metals.get('الذهب (21)', 0):,.0f} ج.م\n• الذهب (24):"
            f" {metals.get('الذهب (24)', 0):,.0f} ج.م\n• الجنيه الذهب:"
            f" {metals.get('الجنيه الذهب', 0):,.0f} ج.م\n• الفضة (999):"
            f" {metals.get('الفضة (999)', 0):,.2f}"
            ' ج.م\n-----------------------------------\n🪙 *تحليل العملات'
            f' الرقمية:*\n{wa_crypto_details}-----------------------------------\n⚙️'
            ' التحديث القادم بعد ساعتين'
        )

        if send_whatsapp_message(wa_msg):
          last_whatsapp_time = current_time

      # --- 3. إرسال البريد الإلكتروني الشامل (كل 3 ساعات) ---
      if (
          current_time - last_email_time >= (EMAIL_INTERVAL_HOURS * 3600)
          or last_email_time == 0
      ):
        arabic_news = fetch_live_arabic_news()
        auto_data = get_dynamic_auto_market(usd_egp)

        news_str = ''
        for region, headlines in arabic_news.items():
          news_str += f'\n{region}:\n'
          for h in headlines:
            news_str += f'  • {h}\n'

        macro_str = '\n'.join([f'• {k}: {v}' for k, v in egypt_macro.items()])
        metals_str = '\n'.join(
            [f'• {k}: {v:,.2f} ج.م' for k, v in metals.items()]
        )

        auto_str = ''
        for cat_name, models in auto_data.items():
          auto_str += f'\n{cat_name}:\n'
          for model_name, price_range in models.items():
            auto_str += f'  • {model_name}: {price_range}\n'

        email_report = f"""📊 التقرير المالي والإقتصادي الرسمي والشامل
⏱ التوقيت: {current_time_str}
المستلم: {RECEIVER_EMAIL}
==================================================

1️⃣ النشرة الاقتصادية العاجلة (باللغة العربية بالكامل):
--------------------------------------------------{news_str}

2️⃣ المؤشرات الاقتصادية الكلية (البنك المركزي + CAPMAS + صندوق النقد الدولي):
--------------------------------------------------
{macro_str}

3️⃣ أسعار العملات الأجنبية المباشرة بالجنيه المصري:
--------------------------------------------------
• USD (دولار أمريكي): {usd_egp:.2f} ج.م
• EUR (يورو): {forex_rates.get('EUR', 0):.2f} ج.م
• GBP (جنيه إسترليني): {forex_rates.get('GBP', 0):.2f} ج.م
• SAR (ريال سعودي): {forex_rates.get('SAR', 0):.2f} ج.م
• AED (درهم إماراتي): {forex_rates.get('AED', 0):.2f} ج.م
• KWD (دينار كويتي): {forex_rates.get('KWD', 0):.2f} ج.م

4️⃣ بورصة الصاغة المصرية والمعادن (الأونصة العالمية: ${gold_oz:,.2f}):
--------------------------------------------------
{metals_str}

5️⃣ مؤشرات وتحليل العملات الرقمية المباشر:
--------------------------------------------------
{crypto_msg_tg}

6️⃣ مؤشر ودليل أسعار السيارات في مصر (محدث ديناميكياً):
--------------------------------------------------{auto_str}

==================================================
⚙️ يُولد هذا التقرير المالي تلقائياً كل 3 ساعات عبر السحابة.
"""
        email_subject = (
            f'📈 التقرير المالي والإقتصادي الشامل - {current_time_str}'
        )

        if send_email_report(email_subject, email_report):
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
