from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import FORMULA_WRITE_ROLES, METRIC_WRITE_ROLES
from src.controllers import metric_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.metric import FormulaIn, MetricIn, MetricPatch, ParseIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def list_metrics(
    q: str | None = None,
    domain: str | None = None,
    tier: str | None = None,
    status: str | None = None,
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return metric_controller.list_metrics(
        db, q=q, domain=domain, tier=tier, status=status, limit=page.limit, offset=page.offset
    )


@router.get("/{metric_id}")
def metric_detail(
    metric_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return metric_controller.detail(db, metric_id)


@router.post("", status_code=201)
def create_metric(
    payload: MetricIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*METRIC_WRITE_ROLES)),
) -> dict:
    return metric_controller.create_metric(db, payload.model_dump(), principal, request)


@router.patch("/{metric_id}")
def update_metric(
    metric_id: int,
    payload: MetricPatch,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*METRIC_WRITE_ROLES)),
) -> dict:
    return metric_controller.update_metric(
        db, metric_id, payload.model_dump(exclude_unset=True), principal, request
    )


@router.post("/{metric_id}/parse")
def parse_formula(
    metric_id: int,
    payload: ParseIn,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*FORMULA_WRITE_ROLES)),
) -> dict:
    return metric_controller.parse_dsl(db, metric_id, payload.dsl_text, principal)


@router.post("/{metric_id}/formulas", status_code=201)
def save_formula(
    metric_id: int,
    payload: FormulaIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*FORMULA_WRITE_ROLES)),
) -> dict:
    return metric_controller.save_formula(db, metric_id, payload.model_dump(), principal, request)
