import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"

users = set()

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return set(line.strip() for line in f)
    except:
        return set()

def save_users():
    with open(USERS_FILE, "w") as f:
        for u in users:
            f.write(str(u) + "\n")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    if str(uid) not in users:
        users.add(str(uid))
        save_users()
    await context.bot.send_message(chat_id=uid, text="✅ Ви підписались на сигнали!")

async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id == ADMIN_ID:
        await context.bot.send_message(chat_id=ADMIN_ID, text="\n".join(users))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Бот працює")

def main():
    global users
    users = load_users()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_list))
    app.add_handler(CommandHandler("stats", stats))

    print("✅ Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
