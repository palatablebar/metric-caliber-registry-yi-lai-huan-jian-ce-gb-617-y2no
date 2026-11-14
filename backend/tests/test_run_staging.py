"""校验运行的候选隔离 / 原子切换 / 失败保留 / 断点续跑集成测试（内存 SQLite）。

覆盖需求：
- 校验未完成时中间产物只落候选表，线上 formulas/dependencies 保持上一份可用结果；
- 成功后解析结果、依赖边在同一事务一次性切换；
- 切换阶段失败整体回滚，不出现新旧混合，旧口径可恢复；
- 失败位置写入 Run.failure_info，候选保留；
- 续跑同一校验复用原 Run（不新增运行记录），parse 阶段跳过已完成的指标解析。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base
from src.models.dependency import Dependency
from src.models.formula import Formula
from src.models.metric import Metric
from src.models.report import Report
from src.models.run import Run
from src.models.run_candidate import CandidateDependency, CandidateFormula, RunCandidate
from src.services import dsl_parser, graph_service, run_service, staging_service
from src.utils.errors import AppError


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def add_metric(db: Session, code: str, name: str, dsl: str) -> Metric:
    metric = Metric(
        code=code, name=name, domain="trade", tier="normal", unit="元",
        owner="测试组", status="active",
    )
    db.add(metric)
    db.flush()
    parsed = dsl_parser.parse_dsl(dsl, code)
    db.add(
        Formula(
            metric_id=metric.id, version=1, dsl_text=dsl, author_email="admin@metricreg.io",
            parse_status=parsed["status"], parsed=parsed, signature=parsed["signature"],
            parse_error=None,
        )
    )
    db.flush()
    return metric


def add_report(db: Session, code: str, metric_codes: list[str], *, is_core: bool = False) -> None:
    db.add(
        Report(
            code=code, name=f"报表{code}", owner="测试组", channel="BI",
            is_core=is_core, weight=3 if is_core else 1, metric_codes=list(metric_codes),
        )
    )
    db.flush()


def new_run(db: Session) -> Run:
    run = Run(run_no=run_service.next_run_no(db), trigger="manual",
              status="running", operator_email="analyst@metricreg.io")
    db.add(run)
    db.flush()
    return run


def run_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Run)) or 0


def online_edge_keys(db: Session) -> set[tuple]:
    return {
        (edge.from_metric_id, edge.kind, edge.to_ref)
        for edge in db.scalars(select(Dependency)).all()
    }


# --------------------------------------------------------------------------- #
# 1. 成功路径：候选一次性切换，旧边清理，候选归档
# --------------------------------------------------------------------------- #
def test_successful_run_switches_candidate_atomically_and_cleans_up(db):
    m1 = add_metric(db, "m1", "指标一", "m1 = sum(dwd.order.amount) where st = 'paid' group by dt")
    m2 = add_metric(db, "m2", "指标二", "m2 = sum(@m1) where st = 'paid' group by dt")
    add_report(db, "r1", ["m1"])
    # 一条必然失效的旧边，切换时应被清理
    db.add(Dependency(from_metric_id=m1.id, kind="field", to_ref="dwd.legacy.field", weight=1))
    db.flush()
    stale_edges = online_edge_keys(db)

    run = new_run(db)
    run_service.execute_run(db, run)

    assert run.status == "success"
    assert run.failure_info is None
    # 候选已归档
    assert db.scalar(select(func.count()).select_from(RunCandidate)) == 0
    assert db.scalar(select(func.count()).select_from(CandidateFormula)) == 0
    assert db.scalar(select(func.count()).select_from(CandidateDependency)) == 0

    # 线上公式拿到候选解析结果
    f2 = db.scalar(select(Formula).where(Formula.metric_id == m2.id))
    assert f2.parse_status == "ok"
    assert f2.signature and (f2.parsed or {}).get("deps") == ["m1"]

    # 线上依赖边整体替换：旧边消失，新边齐全
    keys = online_edge_keys(db)
    assert stale_edges - keys == {(m1.id, "field", "dwd.legacy.field")}
    assert (m2.id, "metric", "m1") in keys
    assert (m1.id, "field", "dwd.order.amount") in keys
    assert (m1.id, "report", "r1") in keys
    assert run.metrics["dep_edges"] == {"metric": 1, "field": 1, "report": 1}


# --------------------------------------------------------------------------- #
# 2. graph 阶段失败：线上结果不动，候选保留，续跑不新增运行
# --------------------------------------------------------------------------- #
def test_graph_failure_keeps_previous_result_and_resume_reuses_run(db, monkeypatch):
    m1 = add_metric(db, "m1", "指标一", "m1 = sum(dwd.order.amount) group by dt")
    add_metric(db, "m2", "指标二", "m2 = sum(@m1) group by dt")
    add_report(db, "r1", ["m1"])

    first = new_run(db)
    run_service.execute_run(db, first)
    assert first.status == "success"
    baseline_edges = online_edge_keys(db)
    baseline_summary = graph_service.summary(db)
    m2_signature = db.scalar(select(Formula.signature).where(Formula.metric_id == 2))

    # 第二次校验在 graph 阶段失败
    def boom(*args, **kwargs):
        raise RuntimeError("graph 阶段模拟故障")

    monkeypatch.setattr(staging_service, "stage_graph", boom)
    second = new_run(db)
    run_service.execute_run(db, second)

    assert second.status == "failed"
    assert second.failure_info["stage"] == "graph"
    assert "graph 阶段模拟故障" in second.failure_info["message"]
    # 线上表仍是上一份可用结果（指标详情 / 依赖图 / 总览读不到半成品）
    assert online_edge_keys(db) == baseline_edges
    assert graph_service.summary(db) == baseline_summary
    assert db.scalar(select(Formula.signature).where(Formula.metric_id == 2)) == m2_signature
    # 候选保留，且 parse 已完成
    candidate = staging_service.get_candidate(db, second.id)
    assert candidate is not None and candidate.stage == "graph"
    assert db.scalar(
        select(func.count()).select_from(CandidateFormula)
        .where(CandidateFormula.candidate_id == candidate.id)
    ) == 2
    assert run_count(db) == 2

    # 故障恢复后续跑：复用同一条 Run，不新增运行记录
    monkeypatch.undo()
    resumed = run_service.resume_run(db, second.id)
    assert resumed.id == second.id
    assert resumed.status == "success"
    assert run_count(db) == 2
    assert resumed.metrics["attempts"] == 2
    assert staging_service.get_candidate(db, second.id) is None
    assert online_edge_keys(db) == baseline_edges  # 输入未变，切换结果与基线一致


# --------------------------------------------------------------------------- #
# 3. parse 阶段失败：失败位置定位到指标，续跑跳过已完成解析
# --------------------------------------------------------------------------- #
def test_parse_failure_resume_skips_completed_metrics(db, monkeypatch):
    add_metric(db, "m1", "指标一", "m1 = sum(dwd.a.amount) group by dt")
    add_metric(db, "m2", "指标二", "m2 = sum(dwd.b.amount) group by dt")
    add_metric(db, "m3", "指标三", "m3 = sum(dwd.c.amount) group by dt")

    real_parse = dsl_parser.parse_dsl
    first_calls: list[str] = []

    def failing_parse(text, metric_code=None):
        first_calls.append(metric_code)
        if metric_code == "m2":
            raise RuntimeError("解析器模拟故障")
        return real_parse(text, metric_code)

    monkeypatch.setattr(staging_service.dsl_parser, "parse_dsl", failing_parse)
    run = new_run(db)
    run_service.execute_run(db, run)

    assert run.status == "failed"
    assert run.failure_info["stage"] == "parse"
    assert run.failure_info["metric_code"] == "m2"
    assert first_calls == ["m1", "m2"]  # m3 还没轮到
    candidate = staging_service.get_candidate(db, run.id)
    assert candidate.stage == "parse"
    assert candidate.parsed_codes == ["m1"]
    # 已完成指标的候选解析保留
    kept = db.scalars(
        select(CandidateFormula).where(CandidateFormula.candidate_id == candidate.id)
    ).all()
    assert {row.metric_code for row in kept} == {"m1"}
    assert run_count(db) == 1

    # 恢复后续跑：m1 不再重复解析，只补 m2 / m3
    resume_calls: list[str] = []

    def counting_parse(text, metric_code=None):
        resume_calls.append(metric_code)
        return real_parse(text, metric_code)

    monkeypatch.setattr(staging_service.dsl_parser, "parse_dsl", counting_parse)
    resumed = run_service.resume_run(db, run.id)
    assert resumed.id == run.id
    assert resumed.status == "success"
    assert sorted(resume_calls) == ["m2", "m3"]
    assert run_count(db) == 1  # 重跑同一校验没有新增运行
    assert staging_service.get_candidate(db, run.id) is None


# --------------------------------------------------------------------------- #
# 4. cutover 阶段失败：阶段内改动随保存点回滚，线上不出现混合状态
# --------------------------------------------------------------------------- #
def test_cutover_failure_rolls_back_mutation_and_is_resumable(db, monkeypatch):
    m1 = add_metric(db, "m1", "指标一", "m1 = sum(dwd.order.amount) group by dt")
    first = new_run(db)
    run_service.execute_run(db, first)
    original_signature = db.scalar(select(Formula.signature).where(Formula.metric_id == m1.id))
    baseline_edges = online_edge_keys(db)

    def dirty_then_fail(*args, **kwargs):
        # 模拟切换进行到一半：先改了线上公式，随后失败
        formula = db.scalar(select(Formula).where(Formula.metric_id == m1.id))
        formula.signature = "DIRTY-HALF-SWITCHED"
        db.flush()
        raise RuntimeError("cutover 阶段模拟故障")

    monkeypatch.setattr(staging_service, "stage_cutover", dirty_then_fail)
    second = new_run(db)
    run_service.execute_run(db, second)
    assert second.status == "failed"
    assert second.failure_info["stage"] == "cutover"

    # 保存点回滚：线上公式恢复旧值，依赖边仍是旧图，没有新旧混合
    db.expire_all()
    assert db.scalar(select(Formula.signature).where(Formula.metric_id == m1.id)) == original_signature
    assert online_edge_keys(db) == baseline_edges
    candidate = staging_service.get_candidate(db, second.id)
    assert candidate is not None and candidate.stage == "cutover"

    monkeypatch.undo()
    resumed = run_service.resume_run(db, second.id)
    assert resumed.id == second.id and resumed.status == "success"
    assert run_count(db) == 2
    assert staging_service.get_candidate(db, second.id) is None


# --------------------------------------------------------------------------- #
# 5. 只有失败的运行可以续跑
# --------------------------------------------------------------------------- #
def test_resume_non_failed_run_conflicts(db):
    add_metric(db, "m1", "指标一", "m1 = sum(dwd.order.amount) group by dt")
    run = new_run(db)
    run_service.execute_run(db, run)
    assert run.status == "success"
    with pytest.raises(AppError) as exc:
        run_service.resume_run(db, run.id)
    assert exc.value.status_code == 409


# --------------------------------------------------------------------------- #
# 6. seed_key 幂等：同一 key 不新增运行
# --------------------------------------------------------------------------- #
def test_seed_key_does_not_create_duplicate_run(db):
    add_metric(db, "m1", "指标一", "m1 = sum(dwd.order.amount) group by dt")
    first = run_service.create_and_execute(
        db, trigger="seed", operator_email="seed@metricreg.io", seed_key="seed-run-1"
    )
    second = run_service.create_and_execute(
        db, trigger="seed", operator_email="seed@metricreg.io", seed_key="seed-run-1"
    )
    assert first.id == second.id
    assert run_count(db) == 1


# --------------------------------------------------------------------------- #
# 7. 失败位置随运行序列化输出
# --------------------------------------------------------------------------- #
def test_failure_info_is_serialized(db, monkeypatch):
    add_metric(db, "m1", "指标一", "m1 = sum(dwd.order.amount) group by dt")

    def boom(*args, **kwargs):
        raise RuntimeError("analyze 阶段模拟故障")

    monkeypatch.setattr(staging_service, "stage_graph", boom)
    run = new_run(db)
    run_service.execute_run(db, run)

    payload = run_service.serialize(run)
    assert payload["failure_info"]["stage"] == "graph"
    assert payload["failure_info"]["at"]
    assert payload["finished_at"] is not None
