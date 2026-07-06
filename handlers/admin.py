import random
import html

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

import asyncio

import config
import database as db
from handlers.start import main_menu_keyboard

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# Список всех секретных админ-команд с кратким описанием — используется
# командой /admin_help, чтобы не приходилось лезть в код и вспоминать,
# что вообще есть в боте.
ADMIN_COMMANDS = [
    ("/give <user_id> <amount>", "Начислить (или списать, если amount отрицательный) монеты игроку."),
    ("/set_user <user_id> <поле> <значение>", "Изменить ЛЮБОЕ поле игрока: balance, level, xp, username и т.д."),
    ("/broadcast <текст>", "Разослать сообщение всем зарегистрированным пользователям."),
    ("/update_menu", "Разослать всем актуальную клавиатуру меню (если она не обновилась)."),
    ("/stats_global", "Общая статистика бота: игроки, экономика, кейсы, дуэли и т.д."),
    ("/force_jackpot <сумма> <кол-во победителей>", "Принудительно разыграть джекпот прямо сейчас, с любой суммой и числом победителей."),
    ("/remove_from_top_drops <user_id>", "Убрать одного игрока из топа по дропу (не трогает его инвентарь)."),
    ("/clear_top_drops", "Полностью обнулить топ по дропу для всех игроков (не трогает инвентари)."),
    ("/start_event <часы> <xp_множитель> <монеты_множитель> <скидка%> <название>", "Запустить тематический ивент на заданное время."),
    ("/stop_event", "Досрочно завершить текущий ивент."),
    ("/admin_help", "Показать этот список команд."),
]


@router.message(Command("give"))
async def cmd_give(message: Message):
    """Секретная команда: /give <user_id> <amount>
    Работает ТОЛЬКО для ID из config.ADMIN_IDS. Для всех остальных
    пользователей бот делает вид, что такой команды не существует —
    никакого ответа не отправляется, чтобы не палить её наличие.
    """
    if not _is_admin(message.from_user.id):
        return  # молча игнорируем — команда как будто не существует

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "Использование: <code>/give user_id amount</code>\n"
            "Пример: <code>/give 123456789 5000</code>"
        )
        return

    try:
        target_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("user_id и amount должны быть целыми числами.")
        return

    # Начисляем (amount может быть и отрицательным, чтобы забрать монеты)
    db.get_or_create_user(target_id, None)
    db.add_balance(target_id, amount)
    new_balance = db.get_balance(target_id)

    await message.answer(
        f"✅ Готово.\n"
        f"Пользователю <code>{target_id}</code> начислено <b>{amount}</b> монет.\n"
        f"Текущий баланс: <b>{new_balance}</b>."
    )

    if target_id != message.from_user.id:
        try:
            await message.bot.send_message(
                target_id,
                f"💰 Тебе начислено <b>{amount}</b> монет администратором!"
            )
        except Exception:
            pass


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot):
    """Секретная команда: /broadcast текст сообщения
    Отправляет текст всем зарегистрированным пользователям бота.
    Доступна только админам, как и /give."""
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(
            "Использование: <code>/broadcast текст сообщения</code>\n"
            "Пример: <code>/broadcast Привет всем! Скоро новый ивент 🎉</code>"
        )
        return

    content = parts[1]
    user_ids = db.get_all_user_ids()
    status_msg = await message.answer(f"📢 Начинаю рассылку для {len(user_ids)} пользователей...")

    sent, failed = 0, 0
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, content)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # не спамим Telegram API слишком быстро

    await status_msg.edit_text(
        f"📢 Рассылка завершена.\n"
        f"✅ Доставлено: {sent}\n"
        f"❌ Не доставлено (бот заблокирован и т.п.): {failed}"
    )


@router.message(Command("update_menu"))
async def cmd_update_menu(message: Message, bot: Bot):
    """Секретная команда: /update_menu
    Решает проблему "после обновления бота меню внизу не обновилось".

    Дело в том, что Telegram-клиент запоминает клавиатуру (reply-кнопки
    внизу экрана) с прошлого раза, когда бот её присылал, и НЕ обновляет
    её сам по себе, даже если в коде бота кнопки поменялись — новую
    клавиатуру клиент подхватит только когда бот в следующий раз пришлёт
    сообщение с reply_markup. Чистить историю чата для этого не нужно —
    это отдельное, необратимое действие, которое к тому же бот не может
    сделать за пользователя.

    Эта команда просто рассылает всем пользователям короткое сообщение
    с АКТУАЛЬНОЙ клавиатурой — после этого у всех она обновится сама,
    без необходимости просить всех вручную нажать /start."""
    if not _is_admin(message.from_user.id):
        return

    user_ids = db.get_all_user_ids()
    status_msg = await message.answer(f"🔄 Обновляю меню для {len(user_ids)} пользователей...")

    sent, failed = 0, 0
    for user_id in user_ids:
        try:
            await bot.send_message(
                user_id,
                "🔄 Меню бота обновлено — загляни, там могли появиться новые кнопки!",
                reply_markup=main_menu_keyboard()
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"🔄 Обновление меню завершено.\n"
        f"✅ Доставлено: {sent}\n"
        f"❌ Не доставлено (бот заблокирован и т.п.): {failed}"
    )


