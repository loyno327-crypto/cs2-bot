"""
Слот-машина: игрок выбирает ставку (от config.SLOT_BET_MIN до
config.SLOT_BET_MAX), крутит 3 барабана. Выигрыш начисляется ТОЛЬКО если
все три символа совпали — множитель зависит от символа (см.
config.SLOT_PAYOUTS). Если не совпали — ставка сгорает полностью и
уходит в копилку джекпота, как и другие "проигранные" игроками монеты.

Если сейчас идёт тематический ивент с money_multiplier — выигрыш
дополнительно умножается на него (см. database.get_active_event).
"""

import random

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
import config
from handlers import cases

router = Router()


def bet_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"{bet} монет", callback_data=f"slot_bet:{bet}")]
        for bet in config.SLOT_BET_OPTIONS
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _spin_reels() -> list[str]:
    return random.choices(config.SLOT_SYMBOLS, weights=config.SLOT_WEIGHTS, k=3)


@router.message(F.text == "🎲 Слот")
async def show_slot_menu(message: Message):
    user_id = message.from_user.id
    db.get_or_create_user(
        user_id, message.from_user.username or message.from_user.full_name
    )

    payouts_lines = "\n".join(
        f"{symbol}{symbol}{symbol} — x{config.SLOT_PAYOUTS[symbol]}"
        for symbol in config.SLOT_SYMBOLS
    )

    await message.answer(
        "🎲 <b>Слот</b>\n\n"
        f"Выбери ставку (от {config.SLOT_BET_MIN} до {config.SLOT_BET_MAX} монет). "
        "Три одинаковых символа на барабанах — выигрыш! Не совпало — ставка сгорает.\n\n"
        f"<b>Таблица выплат</b> (за 3 одинаковых):\n{payouts_lines}",
        reply_markup=bet_keyboard()
    )


@router.callback_query(F.data.startswith("slot_bet:"))
async def spin_slot(callback: CallbackQuery):
    user_id = callback.from_user.id
    bet = int(callback.data.split(":")[1])

    balance = db.get_balance(user_id)
    if balance < bet:
        await callback.answer(f"Недостаточно монет! Нужно {bet}, у тебя {balance}.", show_alert=True)
        return

    db.add_balance(user_id, -bet)
    db.increment_stat(user_id, "slot_spins")

    reels = _spin_reels()
    won = reels[0] == reels[1] == reels[2]

    reels_line = " | ".join(reels)

    if won:
        symbol = reels[0]
        payout = bet * config.SLOT_PAYOUTS[symbol]

        event = db.get_active_event()
        if event and event["money_multiplier"] != 1.0:
            payout = int(round(payout * event["money_multiplier"]))

        db.add_balance(user_id, payout)
        db.increment_stat(user_id, "slot_wins")
        result = db.add_xp(user_id, config.XP_SLOT_SPIN)

        text = (
            f"🎲 [ {reels_line} ]\n\n"
            f"🎉 Выигрыш! Три {symbol} подряд — получаешь <b>{payout}</b> монет "
            f"(ставка была {bet})."
        )
        text += cases.level_up_notice(result)
    else:
        # Сгоревшая ставка уходит в копилку джекпота — так же, как комиссия
        # с дуэлей и сгоревшие при апгрейде предметы.
        db.add_to_jackpot(bet)
        result = db.add_xp(user_id, config.XP_SLOT_SPIN)

        text = (
            f"🎲 [ {reels_line} ]\n\n"
            f"😔 Не повезло — ставка <b>{bet}</b> монет сгорела."
        )
        text += cases.level_up_notice(result)

    await callback.message.edit_text(text, reply_markup=bet_keyboard())
    await callback.answer()
