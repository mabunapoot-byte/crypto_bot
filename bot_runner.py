import base64
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
  return '🤖 InfoPulse - Realtime Economic Developments Bot is running!'


def run_web_server():
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)


# ---------------------------------------------------------
# 2. الثوابت ومتغيرات البيئة وهوية InfoPulse
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

# يمكن وضع رابط الصورة المباشر أو خزنها هنا (رابط الصورة أو Data Base64)
INFOPULSE_LOGO_URL = os.environ.get(
    'INFOPULSE_LOGO_URL',
    'https://raw.githubusercontent.com/mabunapoot/assets/main/infopulse_logo.png',
)

CHECK_INTERVAL_MINUTES = 5
WHATSAPP_INTERVAL_HOURS = 2
EMAIL_INTERVAL_HOURS = 3
TELEGRAM_INTERVAL_HOURS = 6


# ---------------------------------------------------------
# 3. خدمات الإرسال (إرسال إيميل HTML بتصميم RTL تفاعلي)
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
      'sender': {'name': 'InfoPulse | إنفوبلس', 'email': SENDER_EMAIL},
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
# 4. جلب الأخبار الاقتصادية وأخبار السيارات مع المصادر
# ---------------------------------------------------------
def fetch_news_with_links(sources_dict):
  news_data = {}
  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
          ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      )
  }

  for category, url_list in sources_dict.items():
    items_list = []
    for url in url_list:
      try:
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
          root = ET.fromstring(res.content)
          raw_items = root.findall('.//item')[:3]

          for item in raw_items:
            title_node = item.find('title')
            link_node = item.find('link')

            if title_node is not None and title_node.text:
              title_clean = title_node.text.split(' - ')[0].strip()
              title_clean = re.sub('<[^<]+?>', '', title_clean)
              link_url = link_node.text.strip() if link_node is not None and link_node.text else '#'

              if title_clean and len(title_clean) > 10:
                if not any(i['title'] == title_clean for i in items_list):
                  items_list.append({'title': title_clean, 'link': link_url})

          if len(items_list) >= 2:
            break
      except Exception as e:
        print(f'⚠️ خطأ جلب {category} من {url}: {e}', flush=True)
        continue

    news_data[category] = (
        items_list[:3]
        if items_list
        else [{'title': 'متابعة حية للتحركات اليومية.', 'link': '#'}]
    )

  return news_data


def fetch_all_live_news():
  # 1. أهم الأخبار الاقتصادية العامة
  econ_sources = {
      '🌍 مصر والشرق الأوسط': [
          'https://www.mubasher.info/rss/news/egypt',
          'https://www.skynewsarabia.com/rss/v1/economy.xml',
          'https://news.google.com/rss/search?q=اقتصاد+مصر+البنك+المركزي&hl=ar&gl=EG&ceid=EG:ar',
      ],
      '🇺🇸 الاقتصاد العالمي والفيدرالي': [
          'https://sa.investing.com/rss/news_285.rss',
          'https://news.google.com/rss/search?q=الفيدرالي+الأمريكي+الاقتصاد&hl=ar&gl=EG&ceid=EG:ar',
      ],
      '🇪🇺 الأسواق الأوروبية والإقليمية': [
          'https://news.google.com/rss/search?q=المركزي+الأوروبي+تضخم&hl=ar&gl=EG&ceid=EG:ar',
          'https://www.skynewsarabia.com/rss/v1/economy.xml',
      ],
  }

  # 2. أخبار صناعة السيارات وشركات قطع الغيار العالمية
  auto_sources = {
      '🏎️ مصنعي السيارات وشركات قطع الغيار العالمية (Bosch, Valeo, ZF...)': [
          'https://news.google.com/rss/search?q=Bosch+Valeo+ZF+Continental+Denso+قطع+غيار+سيارات&hl=ar&gl=EG&ceid=EG:ar',
          'https://news.google.com/rss/search?q=صناعة+السيارات+تويوتا+تسلا+فولكس+فاغن+BYD&hl=ar&gl=EG&ceid=EG:ar',
          'https://news.google.com/rss/search?q=شركات+قطع+غيار+السيارات+سلاسل+التوريد&hl=ar&gl=EG&ceid=EG:ar',
      ]
  }

  economic_news = fetch_news_with_links(econ_sources)
  auto_industry_news = fetch_news_with_links(auto_sources)

  return economic_news, auto_industry_news


