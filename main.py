# ✅ Полный рабочий код Telegram-бота для мониторинга Ethereum, Solana и Whale Alert
# Один файл. Всё объединено. Готово к запуску

import logging
import asyncio
import aiohttp
from xml.etree import ElementTree
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === НАСТРОЙКИ ===
TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"
ETHERSCAN_API_KEY = "REV5JFB2CTMDHEAN7NZ9F7N9TXE7C1IIHG"
ETH_THRESHOLD = 1_000_000
SOL_THRESHOLD = 250_000

ETH_CEX_WALLETS = [
    "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",  # Binance
    "0x3f5CE5FBFe3E9af3971dD833D26BA9b5C936f0bE",  # Binance
    "0x564286362092D8e7936f0549571a803B203aAceD",  # KuCoin
    "0x28C6c06298d514Db089934071355E5743bf21d60",  # Binance 14
    "0x5C985E89DeB3f8a4bB5E7013eB4F4e8e36FB0fE1",  # OKX
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0",  # Kraken
    "0xF977814e90dA44bFA03b6295A0616a897441aceC",  # Binance Cold Wallet
    "0xDC76CD25977E0a5Ae17155770273aD58648900D3",  # Gemini
    "0x0A869d79a7052C7f1b55a8EbAbb1c0F922bE40f6",  # Coinbase
    "0x53d284357ec70cE289D6D64134DfAc8E511c8a3D",  # Bitfinex
    "0x4e9ce36e442e55ecd9025b9a6e0d88485d628a67",  # Poloniex
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa",  # Huobi
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8",  # Bitstamp
    "0x3c783c21a0383057d128bae431894a5c19f9c84c",  # Gate.io
    "0x6f46cf5569aefa1acc1009290c8e043747172d89",  # Upbit
    "0x16905cF3f003fD1bB5b057C0d52b97855dCfEd17",  # MEXC
    "0xD551234Ae421e3BCBA99A0Da6d736074f22192FF",  # Bitfinex
    "0xC6BD19086B02522A8C0eCC8B0b4B82b8f19b6E3C",  # BitMart
    "0xE93381fB4c4F14bDa253907b18faD305D799241a",  # Crypto.com
    "0xF65B3B70D99d7E528C9C75B0dF43658fC6940e8e"   # Hotbit
]

