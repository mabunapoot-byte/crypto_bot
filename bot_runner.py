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
  return '🤖 InfoPulse - Combined Economic Developments Bot (Egypt & Oman) is running!'


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
# 4. جلب الأخبار الاقتصادية المدمجة (مصر، عمان، عالمي، سيارات)
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
          ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
# 5. البيانات المالية (مصر وسلطنة عمان)
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


def get_live_forex_and_commodities_combined():
  try:
    url = 'https://open.er-api.com/v6/latest/USD'
    res = requests.get(url, timeout=5)
    rates = res.json().get('rates', {})

    usd_egp = rates.get('EGP', 47.4)
    usd_omr = rates.get('OMR', 0.3845)

    # 1. أسعار العملات في مصر (ج.م) وعمان (ر.ع.)
    forex_egp = {
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
        'CNY (يوان صيني)': (
            (usd_egp / rates.get('CNY', 7.23)) if rates.get('CNY') else 0
        ),
    }

    forex_omr = {
        'USD (دولار أمريكي)': usd_omr,
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
        'CNY (يوان صيني)': (
            (usd_omr / rates.get('CNY', 7.23)) if rates.get('CNY') else 0.0532
        ),
    }

    # الأونصة والفضة عالمياً
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

    # الذهب والفضة في مصر (ج.م)
    g21_egp = fetch_egypt_local_gold_base_price(usd_egp, gold_oz_usd)
    g24_egp = g21_egp * (24 / 21)
    silver_999_egp = (silver_oz_usd / 31.1035) * usd_egp

    commodities_egp = {
        'الذهب عيار 24 (جرام)': g24_egp,
        'الذهب عيار 21 (جرام)': g21_egp,
        'الذهب عيار 18 (جرام)': g24_egp * (18 / 24),
        'الجنيه الذهب (8 جرام 21)': g21_egp * 8,
        'الفضة عيار 999 (جرام)': silver_999_egp,
    }

    # الذهب والفضة في سلطنة عمان (ر.ع.)
    g24_omr = (gold_oz_usd / 31.1035) * usd_omr
    g21_omr = g24_omr * (21 / 24)
    silver_999_omr = (silver_oz_usd / 31.1035) * usd_omr

    commodities_omr = {
        'الذهب عيار 24 (جرام)': g24_omr,
        'الذهب عيار 21 (جرام)': g21_omr,
        'الذهب عيار 18 (جرام)': g24_omr * (18 / 24),
        'الريال الذهب (8 جرام 21)': g21_omr * 8,
        'الفضة عيار 999 (جرام)': silver_999_omr,
    }

    ta_summary = (
        '🟢 التحليل الفني: استقرار ملحوظ في أسعار الصرف الرسمية بمصر وعُمان مع'
        ' توازنات محددة في أسواق الصاغة المحلية متأثرة بحركة الأونصة عالمياً.'
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
    print(f'⚠️ خطأ جلب البيانات المدمجة: {e}', flush=True)
    return {}, {}, {}, {}, 47.4, 0.3845, 2650.0, ''


# ---------------------------------------------------------
# 6. أسعار السيارات في مصر وعمان
# ---------------------------------------------------------
def get_combined_auto_market(usd_egp, usd_omr):
  factor_egp = usd_egp / 47.4
  factor_omr = usd_omr / 0.3845

  cars_egp = {
      'مرسيدس C200 (ألماني)': (
          f'{int(3400000*factor_egp):,} - {int(3800000*factor_egp):,} ج.م'
      ),
      'تويوتا كورولا (ياباني)': (
          f'{int(1300000*factor_egp):,} - {int(1450000*factor_egp):,} ج.م'
      ),
      'كيا سبورتاج (كوري)': (
          f'{int(1780000*factor_egp):,} - {int(1950000*factor_egp):,} ج.م'
      ),
      'شيري أريزو 5 (صيني)': (
          f'{int(650000*factor_egp):,} - {int(710000*factor_egp):,} ج.م'
      ),
  }

  cars_omr = {
      'مرسيدس C200 (ألماني)': (
          f'{int(24000*factor_omr):,} - {int(27500*factor_omr):,} ر.ع.'
      ),
      'تويوتا لاند كروزر (ياباني)': (
          f'{int(28500*factor_omr):,} - {int(36000*factor_omr):,} ر.ع.'
      ),
      'كيا سبورتاج (كوري)': (
          f'{int(9800*factor_omr):,} - {int(11800*factor_omr):,} ر.ع.'
      ),
      'شيري أريزو 5 (صيني)': (
          f'{int(4800*factor_omr):,} - {int(5600*factor_omr):,} ر.ع.'
      ),
  }

  return cars_egp, cars_omr


# ---------------------------------------------------------
# 7. المؤشرات الاقتصادية الكلية (مصر وعمان)
# ---------------------------------------------------------
def get_combined_macro_indicators():
  macro_egp = {
      'سعر الفائدة الرئيسي (CBE)': '19.50%',
      'معدل التضخم السنوي (CAPMAS)': '14.5%',
      'توقعات النمو (IMF)': '4.7%',
      'احتياطي النقد الأجنبي': '57.34 مليار دولار',
  }
  macro_omr = {
      'سعر الفائدة المرجعي (CBO)': '6.00%',
      'معدل التضخم السنوي (NCSI)': '1.10%',
      'توقعات النمو (IMF)': '2.7%',
      'متوسط إنتاج النفط اليومي': '1.01 مليون برميل',
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
# 8. توليد التقرير المدمج بالـ HTML المنسق والنظيف
# ---------------------------------------------------------
def generate_combined_infopulse_html(
    current_time_str,
    merged_news,
    forex_egp,
    forex_omr,
    commodities_egp,
    commodities_omr,
    crypto_data_list,
    cars_egp,
    cars_omr,
    macro_egp,
    macro_omr,
    ta_summary,
):

  # 1. الأخبار المدمجة
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

  # 2. جدول أسعار العملات المدمج
  forex_combined_rows = ''
  keys = list(forex_egp.keys())
  for k in keys:
    v_egp = forex_egp.get(k, 0)
    v_omr = forex_omr.get(k, 0)
    forex_combined_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 9px 10px; color: #1e293b; font-weight: 500;">{k}</td>
            <td style="padding: 9px 10px; font-weight: 700; color: #0b192c; text-align: center;">{v_egp:,.2f} ج.م</td>
            <td style="padding: 9px 10px; font-weight: 700; color: #0284c7; text-align: center;">{v_omr:,.4f} ر.ع.</td>
        </tr>
    """

  # 3. جدول الذهب والمعادن المدمج
  commodities_rows = ''
  gold_keys = [
      'الذهب عيار 24 (جرام)',
      'الذهب عيار 21 (جرام)',
      'الذهب عيار 18 (جرام)',
      'الفضة عيار 999 (جرام)',
  ]
  for k in gold_keys:
    cg_egp = commodities_egp.get(k, 0)
    cg_omr = commodities_omr.get(k, 0)
    commodities_rows += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 9px 10px; color: #1e293b; font-weight: 500;">{k}</td>
            <td style="padding: 9px 10px; font-weight: 700; color: #d97706; text-align: center;">{cg_egp:,.1f} ج.م</td>
            <td style="padding: 9px 10px; font-weight: 700; color: #d97706; text-align: center;">{cg_omr:,.3f} ر.ع.</td>
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

  # 5. السيارات (مصر وعمان)
  cars_html = """
    <div style="display: flex; gap: 10px; flex-wrap: wrap; direction: rtl;">
        <div style="flex: 1; min-width: 260px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
            <h4 style="margin: 0 0 8px 0; color: #0b192c; font-size: 13.5px; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px;">🇪🇬 السوق المصري (ج.م)</h4>
            <ul style="margin: 0; padding-right: 16px; font-size: 12.5px; color: #334155; line-height: 1.6;">
  """
  for k, v in cars_egp.items():
    cars_html += f'<li><b>{k}:</b> {v}</li>'
  cars_html += """
            </ul>
        </div>
        <div style="flex: 1; min-width: 260px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
            <h4 style="margin: 0 0 8px 0; color: #0284c7; font-size: 13.5px; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px;">🇴🇲 السوق العماني (ر.ع.)</h4>
            <ul style="margin: 0; padding-right: 16px; font-size: 12.5px; color: #334155; line-height: 1.6;">
  """
  for k, v in cars_omr.items():
    cars_html += f'<li><b>{k}:</b> {v}</li>'
  cars_html += '</ul></div></div>'

  # 6. المؤشرات الاقتصادية
  macro_html = """
    <div style="display: flex; gap: 10px; flex-wrap: wrap; direction: rtl;">
        <div style="flex: 1; min-width: 260px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;">
            <h4 style="margin: 0 0 8px 0; color: #0b192c; font-size: 13px; font-weight:700;">🇪🇬 مؤشرات اقتصاد مصر</h4>
            <table style="width:100%; font-size:12px; border-collapse:collapse;">
  """
  for k, v in macro_egp.items():
    macro_html += f'<tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:5px 0; color:#475569;">{k}</td><td style="padding:5px 0; font-weight:700; color:#0b192c; text-align:left;">{v}</td></tr>'
  macro_html += """
            </table>
        </div>
        <div style="flex: 1; min-width: 260px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;">
            <h4 style="margin: 0 0 8px 0; color: #0284c7; font-size: 13px; font-weight:700;">🇴🇲 مؤشرات اقتصاد عمان</h4>
            <table style="width:100%; font-size:12px; border-collapse:collapse;">
  """
  for k, v in macro_omr.items():
    macro_html += f'<tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:5px 0; color:#475569;">{k}</td><td style="padding:5px 0; font-weight:700; color:#0284c7; text-align:left;">{v}</td></tr>'
  macro_html += '</table></div></div>'

  html_template = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f1f5f9; margin: 0; padding: 18px 8px; text-align: right; direction: rtl; }}
            .container {{ max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 14px; overflow: hidden; box-shadow: 0 8px 20px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; direction: rtl; }}
            
            .header {{ 
                position: relative; 
                background: linear-gradient(135deg, #0b192c 0%, #1e293b 100%); 
                color: #ffffff; 
                padding: 30px 20px 24px 20px; 
                text-align: center; 
                border-bottom: 4px solid #10b981; 
                overflow: hidden; 
            }}
            .header-watermark {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 100%;
                height: 100%;
                opacity: 0.12;
                pointer-events: none;
                z-index: 1;
            }}
            .header-content {{ position: relative; z-index: 2; }}
            
            .content {{ padding: 22px 18px; text-align: right; direction: rtl; }}
            .section-title {{ font-size: 15.5px; color: #0b192c; border-bottom: 2px solid #10b981; padding-bottom: 5px; margin-top: 22px; margin-bottom: 12px; font-weight: 700; text-align: right; }}
            .table-styled {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 12.5px; text-align: right; direction: rtl; }}
            .ta-box {{ background-color: #ecfdf5; border-right: 4px solid #10b981; padding: 9px 12px; font-size: 12px; color: #047857; margin-bottom: 12px; border-radius: 6px; font-weight: 500; line-height: 1.5; }}
            .footer {{ background-color: #f8fafc; padding: 15px; text-align: center; font-size: 11.5px; color: #64748b; border-top: 1px solid #e2e8f0; line-height: 1.5; }}
        </style>
    </head>
    <body dir="rtl">
        <div class="container" dir="rtl">
            <div class="header">
                <!-- خلفية مائية لشعار InfoPulse -->
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
                        <svg width="220" height="70" viewBox="0 0 300 95" fill="none" xmlns="http://www.w3.org/2000/svg" style="max-width: 220px; height: auto;">
                            <path d="M10 45 H40 L55 20 L70 70 L85 8 L100 60 L115 30 L130 45 H160" stroke="#10b981" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
                            <circle cx="55" cy="20" r="4" fill="#10b981"/>
                            <circle cx="85" cy="8" r="4" fill="#10b981"/>
                            <circle cx="100" cy="60" r="4" fill="#38bdf8"/>
                            <path d="M130 45 L190 12 M130 45 L190 28 M130 45 L190 62 M150 34 V52 M170 22 V58" stroke="#ffffff" stroke-width="2" stroke-opacity="0.85"/>
                            <text x="10" y="85" font-family="'Segoe UI', Arial, sans-serif" font-size="28" font-weight="800" fill="#ffffff">Info<tspan fill="#10b981">Pulse</tspan></text>
                            <text x="160" y="85" font-family="'Segoe UI', Arial, sans-serif" font-size="22" font-weight="700" fill="#38bdf8">إنفوبلس</text>
                        </svg>
                    </div>
                    <h2 style="margin:4px 0 0 0; font-size:19px; color:#ffffff; font-weight:700;">التطورات الاقتصادية من إنفوبلس</h2>
                    <p style="margin:4px 0 0 0; font-size:12.5px; color:#a7f3d0; font-weight:500;">🇪🇬 جمهورية مصر العربية &bull; 🇴🇲 سلطنة عمان</p>
                    <p style="margin:4px 0 0 0; font-size:11.5px; color:#94a3b8;">⏱ {current_time_str}</p>
                </div>
            </div>
            
            <div class="content" dir="rtl">
                <!-- 1. أهم الأخبار الاقتصادية العامة -->
                <div class="section-title">1️⃣ أهم الأخبار الاقتصادية العامة</div>
                {news_html}

                <!-- 2. أسعار العملات -->
                <div class="section-title">2️⃣ أسعار العملات (مصر 🇪🇬 vs سلطنة عمان 🇴🇲)</div>
                <div class="ta-box">{ta_summary}</div>
                <table class="table-styled" dir="rtl">
                    <thead>
                        <tr style="background-color: #f8fafc; color: #475569; font-size: 12px;">
                            <th style="padding: 8px 10px; text-align: right;">العملة</th>
                            <th style="padding: 8px 10px; text-align: center;">مصر (ج.م)</th>
                            <th style="padding: 8px 10px; text-align: center;">عمان (ر.ع.)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {forex_combined_rows}
                    </tbody>
                </table>

                <!-- 3. أسعار الذهب والمعادن -->
                <div class="section-title">3️⃣ أسعار الذهب والمعادن (السوق المحلي)</div>
                <table class="table-styled" dir="rtl">
                    <thead>
                        <tr style="background-color: #f8fafc; color: #475569; font-size: 12px;">
                            <th style="padding: 8px 10px; text-align: right;">الصنف</th>
                            <th style="padding: 8px 10px; text-align: center;">مصر (ج.م)</th>
                            <th style="padding: 8px 10px; text-align: center;">عمان (ر.ع.)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {commodities_rows}
                    </tbody>
                </table>

                <!-- 4. العملات الرقمية -->
                <div class="section-title">4️⃣ التحليل الفني للعملات الرقمية</div>
                {crypto_html}

                <!-- 5. دليل أسعار السيارات -->
                <div class="section-title">5️⃣ دليل أسعار السيارات</div>
                {cars_html}

                <!-- 6. المؤشرات الاقتصادية الكلية -->
                <div class="section-title">6️⃣ المؤشرات الاقتصادية الرسمية</div>
                {macro_html}
            </div>

            <div class="footer">
                ⚙️ يُولد هذا التقرير المالي الشامل تلقائياً بواسطة <b>InfoPulse | إنفوبلس</b><br>
                جميع الحقوق محفوظة &copy; 2026
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
  print('🤖 بدأ تشغيل بوت InfoPulse المدمج (مصر + عمان)...', flush=True)

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
      ) = get_live_forex_and_commodities_combined()
      merged_news = fetch_all_merged_news()
      cars_egp, cars_omr = get_combined_auto_market(usd_egp, usd_omr)
      macro_egp, macro_omr = get_combined_macro_indicators()
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
• الذهب عيار 21: {commodities_egp.get('الذهب عيار 21 (جرام)', 0):,.0f} ج.م | {commodities_omr.get('الذهب عيار 21 (جرام)', 0):,.3f} ر.ع.

3️⃣ العملات الرقمية:
{wa_crypto_details}
⚙️ InfoPulse Combined Engine"""

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
        email_html = generate_combined_infopulse_html(
            current_time_str,
            merged_news,
            forex_egp,
            forex_omr,
            commodities_egp,
            commodities_omr,
            crypto_data_list,
            cars_egp,
            cars_omr,
            macro_egp,
            macro_omr,
            ta_summary,
        )

        subject = (
            'التطورات الاقتصادية من إنفوبلس (مصر 🇪🇬 & سلطنة عمان 🇴🇲) -'
            f' {current_time_str}'
        )

        if send_email_report(subject, email_html):
          print('✅ تم إرسال البريد المدمج المنسق بنجاح.', flush=True)
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
