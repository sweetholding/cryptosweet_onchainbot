import os
import logging
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import requests
import asyncio

# Настройки логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Применяем nest_asyncio для Railway
nest_asyncio.apply()

# Токен бота и ID чата
TOKEN = "7594557278:AAH3JKXfwupIMLqmmzmjYbH3ToSSTUGnmHo"
CHAT_ID = "423798633"

if not TOKEN or not CHAT_ID:
    raise ValueError("Отсутствуют TELEGRAM_BOT_TOKEN или CHAT_ID в переменных окружения!")

# Инициализация бота
app = Application.builder().token(TOKEN).build()

# Команда /start
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("🚀 Бот успешно запущен и следит за рынком!")

# Функция для проверки крупных транзакций
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
                volume = float(token.get("volume", {}).get("h24", 0))
                base_symbol = token["baseToken"]["symbol"]
                price_change = float(token.get("priceChange", {}).get("h24", 0))
                dex_url = token.get("url", "")
                
                # Фильтр объемов для BTC/ETH и остальных токенов
                if (base_symbol in ["BTC", "ETH"] and volume > 1000000) or (volume > 100000):
                    message = (
                        f"🔥 Крупная сделка по {base_symbol}!\n"
                        f"📊 Объем за 24ч: ${volume}\n"
                        f"📈 Изменение цены: {price_change}%\n"
                        f"🔗 [Смотреть на DexScreener]({dex_url})"
                    )
                    logging.info(f"Отправка сообщения: {message}")
                    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Ошибка обработки токена: {e}")

# Регистрация команд
app.add_handler(CommandHandler("start", start))

# Функция основного запуска
async def main():
    logging.info("✅ Бот запущен и работает")
    asyncio.create_task(check_loop())
    await app.start()
    await app.updater.start_polling()

# Функция для повторной проверки
async def check_loop():
    while True:
        logging.info("🔍 Проверка крупных транзакций...")
        await check_large_transactions()
        await asyncio.sleep(600)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
