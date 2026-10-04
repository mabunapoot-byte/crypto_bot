import time
import pandas as pd
import requests

# الثوابت الخاصة بك المثبتة مسبقاً
TELEGRAM_TOKEN = "8214213423:AAGifBdaeIxQLp3r8Ky0y0_Hvwedq2ia6Z4"
TELEGRAM_CHAT_ID = "7727265173"
COIN_ID = "bitcoin"
COIN_NAME = "Bitcoin"
INTERVAL_MINUTES = 15


def fetch_technical_data(coin_id, days=30):
  url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
  params = {"vs_currency": "usd", "days": days}
  try:
    response = requests.get(url, params=params)
    response.raise_for_status()
    prices = response.json().get("prices", [])
    df = pd.DataFrame(prices, columns=["timestamp", "Price"])
    df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")

    # المتوسطات المتحركة
    df["SMA_10"] = df["Price"].rolling(window=10).mean()
    df["SMA_30"] = df["Price"].rolling(window=30).mean()

    # مؤشر RSI (فترة 14)
    delta = df["Price"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    return df.dropna()
  except Exception as e:
    return pd.DataFrame()


def send_telegram_message(message):
  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
  try:
    response = requests.post(url, json=payload)
    return response.status_code == 200
  except Exception as e:
    return False


def main_loop():
  print("🤖 بدأ تشغيل بوت التيليجرام السحابي على Render بنجاح...")
  while True:
    try:
      df_tech = fetch_technical_data(COIN_ID, days=30)
      if not df_tech.empty:
        last_row = df_tech.iloc[-1]
        current_price = last_row["Price"]
        current_rsi = last_row["RSI"]
        sma_10 = last_row["SMA_10"]
        sma_30 = last_row["SMA_30"]
        signal_date = last_row["Date"].strftime("%Y-%m-%d %H:%M")

        status_desc = ""
        if sma_10 > sma_30 and current_rsi < 70 and current_rsi > 30:
          status_desc = (
              "🟢 إشارة شراء (Buy) - الاتجاه صاعد ومؤشر RSI في منطقة استقرار"
              " آمنة."
          )
        elif current_rsi >= 70:
          status_desc = (
              "⚠️ تنبيه تشبع شرائي (Overbought) - السعر مرتفع جداً، يُنصح بتجنب"
              " الشراء."
          )
        elif current_rsi <= 30:
          status_desc = (
              "ℹ️️ تنبيه تشبع بيعي (Oversold) - السعر منخفض جداً، ترقب ارتداد"
              " محتمل."
          )
        elif sma_10 < sma_30:
          status_desc = (
              "🔴 إشارة بيع (Sell) - الاتجاه هابط والمتوسط السريع أدنى البطيء."
          )
        else:
          status_desc = "⚪ احتفاظ (Hold) - لا توجد إشارة اتجاه واضحة حالياً."

        msg = f"""🤖 *تقرير دوري مجدول تلقائياً (السحابة)*
-----------------------------------
🪙 *العملة:* {COIN_NAME}
💰 *السعر الحالي:* ${current_price:,.2f}
⏱ *التوقيت:* {signal_date}
-----------------------------------
📈 *المؤشرات الفنية:*
• متوسط سريع (SMA 10): ${sma_10:,.2f}
• متوسط بطيء (SMA 30): ${sma_30:,.2f}
• مؤشر القوة النسبية (RSI): {current_rsi:.1f}
-----------------------------------
🚦 *القرار الاستثماري والتنبيه:*
{status_desc}
-----------------------------------
⚙️ *إرسال تلقائي كل {INTERVAL_MINUTES} دقيقة*"""

        send_telegram_message(msg)
    except Exception as e:
      print(f"خطأ: {e}")

    time.sleep(INTERVAL_MINUTES * 60)


if __name__ == "__main__":
  main_loop()