from datetime import datetime
from sqlalchemy import Integer, String, SmallInteger, DateTime, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiCallLog(Base):
    __tablename__ = "api_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    params_json: Mapped[dict | None] = mapped_column(JSON)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    headers_remaining: Mapped[int | None] = mapped_column(Integer)
    headers_limit: Mapped[int | None] = mapped_column(Integer)
    job_name: Mapped[str | None] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(String(500))
    called_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_api_call_log_date", "called_at"),
    )

    def __repr__(self) -> str:
        return f"<ApiCallLog id={self.id} endpoint={self.endpoint!r} status={self.http_status}>"
