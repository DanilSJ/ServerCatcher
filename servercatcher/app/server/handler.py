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
    now_dt = datetime.now(MSK)
    now = now_dt.strftime("%d.%m.%Y %H:%M:%S")

    # Оставляем только те, у которых ip не пустой и дата старта уже наступила
    filtered_servers = []
    for srv in servers_data:
        ip = srv.get('ip')
        if not ip:
            continue
        start_str = srv.get('start') or None
        if start_str:
            try:
                start_dt = datetime.strptime(start_str, "%d/%m/%Y").replace(tzinfo=MSK)
            except Exception:
                start_dt = now_dt
        else:
            start_dt = now_dt
        if start_dt <= now_dt:
            filtered_servers.append(srv)

    if not filtered_servers:
        await message.answer(f"Сейчас нет активных серверов.\nОтчет сформирован: {now}")
        return

    ip_list = "\n".join(f"<b>{idx+1}</b>. {srv.get('ip')}" for idx, srv in enumerate(filtered_servers))
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
        query = select(ServerHistory).where(ServerHistory.server_ip == ip_filter)
        result = await session.execute(query)
        histories = result.scalars().all()

    if not histories:
        await message.answer(f"История для {ip_filter} пуста.")
        return

    # Готовим списки событий и пары добавление-удаление
    both_records = [h for h in histories if h.start is not None and h.end is not None]
    start_only = [h for h in histories if h.start is not None and h.end is None]
    end_only = [h for h in histories if h.start is None and h.end is not None]

    both_records.sort(key=lambda h: (h.start, h.end))
    start_only.sort(key=lambda h: h.start)
    end_only.sort(key=lambda h: h.end)

    lines = [f"📜История для IP {ip_filter}:"]

    # Сначала выводим пары, которые уже содержатся в одной записи
    for rec in both_records:
        start_dt = rec.start.astimezone(MSK)
        end_dt = rec.end.astimezone(MSK)
        days_active = abs((end_dt - start_dt).days)
        lines.append(f"➕Добавлен: {start_dt.strftime('%d.%m.%Y')}")
        lines.append(f"➖ Удален: {end_dt.strftime('%d.%m.%Y')} (размещен {days_active} дней)")

    # Затем попарно связываем раздельные start/end записи и чередуем
    pair_count = min(len(start_only), len(end_only))
    for i in range(pair_count):
        s = start_only[i]
        e = end_only[i]
        start_dt = s.start.astimezone(MSK)
        end_dt = e.end.astimezone(MSK)
        days_active = abs((end_dt - start_dt).days)
        lines.append(f"➕Добавлен: {start_dt.strftime('%d.%m.%Y')}")
        lines.append(f"➖ Удален: {end_dt.strftime('%d.%m.%Y')} (размещен {days_active} дней)")

    # Если остались незакрытые добавления — выводим их
    for s in start_only[pair_count:]:
        start_dt = s.start.astimezone(MSK)
        lines.append(f"➕Добавлен: {start_dt.strftime('%d.%m.%Y')}")

    # Если остались удаления без пары — выводим их без длительности
    for e in end_only[pair_count:]:
        end_dt = e.end.astimezone(MSK)
        lines.append(f"➖ Удален: {end_dt.strftime('%d.%m.%Y')}")

    text = "\n".join(lines)
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        await message.answer(text[i:i+chunk_size])