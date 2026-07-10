from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import database as db

router = Router()

NEW_BOT_URL = "https://t.me/Avermancasinobot"

MIGRATION_TEXT = (
    "🚀 <b>Мы переехали в новый бот!</b>\n\n"
    "Этот бот больше не используется — все игры тут отключены.\n"
    "Твой баланс никуда не делся, всё сохранено.\n\n"
    "Переходи в нового бота и попробуй там новое приложение (Web App) прямо в чате 👇"
)


def new_bot_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Перейти в новый бот", url=NEW_BOT_URL)]
    ])


@router.message(CommandStart())
async def cmd_start(message: Message):
    # Регистрацию пользователя оставляем — это дешёво и не мешает,
    # но реального смысла (кроме статистики) уже не несёт.
    db.get_or_create_user(
        message.from_user.id,
        message.from_user.username or message.from_user.full_name
    )
    await message.answer(
        MIGRATION_TEXT,
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer(
        "Жми кнопку ниже, чтобы открыть нового бота:",
        reply_markup=new_bot_keyboard()
    )


# Раньше тут жили обработчики игровых кнопок (Баланс, Инвентарь и т.д.) —
# все они удалены вместе с остальными хендлерами (см. bot.py — там
# теперь подключены только admin.router и этот router). Любое сообщение,
# кроме /start, ловит catch_all ниже и просто повторяет напоминание
# о переезде, чтобы старые кнопки/привычки не приводили в тупик.
@router.message()
async def catch_all(message: Message):
    await message.answer(MIGRATION_TEXT, reply_markup=new_bot_keyboard())
