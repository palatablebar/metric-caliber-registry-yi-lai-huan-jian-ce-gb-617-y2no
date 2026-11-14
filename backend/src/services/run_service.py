"""校验运行服务：算法 A 解析全部口径 → 候选依赖图 → 算法 B 环/冲突 → 单事务切换。

关键约束（候选隔离 + 原子切换）：

1. 运行期间解析结果只写 ``candidate_formulas``、依赖边只写 ``candidate_dependencies``，
   线上 ``formulas`` / ``dependencies`` 全程不动，指标详情、依赖图、总览始终读到
   上一份可用结果，不会出现新旧混合；
2. 全部阶段成功后，在同一个事务里把候选解析结果、依赖边一次性切换到线上表，
   任何一步失败整体回滚，旧口径可继续使用、不被覆盖；
3. 失败位置写 ``Run.failure_info`` 与候选头表，候选原样保留；
4. 重试同一运行复用原 Run 与原候选（不新增运行记录），parse 阶段跳过已完成的
   指标解析，沿用原候选继续执行。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.metric import Metric
from src.models.run import Run
from src.services import (
    formula_service,
    graph_analysis,
    report_service,
    staging_service,
)
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc, local_now, utcnow


def serialize(run: Run) -> dict:
    return {
        "id": run.id,
        "run_no": run.run_no,
        "trigger": run.trigger,
        "status": run.status,
        "operator_email": run.operator_email,
        "input_count": run.input_count,
        "output_count": run.output_count,
        "metrics": run.metrics or {},
        "log_text": run.log_text,
        "failure_info": run.failure_info,
        "started_at": iso_utc(run.started_at),
        "finished_at": iso_utc(run.finished_at),
    }


def next_run_no(db: Session) -> str:
    prefix = f"V{local_now():%Y%m%d}"
    count = db.scalar(select(func.count()).select_from(Run).where(Run.run_no.like(f"{prefix}%"))) or 0
    return f"{prefix}-{count + 1:04d}"


def _record_failure(run: Run, candidate, *, stage: str, exc: Exception,
                    metric_code: str | None = None) -> None:
    """失败留痕：运行状态 + 失败位置；线上表不在此处改动。"""
    message = str(exc) or exc.__class__.__name__
    if isinstance(exc, staging_service.StageFailure):
        metric_code = exc.metric_code or metric_code
    error = None
    if isinstance(exc, AppError):
        error = exc.detail or None
    run.status = "failed"
    run.log_text = f"校验运行失败（阶段 {stage}）：{message}"
    run.metrics = {"error": message[:300], "stage": stage}
    run.failure_info = {
        "stage": stage,
        "metric_code": metric_code,
        "message": message[:500],
        "error": error,
        "at": utcnow().isoformat(timespec="seconds") + "Z",
    }
    if candidate is not None:
        staging_service.mark_failure(
            candidate, stage=stage, message=message, metric_code=metric_code, error=error
        )
    run.finished_at = utcnow()


def execute_run(db: Session, run: Run) -> Run:
    """执行（或断点续跑）一次校验运行。

    成功：候选一次性切换到线上表，运行置 success/partial；
    失败：线上表保持上一份可用结果，运行置 failed 并记录失败位置，候选保留待续跑。
    """
    run.status = "running"
    run.failure_info = None
    run.started_at = run.started_at or utcnow()
    run.finished_at = None
    db.flush()

    candidate = staging_service.get_candidate(db, run.id)
    if candidate is None:
        candidate = staging_service.create_candidate(db, run.id)
    else:
        # 同一次运行重试：沿用原候选，不新增运行记录，只累加尝试次数
        candidate.attempts = (candidate.attempts or 1) + 1
        db.flush()

    metrics = db.scalars(select(Metric).order_by(Metric.code)).all()
    latest = formula_service.latest_map(db)

    def fail(stage: str, exc: Exception, metric_code: str | None = None) -> Run:
        _record_failure(run, candidate, stage=stage, exc=exc, metric_code=metric_code)
        db.flush()
        return run

    def in_savepoint(stage: str, work):
        """在保存点内执行阶段：失败只回滚该阶段，候选头表与已完成阶段不受影响。"""
        try:
            with db.begin_nested():
                return work()
        except Exception as exc:  # noqa: BLE001 - 运行失败要留痕，不抛 500
            fail(stage, exc)
            return None

    # ---- 阶段 1：算法 A 解析（候选隔离，内部按指标保存点，断点续跑）---------- #
    try:
        if candidate.stage == staging_service.STAGE_PARSE:
            staging_service.stage_parse(db, candidate, metrics, latest)
        candidate_rows = db.scalars(
            select(staging_service.CandidateFormula)
            .where(staging_service.CandidateFormula.candidate_id == candidate.id)
            .order_by(staging_service.CandidateFormula.metric_code)
        ).all()
        parsed_by_code = staging_service.candidate_parse_map(candidate_rows)
    except Exception as exc:  # noqa: BLE001 - 解析保存点已回滚，会话仍可用
        return fail(staging_service.STAGE_PARSE, exc)

    # ---- 阶段 2：候选依赖图（不碰线上 dependencies）-------------------------- #
    # graph 阶段是确定性全量重建，重跑到这里直接重建候选边即可
    graph_stats = in_savepoint(
        staging_service.STAGE_GRAPH,
        lambda: staging_service.stage_graph(db, candidate, metrics, parsed_by_code),
    )
    if graph_stats is None:
        return run

    # ---- 阶段 3：算法 B 环检测 + 同名冲突 + 影响面（纯计算，基于候选）-------- #
    def _analyze():
        payloads = staging_service.candidate_payloads(metrics, candidate_rows)
        reports_index = report_service.reports_by_metric(db)
        return graph_analysis.summarize(payloads, reports_index)

    summary = in_savepoint(staging_service.STAGE_ANALYZE, _analyze)
    if summary is None:
        return run

    # ---- 阶段 4：单事务一次性切换（保存点内失败整体回滚，旧结果继续可用）---- #
    dep_stats = in_savepoint(
        staging_service.STAGE_CUTOVER,
        lambda: staging_service.stage_cutover(
            db, candidate, metrics, candidate_rows, graph_stats["edges"]
        ),
    )
    if dep_stats is None:
        return run

    issue_count = len(summary["conflicts"]) + len(summary["cycles"]) + summary["parse_error_count"]
    run.input_count = len(metrics)
    run.output_count = issue_count
    run.metrics = {
        "metrics_total": summary["metrics_total"],
        "parsed_ok": len(metrics) - summary["parse_error_count"],
        "parse_error_count": summary["parse_error_count"],
        "parse_errors": summary["parse_errors"],
        "conflicts_total": summary["conflicts_total"],
        "cycles_total": summary["cycles_total"],
        "severity": summary["severity"],
        "dep_edges": graph_stats["counts"],
        "high_conflicts": [item["name"] for item in summary["conflicts"] if item["severity"] == "high"],
        "cycle_paths": [" → ".join(item["path"]) for item in summary["cycles"]],
        "attempts": candidate.attempts,
    }
    run.status = "success" if metrics else "partial"
    run.failure_info = None
    run.log_text = (
        f"解析 {len(metrics)} 个指标口径，失败 {summary['parse_error_count']} 个；"
        f"依赖边 {dep_stats['total']} 条（指标 {graph_stats['counts']['metric']} / "
        f"字段 {graph_stats['counts']['field']} / 报表 {graph_stats['counts']['report']}）；"
        f"同名冲突 {summary['conflicts_total']} 处，依赖环 {summary['cycles_total']} 个；"
        f"切换新增边 {dep_stats['added']}，清理边 {dep_stats['removed']}"
    )
    run.finished_at = utcnow()
    # 切换已完成，候选不再需要
    staging_service.discard_candidate(db, run.id)
    db.flush()
    return run


def create_and_execute(
    db: Session,
    *,
    trigger: str,
    operator_email: str,
    seed_key: str | None = None,
) -> Run:
    if seed_key:
        existing = db.scalar(select(Run).where(Run.seed_key == seed_key))
        if existing is not None:
            return existing
    run = Run(
        run_no=next_run_no(db),
        trigger=trigger,
        status="running",
        operator_email=operator_email,
        seed_key=seed_key,
    )
    db.add(run)
    db.flush()
    return execute_run(db, run)


def resume_run(db: Session, run_id: int) -> Run:
    """重试一次失败的校验运行：复用原 Run 与原候选，不新增运行记录。"""
    run = db.get(Run, run_id)
    if run is None:
        raise not_found("run", run_id)
    if run.status != "failed":
        raise AppError(
            "CONFLICT",
            409,
            {"run_id": run_id, "status": run.status},
            message="只有失败的校验运行可以续跑",
        )
    candidate = staging_service.get_candidate(db, run.id)
    if candidate is None:
        # 候选缺失（理论上不会发生）：重建候选从头跑，但仍复用同一条 Run
        candidate = staging_service.create_candidate(db, run.id)
    return execute_run(db, run)


def list_runs(db: Session, *, status: str | None, limit: int, offset: int) -> dict:
    stmt = select(Run)
    count_stmt = select(func.count()).select_from(Run)
    if status:
        stmt = stmt.where(Run.status == status)
        count_stmt = count_stmt.where(Run.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Run.id.desc()).limit(limit).offset(offset)).all()
    return {"items": [serialize(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def get_run(db: Session, run_id: int) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise not_found("run", run_id)
    return run


def app_name() -> str:
    return settings.app_name
