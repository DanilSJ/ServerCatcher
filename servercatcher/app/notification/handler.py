import json

import aiohttp
import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from servercatcher.core.models import db_helper
from servercatcher.core.models.server import Server
from servercatcher.core.models.user import User
from servercatcher.core.config import bot

MSK = timezone(timedelta(hours=3))
CHECK_INTERVAL = 60  # Проверка каждые 60 секунд
PASTEBIN_URL = "https://pastebin.com/raw/DnHHkrxx"


async def fetch_servers_from_link() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(PASTEBIN_URL) as resp:
            text = await resp.text()
            data = json.loads(text)  # Преобразуем текст в JSON
            return data.get("servers", [])


async def add_new_servers_to_db(session: AsyncSession, servers_data: list[dict]) -> list[Server]:
    """Добавляет новые серверы в базу и возвращает список добавленных серверов"""
    new_servers = []

    for srv in servers_data:
        ip = srv.get("ip")
        if not ip:  # Пропускаем серверы без IP
            continue

        # Проверка по IP, чтобы не добавлять дубликаты
        result = await session.execute(select(Server).where(Server.ip_adress == ip))
        exists = result.scalars().first()
        if exists:
            continue

        # Безопасное преобразование дат
        start_str = srv.get("start", "")
        end_str = srv.get("end", "")

        start = datetime.strptime(start_str, "%d/%m/%Y").replace(tzinfo=MSK) if start_str else None
        end = datetime.strptime(end_str, "%d/%m/%Y").replace(tzinfo=MSK) if end_str else None

        new_server = Server(
            ip_adress=ip,
            text=srv.get("name", "Новый сервер"),
            start=start,
            end=end,
        )
        session.add(new_server)
        new_servers.append(new_server)

    if new_servers:
        await session.commit()
    return new_servers

async def notify_users_about_new_servers(session: AsyncSession, servers: list[Server]):
    """Отправляет уведомление всем пользователям о новых серверах"""
    if not servers:
        return

    result = await session.execute(select(User.telegram_id))
    users = result.scalars().all()

    for server in servers:
        message = f"""✅ <b>Добавлен новый сервер!</b>

🖥 IP-адрес: <code>{server.ip_adress}</code>
📝 Текст: <code>{server.text}</code>

⏰ Дата добавления <b>{server.start.strftime('%d.%m.%Y')} МСК</b>"""
        for user_id in users:
            try:
                await bot.send_message(user_id, message, parse_mode="HTML")
            except Exception:
                # Игнорируем ошибки (например, если пользователь заблокировал бота)
                continue

async def check_closed_servers(session: AsyncSession):
    """Проверяет сервера, у которых истек срок end, и уведомляет пользователей"""
    now = datetime.now(MSK)

    # Находим сервера с истекшим сроком
    result = await session.execute(
        select(Server).where(Server.end.is_not(None), Server.end < now)
    )
    closed_servers = result.scalars().all()

    if not closed_servers:
        return

    # Получаем всех пользователей
    result = await session.execute(select(User.telegram_id))
    users = result.scalars().all()

    for server in closed_servers:
        # Считаем срок рекламы (если обе даты заданы)
        days = abs((server.end - server.start).days) if server.start and server.end else "?"
        message = f"""❌ <b>УДАЛЕН СЕРВЕР!</b>

🖥 IP-адрес: <code>{server.ip_adress}</code>
⏳ Срок рекламы: <b>{days} день</b>

🗑 Дата удаления: <b>{server.end.strftime('%d.%m.%Y')} МСК</b>"""

        for user_id in users:
            try:
                await bot.send_message(user_id, message, parse_mode="HTML")
            except Exception:
                continue

        # Можно либо удалять сервер, либо помечать статусом
        # Удаление:
        await session.delete(server)

    await session.commit()


async def check_and_update_servers():
    while True:
        print("Проверка серверов...")
        async with db_helper.session_factory() as session:
            servers_data = await fetch_servers_from_link()
            new_servers = await add_new_servers_to_db(session, servers_data)
            await notify_users_about_new_servers(session, new_servers)
            await check_closed_servers(session)  # <-- новая проверка
        await asyncio.sleep(CHECK_INTERVAL)
