import os
import logging
import nest_asyncio
import requests
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from datetime import datetime, timezone

# Telegram настройки
TOKEN = "7594557278:AAH3JKXfwupIMLqmmzmjYvH3ToSSTUGnmHo"
CHAT_ID = "423798633"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"

# API ключи
COVALENT_API_KEY = "cqt_rQQcYJYvFfxbqpM4HTQvgbX9JcCw"
BITQUERY_API_KEY = "ory_at_q-7dWFwX_AZ0ywxzNaeyXnmEGugaA7qhJVTuEBy_TJ8.-v7__KrOzyePRYY-iF3pVFYYDJ9nnDcNxdWugDfhCMk"

# Фильтры токенов
MIN_FDV = 1_000_000
MAX_FDV = 10_000_000
MIN_GROWTH_PERCENT = 5.0
MIN_TXNS = 500
MIN_HOLDERS = 1000
MIN_NEW_HOLDERS = 1000
MIN_BIG_BUYS = 10
EXCLUDED_SYMBOLS = ["BTC", "ETH", "BNB", "XRP", "USDT", "USDC", "DOGE", "ADA", "SOL", "MATIC", "TRX"]

nest_asyncio.apply()
logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)

app = Application.builder().token(TOKEN).build()

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        pass

def load_users():
    with open(USERS_FILE, "r") as f:
        return set(map(int, f.read().splitlines()))

def save_users(users):
    with open(USERS_FILE, "w") as f:
        f.write("\n".join(map(str, users)))

USER_LIST = load_users()

async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in USER_LIST:
        USER_LIST.add(user_id)
        save_users(USER_LIST)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Вы подписаны на уведомления!")

async def list_users(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    users_text = "\n".join([str(uid) for uid in USER_LIST])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"👥 Подписчики:\n{users_text}")

async def remove_user(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        if uid in USER_LIST:
            USER_LIST.remove(uid)
            save_users(USER_LIST)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ Пользователь {uid} удалён.")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Пользователь {uid} не найден.")
    except:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Укажите ID пользователя. Пример: /remove 123456")

async def fetch_bitquery_big_buys(contract: str):
    url = "https://graphql.bitquery.io/"
    headers = {"X-API-KEY": BITQUERY_API_KEY}
    query = {
        "query": f"""
        {{
          ethereum(network: ethereum) {{
            smartContractCalls(
              smartContractAddress: {{is: \"{contract}\"}},
              options: {{desc: \"block.timestamp.unixtime\", limit: 100}},
              date: {{since: \"1 day ago\"}}
            ) {{
              amount
            }}
          }}
        }}
        """
    }
    try:
        res = requests.post(url, headers=headers, json=query)
        data = res.json()
        calls = data["data"]["ethereum"]["smartContractCalls"]
        big_buys = [float(x["amount"] or 0) for x in calls if x.get("amount") and float(x["amount"]) >= 50000]
        return len(big_buys)
    except:
        return 0

async def fetch_tokens_from_covalent():
    chains = ["eth-mainnet", "bsc-mainnet", "base-mainnet"]
    headers = {"accept": "application/json"}
    results = []

    for chain in chains:
        url = f"https://api.covalenthq.com/v1/{chain}/tokens/?key={COVALENT_API_KEY}"
        try:
            res = requests.get(url, headers=headers)
            data = res.json()
            tokens = data.get("data", {}).get("items", [])
            for token in tokens:
                symbol = token.get("contract_ticker_symbol", "").upper()
                if symbol in EXCLUDED_SYMBOLS:
                    continue

                fdv = token.get("market_cap_usd")
                if not fdv or fdv < MIN_FDV or fdv > MAX_FDV:
                    continue

                holders = token.get("holders_count", 0)
                if holders < MIN_HOLDERS:
                    continue

                growth = token.get("pretty_24h_percent_change", 0)
                if isinstance(growth, str):
                    growth = float(growth.replace("%", "").replace(",", ""))
                if growth < MIN_GROWTH_PERCENT:
                    continue

                contract = token.get("contract_address")
                big_buys = await fetch_bitquery_big_buys(contract)
                if big_buys < MIN_BIG_BUYS:
                    continue

                dex_url = f"https://dexscreener.com/{chain.replace('-mainnet','')}/{contract}"
                results.append({
                    "symbol": symbol,
                    "fdv": fdv,
                    "holders": holders,
                    "growth": growth,
                    "url": dex_url,
                    "big_buys": big_buys
                })
        except Exception as e:
            logging.error(f"Ошибка Covalent ({chain}): {e}")
    return results

async def check_tokens():
    while True:
        logging.info("🔄 Поиск токенов...")
        tokens = await fetch_tokens_from_covalent()
        for token in tokens:
            msg = (
                f"🚀 *Новый токен найден*\n"
                f"💰 Капитализация: ${token['fdv']:,.0f}\n"
                f"📈 Рост: {token['growth']}%\n"
                f"🧠 Покупок >$50K: {token['big_buys']}\n"
                f"👥 Холдеров: {token['holders']}\n"
                f"🔗 [Смотреть токен]({token['url']})"
            )
            for user_id in USER_LIST:
                try:
                    await app.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
                except Exception as e:
                    logging.error(f"Ошибка отправки {user_id}: {e}")
        await asyncio.sleep(600)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("users", list_users))
app.add_handler(CommandHandler("remove", remove_user))

async def main():
    logging.info("✅ Бот запущен")
    asyncio.create_task(check_tokens())
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except RuntimeError:
        logging.error("Ошибка запуска")
