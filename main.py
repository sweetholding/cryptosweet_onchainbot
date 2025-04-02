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

# Применяем nest_asyncio для Railway (для работы с asyncio)
nest_asyncio.apply()

# Токен бота и ID чата
TOKEN = "7594557278:AAH3JKXfwupIMLqmmzmjYbH3ToSSTUGnmHo"
CHAT_ID = "423798633"
ADMIN_ID = 423798633

USERS_FILE = "users.txt"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return set(map(int, f.read().splitlines()))
    return set()

def save_users():
    with open(USERS_FILE, "w") as f:
        f.write("\n".join(map(str, USER_LIST)))

USER_LIST = load_users()

MESSAGE_HISTORY = deque(maxlen=20)

NETWORKS = ["solana", "ethereum", "bsc", "bitcoin", "tron", "base", "xrp"]

MIN_LIQUIDITY = 50000
MIN_VOLUME_24H = 100000
MIN_TXNS_24H = 500
MIN_PRICE_CHANGE_24H = 5.0
MIN_FDV = 1000000
MAX_FDV = 10000000  # Максимальная капитализация $10 миллионов
MAX_TOKEN_AGE_DAYS = 14  # Возраст токенов не более 14 дней

app = Application.builder().token(TOKEN).build()

# Команды для бота
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Неизвестный"
    
    # Добавляем пользователя в список, если его нет
    if user_id not in USER_LIST:
        USER_LIST.add(user_id)
        save_users()  # Сохраняем изменения в файл

    # Отправляем сообщение пользователю
    await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Вы подписаны на уведомления!")

    # Уведомляем администратора
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"👤 Новый пользователь подписался!\n📌 Username: @{username}\n🆔 ID: {user_id}"
    )

async def check_large_transactions():
    while True:
        for network in NETWORKS:
            url = f"https://api.dexscreener.com/latest/dex/search?q={network}"
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                logging.error(f"Ошибка DexScreener ({network}): {e}")
                continue
            if "pairs" not in data or not isinstance(data["pairs"], list):
                continue
            for token in data["pairs"]:
                try:
                    created_at_timestamp_raw = token.get("pairCreatedAt")
                    try:
                        created_at_timestamp = int(created_at_timestamp_raw) / 1000
                    except (ValueError, TypeError):
                        continue
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
                    except (TypeError, ValueError):
                        continue

                    # Логирование капитализации
                    logging.info(f"Токен {token['baseToken']['symbol']} | FDV: {fdv} | Ликвидность: {liquidity} | Объем: {volume} | Транзакции: {txns}")

                    if fdv > MAX_FDV or fdv < MIN_FDV:
                        continue

                    base_symbol = token["baseToken"]["symbol"]
                    dex_url = token.get("url", "")

                    # Фильтр по капитализации
                    if liquidity >= MIN_LIQUIDITY and volume >= MIN_VOLUME_24H and txns >= MIN_TXNS_24H and price_change >= MIN_PRICE_CHANGE_24H and fdv <= MAX_FDV:
                        message = (
                            f"🚀 Перспективный токен {base_symbol} ({network.upper()})!\n"
                            f"💧 Ликвидность: ${liquidity:,.0f}\n"
                            f"📊 Объём: ${volume:,.0f}\n"
                            f"🔁 Транзакции: {txns}\n"
                            f"📈 Рост: {price_change}%\n"
                            f"💰 FDV: ${fdv:,.0f}\n"
                            f"📆 Возраст: {token_age_days} дней\n"
                            f"🔗 [Смотреть в DexScreener]({dex_url})"
                        )
                        for user in USER_LIST:
                            try:
                                await app.bot.send_message(chat_id=user, text=message, parse_mode="Markdown")
                            except Exception as e:
                                logging.error(f"Ошибка отправки {user}: {e}")
                        MESSAGE_HISTORY.append(message)
                        await asyncio.sleep(3)
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
