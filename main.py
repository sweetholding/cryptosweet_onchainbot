import os
import logging
import nest_asyncio
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import requests

# Настройки логирования
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Применяем nest_asyncio для совместимости с Railway
nest_asyncio.apply()

# Токен бота и ID чата
TOKEN = "7594557278:AAH3JKXfwupIMLqmmzmjYbH3ToSSTUGnmHo"
CHAT_ID = "423798633"

if not TOKEN or not CHAT_ID:
    raise ValueError("Отсутствуют TELEGRAM_BOT_TOKEN или CHAT_ID!")

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
                volume = float(token.get("volume", {}).get("h24", 0))
                price_change = float(token.get("priceChange", {}).get("h24", 0))
                symbol = token["baseToken"]["symbol"].upper()

                # Динамический порог
                if symbol in ["BTC", "ETH"]:
                    threshold = 1000000
                else:
                    threshold = 100000
                
                if volume > threshold:
                    message = (
                        f"🔥 Крупное движение по {symbol}!
"
                        f"📊 Объем за 24ч: ${volume:,.2f}
"
                        f"🔗 [Смотреть на DexScreener]({token['url']})"
                    )
                    await app.bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Ошибка обработки токена: {e}")

# Регистрация команд
app.add_handler(CommandHandler("start", start))

# Запуск бота
async def main():
    logging.info("✅ Бот запущен и работает")
    asyncio.create_task(check_loop())
    await app.run_polling()

async def check_loop():
    while True:
        await check_large_transactions()
        await asyncio.sleep(600)  # Проверка раз в 10 минут

if __name__ == "__main__":
    asyncio.run(main())
