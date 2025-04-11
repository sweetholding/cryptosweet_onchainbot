import requests, time, re, asyncio
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"
TX_CACHE = set()
signal_count = 0

THRESHOLDS = {
    "BTC": 2_000_000,
    "ETH": 1_000_000,
    "OTHER": 500_000
}

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return set(int(line.strip()) for line in f)
    except:
        return set()

def save_users(users):
    with open(USERS_FILE, "w") as f:
        for u in users:
            f.write(str(u) + "\n")

users = load_users()

async def send_telegram_message(app, text):
    for uid in users:
        try:
            await app.bot.send_message(chat_id=uid, text=text)
        except Exception as e:
            print(f"❌ Ошибка отправки {uid}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id not in users:
        users.add(user_id)
        save_users(users)
    await update.message.reply_text("✅ Ви підписались на сигнали!")

async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        return
    text = "👥 Користувачі:\n" + "\n".join(str(u) for u in users)
    await update.message.reply_text(text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        return
    await update.message.reply_text(f"📊 Статус: бот працює. Надіслано сигналів: {signal_count}")

def parse_whale_alert():
    url = "https://nitter.net/whale_alert/rss"
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "xml")
        items = soup.find_all("item")
        signals = []
        for item in items:
            title = item.title.text
            link = item.link.text
            if link in TX_CACHE:
                continue
            TX_CACHE.add(link)
            match = re.search(r'(\$[\d,]+)', title)
            if not match:
                continue
            amount = int(match.group(1).replace("$", "").replace(",", ""))
            if "BTC" in title and amount >= THRESHOLDS["BTC"]:
                signals.append(("BTC", title, link))
            elif "ETH" in title and amount >= THRESHOLDS["ETH"]:
                signals.append(("ETH", title, link))
            elif amount >= THRESHOLDS["OTHER"]:
                signals.append(("OTHER", title, link))
        return signals
    except Exception as e:
        print("WhaleAlert error:", e)
        return []

async def monitor_whale_alert(app):
    global signal_count
    buffer = []
    while True:
        new_signals = parse_whale_alert()
        for net, title, link in new_signals:
            buffer.append((net, title, link))
        if len(buffer) >= 5:
            msg = "🚨 5+ великих транзакцій виявлено:\n\n"
            for net, title, link in buffer:
                msg += f"🔹 {title}\n{link}\n\n"
            await send_telegram_message(app, msg)
            signal_count += 1
            buffer = []
        await asyncio.sleep(60)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_list))
    app.add_handler(CommandHandler("stats", stats))
    asyncio.create_task(monitor_whale_alert(app))
    print("✅ Бот запущен...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
