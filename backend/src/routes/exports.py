from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import EXPORT_ROLES
from src.controllers import export_controller
from src.middlewares.rbac import require_roles

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/metrics.csv")
def metrics_csv(
    request: Request, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*EXPORT_ROLES))
):
    return export_controller.metrics_csv(db, principal, request)


@router.get("/conflicts.csv")
def conflicts_csv(
    request: Request, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*EXPORT_ROLES))
):
    return export_controller.conflicts_csv(db, principal, request)


@router.get("/change-requests.csv")
def changes_csv(
    request: Request, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*EXPORT_ROLES))
):
    return export_controller.changes_csv(db, principal, request)


@router.get("/runs.csv")
def runs_csv(
    request: Request, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*EXPORT_ROLES))
):
    return export_controller.runs_csv(db, principal, request)
