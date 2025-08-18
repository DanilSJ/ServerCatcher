import json

import aiohttp
import asyncio
from datetime import datetime, timezone, timedelta
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from servercatcher.core.models import db_helper
from servercatcher.core.models.server import Server, ServerHistory
from servercatcher.core.models.user import User, Chat
from servercatcher.core.config import bot

MSK = timezone(timedelta(hours=3))
CHECK_INTERVAL = 3
PASTEBIN_URL = "http://127.0.0.1:8000"


async def fetch_servers_from_link() -> list[dict]:
    url = f"{PASTEBIN_URL}?nocache={int(time.time())}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'Cache-Control': 'no-cache'}) as resp:
                text = await resp.text()
                data = json.loads(text)
                return data.get("servers", [])
    except Exception as e:

        return []


async def add_new_servers_to_db(session: AsyncSession, servers_data: list[dict]) -> list[Server]:
    new_servers = []

    for srv in servers_data:
        ip = srv.get("ip")
        if not ip:
            continue

        result = await session.execute(select(Server).where(Server.ip_adress == ip))
        server = result.scalars().first()
        start_str = srv.get("start", "")
        start = datetime.strptime(start_str, "%d/%m/%Y").replace(tzinfo=MSK) if start_str else datetime.now(MSK)

        if server:
            if not server.is_active:

                server.is_active = True
                server.end = None
                # Новый период активности
                history = ServerHistory(server_ip=ip, start=start, end=None)
                session.add(history)
            else:
                pass
            # Проверяем, есть ли незавершённая история
            hist_result = await session.execute(
                select(ServerHistory).where(ServerHistory.server_ip == ip, ServerHistory.end == None)
            )
            open_history = hist_result.scalars().first()
            if not open_history:
                # Новый период активности
                history = ServerHistory(server_ip=ip, start=start, end=None)
                session.add(history)
            continue
        # Новый сервер

        new_server = Server(
            ip_adress=ip,
            text=srv.get("name", "Новый сервер"),
            is_active=True,
        )
        session.add(new_server)
        history = ServerHistory(server_ip=ip, start=start, end=None)
        session.add(history)
        new_servers.append(new_server)

    if new_servers:
        await session.commit()
    else:
        await session.commit()  # commit для реактивации
    return new_servers

async def get_all_chats(session: AsyncSession):
    """Получает список всех чатов (пользователей и групп) для отправки уведомлений"""
    chats = set()
    
    # Получаем пользователей из базы
    result = await session.execute(select(User.telegram_id))
    users = result.scalars().all()
    chats.update(users)
    
    # Получаем группы/каналы из базы
    result = await session.execute(select(Chat.chat_id))
    groups = result.scalars().all()
    chats.update(groups)
    
    return list(chats)

async def notify_users_about_new_servers(session: AsyncSession, servers: list[Server]):
    if not servers:
        return

    chats = await get_all_chats(session)

    for server in servers:
        message = f"""✅ <b>Добавлен новый сервер!</b>

🖥 IP-адрес: <code>{server.ip_adress}</code>
📝 Текст: <code>{server.text}</code>

⏰ Дата добавления <b>{server.start.strftime('%d.%m.%Y')} МСК</b>"""
        for chat_id in chats:
            try:
                await bot.send_message(chat_id, message, parse_mode="HTML")
            except Exception as e:
                pass

async def notify_users_about_new_ips(session: AsyncSession, new_ips: list[str], servers_data: list[dict]):
    if not new_ips:
        return
    
    chats = await get_all_chats(session)
    
    for ip in new_ips:
        srv = next((s for s in servers_data if s.get("ip") == ip), None)
        if not srv:
            continue
        name = srv.get("name", "Новый сервер")
        now = datetime.now(MSK)
        message = f"""✅ <b>ДОБАВЛЕН СЕРВЕР!</b>\n\n🖥 IP-адрес: <code>{ip}</code>\n📝 Текст: <code>{name}</code>\n\n⏰ Дата добавления <b>{now.strftime('%d.%m.%Y')} МСК</b>"""
        for chat_id in chats:
            try:
                await bot.send_message(chat_id, message, parse_mode="HTML")
            except Exception as e:
                pass
async def check_closed_servers(session: AsyncSession, current_server_ips: list[str]):
    now = datetime.now(MSK)
    # Получаем все активные сервера
    result = await session.execute(
        select(Server).where(Server.is_active == True)
    )
    active_servers = result.scalars().all()

    if not active_servers:
        return

    chats = await get_all_chats(session)

    for server in active_servers:
        if server.ip_adress not in current_server_ips:
            # days считаем по start и now, приводим start к MSK если нужно
            start = server.start
            if start and start.tzinfo is None:
                start = start.replace(tzinfo=MSK)
            days = abs((now - start).days) if start else "?"
            message = f"""❌ <b>УДАЛЕН СЕРВЕР!</b>\n\n🖥 IP-адрес: <code>{server.ip_adress}</code>\n⏳ Срок рекламы: <b>{days} день</b>\n\n🗑 Дата удаления: <b>{now.strftime('%d.%m.%Y')} МСК</b>"""

            for chat_id in chats:
                try:
                    await bot.send_message(chat_id, message, parse_mode="HTML")

                except Exception as e:
                    pass
            # Закрываем историю
            history = ServerHistory(server_ip=server.ip_adress, start=None, end=now)
            session.add(history)
            server.is_active = False
            server.end = now
    await session.commit()
    # Повторно выводим список активных серверов
    result = await session.execute(
        select(Server).where(Server.is_active == True)
    )
    active_servers = result.scalars().all()


async def check_and_update_servers():
    previous_server_ips = set()
    while True:
        async with db_helper.session_factory() as session:
            servers_data = await fetch_servers_from_link()

            current_server_ips = set(srv.get("ip") for srv in servers_data if srv.get("ip"))
            # Новые IP, которых не было в предыдущем опросе
            new_ips = list(current_server_ips - previous_server_ips)
            await notify_users_about_new_ips(session, new_ips, servers_data)
            new_servers = await add_new_servers_to_db(session, servers_data)
            await notify_users_about_new_servers(session, new_servers)
            await check_closed_servers(session, list(current_server_ips))
            previous_server_ips = current_server_ips
        await asyncio.sleep(CHECK_INTERVAL)