"""指标登记：自然键 code。同名不同口径是本系统的核心问题（用 name 分组检出冲突）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    domain: Mapped[str] = mapped_column(String(20), default="trade", index=True)
    tier: Mapped[str] = mapped_column(String(12), default="normal", index=True)
    unit: Mapped[str] = mapped_column(String(20), default="元")
    owner: Mapped[str] = mapped_column(String(80), default="星野零售 · 指标体系组")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    core_report_count: Mapped[int] = mapped_column(Integer, default=0)
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    created_by: Mapped[str] = mapped_column(String(160), default="seed@metricreg.io")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class MetricAlias(Base):
    """同名指标的展示别名（历史叫法），便于月会对照，不影响冲突判定。"""

    __tablename__ = "metric_aliases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_id: Mapped[int] = mapped_column(index=True)
    alias: Mapped[str] = mapped_column(String(80))
