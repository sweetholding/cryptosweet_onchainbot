# ✅ CryptoSweet Onchain Bot: Ethereum + Solana (USD-based Filter, Clean Alerts)

import logging
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from xml.etree import ElementTree
import nest_asyncio
import os
# === НАСТРОЙКИ ===
TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"
ETHERSCAN_API_KEY = "REV5JFB2CTMDHEAN7NZ9F7N9TXE7C1IIHG"
SOLANA_API_KEY = "f2ab631c-21c1-4db6-aeaa-29bc2300d6f7"
COINGECKO_SOL = "https://api.coingecko.com/api/v3/simple/token_price/solana"
COINGECKO_ETH = "https://api.coingecko.com/api/v3/simple/token_price/ethereum"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens"

ETH_THRESHOLD = 1_000_000
SPL_THRESHOLD = 500_000
EXCLUDED_TOKENS = ["usdt", "usdc", "eth", "dai", "busd", "eurt"]

ETH_CEX_WALLETS = {
    "0x742d35Cc6634C0532925a3b844Bc454e4438f44e": "Binance",
    "0x3f5CE5FBFe3E9af3971dD833D26BA9b5C936f0bE": "Binance",
    "0x28C6c06298d514Db089934071355E5743bf21d60": "Binance",
    "0x5C985E89DeB3f8a4bB5E7013eB4F4e8e36FB0fE1": "OKX",
    "0x564286362092D8e7936f0549571a803B203aAceD": "Huobi",
    "0xF977814e90dA44bFA03b6295A0616a897441aceC": "Binance",
    "0x0A869d79a7052C7f1b55a8EbAbb1c0F922bE40f6": "Binance",
    "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": "Binance",
    "0x53d284357ec70cE289D6D64134DfAc8E511c8a3D": "Kraken",
    "0x4e9ce36e442e55ecd9025b9a6e0d88485d628a67": "Poloniex",
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8": "Bitfinex",
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa": "Gemini",
    "0x3f8CB6fB8c1536B1a78E24F8c5dC4E1a9cF4c80C": "Uniswap",
    "0x1111111254fb6c44bac0bed2854e76f90643097d": "1inch",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Project"
}

SOLANA_CEX_WALLETS = {
    "5Rb7SJ5ZPpW6AwWcpY9gH6Z7vb6dTvjkGsY5tBymZ3fA": "Binance",
    "Gd3R5WhquVL7mvJdkfLvb1hZUB7AzTPaH75XEfD4eX2j": "Binance",
    "9xzZrLTV7XvEhTQAnjEDY3QoZXpgfvuP1C4HZJG9jXcT": "Coinbase",
    "CKk1RMVDp98YAHFihkZ6vGGMFNooRxXqKNVN8YcKX6tH": "Kraken",
    "5F2VuMgnSUpx3f5dfhzPbZLgKSPayDtAuTQkGg7Rf2o5": "Gate.io",
    "3gCzvDMEzM9pbyv3AVZVvPZjGppMX5mNxdVyk7Vzzfwu": "Raydium",
    "6F2vZ5hbf1PdLtYAvXWk7mU3zcnUXkWBcU5wToUaERjE": "Orca",
    "9xQeWvG816bUx9EPn6bDQoNqjAmpJZT89XepS6v3Z7jR": "Jupiter",
    "Es9vMFrzaCERGrv7Dt9WzrbU98hGTyYqCVyfM7VNqTZz": "Serum"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

user_ids = set()

def save_users():
    with open(USERS_FILE, "w") as f:
        for uid in user_ids:
            f.write(f"{uid}\n")

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            for line in f:
                user_ids.add(int(line.strip()))
    except FileNotFoundError:
        pass

def get_user_list():
    return list(user_ids)

load_users()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_ids:
        user_ids.add(uid)
        save_users()
    await context.bot.send_message(chat_id=uid, text="✅ Ви підписались на сигнали!")

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await context.bot.send_message(chat_id=ADMIN_ID, text="\n".join(str(i) for i in user_ids))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_user.id, text="✅ Бот працює")

class EtherscanChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked = set()

    async def get_price(self, session, contract):
        try:
            params = {"contract_addresses": contract, "vs_currencies": "usd"}
            async with session.get(COINGECKO_ETH, params=params) as r:
                data = await r.json()
                return data.get(contract.lower(), {}).get("usd", 0.0)
        except:
            return 0.0

    async def run(self, get_users):
        while True:
            try:
                now = datetime.now(timezone.utc)
                async with aiohttp.ClientSession() as s:
                    for wallet, exch in ETH_CEX_WALLETS.items():
                        url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={wallet}&sort=desc&apikey={ETHERSCAN_API_KEY}"
                        async with s.get(url) as r:
                            data = await r.json()
                        txs = data.get("result", [])
                        grouped = {}
                        for tx in txs:
                            hash = tx["hash"]
                            if hash in self.checked:
                                continue
                            if hash not in grouped:
                                grouped[hash] = []
                            grouped[hash].append(tx)

                        for hash, tx_list in grouped.items():
                            total_usd = 0
                            symbol = ""
                            for tx in tx_list:
                                timestamp = int(tx.get("timeStamp", "0"))
                                tx_time = datetime.fromtimestamp(timestamp, timezone.utc)
                                if (now - tx_time).total_seconds() > 600:
                                    continue
                                contract = tx["contractAddress"]
                                token = tx["tokenSymbol"].lower()
                                if token in EXCLUDED_TOKENS:
                                    continue
                                amount = float(tx["value"]) / 10**int(tx["tokenDecimal"])
                                if amount == 0:
                                    continue
                                price = await self.get_price(s, contract)
                                usd = price * amount
                                total_usd += usd
                                symbol = token.upper()
                            if total_usd >= ETH_THRESHOLD:
                                tx_sample = tx_list[0]
                                direction = "➡️ deposit to" if tx_sample["to"].lower() == wallet.lower() else "⬅️ withdraw from"
                                msg = (
                                    f"🔆 {symbol} on Ethereum\n"
                                    f"💰 {total_usd:,.0f}$\n"
                                    f"📤 {tx_sample['from']}\n"
                                    f"📥 {tx_sample['to']}\n"
                                    f"📊 {direction} ({exch})\n"
                                    f"🔗 https://etherscan.io/tx/{hash}"
                                )
                                for uid in get_users():
                                    await self.bot.send_message(chat_id=uid, text=msg)
                                self.checked.add(hash)
            except Exception as e:
                logging.error(f"EtherscanChecker error: {e}")
            await asyncio.sleep(600)

class SolanaChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked = set()

    async def run(self, get_users):
        await asyncio.sleep(30)
        while True:
            try:
                now = datetime.now(timezone.utc)
                today = int(now.timestamp())
                yesterday = int((now - timedelta(hours=3)).timestamp())
                async with aiohttp.ClientSession() as s:
                    for wallet, exch in SOLANA_CEX_WALLETS.items():
                        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={SOLANA_API_KEY}&before={today}&after={yesterday}"
                        async with s.get(url) as r:
                            txs = await r.json()
                        if not isinstance(txs, list):
                            logging.error(f"Unexpected Solana response: {txs}")
                            continue

                        for tx in txs:
                            sig = tx.get("signature")
                            if not sig or sig in self.checked:
                                continue
                            total_usd = 0
                            symbol = ""
                            from_ = to_ = direction = ""
                            for t in tx.get("tokenTransfers", []):
                                token = t.get("tokenSymbol", "").lower()
                                if token in EXCLUDED_TOKENS:
                                    continue
                                amount = float(t.get("tokenAmount", {}).get("uiAmount", 0))
                                if amount == 0:
                                    continue
                                contract = t.get("mint")
                                price = 0.0
                                try:
                                    params = {"contract_addresses": contract, "vs_currencies": "usd"}
                                    async with s.get(COINGECKO_SOL, params=params) as r2:
                                        data = await r2.json()
                                        price = data.get(contract.lower(), {}).get("usd", 0.0)
                                except:
                                    pass
                                usd = price * amount
                                total_usd += usd
                                symbol = token.upper()
                                from_ = t.get("fromUserAccount")
                                to_ = t.get("toUserAccount")
                                direction = "➡️ deposit to" if to_ == wallet else "⬅️ withdraw from"
                            if total_usd >= SPL_THRESHOLD:
                                msg = (
                                    f"🔣 {symbol} on Solana\n"
                                    f"💰 {total_usd:,.0f}$\n"
                                    f"📤 {from_}\n"
                                    f"📥 {to_}\n"
                                    f"📊 {direction} ({exch})\n"
                                    f"🔗 https://solscan.io/tx/{sig}"
                                )
                                for uid in get_users():
                                    await self.bot.send_message(chat_id=uid, text=msg)
                                self.checked.add(sig)
            except Exception as e:
                logging.error(f"SolanaChecker error: {e}")
            await asyncio.sleep(21600)

class WhaleAlertChecker:
    def __init__(self, bot):
        self.bot = bot
        self.seen_file = "seen_whale.txt"
        self.seen = self.load_seen()
        self.first_run = True

    def load_seen(self):
        if not os.path.exists(self.seen_file):
            return set()
        with open(self.seen_file, "r") as f:
            return set(line.strip() for line in f.readlines())

    def save_seen(self):
        with open(self.seen_file, "w") as f:
            for tid in self.seen:
                f.write(tid + "\n")

    async def run(self, get_users):
        while True:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
                    async with s.get("https://rsshub.app/twitter/user/whale_alert") as r:
                        text = await r.text()
                root = ElementTree.fromstring(text)
                items = root.findall(".//item")[:3]
                if self.first_run and items:
                    items = [items[0]]
                    self.first_run = False
                for item in items:
                    title = item.find("title").text.strip()
                    link = item.find("link").text.strip()
                    tweet_id = link.split("/")[-1].strip()
                    if tweet_id in self.seen:
                        continue
                    msg = (
                        f"🐋 Whale Alert\n"
                        f"🔔 {title}\n"
                        f"🔗 {link}"
                    )
                    for uid in get_users():
                        await self.bot.send_message(chat_id=uid, text=msg)
                    self.seen.add(tweet_id)
                    self.save_seen()
            except Exception as e:
                logging.error(f"WhaleAlert error: {e}")
            await asyncio.sleep(60)



async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("stats", stats))

    await asyncio.sleep(2)
    await app.bot.send_message(chat_id=ADMIN_ID, text="✅ CryptoSweet Onchain запущено")

    asyncio.create_task(EtherscanChecker(app.bot).run(get_user_list))
    asyncio.create_task(SolanaChecker(app.bot).run(get_user_list))
    asyncio.create_task(WhaleAlertChecker(app.bot).run(get_user_list))

    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
