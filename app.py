from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    print("Bot is alive!")
    return "Bot is running!"

def run_bot():
    # اجرای فایل اصلی بات شما
    os.system("python3 bot2.py")

if __name__ == "__main__":
    # اجرای بات در پس‌زمینه
    t = threading.Thread(target=run_bot)
    t.start()

    # اجرای وب‌سرور برای پاسخ به درخواست‌های Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
