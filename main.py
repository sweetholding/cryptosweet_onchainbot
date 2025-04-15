# ✅ Обновлённый бот с фильтрами: исключены ETH/USDT/USDC + отображение бирж по обеим сторонам
import logging
import asyncio
import aiohttp
from xml.etree import ElementTree
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "7594557278:AAHkeOZN2bsn4XjtoC-7zQI3yrcRFHA1gjs"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"
ETHERSCAN_API_KEY = "REV5JFB2CTMDHEAN7NZ9F7N9TXE7C1IIHG"
SOLANA_API_KEY = "f2ab631c-21c1-4db6-aeaa-29bc2300d6f7"
ETH_THRESHOLD_SUM = 3_000_000
ERC20_THRESHOLD = 3_000_000
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
    "0x53d284357ec70cE289D6D64134DfAc8E511c8a3D": "Kraken",
    "0x4e9ce36e442e55ecd9025b9a6e0d88485d628a67": "Poloniex",
    "0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8": "Bitfinex",
    "0x876eabf441b2ee5b5b0554fd502a8e0600950cfa": "Gemini"
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
    eth_count = len(EtherscanChecker.checked) if hasattr(EtherscanChecker, 'checked') else 'N/A'
    sol_count = len(SolanaChecker.checked) if hasattr(SolanaChecker, 'checked') else 'N/A'
    whale_count = len(WhaleAlertChecker.seen) if hasattr(WhaleAlertChecker, 'seen') else 'N/A'
    msg = f"""
✅ Бот працює
🟦 Оброблено Ethereum-транзакцій: {eth_count}
🟨 Оброблено Solana-транзакцій: {sol_count}
🐋 Whale-сигналів: {whale_count}
"""
    await context.bot.send_message(chat_id=update.effective_user.id, text=msg)

class EtherscanChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked = set()

    async def get_token_price(self, session, contract_address):
        url = f"https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses={contract_address}&vs_currencies=usd"
        async with session.get(url) as r:
            if r.status != 200:
                return None
            data = await r.json()
            return data.get(contract_address.lower(), {}).get("usd")

    async def run(self, get_user_list):
        async with aiohttp.ClientSession() as s:
            retries = 3
            eth_price = None
            for i in range(retries):
                price_resp = await s.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd")
                price_data = await price_resp.json()
                if "ethereum" in price_data and "usd" in price_data["ethereum"]:
                    eth_price = price_data["ethereum"]["usd"]
                    break
                logging.warning("🔁 Повтор запроса CoinGecko для ETH... (%d/%d)", i+1, retries)
                await asyncio.sleep(10)
            if eth_price is None:
                logging.error("ETH price not found in CoinGecko response after retries")
                return

            for addr, exch_from in ETH_CEX_WALLETS.items():
                url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={addr}&sort=desc&apikey={ETHERSCAN_API_KEY}"
                async with s.get(url) as r:
                    data = await r.json()
                for tx in data.get("result", []):
                    if tx["hash"] in self.checked or not is_recent_tx(tx["timeStamp"]):
                        continue
                    symbol = tx.get("tokenSymbol", "").lower()
                    if symbol in ["usdt", "usdc", "eth", "dai", "busd"]:
                        continue
                    decimals = int(tx.get("tokenDecimal", 18))
                    value = int(tx["value"]) / (10 ** decimals)
                    token_address = tx.get("contractAddress", "").lower()
                    token_price = await self.get_token_price(s, token_address)
                    if token_price is None:
                        logging.warning(f"Token {symbol.upper()}: цена не найдена — пропущено")
                        continue
                    logging.info(f"Token {symbol.upper()}: цена {token_price}$, сумма {usd:,.2f}$")
                    usd = value * token_price
                    if usd < ERC20_THRESHOLD:
                        continue
                    from_ = tx.get("from", "").lower()
                    to_ = tx.get("to", "").lower()
                    exch_to = ETH_CEX_WALLETS.get(to_)
                    exch_final = exch_to if exch_to else (ETH_CEX_WALLETS.get(from_) or "❔")
                    direction = "➡️ deposit to" if to_ in ETH_CEX_WALLETS else "⬅️ withdraw from"
                    msg = (
                        f"💸 transaction on Ethereum token {tx.get('tokenSymbol', '')}\n"
                        f"💰 {usd:,.0f}$\n"
                        f"📤 {from_}\n"
                        f"📥 {to_}\n"
                        f"📊 {direction} ({exch_final})\n"
                        f"🔗 https://etherscan.io/tx/{tx['hash']}"
                    )
                    for uid in get_user_list():
                        await self.bot.send_message(chat_id=uid, text=msg)
                    self.checked.add(tx["hash"])
                    if len(self.checked) > 500:
                        self.checked.clear()

class SolanaChecker:
    def __init__(self, bot):
        self.bot = bot
        self.checked = set()

    async def run(self, get_user_list):
        while True:
            try:
                await self.check(get_user_list)
            except Exception as e:
                logging.error(f"SOL error: {e}")
            await asyncio.sleep(60)

    async def check(self, get_user_list):
        async with aiohttp.ClientSession() as s:
            try:
                async with s.get("https://rsshub.app/twitter/user/whale_alert") as r:
                    if r.status != 200:
                        logging.warning("WhaleAlert: RSSHub вернул статус %s", r.status)
                        return
                    text = await r.text()
            except Exception as e:
                logging.error(f"Whale RSS error: {e}")
                return
            retries = 3
            sol_price = None
            for i in range(retries):
                price_resp = await s.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
                price_data = await price_resp.json()
                if "solana" in price_data and "usd" in price_data["solana"]:
                    sol_price = price_data["solana"]["usd"]
                    break
                logging.warning("🔁 Повтор запроса CoinGecko для SOL... (%d/%d)", i+1, retries)
                await asyncio.sleep(10)
            if sol_price is None:
                logging.error("SOL price not found in CoinGecko response after retries")
                return

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
                        symbol = ch.get("tokenSymbol", "SPL").lower()
                        if symbol in ["usdt", "usdc", "eth", "dai", "busd"]:
                            continue
                        amount = float(ch.get("tokenAmount", {}).get("uiAmount", 0))
                        usd = amount * sol_price
                        if usd < SPL_THRESHOLD_SINGLE:
                            continue
                        to = ch.get("toUserAccount")
                        from_ = ch.get("fromUserAccount")
                        exch = SOLANA_CEX_WALLETS.get(to) or SOLANA_CEX_WALLETS.get(from_, "❔")
                        direction = "➡️ deposit to" if to == addr else "⬅️ withdraw from"
                        msg = (
                            f"💸 transaction on Solana token {symbol.upper()}\n"
                            f"💰 {usd:,.0f}$\n"
                            f"📤 {from_}\n"
                            f"📥 {to}\n"
                            f"📊 {direction} ({exch})\n"
                            f"🔗 https://solscan.io/tx/{sig}"
                        )
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

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    await asyncio.sleep(2)
    try:
        await app.bot.send_message(chat_id=ADMIN_ID, text="✅ Бот запущен. Мониторинг активен для Ethereum, Solana и WhaleAlert.")
    except Exception as e:
        logging.error(f"❗ Ошибка отправки стартового сообщения: {e}")
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
