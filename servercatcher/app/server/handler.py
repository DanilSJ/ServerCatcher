from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from datetime import datetime, timezone, timedelta
from servercatcher.core.models import db_helper
from servercatcher.core.models.server import ServerHistory
from sqlalchemy import select
from servercatcher.app.server.crud import get_active_servers, get_all_servers
from servercatcher.app.notification.handler import fetch_servers_from_link

MSK = timezone(timedelta(hours=3))
router = Router()

@router.message(Command("main"))
async def cmd_main(message: Message):
    servers_data = await fetch_servers_from_link()
    now = datetime.now(MSK).strftime("%d.%m.%Y %H:%M:%S")

    # Оставляем только те, у которых ip не пустой
    servers_data = [srv for srv in servers_data if srv.get('ip')]

    if not servers_data:
        await message.answer(f"Сейчас нет активных серверов.\nОтчет сформирован: {now}")
        return

    ip_list = "\n".join(f"<b>{idx+1}</b>. {srv.get('ip')}" for idx, srv in enumerate(servers_data))
    text = f"""
📌Рекламируемые серверы на главной:
{ip_list}

⏰Отчет сформирован: <b>{now} МСК</b>"""

    await message.answer(text, parse_mode="HTML")


@router.message(Command("history"))
async def cmd_history(message: Message):
    args = message.text.split()
    if len(args) == 1:
        await message.answer("Пожалуйста, укажите IP-адрес после команды.")
        return
    ip_filter = args[1]
    async with db_helper.session_factory() as session:
        query = select(ServerHistory).order_by(ServerHistory.server_ip, ServerHistory.start)
        query = query.where(ServerHistory.server_ip == ip_filter)
        result = await session.execute(query)
        histories = result.scalars().all()

    if not histories:
        await message.answer(f"История для {ip_filter} пуста.")
        return

    lines = []
    current_ip = None
    for hist in histories:
        if hist.server_ip != current_ip:
            lines.append(f"\n📜История для IP {hist.server_ip}:")
            current_ip = hist.server_ip
        if hist.start is None and hist.end is not None:
            end = hist.end.astimezone(MSK).strftime("%d.%m.%Y")
            # Ищем запись с start для того же IP, чтобы посчитать дни
            start_record = next((h for h in histories if h.server_ip == hist.server_ip and h.start is not None), None)
            if start_record:
                days_active = abs((hist.end - start_record.start).days)
                lines.append(f"➖ Удален: {end} (размещен {days_active} дней)")
            else:
                lines.append(f"➖ Удален: {end} - {hist.server_ip}")
        elif hist.start and hist.end:
            start = hist.start.astimezone(MSK).strftime("%d.%m.%Y")
            end = hist.end.astimezone(MSK).strftime("%d.%m.%Y")
            days_active = abs((hist.end - hist.start).days)
            lines.append(f"➕Добавлен: {start}")
            # Ищем запись об удалении для этого сервера
            removal_record = next((h for h in histories if h.server_ip == hist.server_ip and h.start is None and h.end), None)
            if removal_record:
                removal_end = removal_record.end.astimezone(MSK).strftime("%d.%m.%Y")
                lines.append(f"➖Удален: {removal_end} (размещен {days_active} дней) - {removal_record.server_ip}")
            else:
                lines.append(f"➖Удален: {end} (размещен {days_active} дней) ")
        elif hist.start:
            start = hist.start.astimezone(MSK).strftime("%d.%m.%Y")
            lines.append(f"➕Добавлен: {start}")

    text = "\n".join(lines)
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        await message.answer(text[i:i+chunk_size])