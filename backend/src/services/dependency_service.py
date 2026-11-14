"""依赖边服务：按当前口径重建 metric -> metric / field / report 三类边。"""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.constants.enums import DependencyKind
from src.models.dependency import Dependency
from src.models.metric import Metric
from src.models.report import Report
from src.services import dsl_parser
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


def rebuild(db: Session, metrics: list[Metric], parsed_by_code: dict[str, dict]) -> dict:
    """用当前解析结果重建依赖边；返回统计。"""
    by_code = {metric.code: metric for metric in metrics}
    desired: dict[tuple[int, str, str], dict] = {}
    for metric in metrics:
        parsed = parsed_by_code.get(metric.code) or {}
        if parsed.get("status") != "ok":
            continue
        for ref in parsed.get("deps") or []:
            if ref in by_code:
                desired[(metric.id, DependencyKind.METRIC.value, ref)] = {
                    "to_metric_id": by_code[ref].id,
                    "weight": 1,
                    "note": "DSL 引用",
                }
        for field in parsed.get("fields") or []:
            desired[(metric.id, DependencyKind.FIELD.value, field)] = {
                "to_metric_id": None,
                "weight": 1,
                "note": "数仓字段",
            }

    for report in db.scalars(select(Report)).all():
        for metric_code in report.metric_codes or []:
            metric = by_code.get(metric_code)
            if metric is None:
                continue
            desired[(metric.id, DependencyKind.REPORT.value, report.code)] = {
                "to_metric_id": None,
                "weight": report.weight or 1,
                "note": "报表引用",
            }

    existing = {
        (edge.from_metric_id, edge.kind, edge.to_ref): edge
        for edge in db.scalars(select(Dependency)).all()
    }
    added = 0
    for key, payload in desired.items():
        if key in existing:
            edge = existing[key]
            edge.to_metric_id = payload["to_metric_id"]
            edge.weight = payload["weight"]
            edge.note = payload["note"]
            continue
        db.add(
            Dependency(
                from_metric_id=key[0],
                kind=key[1],
                to_ref=key[2],
                to_metric_id=payload["to_metric_id"],
                weight=payload["weight"],
                note=payload["note"],
            )
        )
        added += 1
    stale = [edge.id for key, edge in existing.items() if key not in desired]
    if stale:
        db.execute(delete(Dependency).where(Dependency.id.in_(stale)))
    db.flush()
    counts = {
        DependencyKind.METRIC.value: sum(1 for key in desired if key[1] == DependencyKind.METRIC.value),
        DependencyKind.FIELD.value: sum(1 for key in desired if key[1] == DependencyKind.FIELD.value),
        DependencyKind.REPORT.value: sum(1 for key in desired if key[1] == DependencyKind.REPORT.value),
    }
    return {"added": added, "removed": len(stale), "total": len(desired), "counts": counts}


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


def parse_formulas(metrics: list[Metric], formulas_by_metric: dict[int, object]) -> dict[str, dict]:
    """对每个指标当前版本的 DSL 跑一次算法 A（纯计算，不落库）。"""
    parsed: dict[str, dict] = {}
    for metric in metrics:
        formula = formulas_by_metric.get(metric.id)
        parsed[metric.code] = dsl_parser.parse_dsl(formula.dsl_text if formula else "", metric.code)
    return parsed
