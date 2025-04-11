import requests, time, re, threading
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"
RSS_URL = "https://nitter.net/whale_alert/rss"
DEX_URL = "https://api.dexscreener.com/latest/dex/pairs"

THRESHOLDS = {"BTC": 2_000_000, "ETH": 1_000_000, "SOL": 250_000}
TX_CACHE = []
DEX_CACHE = []
DEX_INTERVAL = 300

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
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": uid, "text": text}
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in users:
        users.add(user_id)
        save_users(users)
    await update.message.reply_text("✅ Ви підписались на сигнали!")

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(f"👥 Користувачі:\n" + "\n".join(users))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот активний і працює.")

def parse_amount(text):
    match = re.search(r"\(([\d,.]+) USD\)", text)
    return float(match.group(1).replace(",", "")) if match else 0

def parse_token(text):
    match = re.search(r"#(\w+)", text)
    return match.group(1).upper() if match else "UNKNOWN"

def parse_direction(text):
    if "to unknown" in text or "to unknown wallet" in text:
        return "🟢"
    elif "to" in text:
        return "🔴"
    return "🔘"

def check_whale_alert():
    global TX_CACHE
    try:
        soup = BeautifulSoup(requests.get(RSS_URL, timeout=10).content, "xml")
        items = soup.find_all("item")
        for item in items:
            title = item.title.text
            amount = parse_amount(title)
            token = parse_token(title)
            direction = parse_direction(title)
            threshold = THRESHOLDS.get(token, 500_000)

            if amount >= threshold and title not in TX_CACHE:
                TX_CACHE.append(f"{direction} {title}")
                if len(TX_CACHE) >= 5:
                    send_telegram_message("📡 Whale Alert:\n" + "\n".join(TX_CACHE))
                    TX_CACHE = []
    except Exception as e:
        print("WhaleAlert error:", e)

def check_dexscreener():
    global DEX_CACHE
    try:
        res = requests.get(DEX_URL, timeout=10)
        data = res.json()
        signals = []
        for t in data.get("pairs", []):
            base = t.get("baseToken", {}).get("symbol", "")
            quote = t.get("quoteToken", {}).get("symbol", "")
            volume_usd = float(t.get("volume", {}).get("h1", 0))
            price_change = float(t.get("priceChange", {}).get("h1", 0))
            url = t.get("url", "")

            if volume_usd >= 500000 and price_change >= 5 and url not in DEX_CACHE:
                signals.append(f"📈 {base}/{quote} +{price_change}%\n💰 Обсяг: ${int(volume_usd):,}\n🔗 {url}")
                DEX_CACHE.append(url)

            if len(signals) >= 5:
                send_telegram_message("📡 DexScreener:\n" + "\n\n".join(signals))
                break
    except Exception as e:
        print("DexScreener error:", e)

def polling_loop():
    counter = 0
    while True:
        check_whale_alert()
        if counter % (DEX_INTERVAL // 60) == 0:
            check_dexscreener()
        time.sleep(60)
        counter += 1

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("stats", stats))

    thread = threading.Thread(target=polling_loop)
    thread.daemon = True
    thread.start()

    print("✅ Бот запущен...")
    app.run_polling()