# ---------------------------------------------------------
# 5. جلب أسعار العملات والمعادن والسوق المحلي المصري
# ---------------------------------------------------------
def fetch_egypt_local_gold_base_price(usd_egp, gold_oz_usd):
  headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

  try:
    url = 'https://api.gold-era.com/api/prices/gold'
    res = requests.get(url, headers=headers, timeout=5)
    if res.status_code == 200:
      data = res.json()
      g21 = float(data.get('gram21', 0))
      if g21 > 2000:
        return g21
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
          return g21
  except Exception:
    pass

  g24_est = (gold_oz_usd / 31.1035) * usd_egp
  return g24_est * (21 / 24)


def get_live_forex_and_commodities():
  try:
    url = 'https://open.er-api.com/v6/latest/USD'
    res = requests.get(url, timeout=5)
    rates = res.json().get('rates', {})
    usd_egp = rates.get('EGP', 47.4)

    # 3. أسعار العملات (شاملة اليوان الصيني)
    forex = {
        'USD (دولار أمريكي)': usd_egp,
        'EUR (يورو أوروبي)': (
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
        'CNY (يوان صيني)': (
            (usd_egp / rates.get('CNY', 7.23)) if rates.get('CNY') else 0
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

    # 4. أسعار الذهب في مصر (السوق المحلي) لجميع العيارات والفضة
    g21_local = fetch_egypt_local_gold_base_price(usd_egp, gold_oz_usd)
    g24_local = g21_local * (24 / 21)
    silver_999_local = (silver_oz_usd / 31.1035) * usd_egp

    commodities = {
        'الذهب عيار 24 (جرام)': g24_local,
        'الذهب عيار 22 (جرام)': g24_local * (22 / 24),
        'الذهب عيار 21 (جرام)': g21_local,
        'الذهب عيار 18 (جرام)': g24_local * (18 / 24),
        'الذهب عيار 14 (جرام)': g24_local * (14 / 24),
        'الذهب عيار 12 (جرام)': g24_local * (12 / 24),
        'الجنيه الذهب (8 جرام عيار 21)': g21_local * 8,
        'أونصة الذهب محلياً (31.1 جرام عيار 24)': g24_local * 31.1035,
        'الفضة عيار 999 (سبيكة/جرام)': silver_999_local,
        'الفضة عيار 925 (استرليني/جرام)': silver_999_local * 0.925,
        'الفضة عيار 900 (جرام)': silver_999_local * 0.900,
        'الفضة عيار 800 (مجوهرات/جرام)': silver_999_local * 0.800,
        'النفط خام برنت (برميل)': 78.5 * usd_egp,
        'القمح العالمي (طن)': 245.0 * usd_egp,
        'الذرة العالمية (طن)': 175.0 * usd_egp,
        'النحاس الصناعي (طن)': 9500.0 * usd_egp,
    }

    forex_ta_summary = (
        '🟢 التحليل الفني للعملات: استقرار واستقرار نسبي للدولار واليوان'
        ' الصيني مع توازنات في العرض والطلب بالجهاز المصرفي.'
    )
    commodities_ta_summary = (
        '🟡 التحليل الفني للذهب والمعادن: اتجاه عرضي مائل للصعود في الصاغة'
        ' المصرية متأثراً بأسعار الأونصة العالمية وتوازن الطلب المحلي.'
    )

    return (
        forex,
        commodities,
        usd_egp,
        gold_oz_usd,
        forex_ta_summary,
        commodities_ta_summary,
    )
  except Exception as e:
    print(f'⚠️ خطأ جلب البيانات المالية: {e}', flush=True)
    return {'USD (دولار أمريكي)': 47.4}, {}, 47.4, 2650.0, '', ''


# ---------------------------------------------------------
# 6. دليل أسعار السيارات (ماركات أوروبية وآسيوية فقط)
# ---------------------------------------------------------
def get_european_asian_auto_market(usd_egp):
  factor = usd_egp / 47.4
  cars = {
      '🇪🇺 الماركات الأوروبية (European Brands)': {
          'مرسيدس C200 (ألماني)': (
              f'{int(3400000*factor):,} - {int(3800000*factor):,} ج.م'
          ),
          'بي إم دبليو 320i (ألماني)': (
              f'{int(3200000*factor):,} - {int(3600000*factor):,} ج.م'
          ),
          'فولكس فاجن ID.4 (كهرباء ألماني)': (
              f'{int(1650000*factor):,} - {int(1850000*factor):,} ج.م'
          ),
          'بيجو 408 (فرنسي)': (
              f'{int(1950000*factor):,} - {int(2150000*factor):,} ج.م'
          ),
          'سكودا أوكتافيا (تشيكي)': (
              f'{int(1800000*factor):,} - {int(1980000*factor):,} ج.م'
          ),
          'رينو ميجان (فرنسي)': (
              f'{int(1250000*factor):,} - {int(1420000*factor):,} ج.م'
          ),
      },
      '🌏 الماركات الآسيوية (Asian Brands)': {
          'تويوتا كورولا (ياباني)': (
              f'{int(1300000*factor):,} - {int(1450000*factor):,} ج.م'
          ),
          'نيسان صني (ياباني)': (
              f'{int(695000*factor):,} - {int(750000*factor):,} ج.م'
          ),
          'هيونداي إلترا AD (كوري)': (
              f'{int(890000*factor):,} - {int(980000*factor):,} ج.م'
          ),
          'كيا سبورتاج (كوري)': (
              f'{int(1780000*factor):,} - {int(1950000*factor):,} ج.م'
          ),
          'شيري أريزو 5 (صيني)': (
              f'{int(650000*factor):,} - {int(710000*factor):,} ج.م'
          ),
          'إم جي ZS (صيني)': (
              f'{int(975000*factor):,} - {int(1050000*factor):,} ج.م'
          ),
          'BYD Song Plus (كهرباء صيني)': (
              f'{int(1550000*factor):,} - {int(1720000*factor):,} ج.م'
          ),
      },
  }
  return cars


# ---------------------------------------------------------
# 7. المؤشرات الاقتصادية الكلية الرسمية (مصر)
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
# 8. توليد البريد الإلكتروني HTML التفاعلي لماركة InfoPulse (RTL)
# ---------------------------------------------------------
def generate_infopulse_html_email(
    current_time_str,
    economic_news,
    auto_industry_news,
    forex_rates,
    forex_ta,
    commodities,
    commodities_ta,
    crypto_data_list,
    auto_market_data,
    egypt_macro,
):

  # 1. أهم الأخبار الاقتصادية العامة
  econ_news_html = ''
  for region, items in economic_news.items():
    econ_news_html += f"""
        <div style="background-color: #ffffff; border-right: 4px solid #10b981; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.04);">
            <h4 style="margin: 0 0 10px 0; color: #0b192c; font-size: 15px; display: flex; align-items: center; gap: 6px;">
                <span style="color: #10b981;">⚡</span> {region}
            </h4>
            <ul style="margin: 0; padding-right: 18px; color: #334155; font-size: 13px; line-height: 1.6;">
    """
    for item in items:
      econ_news_html += f"""
                <li style="margin-bottom: 10px;">
                    <div style="font-weight: 600; color: #1e293b;">{item['title']}</div>
                    <div style="margin-top: 3px;">
                        <a href="{item['link']}" target="_blank" style="display: inline-block; font-size: 11px; color: #0284c7; background-color: #e0f2fe; padding: 2px 10px; border-radius: 12px; text-decoration: none; font-weight: 500;">🔗 رابط المصدر</a>
                    </div>
                </li>
      """
    econ_news_html += '</ul></div>'

  # 2. أخبار صناعة السيارات وشركات قطع الغيار العالمية
  auto_news_html = ''
  for region, items in auto_industry_news.items():
    auto_news_html += f"""
        <div style="background-color: #f0fdf4; border-right: 4px solid #059669; border-radius: 10px; padding: 14px 16px; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.04);">
            <h4 style="margin: 0 0 10px 0; color: #065f46; font-size: 15px; display: flex; align-items: center; gap: 6px;">
                <span>⚙️</span> {region}
            </h4>
            <ul style="margin: 0; padding-right: 18px; color: #1e293b; font-size: 13px; line-height: 1.6;">
    """
    for item in items:
      auto_news_html += f"""
                <li style="margin-bottom: 10px;">
                    <div style="font-weight: 600; color: #0f172a;">{item['title']}</div>
                    <div style="margin-top: 3px;">
                        <a href="{item['link']}" target="_blank" style="display: inline-block; font-size: 11px; color: #059669; background-color: #d1fae5; padding: 2px 10px; border-radius: 12px; text-decoration: none; font-weight: 500;">🔗 رابط المصدر</a>
                    </div>
                </li>
      """
    auto_news_html += '</ul></div>'

  # 3. أسعار العملات
  forex_rows = ''
  for curr, rate in forex_rates.items():
    forex_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 10px 12px; color: #1e293b; font-weight: 500;">{curr}</td>
            <td style="padding: 10px 12px; font-weight: 700; color: #0b192c; text-align: left;">{rate:,.2f} ج.م</td>
        </tr>
    """

  # 4. أسعار الذهب والمعادن في مصر (السوق المحلي)
  commodities_rows = ''
  for item, price in commodities.items():
    commodities_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 10px 12px; color: #1e293b; font-weight: 500;">{item}</td>
            <td style="padding: 10px 12px; font-weight: 700; color: #d97706; text-align: left;">{price:,.2f} ج.م</td>
        </tr>
    """

  # 5. التحليل الفني للعملات الرقمية
  crypto_html = ''
  for c in crypto_data_list:
    badge_bg = '#dcfce7' if c['status_short'] == 'Buy' else '#fee2e2'
    badge_color = '#15803d' if c['status_short'] == 'Buy' else '#b91c1c'
    crypto_html += f"""
        <div style="border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; background-color: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="display: flex; justify-content: space-between; align-items: center; direction: rtl;">
                <span style="font-weight: 700; color: #0b192c; font-size: 14px;">🪙 {c['name']}</span>
                <span style="background-color: {badge_bg}; color: {badge_color}; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 700;">{c['status_short']}</span>
            </div>
            <div style="margin-top: 8px; font-size: 12px; color: #475569; line-height: 1.5; direction: rtl; text-align: right;">
                السعر: <b style="color:#0b192c;">${c['price_usd']:,.2f}</b> ({c['price_egp']:,.0f} ج.م) &bull; RSI: <b>{c['rsi']:.1f}</b> &bull; SMA10: <b>${c['sma10']:,.0f}</b>
            </div>
        </div>
    """

  # 6. دليل أسعار السيارات في مصر (ماركات أوروبية وآسيوية فقط)
  auto_market_html = ''
  for brand_cat, models in auto_market_data.items():
    auto_market_html += f'<h4 style="color: #0b192c; margin: 12px 0 6px 0; font-size: 14px;">{brand_cat}</h4><ul style="margin: 0; padding-right: 18px; font-size: 13px; color: #334155; line-height: 1.7;">'
    for m_name, m_price in models.items():
      auto_market_html += (
          f'<li style="margin-bottom: 4px;"><b>{m_name}:</b> {m_price}</li>'
      )
    auto_market_html += '</ul>'

  # 7. المؤشرات الاقتصادية الرسمية (مصر)
  macro_rows = ''
  for k, v in egypt_macro.items():
    macro_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 9px 12px; color: #334155;">{k}</td>
            <td style="padding: 9px 12px; font-weight: 700; color: #0284c7; text-align: left;">{v}</td>
        </tr>
    """

  html_template = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px 10px; text-align: right; direction: rtl; }}
            .container {{ max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 14px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; direction: rtl; }}
            .header {{ background: linear-gradient(135deg, #0b192c 0%, #1e293b 100%); color: #ffffff; padding: 28px 20px; text-align: center; border-bottom: 4px solid #10b981; }}
            .logo-container {{ margin-bottom: 12px; text-align: center; }}
            .logo-img {{ max-width: 220px; height: auto; filter: drop-shadow(0px 2px 8px rgba(0,0,0,0.3)); }}
            .content {{ padding: 25px 20px; text-align: right; direction: rtl; }}
            .section-title {{ font-size: 16px; color: #0b192c; border-bottom: 2px solid #10b981; padding-bottom: 6px; margin-top: 24px; margin-bottom: 14px; font-weight: 700; text-align: right; }}
            .table-styled {{ width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 13px; text-align: right; direction: rtl; }}
            .ta-box {{ background-color: #ecfdf5; border-right: 4px solid #10b981; padding: 10px 14px; font-size: 12px; color: #047857; margin-bottom: 14px; border-radius: 6px; font-weight: 500; line-height: 1.5; }}
            .footer {{ background-color: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; line-height: 1.5; }}
        </style>
    </head>
    <body dir="rtl">
        <div class="container" dir="rtl">
            <div class="header">
                <div class="logo-container">
                    <img src="{INFOPULSE_LOGO_URL}" alt="InfoPulse - إنفوبلس" class="logo-img" onerror="this.style.display='none'; document.getElementById('text-logo').style.display='block';">
                    <div id="text-logo" style="display:none; font-size:26px; font-weight:bold; color:#ffffff; letter-spacing:1px;">
                        <span style="color:#ffffff;">Info</span><span style="color:#10b981;">Pulse</span>
                        <div style="font-size:18px; color:#94a3b8; margin-top:2px;">إنفوبلس</div>
                    </div>
                </div>
                <h2 style="margin:10px 0 0 0; font-size:20px; color:#ffffff; font-weight:700;">التطورات الاقتصادية من إنفوبلس</h2>
                <p style="margin:6px 0 0 0; font-size:12px; color:#a7f3d0; font-weight:500;">⏱ التوقيت: {current_time_str}</p>
            </div>
            
            <div class="content" dir="rtl">
                <!-- 1. أهم الأخبار الاقتصادية العامة -->
                <div class="section-title">1️⃣ أهم الأخبار الاقتصادية العامة</div>
                {econ_news_html}

                <!-- 2. أخبار صناعة السيارات وشركات قطع الغيار العالمية -->
                <div class="section-title">2️⃣ أخبار صناعة السيارات وشركات قطع الغيار العالمية</div>
                {auto_news_html}

                <!-- 3. أسعار العملات -->
                <div class="section-title">3️⃣ أسعار العملات</div>
                <div class="ta-box">{forex_ta}</div>
                <table class="table-styled" dir="rtl">
                    {forex_rows}
                </table>

                <!-- 4. أسعار الذهب في مصر (السوق المحلي والمعادن) -->
                <div class="section-title">4️⃣ أسعار الذهب في مصر (السوق المحلي والمعادن)</div>
                <div class="ta-box">{commodities_ta}</div>
                <table class="table-styled" dir="rtl">
                    {commodities_rows}
                </table>

                <!-- 5. التحليل الفني للعملات الرقمية -->
                <div class="section-title">5️⃣ التحليل الفني للعملات الرقمية</div>
                {crypto_html}

                <!-- 6. دليل أسعار السيارات في مصر -->
                <div class="section-title">6️⃣ دليل أسعار السيارات في مصر (ماركات أوروبية وآسيوية فقط)</div>
                {auto_market_html}

                <!-- 7. المؤشرات الاقتصادية الرسمية (مصر) -->
                <div class="section-title">7️⃣ المؤشرات الاقتصادية الرسمية (مصر)</div>
                <table class="table-styled" dir="rtl">
                    {macro_rows}
                </table>
            </div>

            <div class="footer">
                ⚙️ يُولد هذا التقرير المالي تلقائياً عبر السحابة بواسطة <b>InfoPulse | إنفوبلس</b><br>
                جميع الأسعار مقومة بالجنيه المصري (ج.م).
            </div>
        </div>
    </body>
    </html>
    """
  return html_template


# ---------------------------------------------------------
# 9. الحلقة الرئيسية والجدولة
# ---------------------------------------------------------
def main_loop():
  print(
      '🤖 بدأ تشغيل بوت InfoPulse (إنفوبلس) مع التنسيق التفاعلي RTL...',
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
      (
          forex_rates,
          commodities,
          usd_egp,
          gold_oz,
          forex_ta,
          commodities_ta,
      ) = get_live_forex_and_commodities()
      economic_news, auto_industry_news = fetch_all_live_news()
      auto_market_data = get_european_asian_auto_market(usd_egp)
      egypt_macro = get_egypt_macro_indicators()
      current_time_str = time.strftime('%Y-%m-%d %H:%M UTC')

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
          elif rsi >= 70:
            status_short = 'Overbought'
          elif rsi <= 30:
            status_short = 'Oversold'
          elif sma10 < sma30:
            status_short = 'Sell'
          else:
            status_short = 'Hold'

          crypto_data_list.append({
              'name': name,
              'price_usd': price_usd,
              'price_egp': price_egp,
              'rsi': rsi,
              'sma10': sma10,
              'sma30': sma30,
              'status_short': status_short,
          })

          crypto_msg_tg += f'🪙 {name}: ${price_usd:,.2f} ({price_egp:,.0f} ج.م) | RSI:{rsi:.1f} ({status_short})\n'
          short_name = name.split(' ')[0]
          wa_crypto_details += f'• {short_name}: ${price_usd:,.2f} | RSI:{rsi:.1f} ({status_short})\n'

        time.sleep(0.2)

      news_tg_summary = '1️⃣ أهم الأخبار الاقتصادية العامة:\n'
      for r, items in economic_news.items():
        for i in items[:2]:
          news_tg_summary += f'• {i["title"]}\n  🔗 {i["link"]}\n'

      auto_tg_summary = '\n2️⃣ أخبار صناعة السيارات وقطع الغيار:\n'
      for r, items in auto_industry_news.items():
        for i in items[:2]:
          auto_tg_summary += f'• {i["title"]}\n  🔗 {i["link"]}\n'

      # --- 1. إرسال تيليجرام (كل 6 ساعات) ---
      if (
          current_time - last_telegram_time >= (TELEGRAM_INTERVAL_HOURS * 3600)
          or last_telegram_time == 0
      ):
        tg_report = f"""📊 التطورات الاقتصادية من إنفوبلس
⏱ التوقيت: {current_time_str}
===================================
{news_tg_summary}{auto_tg_summary}
3️⃣ أسعار العملات:
• USD: {usd_egp:.2f} ج.م | EUR: {forex_rates.get('EUR (يورو أوروبي)', 0):.2f} ج.م
• CNY (اليوان الصيني): {forex_rates.get('CNY (يوان صيني)', 0):.2f} ج.م

4️⃣ أسعار الذهب في مصر:
• عيار 21: {commodities.get('الذهب عيار 21 (جرام)', 0):,.0f} ج.م
• الجنيه الذهب: {commodities.get('الجنيه الذهب (8 جرام عيار 21)', 0):,.0f} ج.م

5️⃣ العملات الرقمية:
{wa_crypto_details}
⚙️ InfoPulse Automated Engine"""

        if send_telegram_message(tg_report):
          print('✅ تم إرسال تقرير تيليجرام بنجاح.', flush=True)
          last_telegram_time = current_time

      # --- 2. إرسال الواتساب (كل ساعتين) ---
      if (
          current_time - last_whatsapp_time >= (WHATSAPP_INTERVAL_HOURS * 3600)
          or last_whatsapp_time == 0
      ):
        wa_msg = f"""📊 *التطورات الاقتصادية من إنفوبلس*
⏱ {current_time_str}
-----------------------------------
📰 *أبرز عناوين الأخبار والسيارات:*
• USD: {usd_egp:.2f} ج.م | CNY: {forex_rates.get('CNY (يوان صيني)', 0):.2f} ج.م
• الذهب عيار 21: {commodities.get('الذهب عيار 21 (جرام)', 0):,.0f} ج.م
-----------------------------------
🪙 *العملات الرقمية:*
{wa_crypto_details}-----------------------------------
⚙️ التحديث القادم بعد ساعتين"""

        if send_whatsapp_message(wa_msg):
          print('✅ تم إرسال تقرير الواتساب بنجاح.', flush=True)
          last_whatsapp_time = current_time

      # --- 3. إرسال البريد الإلكتروني المنسق الشامل (كل 3 ساعات) ---
      if (
          current_time - last_email_time >= (EMAIL_INTERVAL_HOURS * 3600)
          or last_email_time == 0
      ):
        email_html = generate_infopulse_html_email(
            current_time_str,
            economic_news,
            auto_industry_news,
            forex_rates,
            forex_ta,
            commodities,
            commodities_ta,
            crypto_data_list,
            auto_market_data,
            egypt_macro,
        )

        subject = f'التطورات الاقتصادية من إنفوبلس - {current_time_str}'

        if send_email_report(subject, email_html):
          print('✅ تم إرسال بريد إنفوبلس بنجاح.', flush=True)
          last_email_time = current_time

    except Exception as e:
      print(f'❌ خطأ في الحلقة الرئيسية: {e}', flush=True)

    time.sleep(CHECK_INTERVAL_MINUTES * 60)


# ---------------------------------------------------------
# 10. نقطة الانطلاق
# ---------------------------------------------------------
if __name__ == '__main__':
  web_thread = Thread(target=run_web_server)
  web_thread.daemon = True
  web_thread.start()

  main_loop()
