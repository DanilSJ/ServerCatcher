from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from datetime import datetime, timezone, timedelta
from servercatcher.core.models import db_helper
from servercatcher.core.models.server import ServerHistory
from sqlalchemy import select
from servercatcher.app.server.crud import get_active_servers, get_all_servers

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

    ip_list = "\n".join(f"<b>{idx+1}</b>. {server.ip_adress}" for idx, server in enumerate(servers))
    text = f"""
📌Рекламируемые серверы на главной:
{ip_list}

⏰Отчет сформирован: <b>{now} МСК</b>"""

    await message.answer(text, parse_mode="HTML")


@router.message(Command("history"))
async def cmd_history(message: Message):
    args = message.text.split()
    ip_filter = args[1] if len(args) > 1 else None
    async with db_helper.session_factory() as session:
        query = select(ServerHistory).order_by(ServerHistory.server_ip, ServerHistory.start)
        if ip_filter:
            query = query.where(ServerHistory.server_ip == ip_filter)
        result = await session.execute(query)
        histories = result.scalars().all()

    if not histories:
        await message.answer("История серверов пуста." if not ip_filter else f"История для {ip_filter} пуста.")
        return

    lines = []
    current_ip = None
    for hist in histories:
        if hist.server_ip != current_ip:
            lines.append(f"\n📜История для IP {hist.server_ip}:")
            current_ip = hist.server_ip
        start = hist.start.astimezone(MSK).strftime("%d.%m.%Y")
        if hist.end:
            end = hist.end.astimezone(MSK).strftime("%d.%m.%Y")
            days_active = abs((hist.end - hist.start).days)
            lines.append(f"➕Добавлен: {start}")
            lines.append(f"➖Удален: {end} (размещен {days_active} дней)")
        else:
            lines.append(f"➕Добавлен: {start}")
            lines.append(f"➖Удален: ещё активен (размещен ? дней)")

    text = "\n".join(lines)
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        await message.answer(text[i:i+chunk_size])