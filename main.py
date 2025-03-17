import os
import logging
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import requests
import asyncio

# Настройки логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Применяем nest_asyncio для совместимости с Railway
nest_asyncio.apply()

# Токен бота и ID чата из переменных Railway
TOKEN = "7594557278:AAH3JKXfwupIMLqmmzmjYbH3ToSSTUGnmHo"
CHAT_ID = "423798633"

# Проверка наличия токена
if not TOKEN or not CHAT_ID:
    raise ValueError("Отсутствуют TELEGRAM_BOT_TOKEN или CHAT_ID в переменных окружения!")

# Инициализация бота
app = Application.builder().token(TOKEN).build()

# Команда /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("🚀 Бот успешно запущен и следит за рынком!")

# Проверка крупных транзакций
async def check_large_transactions():
    url = "https://api.dexscreener.com/latest/dex/tokens"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logging.error(f"Ошибка запроса к DexScreener: {e}")
        return
    
    if "pairs" in data:
        for token in data["pairs"]:
            try:
                symbol = token['baseToken']['symbol']
                volume = float(token.get("volume", {}).get("h24", 0))
                price_change = float(token.get("priceChange", {}).get("h24", 0))
                
                # Определяем минимальный порог сделки
                min_threshold = 100000  # Для всех токенов
                if symbol in ["BTC", "ETH"]:
                    min_threshold = 1000000  # Для BTC и ETH
                
                if volume >= min_threshold:
                    message = (
                        f"🔥 Крупная транзакция по {symbol}!
"
                        f"📊 Объем за 24ч: ${volume}
"
                        f"📈 Изменение цены: {price_change}%
"
                        f"🔗 [Смотреть на DexScreener]({token['url']})"
                    )
                    bot = app.bot
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Ошибка обработки токена: {e}")

# Регистрация команд
app.add_handler(CommandHandler("start", start))

# Запуск бота
async def run():
    async with app:
        logging.info("✅ Бот запущен и работает")
        asyncio.create_task(check_loop())
        await app.run_polling()

async def check_loop():
    while True:
        await check_large_transactions()
        await asyncio.sleep(600)  # Проверка раз в 10 минут

if __name__ == "__main__":
    asyncio.run(run())
