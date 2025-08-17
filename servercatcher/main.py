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


dp = Dispatcher()


async def main():

    dp.include_router(start)

    await asyncio.gather(
        dp.start_polling(bot),
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
