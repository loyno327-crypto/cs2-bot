import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
from database import init_db
from handlers import start, admin


async def main():
    logging.basicConfig(level=logging.INFO)

    if not config.BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN не задан. Укажи переменную окружения BOT_TOKEN "
            "в настройках проекта на bothost.ru (Environment variables)."
        )

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    init_db()

    dp.include_router(admin.router)
    dp.include_router(start.router)

    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен (режим 'переехали в другого бота'). Нажми Ctrl+C, чтобы остановить.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
