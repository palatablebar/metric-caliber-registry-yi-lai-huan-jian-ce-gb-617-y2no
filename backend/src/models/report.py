"""报表登记：指标被哪些 BI 报表消费；核心报表权重 ×3，参与影响面打分。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    owner: Mapped[str] = mapped_column(String(80), default="星野零售 · 指标体系组")
    channel: Mapped[str] = mapped_column(String(40), default="BI")
    is_core: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    metric_codes: Mapped[list] = mapped_column(JSON, default=list)
    refresh_cron: Mapped[str] = mapped_column(String(40), default="0 7 * * *")
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
