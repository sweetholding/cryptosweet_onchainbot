from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import requests
import asyncio

TOKEN = "7594557278:AAH3JKXfwupIMLqmmzmjYbH3ToSSTUGnmHo"
CHAT_ID = "423798633"

async def start(update: Update, context):
    await update.message.reply_text("🚀 Бот успешно запущен и следит за рынком!")

async def check_transactions():
    url = "https://api.dexscreener.com/latest/dex/tokens"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for token in data["pairs"]:
            if float(token["priceChange"]["h24"]) > 30:  
                message = f"🚀 Токен {token['baseToken']['name']} вырос на {token['priceChange']['h24']}%!\nСсылка: {token['url']}"
                async with Application.builder().token(TOKEN).build() as bot:
                    await bot.bot.send_message(chat_id=CHAT_ID, text=message)

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("✅ Бот запущен...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())


