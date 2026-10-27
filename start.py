import asyncio
import uvicorn
from bot import dp, bot
from main import app

async def start_bot():
    print("🤖 Бот запускается...")
    await dp.start_polling(bot)

async def start_web():
    print("🌐 Сайт запускается на порту 8000...")
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # Запускаем бота и веб-сервер одновременно
    await asyncio.gather(
        start_bot(),
        start_web()
    )

if name == "main":
    asyncio.run(main())
