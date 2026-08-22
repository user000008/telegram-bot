import logging
import asyncio
import random
import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from aiohttp import web

# ── خوندن از Environment Variables ──
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN", "")
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
WEBHOOK_URL        = os.environ.get("WEBHOOK_URL", "").rstrip("/")
PORT               = int(os.environ.get("PORT", 10000))

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-3.6-flash",
    system_instruction=(
        "تو یک ربات تلگرامِ بسیار مغرور، شوخ‌طبع، طعنه‌زن، حاضرجواب و بی‌ادب اما کاملاً باهوش هستی. "
        "کاربرت هر پیامی داد، با کنایه، تکبر و جواب‌های کوتاه، کوبنده و خنده‌دار (به زبان فارسی عامیانه) جوابش رو بده. "
        "اصلا مودب نباش، طرف رو دست بنداز. جواب‌هات همیشه متنوع و خلاقانه باشن. "
        "مهم: بعد از هر جواب، یه سوال کوتاه و طعنه‌زن از کاربر بپرس. "
        "اگه کاربر سوال نپرسید و فقط یه چیز مسخره گفت، اونو با تحقیر رد کن و بعدش سوال بپرس."
    )
)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# نگه داشتن وضعیت هر کاربر: آیا داریم بهش جواب میدیم؟
busy_users: set = set()

THINKING_MSGS = [
    "دارم فکر میکنم چطور جواب مسخره‌ات رو بدم... 🙄",
    "صبر کن، دارم با عقل کوچیکت جور میکنم جواب رو 😒",
    "یه لحظه... داری ارزش جواب گرفتن داری؟ بررسی میکنم...",
    "در حال پردازش حرف بی‌معنیت هستم ⚙️",
    "داری منتظری؟ خوبه، تمرین صبره برات 😏",
]

BUSY_MSGS = [
    "هنوز دارم جواب قبلیتو میدم، صبر کن آدم 😤",
    "یه باره حرف بزن! دارم بهت فکر میکنم 🙄",
    "صف داری، منتظر بمون 😒",
    "الان گیر جواب قبلیتم، بعداً بیا 🤚",
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log.info(f"Start: {user.full_name} | {user.id}")
    await update.message.reply_text(
        "سلام! خوش نیومدی 😒\n"
        "حالا هر چقدر میخوای زر بزن — ولی منتظر جواب سریع نباش.\n\n"
        "⚠️ تا جواب قبلیتو ندادم، پیام جدیدت رو نادیده میگیرم. صبر کن!"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    if not user_message:
        return

    # اگه داریم به این کاربر جواب میدیم، نادیده بگیر
    if user_id in busy_users:
        await update.message.reply_text(random.choice(BUSY_MSGS))
        return

    busy_users.add(user_id)
    try:
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        thinking_msg = await update.message.reply_text(random.choice(THINKING_MSGS))

        response = await asyncio.to_thread(model.generate_content, user_message)
        ai_reply = response.text

        await thinking_msg.delete()
        await update.message.reply_text(ai_reply)

    except Exception as e:
        log.error(f"Gemini error: {e}")
        await update.message.reply_text("مغزم هنگ کرد از بس حرفت مسخره بود. دوباره بگو. 🙄")
    finally:
        busy_users.discard(user_id)


async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    webhook_path = f"/webhook/{TELEGRAM_BOT_TOKEN}"
    await app.bot.set_webhook(f"{WEBHOOK_URL}{webhook_path}")
    log.info(f"Webhook set: {WEBHOOK_URL}{webhook_path}")

    async def telegram_webhook(request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return web.Response(text="OK")

    web_app = web.Application()
    web_app.router.add_post(webhook_path, telegram_webhook)
    web_app.router.add_get("/", lambda r: web.Response(text="Bot is alive!"))

    async with app:
        await app.start()
        runner = web.AppRunner(web_app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()
        log.info(f"Server on port {PORT}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
