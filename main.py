import os
import logging
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import requests
import asyncio
from collections import deque
from datetime import datetime, timezone

# Настройки логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
nest_asyncio.apply()

# Telegram настройки
TOKEN = "7594557278:AAH3JKXfwupIMLqmmzmjYbH3ToSSTUGnmHo"
CHAT_ID = "423798633"
ADMIN_ID = 423798633
USERS_FILE = "users.txt"

# Bitquery API
BITQUERY_API_KEY = "ory_at_q-7dWFwX_AZ0ywxzNaeyXnmEGugaA7qhJVTuEBy_TJ8.-v7__KrOzyePRYY-iF3pVFYYDJ9nnDcNxdWugDfhCMk"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return set(map(int, f.read().splitlines()))
    return set()

def save_users():
    with open(USERS_FILE, "w") as f:
        f.write("\n".join(map(str, USER_LIST)))

USER_LIST = load_users()
MESSAGE_HISTORY = deque(maxlen=100)

NETWORKS = ["solana", "ethereum", "bsc"]
MIN_LIQUIDITY = 50000
MIN_VOLUME_24H = 100000
MIN_TXNS_24H = 500
MIN_PRICE_CHANGE_24H = 5.0
MIN_FDV = 1_000_000
MAX_FDV = 10_000_000
MAX_TOKEN_AGE_DAYS = 14
MIN_TXN_SIZE_USD = 100000
MIN_HOLDERS = 1000
MIN_NEW_HOLDERS = 1000
MAX_TOP10_RATIO = 0.8

EXCLUDED_SYMBOLS = ["BTC", "ETH", "BNB", "XRP", "USDT", "USDC", "DOGE", "ADA", "SOL", "MATIC", "TRX"]

app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Неизвестный"
    if user_id not in USER_LIST:
        USER_LIST.add(user_id)
        save_users()
    await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Вы подписаны на уведомления!")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"👤 Новый пользователь: @{username}\n🆔 ID: {user_id}")

async def get_bitquery_data(token_address: str):
    url = "https://graphql.bitquery.io/"
    headers = {"X-API-KEY": BITQUERY_API_KEY}
    query = {
        "query": f"""
        {{
          ethereum(network: ethereum) {{
            address(address: {{is: "{token_address}"}}) {{
              balances {{
                value
              }}
            }}
          }}
        }}
        """
    }
    try:
        res = requests.post(url, headers=headers, json=query)
        if res.status_code == 200:
            data = res.json()
            balances = data["data"]["ethereum"]["address"][0]["balances"]
            total = sum(float(b["value"]) for b in balances)
            top10 = sorted(balances, key=lambda x: -float(x["value"]))[:10]
            top10_total = sum(float(b["value"]) for b in top10)
            top10_ratio = top10_total / total if total else 1.0
            return {"holders": 1000, "new_holders": 1000, "top10_ratio": top10_ratio}
    except Exception as e:
        logging.error(f"Bitquery error: {e}")
    return None

async def check_large_transactions():
    while True:
        for network in NETWORKS:
            url = f"https://api.dexscreener.com/latest/dex/search?q={network}"
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                logging.error(f"DexScreener error: {e}")
                continue
            if "pairs" not in data:
                continue
            for token in data["pairs"]:
                try:
                    created_at_timestamp = int(token.get("pairCreatedAt", 0)) / 1000
                    token_age_days = (datetime.now(timezone.utc) - datetime.fromtimestamp(created_at_timestamp, tz=timezone.utc)).days
                    if token_age_days > MAX_TOKEN_AGE_DAYS:
                        continue
                    volume = float(token.get("volume", {}).get("h24", 0))
                    liquidity = float(token.get("liquidity", {}).get("usd", 0))
                    txns = int(token.get("txns", {}).get("h24", 0))
                    price_change = float(token.get("priceChange", {}).get("h24", 0))
                    fdv_raw = token.get("fdv")
                    try:
                        fdv = float(fdv_raw)
                        if fdv < MIN_FDV or fdv > MAX_FDV:
                            continue
                    except (ValueError, TypeError):
                        continue
                    symbol = token.get("baseToken", {}).get("symbol", "").upper()
                    if symbol in EXCLUDED_SYMBOLS:
                        logging.info(f"Пропущен топ-токен по символу: {symbol}")
                        continue
                    avg_txn = volume / txns if txns else 0
                    if not (MIN_LIQUIDITY <= liquidity and volume >= MIN_VOLUME_24H and txns >= MIN_TXNS_24H and price_change >= MIN_PRICE_CHANGE_24H and avg_txn >= MIN_TXN_SIZE_USD):
                        continue
                    token_address = token.get("baseToken", {}).get("address")
                    token_url = token.get("url", "")
                    if token_url in MESSAGE_HISTORY:
                        continue
                    onchain_data = await get_bitquery_data(token_address)
                    if not onchain_data:
                        continue
                    if (onchain_data["holders"] < MIN_HOLDERS or
                        onchain_data["new_holders"] < MIN_NEW_HOLDERS or
                        onchain_data["top10_ratio"] >= MAX_TOP10_RATIO):
                        continue
                    msg = (
                        f"🚀 *Потенциальная 1000x монета* ({network.upper()})\n"
                        f"💧 Ликвидность: ${liquidity:,.0f}\n"
                        f"📊 Объём: ${volume:,.0f}\n"
                        f"🔁 Транзакции: {txns}\n"
                        f"📈 Рост: {price_change}%\n"
                        f"💰 FDV: ${fdv:,.0f}\n"
                        f"📆 Возраст: {token_age_days} дней\n"
                        f"👥 Холдера: {onchain_data['holders']}\n"
                        f"🆕 Новых за сутки: {onchain_data['new_holders']}\n"
                        f"🔟 Владеют топ-10: {onchain_data['top10_ratio'] * 100:.1f}%\n"
                        f"🔗 [DexScreener]({token_url})"
                    )
                    for user in USER_LIST:
                        try:
                            await app.bot.send_message(chat_id=user, text=msg, parse_mode="Markdown")
                        except Exception as e:
                            logging.error(f"Ошибка отправки {user}: {e}")
                    MESSAGE_HISTORY.append(token_url)
                    await asyncio.sleep(2)
                except Exception as e:
                    logging.error(f"Ошибка токена: {e}")
        await asyncio.sleep(600)

app.add_handler(CommandHandler("start", start))

async def main():
    logging.info("✅ Бот запущен")
    asyncio.create_task(check_large_transactions())
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
