"""校验运行的隔离候选（staging）。

一次校验运行在「切换」之前，所有中间产物都只写候选表，线上表（formulas /
dependencies）保持上一份可用结果不动：

- ``RunCandidate``     一次运行一份候选，记录所处阶段、解析进度与失败位置；
- ``CandidateFormula`` 算法 A 的逐指标解析结果（候选口径，不覆盖 formulas）；
- ``CandidateDependency`` 由候选口径推导出的期望依赖边（不覆盖 dependencies）。

运行成功后在同一个事务里把候选一次性切换到线上表；运行失败则候选原样保留，
重试同一运行时沿用原候选、跳过已完成的解析，不新增运行记录。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class RunCandidate(Base):
    """一次校验运行的隔离候选头表（run 1:1 candidate）。"""

    __tablename__ = "run_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), unique=True, index=True
    )
    # parse / graph / analyze / cutover / done，见 run_service.STAGE_*
    stage: Mapped[str] = mapped_column(String(20), default="parse", index=True)
    # 已完成解析的指标编码（parse 阶段断点续跑用）
    parsed_codes: Mapped[list] = mapped_column(JSON, default=list)
    # 最近一次失败的位置：{stage, metric_code, message, error, at}
    failure_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 失败累计次数（同一次运行重试不新增 run，只累加计数）
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CandidateFormula(Base):
    """算法 A 对单个指标当前 DSL 的候选解析结果。"""

    __tablename__ = "candidate_formulas"
    __table_args__ = (
        UniqueConstraint("candidate_id", "metric_code", name="uq_candidate_formula_metric"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("run_candidates.id", ondelete="CASCADE"), index=True
    )
    metric_id: Mapped[int] = mapped_column(Integer, index=True)
    metric_code: Mapped[str] = mapped_column(String(48), index=True)
    formula_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dsl_text: Mapped[str] = mapped_column(Text, default="")
    parse_status: Mapped[str] = mapped_column(String(12), default="error", index=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed: Mapped[dict] = mapped_column(JSON, default=dict)
    signature: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CandidateDependency(Base):
    """候选依赖边：指标 -> 引用指标 / 数仓字段 / 报表。"""

    __tablename__ = "candidate_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "from_metric_id", "kind", "to_ref", name="uq_candidate_dependency_edge"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("run_candidates.id", ondelete="CASCADE"), index=True
    )
    from_metric_id: Mapped[int] = mapped_column(Integer, index=True)
    from_metric_code: Mapped[str] = mapped_column(String(48), index=True)
    kind: Mapped[str] = mapped_column(String(12), index=True)
    to_ref: Mapped[str] = mapped_column(String(120), index=True)
    to_metric_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
