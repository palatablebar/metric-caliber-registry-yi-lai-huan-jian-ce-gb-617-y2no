from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CHANGE_APPROVE_ROLES, CHANGE_WRITE_ROLES
from src.controllers import change_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.change import ChangeIn, DecisionIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/change-requests", tags=["change-requests"])


@router.get("")
def list_changes(
    status: str | None = None,
    severity: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return change_controller.list_changes(db, status=status, severity=severity, limit=page.limit, offset=page.offset)


@router.get("/{change_id}")
def get_change(
    change_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return change_controller.get_change(db, change_id)


@router.post("", status_code=201)
def create_change(
    payload: ChangeIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CHANGE_WRITE_ROLES)),
) -> dict:
    return change_controller.create_change(db, payload.model_dump(), principal, request)


@router.patch("/{change_id}")
def decide_change(
    change_id: int,
    payload: DecisionIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*CHANGE_APPROVE_ROLES)),
) -> dict:
    return change_controller.decide(db, change_id, payload.model_dump(), principal, request)
