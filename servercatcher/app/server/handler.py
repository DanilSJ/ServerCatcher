from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from datetime import datetime, timezone, timedelta
from servercatcher.core.models import db_helper
from .crud import get_active_servers, get_all_servers

MSK = timezone(timedelta(hours=3))
router = Router()

@router.message(Command("main"))
async def cmd_main(message: Message):
    async with db_helper.session_factory() as session:
        servers = await get_active_servers(session)

    now = datetime.now(MSK).strftime("%d.%m.%Y %H:%M:%S")

    if not servers:
        await message.answer(f"Сейчас нет активных серверов.\nОтчет сформирован: {now}")
        return

    # Формируем одно сообщение с IP всех серверов
    ip_list = "\n".join(f"{idx+1}. {server.ip_adress}" for idx, server in enumerate(servers))
    text = f"Рекламируемые серверы на главной:\n{ip_list}\n\nОтчет сформирован: {now}"

    await message.answer(text)


@router.message(Command("history"))
async def cmd_history(message: Message):
    async with db_helper.session_factory() as session:
        servers = await get_all_servers(session)

    if not servers:
        await message.answer("История серверов пуста.")
        return

    lines = []
    for server in servers:
        start = server.start.astimezone(MSK).strftime("%d.%m.%Y %H:%M:%S")
        end = server.end.astimezone(MSK).strftime("%d.%m.%Y %H:%M:%S")
        days_active = (server.end - server.start).days
        lines.append(
            f"История для IP {server.ip_adress}:\n"
            f"Добавлен: {start}\n"
            f"Удален: {end} (размещен {days_active} дней)\n"
        )

    text = "\n".join(lines)
    await message.answer(text)