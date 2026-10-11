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
  return (
      '🤖 InfoPulse - Complete Combined Economic Bot (Egypt & Oman) is running!'
  )


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
# 3. خدمات الإرسال
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
# 4. جلب الأخبار الاقتصادية العامة والسيارات
# ---------------------------------------------------------
def fetch_all_merged_news():
  sources = [
      'https://www.mubasher.info/rss/news/egypt',
      'https://news.google.com/rss/search?q=اقتصاد+سلطنة+عمان+البنك+المركزي&hl=ar&gl=OM&ceid=OM:ar',
      'https://www.skynewsarabia.com/rss/v1/economy.xml',
      'https://news.google.com/rss/search?q=Bosch+Valeo+ZF+Continental+Denso+قطع+غيار+سيارات&hl=ar&gl=EG&ceid=EG:ar',
      'https://news.google.com/rss/search?q=صناعة+السيارات+تويوتا+تسلا+فولكس+فاغن+BYD&hl=ar&gl=EG&ceid=EG:ar',
      'https://sa.investing.com/rss/news_285.rss',
  ]

  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      )
  }
  merged_items = []

  for url in sources:
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
              if not any(i['title'] == title_clean for i in merged_items):
                merged_items.append({'title': title_clean, 'link': link_url})

        if len(merged_items) >= 8:
          break
    except Exception as e:
      print(f'⚠️ خطأ جلب الأخبار من {url}: {e}', flush=True)
      continue

  return (
      merged_items[:8]
      if merged_items
      else [{'title': 'متابعة حية لأحدث التطورات الاقتصادية.', 'link': '#'}]
  )


# ---------------------------------------------------------
# 5. البيانات المالية الشاملة (العملات + الذهب بالسوق المحلي العماني والمصري)
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


