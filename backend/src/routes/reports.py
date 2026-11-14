from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import report_controller
from src.middlewares.rbac import READ_ROLES, require_roles

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def list_reports(
    core: bool | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return report_controller.list_reports(db, core=core, q=q, limit=limit, offset=offset)
