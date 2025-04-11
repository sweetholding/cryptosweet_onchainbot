import requests, time, re, asyncio
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio

nest_asyncio.apply()

TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"
TX_CACHE = set()

THRESHOLDS = {
    "BTC": 2_000_000,
    "ETH": 1_000_000,
    "OTHER": 500_000
}

EXCHANGES_ETH = {
    "0x3f5CE5FBFe3E9af3971dD833D26BA9b5C936f0bE": "Binance",
    "0xf164fC0Ec4E93095b804a4795bBe1e041497b92a": "Uniswap",
    "0xBCfCcbde45cE874adCB698cC183deBcF17952812": "PancakeSwap",
    "0xdAC17F958D2ee523a2206206994597C13D831ec7": "Tether Treasury",
    "0x28C6c06298d514Db089934071355E5743bf21d60": "Binance 14",
    "0x1d9A5c6c219219f2DfA93f1eC62eBe0199A6f173": "Coinbase",
    "0xDC76CD25977E0a5Ae17155770273aD58648900D3": "Bitfinex",
    "0x59A5208B32e627891C389ebafC644145224006E8": "HitBTC",
    "0x1f98431c8ad98523631ae4a59f267346ea31f984": "Uniswap v3",
    "0x2C4Bd064b998838076fa341A83d007FC2FA50957": "Balancer",
    "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc": "Uniswap USDC/ETH",
    "0x11111254369792b2Ca5d084aB5eEA397cA8fa48B": "1inch",
    "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f": "Uniswap v2"
}

EXCHANGES_SOL = {
    "2uwHuZbEoEJwhRSRVRTHYkf5pQg4e84xFBa9v5EnG5zy": "Binance",
    "6oYtKqyoR9AcJc6DDqNEfn5HiEGTkH1iFhiDpC5LNr6N": "MEXC",
    "8KNaMJbEHRWY5kDMSyX7VqkKjgvXUecrrXK1iZdqJ7Jw": "Bybit",
    "F6JPhv3XJk95FXzLXBct1oR8iLKLofgYFbDbynFVxUMi": "OKX",
    "9Gg9fHBuvRUxRZZ4byV3onMR3vZ6VCChgcwAWDrrmtd5": "Gate.io",
    "8HoQnePLqPj4M7PUDzfw8e3YF6LZ9N4K6svkzYxwPmcM": "Raydium",
    "5W4WzDysCtVnsqA6u6mYqbs4FYDjUR63HdThDf1doUzF": "Orca",
    "4k3Dyjzvzp8e2cwxA8GZgx6N6mUqq8Q5SQQLvMgR32A3": "Serum",
    "9vMJfxuKxXBoEa7rM12mYLMwTacLMLDJqHozw96WQL8i": "Jupiter Aggregator"
}

ETHERSCAN_API_KEY = "CXTB4IUT31N836G93ZI3YQBEWBQEGGH5QS"
SOLSCAN_API = "https://public-api.solscan.io/account/tokens"

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
    await update.message.reply_text(f"✅ Бот працює")

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
    while True:
        new_signals = parse_whale_alert()
        for net, title, link in new_signals:
            msg = f"🚨 Whale Alert:\n🔹 {title}\n{link}"
            await send_telegram_message(app, msg)
        await asyncio.sleep(60)

async def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users_list))
    app.add_handler(CommandHandler("stats", stats))
    asyncio.create_task(monitor_whale_alert(app))
    print("✅ Бот запущен...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except RuntimeError as e:
        if "running event loop" in str(e):
            loop = asyncio.get_event_loop()
            loop.create_task(run_bot())
            loop.run_forever()
        else:
            raise