def get_live_forex_and_commodities_full():
  try:
    url = 'https://open.er-api.com/v6/latest/USD'
    res = requests.get(url, timeout=5)
    rates = res.json().get('rates', {})

    usd_egp = rates.get('EGP', 47.4)
    usd_omr = rates.get('OMR', 0.3845)

    egp_per_omr = usd_egp / usd_omr  # سعر الريال العماني بالجنيه المصري
    omr_per_egp = usd_omr / usd_egp  # سعر الجنيه المصري بالريال العماني

    # 1. أسعار العملات الشاملة (تتضمن EGP و OMR)
    forex_egp = {
        'USD (دولار أمريكي)': usd_egp,
        'OMR (ريال عماني)': egp_per_omr,
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
        'EGP (جنيه مصري)': 1.00,
    }

    forex_omr = {
        'USD (دولار أمريكي)': usd_omr,
        'OMR (ريال عماني)': 1.0000,
        'EUR (يورو أوروبي)': (
            (usd_omr / rates.get('EUR', 1.0)) if rates.get('EUR') else 0.415
        ),
        'GBP (جنيه إسترليني)': (
            (usd_omr / rates.get('GBP', 1.0)) if rates.get('GBP') else 0.490
        ),
        'SAR (ريال سعودي)': (
            (usd_omr / rates.get('SAR', 3.75)) if rates.get('SAR') else 0.1025
        ),
        'AED (درهم إماراتي)': (
            (usd_omr / rates.get('AED', 3.67)) if rates.get('AED') else 0.1047
        ),
        'KWD (دينار كويتي)': (
            (usd_omr / rates.get('KWD', 0.30)) if rates.get('KWD') else 1.255
        ),
        'CNY (يوان صيني)': (
            (usd_omr / rates.get('CNY', 7.23)) if rates.get('CNY') else 0.0532
        ),
        'EGP (جنيه مصري)': omr_per_egp,
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

    # 2. أسعار الذهب والسلع بمصر (سوق محلي)
    g21_egp = fetch_egypt_local_gold_base_price(usd_egp, gold_oz_usd)
    g24_egp = g21_egp * (24 / 21)
    silver_999_egp = (silver_oz_usd / 31.1035) * usd_egp

    commodities_egp = {
        'الذهب عيار 24 (جرام)': g24_egp,
        'الذهب عيار 22 (جرام)': g24_egp * (22 / 24),
        'الذهب عيار 21 (جرام)': g21_egp,
        'الذهب عيار 18 (جرام)': g24_egp * (18 / 24),
        'الذهب عيار 14 (جرام)': g24_egp * (14 / 24),
        'الذهب عيار 12 (جرام)': g24_egp * (12 / 24),
        'الجنيه الذهب (8 جرام عيار 21)': g21_egp * 8,
        'أونصة الذهب محلياً (31.1 جرام عيار 24)': g24_egp * 31.1035,
        'الفضة عيار 999 (سبيكة/جرام)': silver_999_egp,
        'الفضة عيار 925 (استرليني/جرام)': silver_999_egp * 0.925,
        'الفضة عيار 900 (جرام)': silver_999_egp * 0.900,
        'الفضة عيار 800 (مجوهرات/جرام)': silver_999_egp * 0.800,
        'النفط خام برنت (برميل)': 78.5 * usd_egp,
        'القمح العالمي (طن)': 245.0 * usd_egp,
        'الذرة العالمية (طن)': 175.0 * usd_egp,
        'النحاس الصناعي (طن)': 9500.0 * usd_egp,
    }

    # 3. أسعار الذهب والسلع بالسلطنة (سوق محلي عماني)
    g24_omr = (gold_oz_usd / 31.1035) * usd_omr
    g22_omr = g24_omr * (22 / 24)  # متداول بكثرة بالسوق العماني
    g21_omr = g24_omr * (21 / 24)
    silver_999_omr = (silver_oz_usd / 31.1035) * usd_omr

    commodities_omr = {
        'الذهب عيار 24 (جرام)': g24_omr,
        'الذهب عيار 22 (جرام)': g22_omr,
        'الذهب عيار 21 (جرام)': g21_omr,
        'الذهب عيار 18 (جرام)': g24_omr * (18 / 24),
        'الذهب عيار 14 (جرام)': g24_omr * (14 / 24),
        'الذهب عيار 12 (جرام)': g24_omr * (12 / 24),
        'الريال الذهب (8 جرام عيار 22 عماني)': g22_omr * 8,
        'أونصة الذهب عمانياً (31.1 جرام عيار 24)': g24_omr * 31.1035,
        'الفضة عيار 999 (سبيكة/جرام)': silver_999_omr,
        'الفضة عيار 925 (استرليني/جرام)': silver_999_omr * 0.925,
        'الفضة عيار 900 (جرام)': silver_999_omr * 0.900,
        'الفضة عيار 800 (مجوهرات/جرام)': silver_999_omr * 0.800,
        'النفط خام عمان (برميل)': 79.2 * usd_omr,
        'النفط خام برنت (برميل)': 78.5 * usd_omr,
        'القمح العالمي (طن)': 245.0 * usd_omr,
        'الذرة العالمية (طن)': 175.0 * usd_omr,
        'النحاس الصناعي (طن)': 9500.0 * usd_omr,
    }

    ta_summary = (
        '🟢 التحليل الفني الشامل: استقرار وتوازنات نقدية متينة في الجهاز'
        ' المصرفي بمصر وعمان مع حركة عرضية متوازنة لأسواق الذهب محلياً تزامناً'
        ' مع أداء الأونصة عالمياً.'
    )

    return (
        forex_egp,
        forex_omr,
        commodities_egp,
        commodities_omr,
        usd_egp,
        usd_omr,
        gold_oz_usd,
        ta_summary,
    )
  except Exception as e:
    print(f'⚠️ خطأ جلب البيانات المالية الشاملة: {e}', flush=True)
    return {}, {}, {}, {}, 47.4, 0.3845, 2650.0, ''


# ---------------------------------------------------------
# 6. لوجوهات الشركات الصانعة وتوليد جدول متوسط أسعار السيارات
# ---------------------------------------------------------
CAR_LOGOS_SVG = {
    'Mercedes': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><circle cx="12"'
        ' cy="12" r="10" stroke="#0b192c" stroke-width="1.8"/><path d="M12'
        ' 2v10m0 0l-7.5 4.5M12 12l7.5 4.5" stroke="#0b192c" stroke-width="1.8"'
        ' stroke-linecap="round"/></svg>'
    ),
    'BMW': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><circle cx="12"'
        ' cy="12" r="10" stroke="#0b192c" stroke-width="1.8"'
        ' fill="#0b192c"/><path d="M12 4a8 8 0 0 1 8 8h-8V4z"'
        ' fill="#0284c7"/><path d="M12 20a8 8 0 0 1-8-8h8v8z"'
        ' fill="#0284c7"/></svg>'
    ),
    'VW': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><circle cx="12"'
        ' cy="12" r="10" stroke="#0b192c" stroke-width="1.8"/><path d="M6 7l3 9'
        ' 3-9M12 7l3 9 3-9" stroke="#0b192c" stroke-width="1.5"'
        ' stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    'Peugeot': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><path d="M12 2L4'
        ' 5v6c0 5.5 3.5 10.5 8 11 4.5-0.5 8-5.5 8-11V5l-8-3z" stroke="#0b192c"'
        ' stroke-width="1.8" fill="#10b981" fill-opacity="0.1"/><path d="M10'
        ' 8c1-1 3-1 4 0s0 3-1 4l2 3h-2l-1.5-2H10v2H8.5V8H10z" fill="#0b192c"/></svg>'
    ),
    'Skoda': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><circle cx="12"'
        ' cy="12" r="10" stroke="#059669" stroke-width="1.8"/><path d="M8'
        ' 12l8-4-4 8" stroke="#059669" stroke-width="1.5"'
        ' stroke-linecap="round"/></svg>'
    ),
    'Renault': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><path d="M12 2L4'
        ' 12l8 10 8-10L12 2z" stroke="#d97706" stroke-width="1.8"'
        ' fill="none"/></svg>'
    ),
    'Toyota': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><ellipse cx="12"'
        ' cy="12" rx="10" ry="7" stroke="#0b192c" stroke-width="1.5"/><ellipse'
        ' cx="12" cy="12" rx="4" ry="7" stroke="#0b192c"'
        ' stroke-width="1.5"/><ellipse cx="12" cy="9" rx="7" ry="3"'
        ' stroke="#0b192c" stroke-width="1.5"/></svg>'
    ),
    'Nissan': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><circle cx="12"'
        ' cy="12" r="9" stroke="#0b192c" stroke-width="1.5"/><rect x="3" y="10"'
        ' width="18" height="4" fill="#0b192c"/></svg>'
    ),
    'Hyundai': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><ellipse cx="12"'
        ' cy="12" rx="10" ry="6" stroke="#0284c7" stroke-width="1.5"/><path'
        ' d="M8 8v8M16 8v8M8 12c4-2 4 2 8 0" stroke="#0284c7" stroke-width="1.5"'
        ' stroke-linecap="round"/></svg>'
    ),
    'Kia': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><ellipse cx="12"'
        ' cy="12" rx="10" ry="5" stroke="#b91c1c" stroke-width="1.5"/><text'
        ' x="6" y="15" font-family="sans-serif" font-size="8" font-weight="bold"'
        ' fill="#b91c1c">KIA</text></svg>'
    ),
    'Chery': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><circle cx="12"'
        ' cy="12" r="9" stroke="#0b192c" stroke-width="1.5"/><path d="M7 12a5 5'
        ' 0 0 1 10 0" stroke="#0b192c" stroke-width="1.5"/></svg>'
    ),
    'MG': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><path d="M7 2h10l5'
        ' 5v10l-5 5H7l-5-5V7l5-5z" stroke="#b91c1c" stroke-width="1.5"'
        ' fill="none"/><text x="5" y="15" font-family="sans-serif" font-size="8"'
        ' font-weight="bold" fill="#b91c1c">MG</text></svg>'
    ),
    'BYD': (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"'
        ' style="vertical-align: middle; margin-left: 5px;"><ellipse cx="12"'
        ' cy="12" rx="10" ry="6" stroke="#0284c7" stroke-width="1.5"/><text'
        ' x="4.5" y="15" font-family="sans-serif" font-size="7"'
        ' font-weight="bold" fill="#0284c7">BYD</text></svg>'
    ),
}


