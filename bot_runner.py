import urllib.parse


def send_whatsapp_message(message_body):
  phone_number = os.environ.get('MY_PHONE_NUMBER')  # مثال: +201012345678
  api_key = os.environ.get('CALLMEBOT_API_KEY')  # مفتاح API من CallMeBot

  if not phone_number or not api_key:
    print('⚠️ بيانات CallMeBot غير مكتملة في Render.', flush=True)
    return False

  # ترميز النص ليكون متوافقاً مع رابط الـ URL
  encoded_text = urllib.parse.quote(message_body)
  url = f'https://api.callmebot.com/whatsapp.php?phone={phone_number}&text={encoded_text}&apikey={api_key}'

  try:
    response = requests.get(url, timeout=15)
    if response.status_code == 200:
      print('💬 تم إرسال تقرير الواتساب بنجاح عبر CallMeBot!', flush=True)
      return True
    else:
      print(f'❌ فشل إرسال الواتساب: {response.text}', flush=True)
      return False
  except Exception as e:
    print(f'❌ خطأ في الاتصال بـ CallMeBot: {e}', flush=True)
    return False
