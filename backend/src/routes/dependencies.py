from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import dependency_controller
from src.middlewares.rbac import READ_ROLES, require_roles

router = APIRouter(tags=["dependencies"])


@router.get("/dependencies")
def list_dependencies(
    kind: str | None = None,
    metric_code: str | None = None,
    limit: int = Query(100, ge=1, le=400),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return dependency_controller.list_edges(db, kind=kind, metric_code=metric_code, limit=limit, offset=offset)


@router.get("/graph")
def graph(db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return dependency_controller.graph(db)


@router.get("/cycles")
def cycles(db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))) -> dict:
    return dependency_controller.cycles(db)


@router.get("/impact")
def impact(
    field: str | None = None,
    metric: str | None = None,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return dependency_controller.impact(db, field=field, metric=metric)
