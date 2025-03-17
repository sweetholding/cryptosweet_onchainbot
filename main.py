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

# Файлы для хранения пользователей
USER_LOG_FILE = "users.txt"
BANNED_USERS_FILE = "banned_users.txt"

# Список сетей, которые отслеживает бот
NETWORKS = ["solana", "ethereum", "bsc", "bitcoin", "tron", "base", "ton", "xrp", "zora"]

# История последних 20 сообщений
MESSAGE_HISTORY = deque(maxlen=20)

if not TOKEN or not CHAT_ID:
    raise ValueError("Отсутствуют TELEGRAM_BOT_TOKEN или CHAT_ID в переменных окружения!")

# Инициализация бота
app = Application.builder().token(TOKEN).build()

# Загружаем список заблокированных пользователей
def load_banned_users():
    if not os.path.exists(BANNED_USERS_FILE):
        return set()
    with open(BANNED_USERS_FILE, "r", encoding="utf-8") as f:
        return set(int(line.strip()) for line in f)

banned_users = load_banned_users()

# Функция для логирования пользователей
def log_user(user_id, username):
    if user_id in banned_users:
        return  # Если пользователь заблокирован, не добавляем его
    
    user_info = f"{user_id} - {username}\n"
    if not os.path.exists(USER_LOG_FILE):
        with open(USER_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(user_info)
    else:
        with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
            if user_info not in f.read():
                with open(USER_LOG_FILE, "a", encoding="utf-8") as fa:
                    fa.write(user_info)
    logging.info(f"👤 Новый пользователь: {user_info}")

# Команда /start
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Неизвестный"

    # Проверяем, не заблокирован ли пользователь
    if user_id in banned_users:
        await update.message.reply_text("❌ Вы заблокированы и не можете использовать бота!")
        logging.warning(f"⛔ Блокированный пользователь пытался войти: {user_id} ({username})")
        return

    # Логируем пользователя
    log_user(user_id, username)

    # Уведомляем администратора о новом пользователе
    await app.bot.send_message(chat_id=ADMIN_ID, text=f"👤 Новый пользователь: {username} (ID: {user_id})")
    
    await update.message.reply_text("🚀 Бот успешно запущен и следит за рынком!")

    # Отправляем пользователю последние 10 сообщений
    for msg in MESSAGE_HISTORY:
        await update.message.reply_text(msg)

# Команда /users для просмотра всех пользователей
async def get_users(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У вас нет прав для выполнения этой команды!")
        return
    
    if not os.path.exists(USER_LOG_FILE):
        await update.message.reply_text("📂 Список пользователей пуст.")
        return
    
    with open(USER_LOG_FILE, "r", encoding="utf-8") as f:
        users = f.read()
    await update.message.reply_text(f"📜 Список пользователей:\n{users}")

# Функция для мониторинга крупных сделок
async def check_large_transactions():
    for network in NETWORKS:
        url = f"https://api.dexscreener.com/latest/dex/search?q={network}&networkId=mainnet"
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
                base_symbol = token["baseToken"]["symbol"]
                dex_url = token.get("url", "")
                
                if (base_symbol in ["BTC", "ETH"] and volume > 3000000) or (volume > 200000):
                    message = (
                        f"🔥 Крупная сделка по {base_symbol} ({network.upper()})!\n"
                        f"📊 Объем за 24ч: ${volume}\n"
                        f"🔗 [Смотреть на DexScreener]({dex_url})"
                    )
                    logging.info(f"Отправка сообщения: {message}")
                    MESSAGE_HISTORY.append(message)
                    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
                    await asyncio.sleep(3)  # Ограничение 20 сообщений в минуту
            except Exception as e:
                logging.error(f"Ошибка обработки токена в сети {network}: {e}")

# Фоновая проверка рынка
async def check_loop():
    while True:
        logging.info("🔍 Проверка крупных транзакций по сетям...")
        await check_large_transactions()
        await asyncio.sleep(600)  # Каждые 10 минут

# Регистрация команд
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("users", get_users))

# Функция основного запуска
async def main():
    logging.info("✅ Бот запущен и работает")
    asyncio.create_task(check_loop())
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
