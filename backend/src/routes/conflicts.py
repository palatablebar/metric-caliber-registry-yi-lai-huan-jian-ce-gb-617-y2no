from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import conflict_controller
from src.middlewares.rbac import READ_ROLES, require_roles

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@router.get("")
def list_conflicts(
    severity: str | None = None,
    kind: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return conflict_controller.list_conflicts(db, severity=severity, kind=kind, limit=limit, offset=offset)


@router.get("/{conflict_id}")
def conflict_detail(
    conflict_id: str, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return conflict_controller.detail(db, conflict_id)
