import os
import logging
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import requests
import asyncio
from collections import deque

# Настройки логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Применяем nest_asyncio для Railway (для работы с asyncio)
nest_asyncio.apply()

# Токен бота и ID чата
TOKEN = "7594557278:AAH3JKXfwupIMLqmmzmjYbH3ToSSTUGnmHo"
CHAT_ID = "423798633"
ADMIN_ID = 423798633  # Твой Telegram ID для уведомлений

# Список подписанных пользователей (в памяти, без файлов)
USER_LIST = set()

# История последних 20 сообщений
MESSAGE_HISTORY = deque(maxlen=20)

# Сети для отслеживания крупных сделок
NETWORKS = ["solana", "ethereum", "bsc", "bitcoin", "tron", "base", "ton", "xrp"]

# Пороговые значения фильтров
MIN_LIQUIDITY = 50000
MIN_VOLUME_24H = 100000
MIN_TXNS_24H = 500
MIN_PRICE_CHANGE_24H = 5.0  # В процентах

# Инициализация бота
app = Application.builder().token(TOKEN).build()

# Команда /start (пользователь подписывается)
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Неизвестный"

    await update.message.reply_text("✅ Вы подписаны на уведомления!")

    # Отправляем админу ID нового пользователя
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"👤 Новый пользователь подписался!\n"
             f"📌 Username: @{username}\n"
             f"🆔 ID: {user_id}\n"
             f"Чтобы добавить его в рассылку, используй команду:\n"
             f"/adduser {user_id}"
    )

# Команда /adduser (админ вручную добавляет пользователя в рассылку)
async def add_user(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды!")
        return

    if not context.args:
        await update.message.reply_text("❌ Использование: /adduser USER_ID")
        return

    try:
        user_id = int(context.args[0])
        USER_LIST.add(user_id)
        await update.message.reply_text(f"✅ Пользователь {user_id} добавлен в рассылку.")
    except ValueError:
        await update.message.reply_text("❌ Ошибка: USER_ID должен быть числом.")

# Команда /listusers (просмотр всех добавленных пользователей)
async def list_users(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды!")
        return

    if not USER_LIST:
        await update.message.reply_text("📂 Список пользователей пуст.")
        return

    users_text = "\n".join(map(str, USER_LIST))
    await update.message.reply_text(f"📜 Список пользователей:\n{users_text}")

# Команда /sendall (массовая рассылка)
async def send_to_all(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды!")
        return

    if not USER_LIST:
        await update.message.reply_text("❌ В базе нет пользователей для рассылки!")
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("❌ Введите сообщение после команды!")
        return

    count = 0
    for user in USER_LIST:
        try:
            await context.bot.send_message(chat_id=user, text=message)
            count += 1
        except Exception as e:
            logging.error(f"Ошибка при отправке пользователю {user}: {e}")

    await update.message.reply_text(f"✅ Сообщение отправлено {count} пользователям!")

# Проверка и фильтрация перспективных токенов
async def check_large_transactions():
    while True:
        for network in NETWORKS:
            url = f"https://api.dexscreener.com/latest/dex/search?q={network}"
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                logging.error(f"Ошибка запроса к DexScreener ({network}): {e}")
                continue

            if "pairs" not in data or not isinstance(data["pairs"], list):
                logging.warning(f"⚠️ Некорректный ответ от API для {network}: {data}")
                continue

            for token in data["pairs"]:
                try:
                    volume = float(token.get("volume", {}).get("h24", 0))
                    liquidity = float(token.get("liquidity", {}).get("usd", 0))
                    txns = int(token.get("txns", {}).get("h24", 0))
                    price_change = float(token.get("priceChange", {}).get("h24", 0))
                    base_symbol = token["baseToken"]["symbol"]
                    dex_url = token.get("url", "")

                    if (liquidity >= MIN_LIQUIDITY and
                        volume >= MIN_VOLUME_24H and
                        txns >= MIN_TXNS_24H and
                        price_change >= MIN_PRICE_CHANGE_24H):

                        message = (
                            f"🚀 Найден перспективный токен {base_symbol} ({network.upper()})!\n"
                            f"💧 Ликвидность: ${liquidity:,.0f}\n"
                            f"📊 Объём (24ч): ${volume:,.0f}\n"
                            f"🔁 Транзакций (24ч): {txns}\n"
                            f"📈 Рост цены (24ч): {price_change}%\n"
                            f"🔗 [Смотреть на DexScreener]({dex_url})"
                        )

                        for user in USER_LIST:
                            try:
                                await app.bot.send_message(chat_id=user, text=message, parse_mode="Markdown")
                            except Exception as e:
                                logging.error(f"Ошибка при отправке пользователю {user}: {e}")

                        MESSAGE_HISTORY.append(message)
                        await asyncio.sleep(3)

                except Exception as e:
                    logging.error(f"Ошибка обработки токена в сети {network}: {e}")

        await asyncio.sleep(600)

# Регистрация команд
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("adduser", add_user))
app.add_handler(CommandHandler("listusers", list_users))
app.add_handler(CommandHandler("sendall", send_to_all))

# Функция основного запуска
async def main():
    logging.info("✅ Бот запущен и работает")
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
        logging.error("Ошибка при запуске бота!")
