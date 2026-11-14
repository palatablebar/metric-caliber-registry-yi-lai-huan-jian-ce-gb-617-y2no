"""依赖图控制器：边列表 + 图结构 + 环路径。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import dependency_service, graph_service


def list_edges(db: Session, **filters) -> dict:
    return dependency_service.list_edges(db, **filters)


def graph(db: Session) -> dict:
    return graph_service.graph(db)


def cycles(db: Session) -> dict:
    cycles = graph_service.find_cycles(db)
    return {"items": cycles, "total": len(cycles)}


def impact(db: Session, *, field: str | None = None, metric: str | None = None) -> dict:
    if field:
        return graph_service.impact_for_field(db, field)
    if metric:
        return graph_service.impact_for_metric(db, metric)
    return {"kind": "none", "score": 0, "severity": "low", "reports": [], "report_count": 0}
