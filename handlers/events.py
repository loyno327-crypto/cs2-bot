"""
Публичный экран ивента: показывает, идёт ли сейчас тематический ивент
(запускается админом через /start_event в handlers/admin.py) и какие
бонусы он даёт. Управление ивентом (запуск/остановка) — только у админов,
а посмотреть статус может любой игрок.
"""

from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message

import database as db

router = Router()


def _format_remaining(ends_at_str: str) -> str:
    remaining = datetime.fromisoformat(ends_at_str) - datetime.now()
    total_seconds = max(int(remaining.total_seconds()), 0)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours > 0:
        return f"{hours} ч {minutes} мин"
    return f"{minutes} мин"


@router.message(F.text == "🔥 Ивент")
async def show_event_status(message: Message):
    db.get_or_create_user(
        message.from_user.id,
        message.from_user.username or message.from_user.full_name
    )

    event = db.get_active_event()

    if not event:
        await message.answer(
            "🔥 <b>Ивент</b>\n\n"
            "Сейчас никаких тематических ивентов не проходит. "
            "Следи за анонсами — админы могут запустить ивент с усиленным "
            "опытом, наградами или скидками на кейсы!"
        )
        return

    lines = [f"🔥 <b>Идёт ивент: {event['title'] or 'Без названия'}</b>\n"]

    if event["xp_multiplier"] != 1.0:
        lines.append(f"⭐ Опыт (XP): x{event['xp_multiplier']:.2g}")
    if event["money_multiplier"] != 1.0:
        lines.append(f"💰 Награды за работу и бонус: x{event['money_multiplier']:.2g}")
    if event["case_discount_percent"] > 0:
        lines.append(f"🎁 Доп. скидка на кейсы: -{event['case_discount_percent']}%")

    lines.append(f"\n⏳ До конца ивента: {_format_remaining(event['ends_at'])}")

    await message.answer("\n".join(lines))
