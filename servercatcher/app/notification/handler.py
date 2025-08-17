import json

import aiohttp
import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from servercatcher.core.models import db_helper
from servercatcher.core.models.server import Server, ServerHistory
from servercatcher.core.models.user import User
from servercatcher.core.config import bot

MSK = timezone(timedelta(hours=3))
CHECK_INTERVAL = 3
PASTEBIN_URL = "https://pastebin.com/raw/DnHHkrxx"


async def fetch_servers_from_link() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(PASTEBIN_URL) as resp:
            text = await resp.text()
            data = json.loads(text)
            return data.get("servers", [])


async def add_new_servers_to_db(session: AsyncSession, servers_data: list[dict]) -> list[Server]:
    new_servers = []

    for srv in servers_data:
        ip = srv.get("ip")
        if not ip:
            continue

        result = await session.execute(select(Server).where(Server.ip_adress == ip))
        server = result.scalars().first()
        start_str = srv.get("start", "")
        end_str = srv.get("end", "")
        start = datetime.strptime(start_str, "%d/%m/%Y").replace(tzinfo=MSK) if start_str else datetime.now(MSK)
        end = datetime.strptime(end_str, "%d/%m/%Y").replace(tzinfo=MSK) if end_str else None

        if server:
            # Проверяем, есть ли незавершённая история
            hist_result = await session.execute(
                select(ServerHistory).where(ServerHistory.server_ip == ip, ServerHistory.end == None)
            )
            open_history = hist_result.scalars().first()
            if not open_history:
                # Новый период активности
                history = ServerHistory(server_ip=ip, start=start, end=end)
                session.add(history)
            continue
        # Новый сервер
        new_server = Server(
            ip_adress=ip,
            text=srv.get("name", "Новый сервер"),
            is_active=True,
        )
        session.add(new_server)
        history = ServerHistory(server_ip=ip, start=start, end=end)
        session.add(history)
        new_servers.append(new_server)

    if new_servers:
        await session.commit()
    return new_servers

async def notify_users_about_new_servers(session: AsyncSession, servers: list[Server]):
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
            except Exception as e:
                print(e)

async def check_closed_servers(session: AsyncSession):
    now = datetime.now(MSK)
    result = await session.execute(
        select(Server).where(Server.end.is_not(None), Server.end < now, Server.is_active == True)
    )
    closed_servers = result.scalars().all()

    if not closed_servers:
        return

    result = await session.execute(select(User.telegram_id))
    users = result.scalars().all()

    for server in closed_servers:
        days = abs((server.end - server.start).days) if server.start and server.end else "?"
        message = f"""❌ <b>УДАЛЕН СЕРВЕР!</b>\n\n🖥 IP-адрес: <code>{server.ip_adress}</code>\n⏳ Срок рекламы: <b>{days} день</b>\n\n🗑 Дата удаления: <b>{server.end.strftime('%d.%m.%Y')} МСК</b>"""

        for user_id in users:
            try:
                await bot.send_message(user_id, message, parse_mode="HTML")
            except Exception:
                continue

        hist_result = await session.execute(
            select(ServerHistory).where(ServerHistory.server_ip == server.ip_adress, ServerHistory.end == None)
        )
        open_history = hist_result.scalars().first()
        if open_history:
            open_history.end = now
        server.is_active = False

    await session.commit()


async def check_and_update_servers():
    while True:
        async with db_helper.session_factory() as session:
            servers_data = await fetch_servers_from_link()
            new_servers = await add_new_servers_to_db(session, servers_data)
            await notify_users_about_new_servers(session, new_servers)
            await check_closed_servers(session)
        await asyncio.sleep(CHECK_INTERVAL)