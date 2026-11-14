"""变更单服务：创建时用算法 B 算影响面，审批留痕。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import CHANGE_KIND_LABELS, CHANGE_STATUS_LABELS, ChangeKind, ChangeStatus
from src.models.change_request import ChangeRequest
from src.models.metric import Metric
from src.services import graph_service
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc, local_now, utcnow


def serialize(change: ChangeRequest, metric_code: str | None = None) -> dict:
    return {
        "id": change.id,
        "cr_no": change.cr_no,
        "metric_id": change.metric_id,
        "metric_code": metric_code,
        "target_ref": change.target_ref,
        "change_kind": change.change_kind,
        "change_kind_label": CHANGE_KIND_LABELS.get(change.change_kind, change.change_kind),
        "reason": change.reason,
        "proposed_dsl": change.proposed_dsl,
        "impact": change.impact or {},
        "severity": change.severity,
        "impact_score": change.impact_score,
        "status": change.status,
        "status_label": CHANGE_STATUS_LABELS.get(change.status, change.status),
        "requester_email": change.requester_email,
        "approver_email": change.approver_email,
        "decision_note": change.decision_note,
        "decided_at": iso_utc(change.decided_at),
        "created_at": iso_utc(change.created_at),
    }


def next_cr_no(db: Session) -> str:
    prefix = f"CR{local_now():%Y%m%d}"
    count = db.scalar(select(func.count()).select_from(ChangeRequest).where(ChangeRequest.cr_no.like(f"{prefix}%"))) or 0
    return f"{prefix}-{count + 1:04d}"


def compute_impact(db: Session, *, change_kind: str, target_ref: str, metric_code: str | None) -> dict:
    if change_kind == ChangeKind.FIELD_TYPE.value:
        return graph_service.impact_for_field(db, target_ref)
    if not metric_code:
        raise AppError("VALIDATION", 422, {"field": "metric_code", "message": "口径/公式类变更需要指定指标"})
    return graph_service.impact_for_metric(db, metric_code)


def create_change(db: Session, payload: dict, *, requester: str) -> ChangeRequest:
    change_kind = payload.get("change_kind") or ChangeKind.CALIBER.value
    target_ref = (payload.get("target_ref") or "").strip()
    metric_code = (payload.get("metric_code") or "").strip() or None
    if not target_ref:
        raise AppError("VALIDATION", 422, {"field": "target_ref"})
    if metric_code is None and change_kind != ChangeKind.FIELD_TYPE.value:
        raise AppError("VALIDATION", 422, {"field": "metric_code"})
    metric = None
    if metric_code:
        metric = db.scalar(select(Metric).where(Metric.code == metric_code))
        if metric is None:
            raise AppError("NOT_FOUND", 404, {"entity": "metric", "code": metric_code})
        target_ref = metric_code
    pending = db.scalar(
        select(ChangeRequest).where(
            ChangeRequest.target_ref == target_ref,
            ChangeRequest.change_kind == change_kind,
            ChangeRequest.status == ChangeStatus.PENDING.value,
        )
    )
    if pending is not None:
        raise AppError("CONFLICT", 409, {"cr_no": pending.cr_no, "status": pending.status})
    impact = compute_impact(db, change_kind=change_kind, target_ref=target_ref, metric_code=metric_code)
    change = ChangeRequest(
        cr_no=next_cr_no(db),
        metric_id=metric.id if metric else None,
        target_ref=target_ref,
        change_kind=change_kind,
        reason=payload.get("reason") or "",
        proposed_dsl=payload.get("proposed_dsl"),
        impact=impact,
        severity=impact.get("severity") or "low",
        impact_score=int(impact.get("score") or 0),
        status=ChangeStatus.PENDING.value,
        requester_email=requester,
    )
    db.add(change)
    db.flush()
    return change


def decide(
    db: Session,
    change: ChangeRequest,
    *,
    status: str,
    note: str | None,
    approver: str,
) -> ChangeRequest:
    if change.status != ChangeStatus.PENDING.value:
        raise AppError("CONFLICT", 409, {"cr_no": change.cr_no, "status": change.status})
    if status not in (ChangeStatus.APPROVED.value, ChangeStatus.REJECTED.value):
        raise AppError("VALIDATION", 422, {"field": "status"})
    change.status = status
    change.decision_note = note
    change.approver_email = approver
    change.decided_at = utcnow()
    db.flush()
    return change


def get_change(db: Session, change_id: int) -> ChangeRequest:
    change = db.get(ChangeRequest, change_id)
    if change is None:
        raise not_found("change_request", change_id)
    return change


def list_changes(
    db: Session,
    *,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    stmt = select(ChangeRequest)
    count_stmt = select(func.count()).select_from(ChangeRequest)
    if status:
        stmt = stmt.where(ChangeRequest.status == status)
        count_stmt = count_stmt.where(ChangeRequest.status == status)
    if severity:
        stmt = stmt.where(ChangeRequest.severity == severity)
        count_stmt = count_stmt.where(ChangeRequest.severity == severity)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(ChangeRequest.id.desc()).limit(limit).offset(offset)).all()
    codes = {metric.id: metric.code for metric in db.scalars(select(Metric)).all()}
    return {
        "items": [serialize(row, codes.get(row.metric_id or -1)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
