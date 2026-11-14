"""幂等 seed：3 账号 / 48 指标 / 12 报表 / 1 次校验运行 / 6 张变更单。

自然键 upsert：
  users.email
  metrics.code            -> formulas(metric_id, version) 由 metric 版本号决定
  reports.code
  runs.seed_key
  change_requests.seed_key
  audit_logs.seed_key

重复执行不新增、不覆盖审批/复核状态；SEED_SUMMARY 逐字一致。
"""
from __future__ import annotations

from sqlalchemy import func, select

from src.config.database import session_scope
from src.models.audit import AuditLog
from src.models.change_request import ChangeRequest
from src.models.metric import Metric
from src.models.report import Report
from src.models.run import Run
from src.models.user import User
from src.services import change_service, formula_service, graph_service, metric_service, run_service
from src.utils.security import hash_password

from scripts.demo_config import (
    CHANGE_REQUESTS,
    DEMO_PASSWORD,
    DEMO_USERS,
    METRICS,
    ORG,
    REPORTS,
    SEED_AUDIT,
    SEED_RUN_KEY,
    SEED_RUN_OPERATOR,
    SEED_RUN_TRIGGER,
)


def ensure_users(db) -> int:
    for email, display_name, role in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    display_name=display_name,
                    role=role,
                    org=ORG,
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(User)) or 0


def ensure_metrics(db) -> int:
    for code, name, domain, tier, unit, owner, dsl_text, description in METRICS:
        metric = db.scalar(select(Metric).where(Metric.code == code))
        if metric is not None:
            continue
        metric = metric_service.create_metric(
            db,
            {
                "code": code,
                "name": name,
                "domain": domain,
                "tier": tier,
                "unit": unit,
                "owner": owner,
                "description": description,
                "status": "active",
            },
            author="admin@metricreg.io",
        )
        metric.seed_key = f"seed-metric-{code}"
        formula_service.save_version(
            db,
            metric,
            dsl_text=dsl_text,
            author_email="admin@metricreg.io",
            note="seed 初始口径",
            seed_key=f"seed-formula-{code}",
        )
    db.flush()
    return db.scalar(select(func.count()).select_from(Metric)) or 0


def ensure_reports(db) -> int:
    for code, name, owner, is_core, weight, metric_codes, channel in REPORTS:
        report = db.scalar(select(Report).where(Report.code == code))
        if report is not None:
            continue
        db.add(
            Report(
                code=code,
                name=name,
                owner=owner,
                channel=channel,
                is_core=is_core,
                weight=weight,
                metric_codes=list(metric_codes),
                seed_key=f"seed-report-{code}",
            )
        )
    db.flush()
    return db.scalar(select(func.count()).select_from(Report)) or 0


def ensure_run(db) -> int:
    run_service.create_and_execute(
        db,
        trigger=SEED_RUN_TRIGGER,
        operator_email=SEED_RUN_OPERATOR,
        seed_key=SEED_RUN_KEY,
    )
    return db.scalar(select(func.count()).select_from(Run)) or 0


def ensure_changes(db) -> int:
    for seed_key, change_kind, target_ref, metric_code, reason, requester, proposed_dsl in CHANGE_REQUESTS:
        exists = db.scalar(select(ChangeRequest).where(ChangeRequest.seed_key == seed_key))
        if exists is not None:
            continue
        change = change_service.create_change(
            db,
            {
                "change_kind": change_kind,
                "target_ref": target_ref,
                "metric_code": metric_code,
                "reason": reason,
                "proposed_dsl": proposed_dsl,
            },
            requester=requester,
        )
        change.seed_key = seed_key
    db.flush()
    return db.scalar(select(func.count()).select_from(ChangeRequest)) or 0


def ensure_audit(db) -> None:
    for seed_key, email, role, action, entity, detail in SEED_AUDIT:
        exists = db.scalar(select(AuditLog).where(AuditLog.seed_key == seed_key))
        if exists is not None:
            continue
        db.add(
            AuditLog(
                actor_email=email,
                actor_role=role,
                action=action,
                entity=entity,
                detail=detail,
                layer="seed",
                seed_key=seed_key,
            )
        )
    db.flush()


def seed_all() -> dict:
    with session_scope() as db:
        users = ensure_users(db)
        metrics = ensure_metrics(db)
        ensure_reports(db)
        runs = ensure_run(db)
        ensure_changes(db)
        ensure_audit(db)
        summary = graph_service.summary(db)
        findings = summary["conflicts_total"] + summary["cycles_total"] + summary["parse_error_count"]
        pending = (
            db.scalar(
                select(func.count()).select_from(ChangeRequest).where(ChangeRequest.status == "pending")
            )
            or 0
        )
        line = (
            f"SEED_SUMMARY brand=metricreg users={users} sources={metrics} "
            f"runs={runs} findings={findings} pending={pending}"
        )
        print(line, flush=True)
        return {
            "users": users,
            "sources": metrics,
            "runs": runs,
            "findings": findings,
            "pending": pending,
            "line": line,
        }


if __name__ == "__main__":
    seed_all()
