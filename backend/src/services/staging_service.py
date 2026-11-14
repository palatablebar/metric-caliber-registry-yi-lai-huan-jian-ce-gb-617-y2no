"""隔离候选服务：校验运行的全部中间产物先写候选表，成功后一次性切换到线上表。

阶段（与 RunCandidate.stage 对应）：

    parse    算法 A 逐指标解析，结果写 candidate_formulas（不碰 formulas）
    graph    按候选解析结果重建候选依赖边，写 candidate_dependencies（不碰 dependencies）
    analyze  基于候选跑算法 B（环 / 同名冲突 / 影响面），纯计算
    cutover  单事务把候选解析结果、依赖边切换到线上表
    done     切换完成

失败时只更新候选的 failure_info，线上表保持上一份可用结果；重试同一运行时
沿用原候选，parse 阶段跳过 parsed_codes 里已完成的指标。
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.constants.enums import DependencyKind
from src.models.dependency import Dependency
from src.models.formula import Formula
from src.models.metric import Metric
from src.models.report import Report
from src.models.run_candidate import CandidateDependency, CandidateFormula, RunCandidate
from src.services import dsl_parser, formula_service
from src.utils.timeutil import utcnow

STAGE_PARSE = "parse"
STAGE_GRAPH = "graph"
STAGE_ANALYZE = "analyze"
STAGE_CUTOVER = "cutover"
STAGE_DONE = "done"


class StageFailure(Exception):
    """阶段执行失败：携带阶段名与（可选的）失败指标编码，供运行层记录失败位置。"""

    def __init__(self, stage: str, message: str, metric_code: str | None = None):
        self.stage = stage
        self.metric_code = metric_code
        super().__init__(message)


# --------------------------------------------------------------------------- #
# 候选生命周期
# --------------------------------------------------------------------------- #
def create_candidate(db: Session, run_id: int) -> RunCandidate:
    candidate = RunCandidate(run_id=run_id, stage=STAGE_PARSE, parsed_codes=[], attempts=1)
    db.add(candidate)
    db.flush()
    return candidate


def get_candidate(db: Session, run_id: int) -> RunCandidate | None:
    return db.scalar(select(RunCandidate).where(RunCandidate.run_id == run_id))


def mark_failure(candidate: RunCandidate, *, stage: str, message: str, metric_code: str | None = None,
                 error: dict | None = None) -> None:
    """记录失败位置；线上表不在此处改动，旧结果继续可用。"""
    candidate.stage = stage
    candidate.failure_info = {
        "stage": stage,
        "metric_code": metric_code,
        "message": message[:500],
        "error": error,
        "at": utcnow().isoformat(timespec="seconds") + "Z",
    }


def mark_stage(candidate: RunCandidate, stage: str) -> None:
    candidate.stage = stage
    candidate.failure_info = None


# --------------------------------------------------------------------------- #
# 阶段 1：算法 A 解析 → candidate_formulas（断点续跑，不重复已完成的解析）
# --------------------------------------------------------------------------- #
def stage_parse(db: Session, candidate: RunCandidate, metrics: list[Metric],
                latest: dict[int, Formula]) -> list[CandidateFormula]:
    """把未解析过的指标补解析进候选；已在 parsed_codes 中的指标直接跳过。"""
    done = set(candidate.parsed_codes or [])
    rows = {
        row.metric_code: row
        for row in db.scalars(
            select(CandidateFormula).where(CandidateFormula.candidate_id == candidate.id)
        ).all()
    }
    for metric in metrics:
        if metric.code in done:
            continue
        formula = latest.get(metric.id)
        dsl_text = formula.dsl_text if formula else ""
        # 每个指标一个保存点：单个指标失败只回滚该指标，已完成的候选解析保留
        try:
            with db.begin_nested():
                parsed = dsl_parser.parse_dsl(dsl_text, metric.code)
                row = rows.get(metric.code)
                if row is None:
                    row = CandidateFormula(candidate_id=candidate.id, metric_id=metric.id, metric_code=metric.code)
                    db.add(row)
                row.formula_id = formula.id if formula else None
                row.dsl_text = dsl_text
                row.parsed = {
                    key: parsed.get(key)
                    for key in ("name", "aggs", "fields", "filters", "dims", "deps",
                                "expression", "where_text", "error")
                }
                if parsed["status"] == "ok":
                    row.parse_status = "ok"
                    row.parse_error = None
                    row.signature = parsed["signature"]
                else:
                    row.parse_status = "error"
                    error = parsed.get("error") or {}
                    row.parse_error = (
                        f"{error.get('code')} @{error.get('column')}: {error.get('message')}"
                    )
                    row.signature = ""
        except Exception as exc:  # noqa: BLE001 - 保留失败位置后交给运行层留痕
            raise StageFailure(STAGE_PARSE, str(exc) or exc.__class__.__name__, metric.code) from exc
        done.add(metric.code)
        candidate.parsed_codes = sorted(done)
        # 进度立刻落候选，中途失败后已完成的解析不会丢
        db.flush()
    mark_stage(candidate, STAGE_GRAPH)
    db.flush()
    return db.scalars(
        select(CandidateFormula)
        .where(CandidateFormula.candidate_id == candidate.id)
        .order_by(CandidateFormula.metric_code)
    ).all()


def candidate_parse_map(rows: list[CandidateFormula]) -> dict[str, dict]:
    """把候选解析行装配成 graph_analysis / 依赖构建需要的 dict（按 metric.code 索引）。"""
    return {
        row.metric_code: {
            "status": row.parse_status,
            "deps": (row.parsed or {}).get("deps") or [],
            "fields": (row.parsed or {}).get("fields") or [],
            "parsed": row.parsed or {},
            "signature": row.signature,
        }
        for row in rows
    }


# --------------------------------------------------------------------------- #
# 阶段 2：候选依赖边 → candidate_dependencies（不碰线上 dependencies）
# --------------------------------------------------------------------------- #
def _desired_edges(metrics: list[Metric], parsed_by_code: dict[str, dict],
                   reports: list[Report]) -> list[dict]:
    by_code = {metric.code: metric for metric in metrics}
    desired: dict[tuple[int, str, str], dict] = {}
    for metric in metrics:
        parsed = parsed_by_code.get(metric.code) or {}
        if parsed.get("status") != "ok":
            continue
        for ref in parsed.get("deps") or []:
            if ref in by_code:
                desired[(metric.id, DependencyKind.METRIC.value, ref)] = {
                    "from_metric_code": metric.code,
                    "to_metric_id": by_code[ref].id,
                    "weight": 1,
                    "note": "DSL 引用",
                }
        for field in parsed.get("fields") or []:
            desired[(metric.id, DependencyKind.FIELD.value, field)] = {
                "from_metric_code": metric.code,
                "to_metric_id": None,
                "weight": 1,
                "note": "数仓字段",
            }
    for report in reports:
        for metric_code in report.metric_codes or []:
            metric = by_code.get(metric_code)
            if metric is None:
                continue
            desired[(metric.id, DependencyKind.REPORT.value, report.code)] = {
                "from_metric_code": metric.code,
                "to_metric_id": None,
                "weight": report.weight or 1,
                "note": "报表引用",
            }
    edges = []
    for (from_metric_id, kind, to_ref), payload in desired.items():
        edges.append(
            {
                "from_metric_id": from_metric_id,
                "from_metric_code": payload["from_metric_code"],
                "kind": kind,
                "to_ref": to_ref,
                "to_metric_id": payload["to_metric_id"],
                "weight": payload["weight"],
                "note": payload["note"],
            }
        )
    edges.sort(key=lambda item: (item["from_metric_id"], item["kind"], item["to_ref"]))
    return edges


def stage_graph(db: Session, candidate: RunCandidate, metrics: list[Metric],
                parsed_by_code: dict[str, dict]) -> dict:
    """按候选解析结果全量重建该运行的候选依赖边，返回边统计。"""
    # 进入阶段即标记：阶段中途失败，候选头表也停在正确阶段，续跑才能从这里恢复
    mark_stage(candidate, STAGE_GRAPH)
    db.flush()
    reports = db.scalars(select(Report).order_by(Report.code)).all()
    desired = _desired_edges(metrics, parsed_by_code, reports)

    db.execute(delete(CandidateDependency).where(CandidateDependency.candidate_id == candidate.id))
    for edge in desired:
        db.add(CandidateDependency(candidate_id=candidate.id, **edge))
    mark_stage(candidate, STAGE_ANALYZE)
    db.flush()
    counts = {
        DependencyKind.METRIC.value: sum(1 for edge in desired if edge["kind"] == DependencyKind.METRIC.value),
        DependencyKind.FIELD.value: sum(1 for edge in desired if edge["kind"] == DependencyKind.FIELD.value),
        DependencyKind.REPORT.value: sum(1 for edge in desired if edge["kind"] == DependencyKind.REPORT.value),
    }
    return {"total": len(desired), "counts": counts, "edges": desired}


# --------------------------------------------------------------------------- #
# 阶段 3：基于候选装配算法 B 的纯 dict 输入（线上表全程不参与）
# --------------------------------------------------------------------------- #
def candidate_payloads(metrics: list[Metric], rows: list[CandidateFormula]) -> list[dict]:
    from src.constants.enums import METRIC_DOMAIN_LABELS

    by_metric_id = {row.metric_id: row for row in rows}
    payloads: list[dict] = []
    for metric in metrics:
        row = by_metric_id.get(metric.id)
        parsed = (row.parsed if row else None) or {}
        payloads.append(
            {
                "metric_id": metric.id,
                "code": metric.code,
                "name": metric.name,
                "domain": metric.domain,
                "domain_label": METRIC_DOMAIN_LABELS.get(metric.domain, metric.domain),
                "tier": metric.tier,
                "owner": metric.owner,
                "status": metric.status,
                "version": metric.current_version,
                "signature": row.signature if row else "",
                "parse_status": row.parse_status if row else "error",
                "aggs": parsed.get("aggs") or [],
                "fields": parsed.get("fields") or [],
                "filters": parsed.get("filters") or [],
                "dims": parsed.get("dims") or [],
                "deps": parsed.get("deps") or [],
                "expression": parsed.get("expression") or "",
            }
        )
    return payloads


# --------------------------------------------------------------------------- #
# 阶段 4：一次性切换（cutover）——同一事务内替换 formulas 解析结果与依赖边
# --------------------------------------------------------------------------- #
def stage_cutover(db: Session, candidate: RunCandidate, metrics: list[Metric],
                  candidate_rows: list[CandidateFormula], desired_edges: list[dict]) -> dict:
    """把候选解析结果应用到线上 formulas，并整体替换线上依赖边。

    与调用方处于同一事务：任何一步失败整体回滚，线上表仍指向上一份可用结果，
    不会出现指标已更新、依赖边还是旧图的混合状态。
    """
    # 进入阶段即标记：切换中途失败，续跑从 cutover 重新整体切换
    mark_stage(candidate, STAGE_CUTOVER)
    db.flush()
    # 4.1 候选解析结果 -> 线上最新公式（只改解析字段，不新增公式版本）
    by_metric_id = {row.metric_id: row for row in candidate_rows}
    latest = formula_service.latest_map(db)
    for metric in metrics:
        row = by_metric_id.get(metric.id)
        formula = latest.get(metric.id)
        if formula is None or row is None:
            continue
        formula.parsed = row.parsed
        formula.parse_status = row.parse_status
        formula.parse_error = row.parse_error
        formula.signature = row.signature
    db.flush()

    # 4.2 候选依赖边整体替换线上依赖边（先删后插，同一事务）
    existing = db.scalars(select(Dependency)).all()
    existing_keys = {(edge.from_metric_id, edge.kind, edge.to_ref) for edge in existing}
    desired_keys = {(edge["from_metric_id"], edge["kind"], edge["to_ref"]) for edge in desired_edges}
    removed = len(existing_keys - desired_keys)
    added = len(desired_keys - existing_keys)
    if existing:
        db.execute(delete(Dependency).where(Dependency.id.in_([edge.id for edge in existing])))
    db.flush()
    for edge in desired_edges:
        db.add(
            Dependency(
                from_metric_id=edge["from_metric_id"],
                kind=edge["kind"],
                to_ref=edge["to_ref"],
                to_metric_id=edge["to_metric_id"],
                weight=edge["weight"],
                note=edge["note"],
            )
        )

    candidate.stage = STAGE_DONE
    candidate.failure_info = None
    db.flush()
    return {"added": added, "removed": removed, "total": len(desired_edges)}


def discard_candidate(db: Session, run_id: int) -> None:
    """运行归档后清理候选（切换成功的候选不再需要）。"""
    candidate = get_candidate(db, run_id)
    if candidate is None:
        return
    db.execute(delete(CandidateDependency).where(CandidateDependency.candidate_id == candidate.id))
    db.execute(delete(CandidateFormula).where(CandidateFormula.candidate_id == candidate.id))
    db.delete(candidate)
    db.flush()
