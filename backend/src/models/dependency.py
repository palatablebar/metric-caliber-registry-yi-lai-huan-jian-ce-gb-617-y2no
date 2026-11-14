"""依赖边：指标 -> 引用指标 / 数仓字段 / 报表。运行时会按当前口径重建。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Dependency(Base):
    __tablename__ = "dependencies"
    __table_args__ = (UniqueConstraint("from_metric_id", "kind", "to_ref", name="uq_dependencies_edge"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12), default="metric", index=True)
    to_ref: Mapped[str] = mapped_column(String(120), index=True)
    to_metric_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
