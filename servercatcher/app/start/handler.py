from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from servercatcher.core.models import db_helper
from .crud import add_user

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    async with db_helper.session_factory() as session:
        await add_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            session=session,
        )

    await message.answer("")