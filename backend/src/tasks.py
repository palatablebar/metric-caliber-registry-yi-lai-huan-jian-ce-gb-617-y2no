"""Celery 任务：心跳 + 每日 07:40 自动跑一次口径校验（解析 → 依赖图 → 环/冲突）。"""
from __future__ import annotations

import time

from src.config.celery_app import TASK_DAILY, TASK_HEARTBEAT, celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name=TASK_HEARTBEAT)
def heartbeat() -> str:
    try:
        _redis().set(f"{settings.app_name}:worker:heartbeat", time.time())
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return "error"


@celery_app.task(name=TASK_DAILY)
def daily_refresh() -> dict:
    from src.config.database import session_scope
    from src.services import audit_service, run_service

    operator = "scheduler@" + settings.app_name + ".io"
    with session_scope() as db:
        run = run_service.create_and_execute(db, trigger="schedule", operator_email=operator)
        audit_service.record(
            db,
            actor_email=operator,
            actor_role="admin",
            action="run.create",
            entity="run",
            entity_id=run.id,
            detail={"trigger": "schedule", "run_no": run.run_no, "issues": run.output_count},
            layer="worker",
        )
    logger.info("daily metric validation finished: run=%s issues=%s", run.run_no, run.output_count)
    return {"run_no": run.run_no, "issues": run.output_count}
