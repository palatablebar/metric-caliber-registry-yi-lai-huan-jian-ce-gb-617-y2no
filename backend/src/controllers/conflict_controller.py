"""冲突控制器：同名口径冲突（算法 B 实时计算，不落冗余表）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import graph_service


def list_conflicts(db: Session, *, severity: str | None = None, kind: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    items = graph_service.find_conflicts(db)
    if severity:
        items = [item for item in items if item["severity"] == severity]
    if kind:
        items = [item for item in items if item["kind"] == kind]
    total = len(items)
    return {"items": items[offset : offset + limit], "total": total, "limit": limit, "offset": offset}


def detail(db: Session, conflict_id: str) -> dict:
    for item in graph_service.find_conflicts(db):
        if item["id"] == conflict_id:
            return item
    from src.utils.errors import AppError

    raise AppError("NOT_FOUND", 404, {"entity": "conflict", "id": conflict_id})
