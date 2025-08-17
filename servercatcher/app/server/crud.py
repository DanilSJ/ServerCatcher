from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone, timedelta
from servercatcher.core.models.server import Server

MSK = timezone(timedelta(hours=3))

async def get_active_servers(session: AsyncSession) -> list[Server]:
    now = datetime.now(MSK)
    result = await session.execute(
        select(Server).where(Server.start <= now, Server.end >= now, Server.is_active == True)
    )
    servers = result.scalars().all()
    return list(servers)


async def get_all_servers(session: AsyncSession):
    result = await session.execute(select(Server).order_by(Server.start))
    return result.scalars().all()