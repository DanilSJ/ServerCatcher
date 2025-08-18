from sqlalchemy import DateTime, String, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone, timedelta
from .base import Base

MSK = timezone(timedelta(hours=3))

class Server(Base):
    __tablename__ = "server"  # <- исправлено

    ip_adress: Mapped[str] = mapped_column(String, nullable=False)  # <- FK требует PK или unique
    text: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(MSK),
        nullable=True,
    )

    end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(MSK),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

class ServerHistory(Base):
    __tablename__ = "server_history"  # <- исправлено

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_ip: Mapped[str] = mapped_column(String, ForeignKey("server.ip_adress"), nullable=False)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    server = relationship("Server", backref="history")
