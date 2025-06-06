# ✅ CryptoSweet Onchain Bot: ETH, Solana, Arbitrum, Whale Alert (Final Version)

import logging
import asyncio
import aiohttp
import json
import os
import nest_asyncio
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from xml.etree import ElementTree

# === CONFIG ===
TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"
ETHERSCAN_API_KEY = "REV5JFB2CTMDHEAN7NZ9F7N9TXE7C1IIHG"
SOLSCAN_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NDQ5NzE0NjUxMDksImVtYWlsIjoia2lsYXJ5OEBnbWFpbC5jb20iLCJhY3Rpb24iOiJ0b2tlbi1hcGkiLCJhcGlWZXJzaW9uIjoidjIiLCJpYXQiOjE3NDQ5NzE0NjV9.ERDDGAValYBLgskm1SsrPAWPBQmPgBYnRnYrTtmHZS0"
SOLANA_API_KEY = "f2ab631c-21c1-4db6-aeaa-29bc2300d6f7"
ARBITRUM_API_KEY = "CSV7URMAPDJHVCZRW9WZSGW7IDF9XVISGV"
COINGECKO_ETH = "https://api.coingecko.com/api/v3/simple/token_price/ethereum"
COINGECKO_SOL = "https://api.coingecko.com/api/v3/simple/token_price/solana"
COINGECKO_ARB = "https://api.coingecko.com/api/v3/simple/token_price/arbitrum-one"
EXCLUDED_TOKENS = ["usdt", "usdc", "eth", "dai", "busd", "eurt"]
ETH_WALLETS_FILE = "eth_wallets.json"
SOL_WALLETS_FILE = "sol_wallets.json"
ARBITRUM_WALLETS_FILE = "arbitrum_wallets.json"

logging.basicConfig(level=logging.INFO)
user_ids = set()
usernames = {}

def save_users():
    with open(USERS_FILE, "w") as f:
        for uid in user_ids:
            f.write(f"{uid}\n")

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            for line in f:
                uid = int(line.strip())
                user_ids.add(uid)
    except FileNotFoundError:
        pass

load_users()

def get_user_list():
    return list(user_ids)

