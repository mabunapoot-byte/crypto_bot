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
# 3. خدمات الإرسال (إرسال إيميل HTML بتصميم RTL مميز)
# ---------------------------------------------------------
def send_email_report(subject, html_body):
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
      'sender': {
          'name': 'النشرة المالية وقطاع السيارات',
          'email': SENDER_EMAIL,
      },
      'to': [{'email': RECEIVER_EMAIL}],
      'subject': subject,
      'htmlContent': html_body,
  }

  try:
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    return response.status_code in [200, 201]
  except Exception as e:
    print(f'❌ خطأ في إرسال البريد: {e}', flush=True)
    return False


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
    if res.status_code != 200:
      payload.pop('parse_mode', None)
      res = requests.post(url, json=payload, timeout=10)
    return res.status_code == 200
  except Exception as e:
    print(f'❌ خطأ تيليجرام: {e}', flush=True)
    return False


# ---------------------------------------------------------
# 4. جلب الأخبار الحية بتركيز موسع على صناعة السيارات وقطع الغيار
# ---------------------------------------------------------
def fetch_live_arabic_news():
  news_data = {}

  sources = {
      '🏎️ مصنعي السيارات وشركات قطع الغيار العالمية (Bosch, Valeo, ZF...)': [
          'https://news.google.com/rss/search?q=Bosch+Valeo+ZF+Continental+Denso+قطع+غيار+سيارات&hl=ar&gl=EG&ceid=EG:ar',
          'https://news.google.com/rss/search?q=صناعة+السيارات+تويوتا+تسلا+فولكس+فاغن+BYD&hl=ar&gl=EG&ceid=EG:ar',
          'https://news.google.com/rss/search?q=شركات+قطع+غيار+السيارات+سلاسل+التوريد&hl=ar&gl=EG&ceid=EG:ar',
      ],
      '🌍 مصر والشرق الأوسط': [
          'https://www.mubasher.info/rss/news/egypt',
          'https://www.skynewsarabia.com/rss/v1/economy.xml',
          'https://news.google.com/rss/search?q=اقتصاد+مصر+البنك+المركزي&hl=ar&gl=EG&ceid=EG:ar',
      ],
      '🇺🇸 أمريكا والفيدرالي': [
          'https://sa.investing.com/rss/news_285.rss',
          'https://news.google.com/rss/search?q=الفيدرالي+الأمريكي+الاقتصاد&hl=ar&gl=EG&ceid=EG:ar',
      ],
      '🇪🇺 أوروبا وروسيا': [
          'https://news.google.com/rss/search?q=المركزي+الأوروبي+تضخم&hl=ar&gl=EG&ceid=EG:ar',
          'https://www.skynewsarabia.com/rss/v1/economy.xml',
      ],
      '🪙 أسواق النفط والمعادن والأسواق العالمية': [
          'https://sa.investing.com/rss/news_14.rss',
          'https://news.google.com/rss/search?q=أسعار+النفط+الذهب+الأسواق&hl=ar&gl=EG&ceid=EG:ar',
      ],
  }

  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
          ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      )
  }

  for region, url_list in sources.items():
    headlines = []
    for url in url_list:
      try:
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
          root = ET.fromstring(res.content)
          items = root.findall('.//item/title')[:3]

          for item in items:
            if item.text:
              title_clean = item.text.split(' - ')[0].strip()
              title_clean = re.sub('<[^<]+?>', '', title_clean)
              if (
                  title_clean
                  and len(title_clean) > 10
                  and title_clean not in headlines
              ):
                headlines.append(title_clean)

          if len(headlines) >= 2:
            print(f'✅ تم جلب أخبار {region} بنجاح.', flush=True)
            break
      except Exception as e:
        print(f'⚠️ فشل جلب الأخبار من {url}: {e}', flush=True)
        continue

    news_data[region] = (
        headlines[:3] if headlines else ['متابعة مستمرة لأحدث التحركات الاقتصادية.']
    )

  return news_data


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


