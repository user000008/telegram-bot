import logging
import sqlite3
import os  # این کتابخانه اضافه شد
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# توکن را از تنظیمات Render می‌خواند
BOT_TOKEN = os.environ.get("BOT_TOKEN")  
VIDEO_FILE = "cat.mp4"  # نام ویدیویی که آپلود کردی
STICKER_ID = "CAACAgQAAxkBAAPGaojUKGL2VzmLZfDDfNcGjMNHKoIAAugZAAIe7clRvSbMswyP7KA9BA" # آیدی استیکر نهایی
REPEAT     = 60  # تعداد دفعات فرستادن ویدیو
DB_FILE    = "users.db"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)


def db_init():
    # ساخت جدول کاربران اگه وجود نداشت
    with sqlite3.connect(DB_FILE) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                last_name  TEXT,
                lang       TEXT,
                first_seen TEXT,
                last_seen  TEXT,
                visits     INTEGER DEFAULT 1
            )
        """)


def db_save(user):
    # ذخیره یا آپدیت اطلاعات کاربر
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as con:
        existing = con.execute("SELECT id FROM users WHERE id=?", (user.id,)).fetchone()
        if existing:
            con.execute(
                "UPDATE users SET last_seen=?, visits=visits+1 WHERE id=?",
                (now, user.id)
            )
        else:
            con.execute(
                "INSERT INTO users VALUES (?,?,?,?,?,?,?,1)",
                (user.id, user.username, user.first_name, user.last_name, user.language_code, now, now)
            )
            log.info(f"New user: {user.full_name} | @{user.username} | ID: {user.id}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_save(user)
    log.info(f"Start: {user.full_name} | ID: {user.id}")

    # ۱. ارسال ویدیو به تعداد REPEAT بار (۶۰ بار)
    for _ in range(REPEAT):
        with open(VIDEO_FILE, 'rb') as video:
            await context.bot.send_video(update.effective_chat.id, video)

    # ۲. ارسال استیکر در نهایت (فقط یک بار بعد از اتمام ویدیوها)
    await context.bot.send_sticker(update.effective_chat.id, STICKER_ID)


def main():
    db_init()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    log.info(f"Bot started | DB: {DB_FILE}")
    app.run_polling()


if __name__ == "__main__":
    main()