def load_wallets(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return {}

def save_wallets(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username or "Без ника"
    if uid not in user_ids:
        user_ids.add(uid)
        save_users()
    usernames[uid] = username
    await context.bot.send_message(chat_id=uid, text="✅ Ви підписались на сигнали!")

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    lines = [f"{usernames.get(uid, 'Без ника')} — {uid}" for uid in user_ids]
    await context.bot.send_message(chat_id=ADMIN_ID, text="\n".join(lines))

async def deluser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("❗ Укажи ID пользователя")
        return
    try:
        uid = int(args[0])
        if uid in user_ids:
            user_ids.remove(uid)
            save_users()
            await update.message.reply_text(f"✅ Пользователь {uid} удалён")
        else:
            await update.message.reply_text("❗ Пользователь не найден")
    except ValueError:
        await update.message.reply_text("❗ Неверный формат ID")

async def addwallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 4:
        await update.message.reply_text("❗ Формат: /addwallet eth адрес биржа порог")
        return
    net, address, name, threshold = args[0].lower(), args[1], args[2], float(args[3])
    files = [ETH_WALLETS_FILE, ARBITRUM_WALLETS_FILE] if net == "eth" else [SOL_WALLETS_FILE] if net == "sol" else []
    for file in files:
        wallets = load_wallets(file)
        wallets[address] = {"name": name, "threshold": threshold}
        save_wallets(file, wallets)
    await update.message.reply_text(f"✅ Добавлен: {address} → {name.upper()} ({net.upper()})")

async def delwallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❗ Формат: /delwallet eth/sol адрес")
        return
    net, address = args[0].lower(), args[1]
    files = [ETH_WALLETS_FILE, ARBITRUM_WALLETS_FILE] if net == "eth" else [SOL_WALLETS_FILE]
    for file in files:
        wallets = load_wallets(file)
        if address in wallets:
            del wallets[address]
            save_wallets(file, wallets)
    await update.message.reply_text(f"✅ Удалён: {address} из {net.upper()}")

# === EtherscanChecker ===
class EtherscanChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked = set()

    async def run(self, get_users):
        while True:
            try:
                wallets = load_wallets(ETH_WALLETS_FILE)
                async with aiohttp.ClientSession() as s:
                    for wallet, meta in wallets.items():
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
                                contract = tx["contractAddress"]
                                token = tx["tokenSymbol"].lower()
                                if token in EXCLUDED_TOKENS:
                                    continue
                                amount = float(tx["value"]) / 10**int(tx["tokenDecimal"])
                                if amount == 0:
                                    continue
                                price = await self.get_price(s, contract)
                                if price == 0:
                                    continue
                                usd = price * amount
                                total_usd += usd
                                symbol = token.upper()
                            if total_usd >= meta["threshold"]:
                                tx_sample = tx_list[0]
                                direction = "➡️ deposit to" if tx_sample["to"].lower() == wallet.lower() else "⬅️ withdraw from"
                                msg = (
                                    f"🔆 {symbol} on Ethereum\n"
                                    f"💰 {total_usd:,.0f}$\n"
                                    f"📤 {tx_sample['from']}\n"
                                    f"📥 {tx_sample['to']}\n"
                                    f"📊 {direction} ({meta['name']})\n"
                                    f"🔗 https://etherscan.io/tx/{hash}"
                                )
                                for uid in await get_users():
                                    await self.bot.send_message(chat_id=uid, text=msg)
                                self.checked.add(hash)
            except Exception as e:
                logging.error(f"EtherscanChecker error: {e}")
            await asyncio.sleep(600)

# === SolanaChecker ===
class SolanaChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked = set()

    async def run(self, get_users):
        await asyncio.sleep(30)
        while True:
            try:
                now = datetime.now(timezone.utc)
                wallets = load_wallets(SOL_WALLETS_FILE)
                async with aiohttp.ClientSession() as s:
                    for wallet, meta in wallets.items():
                        url = f"https://pro-api.solscan.io/v1.0/account/{wallet}/transactions?limit=5"
                        headers = {"accept": "application/json", "token": SOLSCAN_API_KEY}
                        async with s.get(url, headers=headers) as r:
                            data = await r.json()
                            txs = data if isinstance(data, list) else data.get("data", [])
                        for tx in txs:
                            sig = tx.get("signature") or tx.get("txHash")
                            if not sig or sig in self.checked:
                                continue
                            self.checked.add(sig)
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
                            if total_usd >= meta["threshold"]:
                                msg = (
                                    f"🔣 {symbol} on Solana\n"
                                    f"💰 {total_usd:,.0f}$\n"
                                    f"📤 {from_}\n"
                                    f"📥 {to_}\n"
                                    f"📊 {direction} ({meta['name']})\n"
                                    f"🔗 https://solscan.io/tx/{sig}"
                                )
                                for uid in await get_users():
                                    await self.bot.send_message(chat_id=uid, text=msg)
            except Exception as e:
                logging.error(f"SolanaChecker error: {e}")
            await asyncio.sleep(3600)

# === ArbitrumChecker ===
class ArbitrumChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked = set()

    async def run(self, get_users):
        while True:
            try:
                wallets = load_wallets(ARBITRUM_WALLETS_FILE)
                async with aiohttp.ClientSession() as s:
                    for wallet, meta in wallets.items():
                        url = f"https://api.arbiscan.io/api?module=account&action=tokentx&address={wallet}&sort=desc&apikey={ARBITRUM_API_KEY}"
                        async with s.get(url) as r:
                            data = await r.json()
                        txs = data.get("result", [])
                        for tx in txs:
                            hash = tx["hash"]
                            if hash in self.checked:
                                continue
                            timestamp = int(tx.get("timeStamp", "0"))
                            tx_time = datetime.fromtimestamp(timestamp, timezone.utc)
                            if (datetime.now(timezone.utc) - tx_time).total_seconds() > 900:
                                continue
                            contract = tx["contractAddress"]
                            token = tx["tokenSymbol"].lower()
                            if token in EXCLUDED_TOKENS:
                                continue
                            amount = float(tx["value"]) / 10**int(tx["tokenDecimal"])
                            if amount == 0:
                                continue
                            price = await self.get_price(s, contract)
                            if price == 0:
                                continue
                            usd = price * amount
                            if usd >= meta["threshold"]:
                                msg = (
                                    f"🧬 {token.upper()} on Arbitrum\n"
                                    f"💰 {usd:,.0f}$\n"
                                    f"📤 {tx['from']}\n"
                                    f"📥 {tx['to']}\n"
                                    f"🔗 https://arbiscan.io/tx/{hash}"
                                )
                                for uid in await get_users():
                                    await self.bot.send_message(chat_id=uid, text=msg)
                            self.checked.add(hash)
            except Exception as e:
                logging.error(f"ArbitrumChecker error: {e}")
            await asyncio.sleep(600)

# === WhaleAlertChecker ===
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

                    self.seen.add(tweet_id)
                    self.save_seen()

                    msg = (
                        f"🐋 Whale Alert\n"
                        f"🔔 {title}\n"
                        f"🔗 {link}"
                    )

                    for uid in await get_users():
                        try:
                            await self.bot.send_message(chat_id=uid, text=msg)
                        except Exception as e:
                            logging.error(f"Ошибка при отправке Whale Alert для {uid}: {e}")

            except Exception as e:
                logging.error(f"WhaleAlert error: {e}")

            await asyncio.sleep(600)

async def wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    eth = load_wallets(ETH_WALLETS_FILE)
    sol = load_wallets(SOL_WALLETS_FILE)
    arb = load_wallets(ARBITRUM_WALLETS_FILE)

    msg = "<b>ETH:</b>\n" + "\n".join(f"{a} → {v['name']} ({v['threshold']}$)" for a, v in eth.items())
    msg += "\n\n<b>SOL:</b>\n" + "\n".join(f"{a} → {v['name']} ({v['threshold']}$)" for a, v in sol.items())
    msg += "\n\n<b>ARBITRUM:</b>\n" + "\n".join(f"{a} → {v['name']} ({v['threshold']}$)" for a, v in arb.items())

    await update.message.reply_text(msg, parse_mode="HTML")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("✅ Бот працює і відправляє сигнали")

# ✅ Динамическая функция для получения актуальных подписчиков
async def get_users():
    return get_user_list()

# === Главная функция запуска бота и всех чекеров ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("deluser", deluser))
    app.add_handler(CommandHandler("addwallet", addwallet))
    app.add_handler(CommandHandler("delwallet", delwallet))
    app.add_handler(CommandHandler("wallets", wallets))
    app.add_handler(CommandHandler("stats", stats))

    await asyncio.sleep(2)
    await app.bot.send_message(chat_id=ADMIN_ID, text="✅ CryptoSweet Onchain запущено")

    # ✅ Запускаем чекеры, передавая функцию get_users
    asyncio.create_task(EtherscanChecker(app.bot).run(get_users))
    asyncio.create_task(SolanaChecker(app.bot).run(get_users))
    asyncio.create_task(ArbitrumChecker(app.bot).run(get_users))
    asyncio.create_task(WhaleAlertChecker(app.bot).run(get_users))

    await app.run_polling()

# === Запуск при старте файла ===
if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
