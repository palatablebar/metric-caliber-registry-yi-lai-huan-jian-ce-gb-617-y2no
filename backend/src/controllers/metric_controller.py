"""指标控制器：注册 / 修改 / 算法 A 预解析 / 保存口径版本。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.formula import Formula
from src.services import audit_service, formula_service, metric_service, report_service


def list_metrics(db: Session, **filters) -> dict:
    return metric_service.list_metrics(
        db,
        formulas=formula_service.latest_map(db),
        reports_index=report_service.reports_by_metric(db),
        **filters,
    )


def detail(db: Session, metric_id: int) -> dict:
    metric = metric_service.get_metric(db, metric_id)
    formula = formula_service.latest_for(db, metric)
    reports = report_service.reports_by_metric(db).get(metric.code, [])
    return {
        "metric": metric_service.serialize(
            metric, formula,
            report_names=[report["name"] for report in reports],
            dep_codes=[dep for dep in ((formula.parsed or {}).get("deps") or [])] if formula else [],
        ),
        "history": [
            formula_service.serialize(row)
            for row in db.scalars(
                select(Formula).where(Formula.metric_id == metric.id).order_by(Formula.version.desc())
            ).all()
        ],
    }


def create_metric(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    metric = metric_service.create_metric(db, payload, author=principal["email"])
    if payload.get("dsl_text"):
        formula_service.save_version(
            db, metric, dsl_text=payload["dsl_text"], author_email=principal["email"], note="注册时初始口径"
        )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="metric.create",
        entity="metric",
        entity_id=metric.id,
        detail={"code": metric.code, "name": metric.name, "tier": metric.tier},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    formula = formula_service.latest_for(db, metric)
    return metric_service.serialize(metric, formula)


def update_metric(db: Session, metric_id: int, payload: dict, principal: dict, request: Request) -> dict:
    metric = metric_service.get_metric(db, metric_id)
    metric_service.update_metric(db, metric, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="metric.update",
        entity="metric",
        entity_id=metric.id,
        detail={"fields": sorted(payload.keys())},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return metric_service.serialize(metric, formula_service.latest_for(db, metric))


def parse_dsl(db: Session, metric_id: int, dsl_text: str, principal: dict) -> dict:
    metric = metric_service.get_metric(db, metric_id)
    return formula_service.parse_preview(dsl_text, metric.code)


def save_formula(db: Session, metric_id: int, payload: dict, principal: dict, request: Request) -> dict:
    metric = metric_service.get_metric(db, metric_id)
    formula = formula_service.save_version(
        db,
        metric,
        dsl_text=payload["dsl_text"],
        author_email=principal["email"],
        note=payload.get("note"),
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="formula.save",
        entity="metric",
        entity_id=metric.id,
        detail={"code": metric.code, "version": formula.version, "signature": formula.signature},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return formula_service.serialize(formula)