# ---------------------------------------------------------
# 5. البيانات المالية والتحليل الفني
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
            'الذهب عيار 24': g24 if g24 > 0 else g21 * (24 / 21),
            'الذهب عيار 21': g21,
            'الذهب عيار 18': g21 * (18 / 21),
            'الجنيه الذهب': g21 * 8,
        }
  except Exception:
    pass

  g24_est = (gold_oz_usd / 31.1035) * usd_egp
  return {
      'الذهب عيار 24': g24_est,
      'الذهب عيار 21': g24_est * (21 / 24),
      'الذهب عيار 18': g24_est * (18 / 24),
      'الجنيه الذهب': (g24_est * (21 / 24)) * 8,
  }


def get_live_forex_and_metals():
  try:
    url = 'https://open.er-api.com/v6/latest/USD'
    res = requests.get(url, timeout=5)
    rates = res.json().get('rates', {})
    usd_egp = rates.get('EGP', 47.4)

    forex = {
        'USD (دولار أمريكي)': usd_egp,
        'EUR (يورو)': (
            (usd_egp / rates.get('EUR', 1.0)) if rates.get('EUR') else 0
        ),
        'GBP (جنيه إسترليني)': (
            (usd_egp / rates.get('GBP', 1.0)) if rates.get('GBP') else 0
        ),
        'SAR (ريال سعودي)': (
            (usd_egp / rates.get('SAR', 3.75)) if rates.get('SAR') else 0
        ),
        'AED (درهم إماراتي)': (
            (usd_egp / rates.get('AED', 3.67)) if rates.get('AED') else 0
        ),
        'KWD (دينار كويتي)': (
            (usd_egp / rates.get('KWD', 0.30)) if rates.get('KWD') else 0
        ),
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
    metals['الفضة عيار 999'] = (silver_oz_usd / 31.1035) * usd_egp
    metals['الفضة عيار 925'] = ((silver_oz_usd / 31.1035) * usd_egp) * 0.925
    metals['البلاتين (أونصة)'] = gold_oz_usd * 0.37 * usd_egp
    metals['البالاديوم (أونصة)'] = gold_oz_usd * 0.39 * usd_egp

    return forex, metals, usd_egp, gold_oz_usd
  except Exception as e:
    print(f'⚠️ خطأ جلب البيانات المالية: {e}', flush=True)
    return {'USD (دولار أمريكي)': 47.4}, {}, 47.4, 2650.0


def get_dynamic_auto_market(usd_egp):
  factor = usd_egp / 47.4
  cars = {
      '🚗 الفئة الاقتصادية': {
          'نيسان صني': f'{int(695000*factor):,} - {int(750000*factor):,} ج.م',
          'شيري أريزو 5': f'{int(650000*factor):,} - {int(710000*factor):,} ج.م',
          'سوزوكي سويفت': f'{int(620000*factor):,} - {int(680000*factor):,} ج.م',
      },
      '🚘 الفئة المتوسطة': {
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
      '🏎️ الفئة الفاخرة والكهرباء': {
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
# 6. بناء قالب البريد الإلكتروني HTML (RTL)
# ---------------------------------------------------------
def generate_html_email_report(
    current_time_str,
    arabic_news,
    egypt_macro,
    forex_rates,
    metals,
    crypto_data_list,
    auto_data,
    usd_egp,
    gold_oz,
):
  # قسم الأخبار ببطاقات مميزة
  news_html = ''
  for region, headlines in arabic_news.items():
    is_auto = 'مصنعي السيارات' in region
    card_bg = '#f0f7ff' if is_auto else '#ffffff'
    border_color = '#0284c7' if is_auto else '#e2e8f0'

    news_html += f"""
        <div style="background-color: {card_bg}; border-right: 4px solid {border_color}; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <h3 style="margin: 0 0 10px 0; color: #1e293b; font-size: 16px;">{region}</h3>
            <ul style="margin: 0; padding-right: 20px; color: #334155; font-size: 14px; line-height: 1.6;">
    """
    for h in headlines:
      news_html += f'<li style="margin-bottom: 6px;">{h}</li>'
    news_html += '</ul></div>'

  # جدول العملات
  forex_rows = ''
  for curr, rate in forex_rates.items():
    forex_rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #f1f5f9; color: #1e293b;">{curr}</td>
            <td style="padding: 10px; border-bottom: 1px solid #f1f5f9; font-weight: bold; color: #0f172a; text-align: left;">{rate:,.2f} ج.م</td>
        </tr>
    """

  # جدول الذهب والمعادن
  metals_rows = ''
  for item, price in metals.items():
    metals_rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #f1f5f9; color: #1e293b;">{item}</td>
            <td style="padding: 10px; border-bottom: 1px solid #f1f5f9; font-weight: bold; color: #b45309; text-align: left;">{price:,.2f} ج.م</td>
        </tr>
    """

  # جدول مؤشرات مصر الكلية
  macro_rows = ''
  for key, val in egypt_macro.items():
    macro_rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #f1f5f9; color: #334155;">{key}</td>
            <td style="padding: 10px; border-bottom: 1px solid #f1f5f9; font-weight: bold; color: #0284c7; text-align: left;">{val}</td>
        </tr>
    """

  # بطاقات العملات الرقمية
  crypto_html = ''
  for c in crypto_data_list:
    badge_bg = '#dcfce7' if c['status_short'] == 'Buy' else '#fee2e2'
    badge_color = '#15803d' if c['status_short'] == 'Buy' else '#b91c1c'
    crypto_html += f"""
        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 10px; background-color: #fafafa;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: bold; color: #0f172a; font-size: 15px;">🪙 {c['name']}</span>
                <span style="background-color: {badge_bg}; color: {badge_color}; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">{c['status_short']}</span>
            </div>
            <div style="margin-top: 8px; font-size: 13px; color: #475569; line-height: 1.5;">
                السعر: <b>${c['price_usd']:,.2f}</b> ({c['price_egp']:,.0f} ج.م) | RSI: <b>{c['rsi']:.1f}</b><br>
                SMA 10: ${c['sma10']:,.2f} | SMA 30: ${c['sma30']:,.2f}
            </div>
        </div>
    """

  # دليل السيارات
  auto_html = ''
  for cat, models in auto_data.items():
    auto_html += f'<h4 style="color: #475569; margin: 12px 0 6px 0;">{cat}</h4><ul style="margin: 0; padding-right: 20px; font-size: 13px; color: #334155;">'
    for m_name, m_price in models.items():
      auto_html += f'<li><b>{m_name}:</b> {m_price}</li>'
    auto_html += '</ul>'

  html_template = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; text-align: right; }}
            .container {{ max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }}
            .header {{ background: linear-gradient(135deg, #0f172a, #1e293b); color: #ffffff; padding: 25px; text-align: center; }}
            .content {{ padding: 25px; }}
            .section-title {{ font-size: 18px; color: #0f172a; border-bottom: 2px solid #0284c7; padding-bottom: 6px; margin-top: 25px; margin-bottom: 15px; font-weight: bold; }}
            .table-styled {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 14px; }}
            .footer {{ background-color: #f8fafc; padding: 15px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin:0; font-size:22px;">📊 التقرير المالي الشامل وقطاع السيارات</h1>
                <p style="margin:8px 0 0 0; font-size:13px; color:#94a3b8;">⏱ التوقيت: {current_time_str}</p>
            </div>
            
            <div class="content">
                <div class="section-title">📰 النشرة الاقتصادية وقطاع السيارات العالمي</div>
                {news_html}

                <div class="section-title">🏛️ المؤشرات الاقتصادية الرسمية (مصر)</div>
                <table class="table-styled">
                    {macro_rows}
                </table>

                <div class="section-title">💵 أسعار العملات المباشرة (مقابل الجنيه)</div>
                <table class="table-styled">
                    {forex_rows}
                </table>

                <div class="section-title">👑 أسعار الصاغة والمعادن (أونصة الذهب: ${gold_oz:,.2f})</div>
                <table class="table-styled">
                    {metals_rows}
                </table>

                <div class="section-title">🪙 التحليل الفني للعملات الرقمية</div>
                {crypto_html}

                <div class="section-title">🚗 دليل أسعار السيارات في مصر (محدث ديناميكياً)</div>
                {auto_html}
            </div>

            <div class="footer">
                ⚙️ يُولد هذا التقرير المالي تلقائياً كل 3 ساعات عبر السحابة.
            </div>
        </div>
    </body>
    </html>
    """
  return html_template


# ---------------------------------------------------------
# 7. الحلقة الرئيسية والجدولة
# ---------------------------------------------------------
def main_loop():
  print('🤖 بدأ تشغيل البوت المحدث بتنسيق HTML RTL...', flush=True)

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
      arabic_news = fetch_live_arabic_news()
      current_time_str = time.strftime('%Y-%m-%d %H:%M UTC')

      # صياغة نص الأخبار لتيليجرام وواتساب
      news_summary_str = ''
      for region, headlines in arabic_news.items():
        news_summary_str += f'\n{region}:\n'
        for h in headlines:
          news_summary_str += f'  • {h}\n'

      # جمع بيانات التحليل الفني
      crypto_data_list = []
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

          crypto_data_list.append({
              'name': name,
              'price_usd': price_usd,
              'price_egp': price_egp,
              'rsi': rsi,
              'sma10': sma10,
              'sma30': sma30,
              'status_short': status_short,
          })

          crypto_msg_tg += (
              f'🪙 {name}\n'
              f'• السعر: ${price_usd:,.2f} ({price_egp:,.0f} ج.م)\n'
              f'📈 المؤشرات: RSI:{rsi:.1f} | SMA10:${sma10:,.0f}\n'
              f'🚦 القرار: {status_short}\n'
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

        full_tg_report = f"""📊 تقرير السوق الشامل والنشرة الإخبارية الحية
⏱ التوقيت: {current_time_str}
===================================
📰 أهم الأخبار الاقتصادية وقطع غيار السيارات:
{news_summary_str}
===================================
{forex_msg_tg}===================================
{crypto_msg_tg}⚙️ إرسال تلقائي عبر السحابة"""

        if send_telegram_message(full_tg_report):
          print('✅ تم إرسال تقرير تيليجرام بنجاح.', flush=True)
          last_telegram_time = current_time

      # --- 2. إرسال الواتساب (كل ساعتين) ---
      if (
          current_time - last_whatsapp_time >= (WHATSAPP_INTERVAL_HOURS * 3600)
          or last_whatsapp_time == 0
      ):
        wa_msg = f"""📊 *تقرير السوق والأخبار العاجلة*
⏱ {current_time_str}
-----------------------------------
📰 *أبرز العناوين وقطاع السيارات:*
{news_summary_str}
-----------------------------------
💵 *الدولار:* {usd_egp:.2f} ج.م | *الذهب عيار 21:* {metals.get('الذهب عيار 21', 0):,.0f} ج.م
-----------------------------------
🪙 *العملات الرقمية:*
{wa_crypto_details}-----------------------------------
⚙️ التحديث القادم بعد ساعتين"""

        if send_whatsapp_message(wa_msg):
          print('✅ تم إرسال تقرير الواتساب بنجاح.', flush=True)
          last_whatsapp_time = current_time

      # --- 3. إرسال البريد الإلكتروني الشامل بتنسيق HTML (كل 3 ساعات) ---
      if (
          current_time - last_email_time >= (EMAIL_INTERVAL_HOURS * 3600)
          or last_email_time == 0
      ):
        auto_data = get_dynamic_auto_market(usd_egp)

        html_email_content = generate_html_email_report(
            current_time_str,
            arabic_news,
            egypt_macro,
            forex_rates,
            metals,
            crypto_data_list,
            auto_data,
            usd_egp,
            gold_oz,
        )

        email_subject = (
            f'📈 التقرير المالي وقطاع السيارات الشامل - {current_time_str}'
        )

        if send_email_report(email_subject, html_email_content):
          print(
              '✅ تم إرسال البريد الإلكتروني Mapped HTML بنجاح.', flush=True
          )
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
