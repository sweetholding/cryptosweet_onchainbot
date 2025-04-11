import requests, time, re, threading
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"

THRESHOLDS = {"BTC": 2_000_000, "ETH": 1_000_000, "SOL": 250_000}
TX_CACHE = []
DEX_CACHE = []
last_check = ""

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return set(line.strip() for line in f)
    except:
        return set()

def save_users(users):
    with open(USERS_FILE, "w") as f:
        for u in users:
            f.write(str(u) + "\n")

users = load_users()

def send_telegram_message(text):
    for uid in users:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      data={"chat_id": uid, "text": text, "parse_mode": "HTML"})

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in users:
        users.add(user_id)
        save_users(users)
    await context.bot.send_message(chat_id=update.effective_chat.id,
        text="👋 Привет! Я отслеживаю китов и памп токены. Жди сигналы тут!")

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    msg = "👥 Подписчики:\n" + "\n".join(users)
    await update.message.reply_text(msg)

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if context.args:
        user_id = context.args[0]
        if user_id in users:
            users.remove(user_id)
            save_users(users)
            await update.message.reply_text(f"✅ Пользователь {user_id} удалён.")
        else:
            await update.message.reply_text("❌ Пользователь не найден.")
    else:
        await update.message.reply_text("⚠️ Введи ID: /kick 123456")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"📊 Бот работает\n👥 Пользователей: {len(users)}\n⏰ Последняя проверка: {last_check}"
    await update.message.reply_text(msg)

def fetch_whale_alert_tweets():
    url = "https://nitter.net/whale_alert"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    tweets = soup.find_all("div", class_="timeline-item")
    return [t.find("div", class_="tweet-content media-body").text.strip() for t in tweets[:15]]

def extract_tx_info(tweet):
    match = re.search(r"Transferred (\$[\d,.]+) \((\d+(?:\.\d+)?) (\w+)\)", tweet)
    if match:
        usd_str, _, token = match.groups()
        usd = float(usd_str.replace("$", "").replace(",", ""))
        return usd, token
    return None, None

def monitor_whale():
    global last_check
    while True:
        try:
            tweets = fetch_whale_alert_tweets()
            for tweet in tweets:
                usd, token = extract_tx_info(tweet)
                if token in THRESHOLDS and usd and usd >= THRESHOLDS[token]:
                    TX_CACHE.append((token, usd, tweet))
            if len(TX_CACHE) >= 5:
                text = f"🐋 Обнаружено 5+ крупных транзакций:\n"
                for tx in TX_CACHE:
                    text += f"\n💰 {tx[0]} — ${int(tx[1]):,}\n🔹 {tx[2][:120]}..."
                send_telegram_message(text)
                TX_CACHE.clear()
            last_check = time.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print("❌ Ошибка в whale_alert:", e)
        time.sleep(60)

def fetch_dexscreener_data():
    url = "https://api.dexscreener.com/latest/dex/pairs"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("pairs", [])

def monitor_dex():
    while True:
        try:
            tokens = fetch_dexscreener_data()
            count = 0
            top = []
            for token in tokens:
                vol = float(token.get("volume", {}).get("h1", 0))
                change = float(token.get("priceChange", {}).get("m5", 0))
                if vol >= 100000 and change >= 10:
                    top.append(token)
                    count += 1
            if count >= 5:
                msg = "🚀 Найдено 5+ памп-токенов на DexScreener:\n"
                for t in top[:5]:
                    name = t.get("baseToken", {}).get("symbol", "Unknown")
                    price = t.get("priceUsd", "?")
                    url = t.get("url", "#")
                    msg += f"\n🔸 <b>{name}</b> | 💵 ${price} | 📈 +{t['priceChange']['m5']}%\n🔗 {url}"
                send_telegram_message(msg)
        except Exception as e:
            print("❌ Ошибка в DexScreener:", e)
        time.sleep(90)

if __name__ == "__main__":
    print("✅ Бот запущен...")
    threading.Thread(target=monitor_whale, daemon=True).start()
    threading.Thread(target=monitor_dex, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("stats", stats))
    app.run_polling()