SOLANA_CEX_WALLETS = [
    "5Rb7SJ5ZPpW6AwWcpY9gH6Z7vb6dTvjkGsY5tBymZ3fA",  # Binance
    "Gd3R5WhquVL7mvJdkfLvb1hZUB7AzTPaH75XEfD4eX2j",  # Coinbase
    "9xzZrLTV7XvEhTQAnjEDY3QoZXpgfvuP1C4HZJG9jXcT",  # Kraken
    "CKk1RMVDp98YAHFihkZ6vGGMFNooRxXqKNVN8YcKX6tH",  # Huobi
    "5F2VuMgnSUpx3f5dfhzPbZLgKSPayDtAuTQkGg7Rf2o5",  # KuCoin
    "GThgxyHNPsTbgpgNHMtBM4szTwvwThYV2ZozG6RHWsKi",  # Bitfinex
    "9h8ULmCU5gDp1s9R5vG1dAHKVkZEnR1nDBYUEuMfiYSP",  # OKX
    "DgfZrAZzxrjTJXNc1JAhcHeBB3GrT1e9bZ74uTyuS9Zw",  # Crypto.com
    "BwFzUoS1QjqwSGPY3hRGEE4NgVrxA5WwwEYMHkxLjMqt",  # Bybit
    "5Ar1P9xKbVXGzz7gj3fGjMsEKNPvZ3nVRG8LRvAYEJKt"   # Gate.io
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# === ПОЛЬЗОВАТЕЛИ ===
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

# === КОМАНДЫ ===
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

# === ETHERSCAN ===
class EtherscanChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked_txs = set()

    async def get_price(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd") as r:
                    data = await r.json()
                    return data["ethereum"]["usd"]
        except:
            return 3000

    async def run(self, get_user_list):
        while True:
            try:
                await self.check(get_user_list)
            except Exception as e:
                logging.error(f"ETH Checker error: {e}")
            await asyncio.sleep(60)

    async def check(self, get_user_list):
        eth_price = await self.get_price()
        for address in ETH_CEX_WALLETS:
            url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&sort=desc&apikey={ETHERSCAN_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()

            for tx in data.get("result", []):
                if tx.get("isError") == "1": continue
                tx_hash = tx["hash"]
                if tx_hash in self.checked_txs: continue
                from_addr = tx["from"].lower()
                to_addr = tx["to"].lower()
                value_eth = int(tx["value"]) / 10**18
                usd_amount = value_eth * eth_price
                if usd_amount >= ETH_THRESHOLD:
                    direction = "➡️ ЗАВОД НА БІРЖУ" if to_addr in ETH_CEX_WALLETS else ("⬅️ ВИВІД З БІРЖІ" if from_addr in ETH_CEX_WALLETS else "❔ НЕВІДОМИЙ НАПРЯМОК")
                    message = f"🔔 Ethereum транзакція\n💰 {usd_amount:,.0f}$\n📤 From: `{from_addr}`\n📥 To: `{to_addr}`\n📊 {direction}\n🔗 https://etherscan.io/tx/{tx_hash}"
                    for user_id in get_user_list():
                        await self.bot.send_message(chat_id=user_id, text=message)
                    self.checked_txs.add(tx_hash)
                    if len(self.checked_txs) > 500: self.checked_txs.clear()

# === SOLANA ===
class SolanaChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked_sigs = set()

    async def get_price(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as r:
                    data = await r.json()
                    return data["solana"]["usd"]
        except:
            return 170

    async def run(self, get_user_list):
        while True:
            try:
                await self.check(get_user_list)
            except Exception as e:
                logging.error(f"SolanaChecker error: {e}")
            await asyncio.sleep(60)

    async def check(self, get_user_list):
        sol_price = await self.get_price()
        headers = {"accept": "application/json"}
        for address in SOLANA_CEX_WALLETS:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://public-api.solscan.io/account/transactions?account={address}&limit=10", headers=headers) as resp:
                    txs = await resp.json()

            for tx in txs:
                sig = tx.get("signature")
                if sig in self.checked_sigs: continue
                instr = tx.get("parsedInstruction", [{}])[0].get("params", {})
                from_addr = instr.get("source")
                to_addr = instr.get("destination")
                lamports = instr.get("lamports", 0)
                sol_amount = int(lamports) / 1e9
                usd_amount = sol_amount * sol_price
                if usd_amount >= SOL_THRESHOLD:
                    direction = "➡️ ЗАВОД НА БІРЖУ" if address == to_addr else ("⬅️ ВИВІД З БІРЖІ" if address == from_addr else "❔")
                    message = f"🔔 Solana транзакція\n💰 {usd_amount:,.0f}$\n📤 From: `{from_addr}`\n📥 To: `{to_addr}`\n📊 {direction}\n🔗 https://solscan.io/tx/{sig}"
                    for user_id in get_user_list():
                        await self.bot.send_message(chat_id=user_id, text=message)
                    self.checked_sigs.add(sig)
                    if len(self.checked_sigs) > 500: self.checked_sigs.clear()

# === WHALE ALERT ===
class WhaleAlertChecker:
    def __init__(self, bot):
        self.bot = bot
        self.seen_links = set()

    async def run(self, get_user_list):
        while True:
            try:
                await self.check_feed(get_user_list)
            except Exception as e:
                logging.error(f"WhaleAlertChecker error: {e}")
            await asyncio.sleep(60)

    async def check_feed(self, get_user_list):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://nitter.net/whale_alert/rss") as resp:
                text = await resp.text()

        root = ElementTree.fromstring(text)
        for item in root.findall(".//item"):
            title = item.find("title").text
            link = item.find("link").text
            if link in self.seen_links: continue
            message = f"🐋 Whale Alert\n🔔 {title}\n🔗 {link}"
            for user_id in get_user_list():
                await self.bot.send_message(chat_id=user_id, text=message)
            self.seen_links.add(link)
            if len(self.seen_links) > 100: self.seen_links.clear()

# === ЗАПУСК ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("stats", stats))

    etherscan = EtherscanChecker(app.bot)
    solana = SolanaChecker(app.bot)
    whale = WhaleAlertChecker(app.bot)

    loop = asyncio.get_event_loop()
    loop.create_task(etherscan.run(get_user_list))
    loop.create_task(solana.run(get_user_list))
    loop.create_task(whale.run(get_user_list))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