@router.message(Command("stats_global"))
async def cmd_global_stats(message: Message):
    """Секретная команда: общая статистика бота (только для админов)."""
    if not _is_admin(message.from_user.id):
        return

    s = db.get_global_stats()
    text = (
        f"📊 <b>Общая статистика бота</b>\n\n"
        f"👥 Игроков зарегистрировано: <b>{s['users_count']}</b>\n"
        f"💰 Суммарный баланс всех игроков: <b>{s['total_balance']}</b>\n"
        f"📈 Всего заработано за всё время: <b>{s['total_earned']}</b>\n"
        f"📉 Всего потрачено/проиграно: <b>{s['total_spent']}</b>\n\n"
        f"🎁 Кейсов открыто: <b>{s['cases_opened']}</b>\n"
        f"⚔️ Дуэлей сыграно: <b>{s['duels_played']}</b>\n"
        f"🛠 Апгрейдов удачных/сгоревших: <b>{s['upgrades_success']}</b> / "
        f"<b>{s['upgrades_failed']}</b>\n\n"
        f"📦 Предметов в инвентарях всех игроков: <b>{s['items_count']}</b>\n"
        f"💎 Их суммарная стоимость: <b>{s['items_total_value']}</b>\n\n"
        f"🎰 Сейчас в копилке джекпота: <b>{s['jackpot_amount']}</b> монет"
    )
    await message.answer(text)


@router.message(Command("admin_help"))
async def cmd_admin_help(message: Message):
    """Секретная команда: /admin_help
    Показывает список всех админ-команд бота с кратким описанием —
    удобно, когда забыл, что вообще есть в боте."""
    if not _is_admin(message.from_user.id):
        return

    lines = ["🛠 <b>Админ-команды бота</b>\n"]
    for cmd, description in ADMIN_COMMANDS:
        safe_cmd = html.escape(cmd)
        lines.append(f"<code>{safe_cmd}</code>\n{description}\n")

    await message.answer("\n".join(lines))


@router.message(Command("set_user"))
async def cmd_set_user(message: Message):
    """Секретная команда: /set_user <user_id> <поле> <значение>
    Позволяет изменить ЛЮБОЕ разрешённое поле игрока напрямую (в отличие
    от /give, которая только ДОБАВЛЯЕТ монеты, тут значение УСТАНАВЛИВАЕТСЯ
    как есть). Список разрешённых полей — database.EDITABLE_USER_FIELDS."""
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=3)
    if len(parts) != 4:
        fields_str = ", ".join(sorted(db.EDITABLE_USER_FIELDS.keys()))
        await message.answer(
            "Использование: <code>/set_user user_id поле значение</code>\n"
            "Пример: <code>/set_user 123456789 level 25</code>\n\n"
            f"Доступные поля: {fields_str}"
        )
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("user_id должен быть целым числом.")
        return

    field = parts[2]
    raw_value = parts[3]

    if field not in db.EDITABLE_USER_FIELDS:
        fields_str = ", ".join(sorted(db.EDITABLE_USER_FIELDS.keys()))
        await message.answer(f"Недопустимое поле «{field}».\nДоступные поля: {fields_str}")
        return

    field_type = db.EDITABLE_USER_FIELDS[field]
    try:
        value = field_type(raw_value)
    except ValueError:
        await message.answer(f"Значение для «{field}» должно быть типа {field_type.__name__}.")
        return

    db.get_or_create_user(target_id, None)
    db.set_user_field(target_id, field, value)

    await message.answer(
        f"✅ Готово.\n"
        f"Пользователю <code>{target_id}</code> установлено «{field}» = <b>{value}</b>."
    )

    if target_id != message.from_user.id:
        try:
            await message.bot.send_message(
                target_id,
                f"⚙️ Администратор изменил твой параметр «{field}»."
            )
        except Exception:
            pass


