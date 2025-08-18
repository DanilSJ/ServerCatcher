import asyncio
from aiogram import Dispatcher
from aiogram.exceptions import (
    TelegramNetworkError,
    TelegramAPIError,
    TelegramServerError,
    TelegramUnauthorizedError,
    TelegramNotFound,
    TelegramBadRequest,
)

from servercatcher.core.config import bot
from servercatcher.app.start.handler import router as start
from servercatcher.app.server.handler import router as server
from servercatcher.app.notification.handler import check_and_update_servers


dp = Dispatcher()


async def main():
    print("Starting bot...")
    
    # Включаем роутеры
    dp.include_router(start)
    dp.include_router(server)
    
    print("Routers included:")
    print(f"- Start router: {start}")
    print(f"- Server router: {server}")
    
    # Запускаем бота с поддержкой всех типов обновлений
    print("Starting polling with chat_member updates...")
    await asyncio.gather(
        dp.start_polling(
            bot, 
            allowed_updates=["message", "chat_member", "my_chat_member"],
            drop_pending_updates=True
        ),
        check_and_update_servers()
    )


if __name__ == "__main__":
    print("Starting...")
    try:
        asyncio.run(main())
    except TelegramNetworkError:
        print("No internet connection")
    except TelegramUnauthorizedError:
        print("No authorization token")
    except TelegramNotFound:
        print("No bot token")
    except TelegramServerError:
        print("No server connection")
    except TelegramBadRequest:
        print("Bad request")
    except TelegramAPIError:
        print("No API connection")
    except KeyboardInterrupt:
        print("Exit")
