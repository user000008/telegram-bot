import logging
import asyncio
import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, filters, ContextTypes
)
from aiohttp import web
import os

# ==============================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
WEBHOOK_URL        = os.environ.get("WEBHOOK_URL", "")  # مثلا: https://your-app.onrender.com
PORT               = int(os.environ.get("PORT", 8443))
# ==============================

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
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
busy_users: set[int] = set()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log.info(f"Start: {user.full_name} | {user.id}")
    await update.message.reply_text(
        "سلام! خوش نیومدی 😒\n"
        "حالا هر چقدر میخوای زر بزن — ولی منتظر جواب سریع نباش، "
        "مغزم باید کمی با حرف‌های مسخره‌ات کنار بیاد.\n\n"
        "⚠️ تا جواب قبلیتو ندادم، پیام جدیدت رو نادیده میگیرم. صبر کن!"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    if not user_message:
        return

    # اگه داریم به این کاربر جواب میدیم، نادیده بگیر
    if user_id in busy_users:
        await update.message.reply_text(
            random_busy_msg(),
            reply_to_message_id=update.message.message_id
        )
        return

    busy_users.add(user_id)
    try:
        # پیام تایپینگ + پیام انتظار طعنه‌زن
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        thinking_msg = await update.message.reply_text(random_thinking_msg())

        # گرفتن جواب از Gemini
        response = await asyncio.to_thread(model.generate_content, user_message)
        ai_reply = response.text

        # حذف پیام انتظار و ارسال جواب اصلی
        await thinking_msg.delete()
        await update.message.reply_text(ai_reply)

    except Exception as e:
        log.error(f"Gemini error: {e}")
        await update.message.reply_text("مغزم هنگ کرد از بس حرفت مسخره بود. دوباره بگو. 🙄")
    finally:
        busy_users.discard(user_id)


def random_thinking_msg() -> str:
    import random
    msgs = [
        "دارم فکر میکنم چطور جواب مسخره‌ات رو بدم... 🙄",
        "صبر کن، دارم با عقل کوچیکت جور میکنم جواب رو 😒",
        "یه لحظه... داری ارزشِ جواب گرفتن داری؟ بررسی میکنم...",
        "در حال پردازش حرف بی‌معنیت هستم ⚙️",
        "داری منتظری؟ خوبه، تمرین صبره برات 😏",
    ]
    return random.choice(msgs)


def random_busy_msg() -> str:
    import random
    msgs = [
        "هنوز دارم جواب قبلیتو میدم، صبر کن آدم 😤",
        "یه باره حرف بزن! دارم بهت فکر میکنم 🙄",
        "صف داری، منتظر بمون 😒",
        "الان گیر جواب قبلیتم، بعداً بیا 🤚",
    ]
    return random.choice(msgs)


# ── Webhook Setup برای Render ──────────────────────────────
async def main():
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN set nist!")
        return
    if not GEMINI_API_KEY:
        log.error("GEMINI_API_KEY set nist!")
        return
    if not WEBHOOK_URL:
        log.error("WEBHOOK_URL set nist!")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # تنظیم webhook
    webhook_path = f"/webhook/{TELEGRAM_BOT_TOKEN}"
    full_webhook = f"{WEBHOOK_URL}{webhook_path}"

    await app.bot.set_webhook(full_webhook)
    log.info(f"Webhook set: {full_webhook}")

    # وب‌سرور aiohttp
    async def telegram_webhook(request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return web.Response(text="OK")

    async def health(request):
        return web.Response(text="Bot is alive!")

    web_app = web.Application()
    web_app.router.add_post(webhook_path, telegram_webhook)
    web_app.router.add_get("/", health)

    async with app:
        await app.start()
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        log.info(f"Server running on port {PORT}")
        await asyncio.Event().wait()  # تا ابد بمون روشن


if __name__ == "__main__":
    asyncio.run(main())
