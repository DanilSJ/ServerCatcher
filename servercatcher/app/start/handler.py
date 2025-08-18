from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated
from sqlalchemy import select
from servercatcher.core.models import db_helper
from servercatcher.core.models.user import Chat
from .crud import add_user

router = Router()

print(f"[DEBUG] Start router created: {router}")

@router.message(Command("start"))
async def cmd_start(message: Message):
    print(f"[DEBUG] /start command received from user {message.from_user.id}")
    async with db_helper.session_factory() as session:
        await add_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            session=session,
        )

    await message.answer("Привет! Я бот для отслеживания серверов.")

@router.my_chat_member()
async def on_chat_member_update(event: ChatMemberUpdated):
    """Отслеживает добавление/удаление бота из групп и каналов"""
    print(f"[DEBUG] Chat member update received: {event}")
    print(f"[DEBUG] New member status: {event.new_chat_member.status}")
    print(f"[DEBUG] User ID: {event.new_chat_member.user.id}")
    print(f"[DEBUG] Bot ID: {event.bot.id}")
    
    if event.new_chat_member.user.id == event.bot.id:
        print("dwdwdwdwwd")
        chat_id = event.chat.id
        chat_type = event.chat.type
        title = event.chat.title
        username = event.chat.username
        
        print(f"[DEBUG] Bot added/removed from chat: {chat_id} ({chat_type}) - {title}")
        
        async with db_helper.session_factory() as session:
            if event.new_chat_member.status in ["member", "administrator"]:
                # Бот добавлен в группу/канал
                result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
                existing_chat = result.scalars().first()
                
                if not existing_chat:
                    new_chat = Chat(
                        chat_id=chat_id,
                        chat_type=chat_type,
                        title=title,
                        username=username
                    )
                    session.add(new_chat)
                    await session.commit()
                    print(f"[DEBUG] Бот добавлен в {chat_type}: {title} (ID: {chat_id})")
                else:
                    print(f"[DEBUG] Бот уже есть в базе для {chat_type}: {title}")
                    
            elif event.new_chat_member.status in ["left", "kicked"]:
                # Бот удален из группы/канала
                result = await session.execute(select(Chat).where(Chat.chat_id == chat_id))
                existing_chat = result.scalars().first()
                
                if existing_chat:
                    await session.delete(existing_chat)
                    await session.commit()
                    print(f"[DEBUG] Бот удален из {chat_type}: {title} (ID: {chat_id})")
                else:
                    print(f"[DEBUG] Запись о чате не найдена для удаления: {chat_id}")
    else:
        print(f"[DEBUG] Not a bot update, user ID: {event.new_chat_member.user.id}")

print(f"[DEBUG] Start router handlers registered: {len(router.message.handlers)} message handlers, {len(router.chat_member.handlers)} chat_member handlers")