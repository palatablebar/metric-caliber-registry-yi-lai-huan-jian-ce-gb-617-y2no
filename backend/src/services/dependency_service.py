"""依赖边服务：线上依赖边的只读查询。

依赖边的写入口径已统一收口到 ``staging_service``（校验运行先写候选边，
成功后在单事务内整体替换线上表），本服务不再提供运行期直接改线上表的方法，
避免校验未完成时线上依赖图被改写。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.dependency import Dependency
from src.models.metric import Metric
from src.utils.timeutil import iso_utc


def serialize(edge: Dependency, metric_names: dict[int, str] | None = None) -> dict:
    return {
        "id": edge.id,
        "from_metric_id": edge.from_metric_id,
        "from_metric_code": (metric_names or {}).get(edge.from_metric_id, ""),
        "kind": edge.kind,
        "to_ref": edge.to_ref,
        "to_metric_id": edge.to_metric_id,
        "weight": edge.weight,
        "note": edge.note,
        "created_at": iso_utc(edge.created_at),
    }


def list_edges(
    db: Session,
    *,
    kind: str | None = None,
    metric_code: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    stmt = select(Dependency)
    count_stmt = select(func.count()).select_from(Dependency)
    if kind:
        stmt = stmt.where(Dependency.kind == kind)
        count_stmt = count_stmt.where(Dependency.kind == kind)
    if metric_code:
        metric = db.scalar(select(Metric).where(Metric.code == metric_code))
        metric_id = metric.id if metric else -1
        stmt = stmt.where(Dependency.from_metric_id == metric_id)
        count_stmt = count_stmt.where(Dependency.from_metric_id == metric_id)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Dependency.from_metric_id, Dependency.kind, Dependency.to_ref).limit(limit).offset(offset)).all()
    names = {metric.id: metric.code for metric in db.scalars(select(Metric)).all()}
    return {
        "items": [serialize(row, names) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
