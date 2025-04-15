import logging
import asyncio
import aiohttp
from xml.etree import ElementTree
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === НАСТРОЙКИ ===
TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"
ETHERSCAN_API_KEY = "REV5JFB2CTMDHEAN7NZ9F7N9TXE7C1IIHG"
SOLANA_API_KEY = "f2ab631c-21c1-4db6-aeaa-29bc2300d6f7"
ETH_THRESHOLD_SUM = 10_000_000
ERC20_THRESHOLD = 1_000_000
SPL_THRESHOLD_SINGLE = 300_000

ETH_CEX_WALLETS = {
    "0x742d35Cc6634C0532925a3b844Bc454e4438f44e": "Binance",
    "0x3f5CE5FBFe3E9af3971dD833D26BA9b5C936f0bE": "Binance",
    "0x564286362092D8e7936f0549571a803B203aAceD": "Huobi",
    "0x28C6c06298d514Db089934071355E5743bf21d60": "Binance",
    "0x5C985E89DeB3f8a4bB5E7013eB4F4e8e36FB0fE1": "OKX",
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": "Binance",
    "0xF977814e90dA44bFA03b6295A0616a897441aceC": "Binance",
    "0xDC76CD25977E0a5Ae17155770273aD58648900D3": "Binance",
    "0x0A869d79a7052C7f1b55a8EbAbb1c0F922bE40f6": "Binance",
    "0x53d284357ec70cE289D6D64134DfAc8E511c8a3D": "Kraken"
}

SOLANA_CEX_WALLETS = {
    "5Rb7SJ5ZPpW6AwWcpY9gH6Z7vb6dTvjkGsY5tBymZ3fA": "Binance",
    "Gd3R5WhquVL7mvJdkfLvb1hZUB7AzTPaH75XEfD4eX2j": "Binance",
    "9xzZrLTV7XvEhTQAnjEDY3QoZXpgfvuP1C4HZJG9jXcT": "Coinbase",
    "CKk1RMVDp98YAHFihkZ6vGGMFNooRxXqKNVN8YcKX6tH": "Kraken",
    "5F2VuMgnSUpx3f5dfhzPbZLgKSPayDtAuTQkGg7Rf2o5": "Gate.io"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

try:
    with open(USERS_FILE, "r") as f:
        user_ids = set(int(line.strip()) for line in f)
except FileNotFoundError:
    user_ids = set()

def save_users():
    with open(USERS_FILE, "w") as f:
        for uid in user_ids:
            f.write(str(uid) + "\n")

def get_user_list():
    return list(user_ids)

def is_recent_tx(timestamp):
    try:
        tx_time = datetime.utcfromtimestamp(int(timestamp)).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - tx_time).total_seconds() < 1500
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_ids:
        user_ids.add(user_id)
        save_users()
    await context.bot.send_message(chat_id=user_id, text="✅ Ви підписались на сигнали!")

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        msg = "\n".join(str(uid) for uid in user_ids)
        await context.bot.send_message(chat_id=update.effective_user.id, text=msg or "No users")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_user.id, text="✅ Бот працює")

class EtherscanChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked = set()

    async def get_price(self):
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd") as r:
                return (await r.json())["ethereum"]["usd"]

    async def run(self, get_user_list):
        while True:
            try:
                await self.check(get_user_list)
            except Exception as e:
                logging.error(f"ETH error: {e}")
            await asyncio.sleep(60)

    async def check(self, get_user_list):
        price = await self.get_price()
        for addr, exchange in ETH_CEX_WALLETS.items():
            url = f"https://api.etherscan.io/api?module=account&action=txlist&address={addr}&sort=desc&apikey={ETHERSCAN_API_KEY}"
            async with aiohttp.ClientSession() as s:
                async with s.get(url) as r:
                    data = await r.json()
            for tx in data.get("result", []):
                if tx["hash"] in self.checked or tx.get("isError") == "1" or not is_recent_tx(tx["timeStamp"]):
                    continue
                from_ = tx.get("from", "").lower()
                to_ = tx.get("to", "").lower()
                direction = "➡️ ЗАВОД НА БІРЖУ" if to_ in ETH_CEX_WALLETS else ("⬅️ ВИВІД З БІРЖІ" if from_ in ETH_CEX_WALLETS else "❔")
                val = int(tx["value"]) / 1e18
                usd = val * price
                if usd >= ETH_THRESHOLD_SUM:
                    msg = f"💸 Ethereum\n💰 {usd:,.0f}$\n📤 {from_}\n📥 {to_}\n📊 {direction} ({exchange})\n🔗 https://etherscan.io/tx/{tx['hash']}"
                    for uid in get_user_list():
                        await self.bot.send_message(chat_id=uid, text=msg)
                self.checked.add(tx["hash"])
                if len(self.checked) > 500:
                    self.checked.clear()

class SolanaChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked = set()

    async def get_price(self):
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as r:
                return (await r.json())["solana"]["usd"]

    async def run(self, get_user_list):
        while True:
            try:
                await self.check(get_user_list)
            except Exception as e:
                logging.error(f"SOL error: {e}")
            await asyncio.sleep(60)

    async def check(self, get_user_list):
        price = await self.get_price()
        async with aiohttp.ClientSession() as s:
            for addr, exchange in SOLANA_CEX_WALLETS.items():
                url = f"https://api.helius.xyz/v0/addresses/{addr}/transactions?api-key={SOLANA_API_KEY}"
                async with s.get(url) as r:
                    if r.status != 200:
                        continue
                    txs = await r.json()
                for tx in txs:
                    sig = tx.get("signature")
                    if sig in self.checked:
                        continue
                    changes = tx.get("tokenTransfers", [])
                    for ch in changes:
                        owner = ch.get("toUserAccount", ch.get("fromUserAccount"))
                        amount = float(ch.get("tokenAmount", {}).get("uiAmount", 0))
                        usd = amount * price
                        direction = "➡️ ЗАВОД НА БІРЖУ" if ch.get("toUserAccount") == addr else ("⬅️ ВИВІД З БІРЖІ" if ch.get("fromUserAccount") == addr else "❔")
                        if usd >= SPL_THRESHOLD_SINGLE:
                            msg = f"🟣 SPL Token\n💰 {usd:,.0f}$\n📊 {direction} ({exchange})\n🔗 https://solscan.io/tx/{sig}"
                            for uid in get_user_list():
                                await self.bot.send_message(chat_id=uid, text=msg)
                    self.checked.add(sig)
                    if len(self.checked) > 500:
                        self.checked.clear()

class WhaleAlertChecker:
    def __init__(self, bot):
        self.bot = bot
        self.seen = set()

    async def run(self, get_user_list):
        while True:
            try:
                await self.check(get_user_list)
            except Exception as e:
                logging.error(f"Whale error: {e}")
            await asyncio.sleep(60)

    async def check(self, get_user_list):
        async with aiohttp.ClientSession() as s:
            async with s.get("https://nitter.net/whale_alert/rss") as r:
                if r.status != 200:
                    return
                text = await r.text()
        root = ElementTree.fromstring(text)
        for item in root.findall(".//item"):
            title = item.find("title").text
            link = item.find("link").text
            if link in self.seen:
                continue
            msg = f"🐋 Whale Alert\n🔔 {title}\n🔗 {link}"
            for uid in get_user_list():
                await self.bot.send_message(chat_id=uid, text=msg)
            self.seen.add(link)
            if len(self.seen) > 100:
                self.seen.clear()

# === ЗАПУСК ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("stats", stats))

    loop = asyncio.get_event_loop()
    loop.create_task(EtherscanChecker(app.bot).run(get_user_list))
    loop.create_task(SolanaChecker(app.bot).run(get_user_list))
    loop.create_task(WhaleAlertChecker(app.bot).run(get_user_list))

    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
