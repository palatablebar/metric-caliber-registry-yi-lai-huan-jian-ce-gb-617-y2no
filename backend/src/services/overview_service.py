"""总览：指标/报表/冲突/环/高风险/待审批 + worker 心跳 + 近 7 天校验趋势。"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import (
    CHANGE_STATUS_LABELS,
    CONFLICT_KIND_LABELS,
    METRIC_DOMAIN_LABELS,
    RUN_STATUS_LABELS,
    SEVERITY_LABELS,
    ChangeStatus,
)
from src.models.change_request import ChangeRequest
from src.models.metric import Metric
from src.models.report import Report
from src.models.run import Run
from src.services import graph_service
from src.utils.timeutil import local_now, utcnow


def worker_alive() -> bool:
    try:
        import time

        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        value = client.get(f"{settings.app_name}:worker:heartbeat")
        return bool(value) and (time.time() - float(value)) < 120
    except Exception:
        return False


def overview(db: Session) -> dict:
    summary = graph_service.summary(db)
    metrics_total = db.scalar(select(func.count()).select_from(Metric)) or 0
    reports_total = db.scalar(select(func.count()).select_from(Report)) or 0
    core_reports = db.scalar(select(func.count()).select_from(Report).where(Report.is_core.is_(True))) or 0
    pending_changes = (
        db.scalar(
            select(func.count()).select_from(ChangeRequest).where(ChangeRequest.status == ChangeStatus.PENDING.value)
        )
        or 0
    )
    domain_rows = db.execute(
        select(Metric.domain, func.count()).group_by(Metric.domain).order_by(Metric.domain)
    ).all()
    kind_counter: dict[str, int] = {}
    for item in summary["conflicts"]:
        kind_counter[item["kind"]] = kind_counter.get(item["kind"], 0) + 1
    latest_run = db.scalar(select(Run).order_by(Run.id.desc()).limit(1))

    since = utcnow() - timedelta(days=7)
    recent_runs = db.scalars(select(Run).where(Run.started_at >= since)).all()
    today = local_now().date()
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        count = sum(
            1
            for run in recent_runs
            if run.started_at
            and (run.started_at + timedelta(minutes=settings.app_timezone_offset_minutes)).date() == day
        )
        trend.append({"date": day.isoformat(), "runs": count})

    severity_counter = summary["severity"]
    return {
        "metrics_total": metrics_total,
        "reports_total": reports_total,
        "core_reports": core_reports,
        "conflicts_total": summary["conflicts_total"],
        "cycles_total": summary["cycles_total"],
        "parse_error_count": summary["parse_error_count"],
        "high_risk": severity_counter.get("high", 0),
        "pending_changes": pending_changes,
        "worker_alive": worker_alive(),
        "severity": [
            {"key": key, "label": SEVERITY_LABELS.get(key, key), "count": severity_counter.get(key, 0)}
            for key in ("high", "medium", "low")
        ],
        "conflict_kinds": [
            {"key": key, "label": CONFLICT_KIND_LABELS.get(key, key), "count": count}
            for key, count in sorted(kind_counter.items())
        ],
        "domains": [
            {"key": key, "label": METRIC_DOMAIN_LABELS.get(key, key), "count": count}
            for key, count in domain_rows
        ],
        "change_status": [
            {
                "key": status,
                "label": CHANGE_STATUS_LABELS.get(status, status),
                "count": db.scalar(
                    select(func.count()).select_from(ChangeRequest).where(ChangeRequest.status == status)
                )
                or 0,
            }
            for status in ("pending", "approved", "rejected")
        ],
        "top_conflicts": [
            {
                "name": item["name"],
                "severity": item["severity"],
                "kind": item["kind"],
                "kind_label": CONFLICT_KIND_LABELS.get(item["kind"], item["kind"]),
                "metric_codes": item["metric_codes"],
                "score": item["score"],
                "report_count": item["impact"]["report_count"],
            }
            for item in summary["conflicts"][:5]
        ],
        "cycle_paths": [" → ".join(item["path"]) for item in summary["cycles"]],
        "latest_run": (
            {
                "id": latest_run.id,
                "run_no": latest_run.run_no,
                "status": latest_run.status,
                "status_label": RUN_STATUS_LABELS.get(latest_run.status, latest_run.status),
                "started_at": latest_run.started_at.isoformat(timespec="seconds") + "Z" if latest_run.started_at else None,
                "output_count": latest_run.output_count,
                "input_count": latest_run.input_count,
            }
            if latest_run
            else None
        ),
        "trend": trend,
    }