@router.message(Command("force_jackpot"))
async def cmd_force_jackpot(message: Message, bot: Bot):
    """Секретная команда: /force_jackpot <сумма> <кол-во победителей>
    Принудительно разыгрывает джекпот ПРЯМО СЕЙЧАС, независимо от
    расписания (config.JACKPOT_DRAW_TIMES) и от того, сколько сейчас
    накоплено в копилке — сумму и число победителей выбирает админ.
    Если в копилке накоплено меньше запрошенной суммы, недостающее
    фактически допечатывается (как и при /give), а копилка обнуляется."""
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "Использование: <code>/force_jackpot сумма кол-во_победителей</code>\n"
            "Пример: <code>/force_jackpot 50000 5</code>"
        )
        return

    try:
        amount = int(parts[1])
        winners_count = int(parts[2])
    except ValueError:
        await message.answer("Сумма и количество победителей должны быть целыми числами.")
        return

    if amount <= 0 or winners_count <= 0:
        await message.answer("Сумма и количество победителей должны быть положительными.")
        return

    all_user_ids = db.get_all_user_ids()
    if len(all_user_ids) < winners_count:
        await message.answer(
            f"В боте всего {len(all_user_ids)} игроков — не могу выбрать {winners_count} победителей."
        )
        return

    winners = random.sample(all_user_ids, winners_count)
    amount_each = amount // winners_count

    for winner_id in winners:
        db.add_balance(winner_id, amount_each)
        db.increment_stat(winner_id, "jackpot_wins")
    db.force_draw_jackpot(winners, amount_each)

    names = []
    for winner_id in winners:
        user = db.get_or_create_user(winner_id, None)
        name = user["username"] if user["username"] else f"id{winner_id}"
        names.append(f"@{name}" if user["username"] else name)
    names_str = ", ".join(names)

    announcement = (
        f"🎰 <b>Внеплановый джекпот разыгран администратором!</b>\n\n"
        f"Победители: {names_str}\n"
        f"Каждый из них получил <b>{amount_each}</b> монет!\n\n"
        f"Удачи в следующий раз! 🍀"
    )

    status_msg = await message.answer(f"🎰 Разыгрываю джекпот среди {len(all_user_ids)} игроков...")

    sent, failed = 0, 0
    for user_id in all_user_ids:
        try:
            await bot.send_message(user_id, announcement)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ Джекпот разыгран: {names_str}, по {amount_each} монет каждому.\n"
        f"📢 Уведомлено: {sent}, не доставлено: {failed}."
    )


@router.message(Command("remove_from_top_drops"))
async def cmd_remove_from_top_drops(message: Message):
    """Секретная команда: /remove_from_top_drops <user_id>
    Убирает ОДНОГО игрока из топа по дропу (кнопка «🏆 Топ» -> «💎 По дропу»),
    удаляя всю его историю из журнала drop_log. Текущий инвентарь игрока
    НЕ трогается — предметы у него остаются, просто пропадают из топа."""
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(
            "Использование: <code>/remove_from_top_drops user_id</code>\n"
            "Пример: <code>/remove_from_top_drops 123456789</code>"
        )
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("user_id должен быть целым числом.")
        return

    removed = db.remove_user_drop_log(target_id)

    if removed == 0:
        await message.answer(f"У игрока <code>{target_id}</code> и так не было записей в топе по дропу.")
        return

    await message.answer(
        f"✅ Готово. Игрок <code>{target_id}</code> убран из топа по дропу "
        f"(удалено записей: {removed}). Инвентарь игрока не тронут."
    )


@router.message(Command("clear_top_drops"))
async def cmd_clear_top_drops(message: Message):
    """Секретная команда: /clear_top_drops
    Полностью обнуляет топ по дропу — для ВСЕХ игроков сразу. Инвентари
    игроков не трогаются, обнуляется только история для топа (drop_log)."""
    if not _is_admin(message.from_user.id):
        return

    removed = db.clear_drop_log()
    await message.answer(
        f"✅ Топ по дропу полностью обнулён (удалено записей: {removed}). "
        f"Инвентари игроков не тронуты."
    )


