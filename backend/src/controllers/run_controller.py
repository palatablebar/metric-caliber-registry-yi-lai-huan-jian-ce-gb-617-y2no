"""校验运行控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, run_service


def create_run(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    run = run_service.create_and_execute(
        db,
        trigger=payload.get("trigger") or "manual",
        operator_email=principal["email"],
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="run.create",
        entity="run",
        entity_id=run.id,
        detail={"run_no": run.run_no, "issues": run.output_count},
        ip=request.client.host if request.client else None,
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="run.complete",
        entity="run",
        entity_id=run.id,
        detail={"status": run.status, "output": run.output_count},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return run_service.serialize(run)


def list_runs(db: Session, **filters) -> dict:
    return run_service.list_runs(db, **filters)


def get_run(db: Session, run_id: int) -> dict:
    return run_service.serialize(run_service.get_run(db, run_id))