def get_unified_car_rows(usd_egp, usd_omr):
  factor_egp = usd_egp / 47.4
  factor_omr = usd_omr / 0.3845

  car_list = [
      {
          'logo': CAR_LOGOS_SVG['Mercedes'],
          'name': 'مرسيدس C200 (ألماني)',
          'avg_egp': int(3600000 * factor_egp),
          'avg_omr': int(25750 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['BMW'],
          'name': 'بي إم دبليو 320i (ألماني)',
          'avg_egp': int(3400000 * factor_egp),
          'avg_omr': int(24250 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['VW'],
          'name': 'فولكس فاجن ID.4 (كهرباء)',
          'avg_egp': int(1750000 * factor_egp),
          'avg_omr': int(14650 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['Peugeot'],
          'name': 'بيجو 408 (فرنسي)',
          'avg_egp': int(2050000 * factor_egp),
          'avg_omr': int(13650 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['Skoda'],
          'name': 'سكودا أوكتافيا (تشيكي)',
          'avg_egp': int(1890000 * factor_egp),
          'avg_omr': int(11350 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['Renault'],
          'name': 'رينو ميجان (فرنسي)',
          'avg_egp': int(1335000 * factor_egp),
          'avg_omr': int(8500 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['Toyota'],
          'name': 'تويوتا كورولا (ياباني)',
          'avg_egp': int(1375000 * factor_egp),
          'avg_omr': int(7900 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['Nissan'],
          'name': 'نيسان صني (ياباني)',
          'avg_egp': int(722500 * factor_egp),
          'avg_omr': int(5800 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['Hyundai'],
          'name': 'هيونداي إلترا / أكسنت',
          'avg_egp': int(935000 * factor_egp),
          'avg_omr': int(6250 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['Kia'],
          'name': 'كيا سبورتاج (كوري)',
          'avg_egp': int(1865000 * factor_egp),
          'avg_omr': int(10800 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['Chery'],
          'name': 'شيري أريزو 5 (صيني)',
          'avg_egp': int(680000 * factor_egp),
          'avg_omr': int(5200 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['MG'],
          'name': 'إم جي ZS (صيني)',
          'avg_egp': int(1012500 * factor_egp),
          'avg_omr': int(6800 * factor_omr),
      },
      {
          'logo': CAR_LOGOS_SVG['BYD'],
          'name': 'BYD Song Plus (كهرباء)',
          'avg_egp': int(1635000 * factor_egp),
          'avg_omr': int(12350 * factor_omr),
      },
  ]

  rows_html = ''
  for item in car_list:
    rows_html += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 8px 6px; text-align: right;">
                <div style="display: flex; align-items: center;">
                    {item['logo']}
                    <span style="font-weight: 600; color: #0b192c; font-size: 12px;">{item['name']}</span>
                </div>
            </td>
            <td style="padding: 8px 4px; font-weight: 700; color: #0b192c; text-align: center; font-size: 11.5px;">{item['avg_egp']:,} ج.م</td>
            <td style="padding: 8px 4px; font-weight: 700; color: #0284c7; text-align: center; font-size: 11.5px;">{item['avg_omr']:,} ر.ع.</td>
        </tr>
    """
  return rows_html


# ---------------------------------------------------------
# 7. المؤشرات الاقتصادية الرسمية الشاملة (المعدلة والمطابقة)
# ---------------------------------------------------------
def get_full_macro_indicators():
  macro_egp = {
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
      'التصنيف الائتماني (Standard & Poor\'s)': 'B/B (نظرة مستقبلية مستقرة)',
  }

  macro_omr = {
      'سعر الفائدة المرجعي (البنك المركزي العماني CBO)': '6.00%',
      'معدل التضخم السنوي (المركز الوطني للإحصاء NCSI)': '1.10%',
      'معدل نمو الناتج المحلي الإجمالي (IMF / Oman)': '2.7%',
      'معدل البطالة العام (NCSI Oman)': '2.3%',
      'إجمالي المعروض النقدي والسيولة M2 (CBO)': '24.2 مليار ريال عماني',
      'متوسط إنتاج النفط اليومي (وزارة الطاقة)': '1.01 مليون برميل/يوم',
      'متوسط سعر برميل النفط العماني': '82.50 دولار',
      'الفائض في الميزانية العامة للدولة': '520 مليون ريال عماني',
      'احتياطيات النقد الأجنبي (البنك المركزي CBO)': '6.85 مليار ريال عماني',
      'عدد السكان الرسمي (المركز الوطني NCSI)': '5.4 مليون نسمة',
      'التصنيف الائتماني (Standard & Poor\'s)': 'BB+ (نظرة مستقبلية إيجابية)',
  }

  return macro_egp, macro_omr


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
# 8. توليد التقرير المدمج بطريقة الاستبدال الآمن
# ---------------------------------------------------------
def generate_complete_infopulse_html(
    current_time_str,
    merged_news,
    forex_egp,
    forex_omr,
    commodities_egp,
    commodities_omr,
    crypto_data_list,
    car_rows_html,
    macro_egp,
    macro_omr,
    ta_summary,
):

  # 1. الأخبار
  news_html = ''
  for item in merged_news:
    news_html += f"""
        <div style="background-color: #ffffff; border-right: 4px solid #10b981; border-radius: 8px; padding: 11px 14px; margin-bottom: 9px; box-shadow: 0 1px 4px rgba(0,0,0,0.03);">
            <div style="font-weight: 600; color: #0b192c; font-size: 13.5px; line-height: 1.5;">{item['title']}</div>
            <div style="margin-top: 4px;">
                <a href="{item['link']}" target="_blank" style="display: inline-block; font-size: 11px; color: #0284c7; background-color: #f0f9ff; padding: 2px 9px; border-radius: 10px; text-decoration: none;">🔗 المصدر</a>
            </div>
        </div>
    """

  # 2. أسعار العملات (شاملة EGP و OMR)
  forex_combined_rows = ''
  for k in forex_egp.keys():
    v_egp = forex_egp.get(k, 0)
    v_omr = forex_omr.get(k, 0)

    # تنسيق خاص بالأرقام الصغيرة للجنيه مقابل الريال العماني
    fmt_egp = f'{v_egp:,.2f} ج.م' if v_egp >= 0.01 else f'{v_egp:,.4f} ج.م'
    fmt_omr = f'{v_omr:,.4f} ر.ع.' if v_omr < 100 else f'{v_omr:,.2f} ر.ع.'

    forex_combined_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 9px 10px; color: #1e293b; font-weight: 500;">{k}</td>
            <td style="padding: 9px 10px; font-weight: 700; color: #0b192c; text-align: center;">{fmt_egp}</td>
            <td style="padding: 9px 10px; font-weight: 700; color: #0284c7; text-align: center;">{fmt_omr}</td>
        </tr>
    """

  # 3. المعادن والسلع بالكامل (مصر وعمان)
  commodities_rows = ''
  for k in commodities_egp.keys():
    cg_egp = commodities_egp.get(k, 0)
    cg_omr = commodities_omr.get(k, 0)

    fmt_egp = f'{cg_egp:,.2f} ج.م' if cg_egp else '-'
    fmt_omr = f'{cg_omr:,.3f} ر.ع.' if cg_omr else '-'

    commodities_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 8px 10px; color: #1e293b; font-weight: 500;">{k}</td>
            <td style="padding: 8px 10px; font-weight: 700; color: #d97706; text-align: center;">{fmt_egp}</td>
            <td style="padding: 8px 10px; font-weight: 700; color: #d97706; text-align: center;">{fmt_omr}</td>
        </tr>
    """

  # 4. العملات الرقمية
  crypto_html = ''
  for c in crypto_data_list:
    badge_bg = '#dcfce7' if c['status_short'] == 'Buy' else '#fee2e2'
    badge_color = '#15803d' if c['status_short'] == 'Buy' else '#b91c1c'
    crypto_html += f"""
        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 11px 13px; margin-bottom: 9px; background-color: #ffffff;">
            <div style="display: flex; justify-content: space-between; align-items: center; direction: rtl;">
                <span style="font-weight: 700; color: #0b192c; font-size: 13.5px;">🪙 {c['name']}</span>
                <span style="background-color: {badge_bg}; color: {badge_color}; padding: 2px 9px; border-radius: 10px; font-size: 11px; font-weight: 700;">{c['status_short']}</span>
            </div>
            <div style="margin-top: 5px; font-size: 11.5px; color: #475569; line-height: 1.5; direction: rtl; text-align: right;">
                السعر: <b>${c['price_usd']:,.2f}</b> | <b>{c['price_egp']:,.0f} ج.م</b> | <b>{c['price_omr']:,.3f} ر.ع.</b> &bull; RSI: <b>{c['rsi']:.1f}</b>
            </div>
        </div>
    """

  # 5. المؤشرات الاقتصادية (متطابقة ومجهزة للعرض الرأسي للموبايل)
  macro_html = """
    <div style="width: 100%; box-sizing: border-box;">
        <div style="width: 100%; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 12px; box-sizing: border-box;">
            <h4 style="margin: 0 0 10px 0; color: #0b192c; font-size: 13.5px; font-weight:700; border-bottom:2px solid #10b981; padding-bottom:5px;">🇪🇬 مؤشرات اقتصاد مصر (CBE / CAPMAS / S&P)</h4>
            <table style="width:100%; font-size:12px; border-collapse:collapse;">
  """
  for k, v in macro_egp.items():
    macro_html += f'<tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:6px 0; color:#475569;">{k}</td><td style="padding:6px 0; font-weight:700; color:#0b192c; text-align:left;">{v}</td></tr>'
  macro_html += """
            </table>
        </div>
        <div style="width: 100%; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; box-sizing: border-box;">
            <h4 style="margin: 0 0 10px 0; color: #0284c7; font-size: 13.5px; font-weight:700; border-bottom:2px solid #0284c7; padding-bottom:5px;">🇴🇲 مؤشرات اقتصاد عمان (CBO / NCSI / S&P)</h4>
            <table style="width:100%; font-size:12px; border-collapse:collapse;">
  """
  for k, v in macro_omr.items():
    macro_html += f'<tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:6px 0; color:#475569;">{k}</td><td style="padding:6px 0; font-weight:700; color:#0284c7; text-align:left;">{v}</td></tr>'
  macro_html += '</table></div></div>'

  # قالب HTML المحدث والآمن
  html_template = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f1f5f9; margin: 0; padding: 14px 6px; text-align: right; direction: rtl; }
        .container { max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 6px 18px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; direction: rtl; }
        .header { position: relative; background: linear-gradient(135deg, #0b192c 0%, #1e293b 100%); color: #ffffff; padding: 26px 16px 20px 16px; text-align: center; border-bottom: 4px solid #10b981; overflow: hidden; }
        .header-watermark { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; height: 100%; opacity: 0.12; pointer-events: none; z-index: 1; }
        .header-content { position: relative; z-index: 2; }
        .content { padding: 18px 14px; text-align: right; direction: rtl; }
        .section-title { font-size: 15px; color: #0b192c; border-bottom: 2px solid #10b981; padding-bottom: 4px; margin-top: 20px; margin-bottom: 11px; font-weight: 700; text-align: right; }
        .table-styled { width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 12px; text-align: right; direction: rtl; }
        .ta-box { background-color: #ecfdf5; border-right: 4px solid #10b981; padding: 9px 12px; font-size: 12px; color: #047857; margin-bottom: 12px; border-radius: 6px; font-weight: 500; line-height: 1.5; }
        .footer { background-color: #f8fafc; padding: 14px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #e2e8f0; line-height: 1.5; }
    </style>
</head>
<body dir="rtl">
    <div class="container" dir="rtl">
        <div class="header">
            <div class="header-watermark">
                <svg viewBox="0 0 500 200" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
                    <path d="M-20 100 H120 L150 40 L180 160 L210 10 L240 140 L270 60 L300 100 H520" stroke="#10b981" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                    <circle cx="150" cy="40" r="9" fill="#10b981"/>
                    <circle cx="210" cy="10" r="9" fill="#10b981"/>
                    <circle cx="240" cy="140" r="9" fill="#38bdf8"/>
                    <path d="M300 100 L460 20 M300 100 L460 60 M300 100 L460 140 M360 70 V120 M420 40 V150" stroke="#ffffff" stroke-width="4" stroke-opacity="0.8"/>
                </svg>
            </div>
            <div class="header-content">
                <div style="margin-bottom: 6px; text-align: center;">
                    <svg width="210" height="65" viewBox="0 0 300 95" fill="none" xmlns="http://www.w3.org/2000/svg" style="max-width: 210px; height: auto;">
                        <path d="M10 45 H40 L55 20 L70 70 L85 8 L100 60 L115 30 L130 45 H160" stroke="#10b981" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
                        <circle cx="55" cy="20" r="4" fill="#10b981"/>
                        <circle cx="85" cy="8" r="4" fill="#10b981"/>
                        <circle cx="100" cy="60" r="4" fill="#38bdf8"/>
                        <path d="M130 45 L190 12 M130 45 L190 28 M130 45 L190 62 M150 34 V52 M170 22 V58" stroke="#ffffff" stroke-width="2" stroke-opacity="0.85"/>
                        <text x="10" y="85" font-family="'Segoe UI', Arial, sans-serif" font-size="28" font-weight="800" fill="#ffffff">Info<tspan fill="#10b981">Pulse</tspan></text>
                        <text x="160" y="85" font-family="'Segoe UI', Arial, sans-serif" font-size="22" font-weight="700" fill="#38bdf8">إنفوبلس</text>
                    </svg>
                </div>
                <h2 style="margin:2px 0 0 0; font-size:18px; color:#ffffff; font-weight:700;">التطورات الاقتصادية من إنفوبلس</h2>
                <p style="margin:3px 0 0 0; font-size:12px; color:#a7f3d0; font-weight:500;">🇪🇬 جمهورية مصر العربية &bull; 🇴🇲 سلطنة عمان</p>
                <p style="margin:3px 0 0 0; font-size:11px; color:#94a3b8;">⏱ __TIME_STR__</p>
            </div>
        </div>
        
        <div class="content" dir="rtl">
            <div class="section-title">1️⃣ أهم الأخبار الاقتصادية العامة</div>
            __NEWS_HTML__

            <div class="section-title">2️⃣ أسعار العملات (مصر 🇪🇬 vs سلطنة عمان 🇴🇲)</div>
            <div class="ta-box">__TA_SUMMARY__</div>
            <table class="table-styled" dir="rtl">
                <thead>
                    <tr style="background-color: #f8fafc; color: #475569; font-size: 11.5px;">
                        <th style="padding: 8px 8px; text-align: right;">العملة</th>
                        <th style="padding: 8px 8px; text-align: center;">مصر (ج.م)</th>
                        <th style="padding: 8px 8px; text-align: center;">عمان (ر.ع.)</th>
                    </tr>
                </thead>
                <tbody>
                    __FOREX_ROWS__
                </tbody>
            </table>

            <div class="section-title">3️⃣ أسعار المعادن والسلع الكاملة (السوق المحلي)</div>
            <table class="table-styled" dir="rtl">
                <thead>
                    <tr style="background-color: #f8fafc; color: #475569; font-size: 11.5px;">
                        <th style="padding: 8px 8px; text-align: right;">الصنف / المعدن</th>
                        <th style="padding: 8px 8px; text-align: center;">مصر (ج.م)</th>
                        <th style="padding: 8px 8px; text-align: center;">عمان (ر.ع.)</th>
                    </tr>
                </thead>
                <tbody>
                    __COMMODITIES_ROWS__
                </tbody>
            </table>

            <div class="section-title">4️⃣ التحليل الفني للعملات الرقمية</div>
            __CRYPTO_HTML__

            <div class="section-title">5️⃣ دليل أسعار السيارات (متوسط السعر لكل دولة)</div>
            <table class="table-styled" dir="rtl">
                <thead>
                    <tr style="background-color: #f8fafc; color: #475569; font-size: 11.5px;">
                        <th style="padding: 8px 6px; text-align: right; width: 42%;">السيارة (اللوجو والموديل)</th>
                        <th style="padding: 8px 4px; text-align: center; width: 29%;">متوسط مصر (ج.م)</th>
                        <th style="padding: 8px 4px; text-align: center; width: 29%;">متوسط عمان (ر.ع.)</th>
                    </tr>
                </thead>
                <tbody>
                    __CAR_ROWS__
                </tbody>
            </table>

            <div class="section-title">6️⃣ المؤشرات الاقتصادية الرسمية الشاملة</div>
            __MACRO_HTML__
        </div>

        <div class="footer">
            ⚙️ يُولد هذا التقرير المالي الشامل تلقائياً بواسطة <b>InfoPulse | إنفوبلس</b><br>
            جميع الحقوق محفوظة &copy; 2026
        </div>
    </div>
</body>
</html>"""

  html = (
      html_template.replace('__TIME_STR__', current_time_str)
      .replace('__NEWS_HTML__', news_html)
      .replace('__TA_SUMMARY__', ta_summary)
      .replace('__FOREX_ROWS__', forex_combined_rows)
      .replace('__COMMODITIES_ROWS__', commodities_rows)
      .replace('__CRYPTO_HTML__', crypto_html)
      .replace('__CAR_ROWS__', car_rows_html)
      .replace('__MACRO_HTML__', macro_html)
  )
  return html


# ---------------------------------------------------------
# 9. الحلقة الرئيسية والجدولة
# ---------------------------------------------------------
def main_loop():
  print('🤖 بدأ تشغيل بوت InfoPulse بجميع التعديلات والمؤشرات الأخيرة...', flush=True)

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
          forex_egp,
          forex_omr,
          commodities_egp,
          commodities_omr,
          usd_egp,
          usd_omr,
          gold_oz,
          ta_summary,
      ) = get_live_forex_and_commodities_full()
      merged_news = fetch_all_merged_news()
      car_rows_html = get_unified_car_rows(usd_egp, usd_omr)
      macro_egp, macro_omr = get_full_macro_indicators()
      current_time_str = time.strftime('%Y-%m-%d %H:%M UTC')

      crypto_data_list = []
      wa_crypto_details = ''

      for name, pair in crypto_pairs.items():
        cdata = fetch_technical_data(pair)
        if cdata:
          price_usd = cdata['Price']
          price_egp = price_usd * usd_egp
          price_omr = price_usd * usd_omr
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
              'price_omr': price_omr,
              'rsi': rsi,
              'status_short': status_short,
          })

          short_name = name.split(' ')[0]
          wa_crypto_details += f'• {short_name}: ${price_usd:,.2f} | RSI:{rsi:.1f} ({status_short})\n'

        time.sleep(0.2)

      news_summary = '1️⃣ أهم الأخبار الاقتصادية:\n'
      for i in merged_news[:4]:
        news_summary += f'• {i["title"]}\n  🔗 {i["link"]}\n'

      # --- 1. إرسال تيليجرام (كل 6 ساعات) ---
      if (
          current_time - last_telegram_time >= (TELEGRAM_INTERVAL_HOURS * 3600)
          or last_telegram_time == 0
      ):
        tg_report = f"""📊 التطورات الاقتصادية من إنفوبلس (مصر 🇪🇬 & عمان 🇴🇲)
⏱ التوقيت: {current_time_str}
===================================
{news_summary}
2️⃣ أسعار العملات والذهب:
• USD: {usd_egp:.2f} ج.م | {usd_omr:.4f} ر.ع.
• OMR مقابل EGP: 1 ر.ع. = {usd_egp/usd_omr:.2f} ج.م
• الذهب عيار 21: {commodities_egp.get('الذهب عيار 21 (جرام)', 0):,.0f} ج.م | {commodities_omr.get('الذهب عيار 21 (جرام)', 0):,.3f} ر.ع.

3️⃣ العملات الرقمية:
{wa_crypto_details}
⚙️ InfoPulse Engine"""

        if send_telegram_message(tg_report):
          print('✅ تم إرسال تقرير تيليجرام بنجاح.', flush=True)
          last_telegram_time = current_time

      # --- 2. إرسال الواتساب (كل ساعتين) ---
      if (
          current_time - last_whatsapp_time >= (WHATSAPP_INTERVAL_HOURS * 3600)
          or last_whatsapp_time == 0
      ):
        wa_msg = f"""📊 *التطورات الاقتصادية من إنفوبلس (مصر 🇪🇬 & عمان 🇴🇲)*
⏱ {current_time_str}
-----------------------------------
📰 *أبرز الأسعار:*
• USD: {usd_egp:.2f} ج.م | {usd_omr:.4f} ر.ع.
• OMR/EGP: {usd_egp/usd_omr:.2f} ج.م لكل ريال
• الذهب 21: {commodities_egp.get('الذهب عيار 21 (جرام)', 0):,.0f} ج.م | {commodities_omr.get('الذهب عيار 21 (جرام)', 0):,.3f} ر.ع.
-----------------------------------
🪙 *العملات الرقمية:*
{wa_crypto_details}-----------------------------------
⚙️ التحديث القادم بعد ساعتين"""

        if send_whatsapp_message(wa_msg):
          print('✅ تم إرسال تقرير الواتساب بنجاح.', flush=True)
          last_whatsapp_time = current_time

      # --- 3. إرسال البريد الإلكتروني (كل 3 ساعات) ---
      if (
          current_time - last_email_time >= (EMAIL_INTERVAL_HOURS * 3600)
          or last_email_time == 0
      ):
        email_html = generate_complete_infopulse_html(
            current_time_str,
            merged_news,
            forex_egp,
            forex_omr,
            commodities_egp,
            commodities_omr,
            crypto_data_list,
            car_rows_html,
            macro_egp,
            macro_omr,
            ta_summary,
        )

        subject = (
            'التطورات الاقتصادية من إنفوبلس (مصر 🇪🇬 & سلطنة عمان 🇴🇲) -'
            f' {current_time_str}'
        )

        if send_email_report(subject, email_html):
          print('✅ تم إرسال البريد المحدث بنجاح.', flush=True)
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