@router.message(Command("start_event"))
async def cmd_start_event(message: Message, bot: Bot):
    """Секретная команда: /start_event <часы> <xp_множитель> <монеты_множитель> <скидка%> <название>
    Запускает тематический ивент на заданное количество часов. На время
    ивента:
      - весь получаемый опыт (работа, кейсы, дуэли, апгрейд, краш, слоты)
        умножается на xp_множитель;
      - награда за "Работу" и ежедневный бонус умножается на монеты_множитель;
      - цена всех кейсов дополнительно снижается на скидка% (складывается
        с уровневой скидкой игрока, суммарно не больше 90%).
    Повторный вызов команды перезаписывает текущий ивент (можно использовать,
    чтобы продлить или изменить уже идущий ивент).
    Пример: <code>/start_event 24 2 1.5 10 Хэллоуин</code> — сутки, x2 к опыту,
    x1.5 к наградам, -10% на кейсы, название "Хэллоуин".
    """
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=5)
    if len(parts) != 6:
        await message.answer(
            "Использование:\n"
            "<code>/start_event часы xp_множитель монеты_множитель скидка% название</code>\n\n"
            "Пример: <code>/start_event 24 2 1.5 10 Хэллоуин</code>\n"
            "(сутки, x2 к опыту, x1.5 к наградам, -10% на кейсы, название «Хэллоуин»)"
        )
        return

    try:
        hours = float(parts[1])
        xp_multiplier = float(parts[2])
        money_multiplier = float(parts[3])
        case_discount = int(parts[4])
    except ValueError:
        await message.answer("часы/xp_множитель/монеты_множитель/скидка% должны быть числами.")
        return

    title = parts[5]

    if not (0 < hours <= config.EVENT_MAX_HOURS):
        await message.answer(f"Длительность должна быть от 0 до {config.EVENT_MAX_HOURS} часов.")
        return
    if not (0 < xp_multiplier <= config.EVENT_MAX_XP_MULTIPLIER):
        await message.answer(f"xp_множитель должен быть от 0 до {config.EVENT_MAX_XP_MULTIPLIER}.")
        return
    if not (0 < money_multiplier <= config.EVENT_MAX_MONEY_MULTIPLIER):
        await message.answer(f"монеты_множитель должен быть от 0 до {config.EVENT_MAX_MONEY_MULTIPLIER}.")
        return
    if not (0 <= case_discount <= config.EVENT_MAX_CASE_DISCOUNT):
        await message.answer(f"скидка% должна быть от 0 до {config.EVENT_MAX_CASE_DISCOUNT}.")
        return

    db.start_event(title, hours, xp_multiplier, money_multiplier, case_discount, message.from_user.id)

    bonus_lines = []
    if xp_multiplier != 1.0:
        bonus_lines.append(f"⭐ Опыт: x{xp_multiplier:.2g}")
    if money_multiplier != 1.0:
        bonus_lines.append(f"💰 Награды за работу и бонус: x{money_multiplier:.2g}")
    if case_discount > 0:
        bonus_lines.append(f"🎁 Доп. скидка на кейсы: -{case_discount}%")
    bonus_text = "\n".join(bonus_lines) if bonus_lines else "(без бонусов — просто тематическое название)"

    hours_str = f"{hours:g}"
    announcement = (
        f"🔥 <b>Запущен ивент: {title}!</b>\n\n"
        f"{bonus_text}\n\n"
        f"⏳ Длительность: {hours_str} ч.\n"
        f"Загляни в «🔥 Ивент» в меню, чтобы посмотреть подробности!"
    )

    all_user_ids = db.get_all_user_ids()
    status_msg = await message.answer(f"🔥 Запускаю ивент «{title}» и рассылаю анонс {len(all_user_ids)} игрокам...")

    sent, failed = 0, 0
    for user_id in all_user_ids:
        try:
            await bot.send_message(user_id, announcement)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ Ивент «{title}» запущен на {hours_str} ч.\n"
        f"📢 Уведомлено: {sent}, не доставлено: {failed}."
    )


@router.message(Command("stop_event"))
async def cmd_stop_event(message: Message, bot: Bot):
    """Секретная команда: /stop_event
    Досрочно завершает текущий ивент (если он идёт) и уведомляет всех игроков."""
    if not _is_admin(message.from_user.id):
        return

    event = db.get_active_event()
    if not event:
        await message.answer("Сейчас никакой ивент не идёт — завершать нечего.")
        return

    db.stop_event()

    announcement = f"🔥 Ивент «{event['title'] or 'без названия'}» завершён администратором."
    all_user_ids = db.get_all_user_ids()
    status_msg = await message.answer(f"🔥 Завершаю ивент и уведомляю {len(all_user_ids)} игроков...")

    sent, failed = 0, 0
    for user_id in all_user_ids:
        try:
            await bot.send_message(user_id, announcement)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ Ивент завершён.\n"
        f"📢 Уведомлено: {sent}, не доставлено: {failed}."
    )
