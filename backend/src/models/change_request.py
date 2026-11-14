"""变更单：口径/公式/字段类型变更的影响面与审批记录。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cr_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    metric_id: Mapped[int | None] = mapped_column(
        ForeignKey("metrics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_ref: Mapped[str] = mapped_column(String(120), index=True)
    change_kind: Mapped[str] = mapped_column(String(20), default="caliber", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    proposed_dsl: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(12), default="medium", index=True)
    impact_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    requester_email: Mapped[str] = mapped_column(String(160), default="")
    approver_email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
