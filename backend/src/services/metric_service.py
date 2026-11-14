"""指标服务：登记、筛选、详情（口径 + 解析结果 + 依赖 + 下游报表）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    METRIC_DOMAIN_LABELS,
    METRIC_STATUS_LABELS,
    METRIC_TIER_LABELS,
    MetricStatus,
)
from src.models.dependency import Dependency
from src.models.formula import Formula
from src.models.metric import Metric
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc


def serialize(
    metric: Metric,
    formula: Formula | None = None,
    *,
    report_names: list[str] | None = None,
    dep_codes: list[str] | None = None,
) -> dict:
    parsed = (formula.parsed or {}) if formula else {}
    return {
        "id": metric.id,
        "code": metric.code,
        "name": metric.name,
        "domain": metric.domain,
        "domain_label": METRIC_DOMAIN_LABELS.get(metric.domain, metric.domain),
        "tier": metric.tier,
        "tier_label": METRIC_TIER_LABELS.get(metric.tier, metric.tier),
        "unit": metric.unit,
        "owner": metric.owner,
        "description": metric.description,
        "status": metric.status,
        "status_label": METRIC_STATUS_LABELS.get(metric.status, metric.status),
        "current_version": metric.current_version,
        "parse_status": formula.parse_status if formula else "error",
        "parse_error": formula.parse_error if formula else "缺少口径公式",
        "signature": formula.signature if formula else "",
        "expression": parsed.get("expression") or (formula.dsl_text if formula else ""),
        "dsl_text": formula.dsl_text if formula else "",
        "aggs": parsed.get("aggs") or [],
        "fields": parsed.get("fields") or [],
        "filters": parsed.get("filters") or [],
        "dims": parsed.get("dims") or [],
        "deps": parsed.get("deps") or [],
        "dep_metrics": dep_codes or [],
        "reports": report_names or [],
        "report_count": len(report_names or []),
        "enabled": metric.enabled,
        "created_by": metric.created_by,
        "created_at": iso_utc(metric.created_at),
        "updated_at": iso_utc(metric.updated_at),
    }


def list_metrics(
    db: Session,
    *,
    q: str | None = None,
    domain: str | None = None,
    tier: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    formulas: dict[int, Formula] | None = None,
    reports_index: dict[str, list[dict]] | None = None,
) -> dict:
    formulas = formulas if formulas is not None else {}
    reports_index = reports_index or {}
    stmt = select(Metric)
    count_stmt = select(func.count()).select_from(Metric)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Metric.name.ilike(like) | Metric.code.ilike(like))
        count_stmt = count_stmt.where(Metric.name.ilike(like) | Metric.code.ilike(like))
    if domain:
        stmt = stmt.where(Metric.domain == domain)
        count_stmt = count_stmt.where(Metric.domain == domain)
    if tier:
        stmt = stmt.where(Metric.tier == tier)
        count_stmt = count_stmt.where(Metric.tier == tier)
    if status:
        stmt = stmt.where(Metric.status == status)
        count_stmt = count_stmt.where(Metric.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Metric.code).limit(limit).offset(offset)).all()
    dep_codes = _dep_codes(db, [metric.id for metric in rows])
    items = [
        serialize(
            row,
            formulas.get(row.id),
            report_names=[report["name"] for report in reports_index.get(row.code, [])],
            dep_codes=dep_codes.get(row.id, []),
        )
        for row in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _dep_codes(db: Session, metric_ids: list[int]) -> dict[int, list[str]]:
    if not metric_ids:
        return {}
    names = {metric.id: metric.code for metric in db.scalars(select(Metric)).all()}
    result: dict[int, list[str]] = {}
    for edge in db.scalars(
        select(Dependency).where(Dependency.from_metric_id.in_(metric_ids), Dependency.kind == "metric")
    ).all():
        result.setdefault(edge.from_metric_id, []).append(names.get(edge.to_metric_id or -1, edge.to_ref))
    return {key: sorted(value) for key, value in result.items()}


def get_metric(db: Session, metric_id: int) -> Metric:
    metric = db.get(Metric, metric_id)
    if metric is None:
        raise not_found("metric", metric_id)
    return metric


def get_by_code(db: Session, code: str) -> Metric | None:
    return db.scalar(select(Metric).where(Metric.code == code))


def create_metric(db: Session, payload: dict, *, author: str) -> Metric:
    if get_by_code(db, payload["code"]) is not None:
        raise AppError("CONFLICT", 409, {"code": payload["code"]})
    metric = Metric(
        code=payload["code"],
        name=payload["name"],
        domain=payload.get("domain") or "trade",
        tier=payload.get("tier") or "normal",
        unit=payload.get("unit") or "元",
        owner=payload.get("owner") or "星野零售 · 指标体系组",
        description=payload.get("description") or "",
        status=payload.get("status") or MetricStatus.ACTIVE.value,
        created_by=author,
    )
    db.add(metric)
    db.flush()
    return metric


def update_metric(db: Session, metric: Metric, payload: dict) -> Metric:
    for field in ("name", "domain", "tier", "unit", "owner", "description", "status", "enabled"):
        if field in payload and payload[field] is not None:
            setattr(metric, field, payload[field])
    db.flush()
    return metric
