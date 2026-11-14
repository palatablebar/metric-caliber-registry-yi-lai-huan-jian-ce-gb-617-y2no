"""依赖图服务：把数据库里的指标/公式/报表装配成算法 B 的纯 dict 输入。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import METRIC_DOMAIN_LABELS
from src.models.metric import Metric
from src.services import formula_service, graph_analysis, report_service
from src.utils.errors import AppError


def collect_inputs(db: Session) -> tuple[list[dict], dict[str, list[dict]], dict[str, Metric]]:
    metrics = db.scalars(select(Metric).order_by(Metric.code)).all()
    latest = formula_service.latest_map(db)
    reports_index = report_service.reports_by_metric(db)
    payloads: list[dict] = []
    for metric in metrics:
        formula = latest.get(metric.id)
        parsed = (formula.parsed or {}) if formula else {}
        parse_status = formula.parse_status if formula else "error"
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
                "signature": formula.signature if formula else "",
                "parse_status": parse_status,
                "aggs": parsed.get("aggs") or [],
                "fields": parsed.get("fields") or [],
                "filters": parsed.get("filters") or [],
                "dims": parsed.get("dims") or [],
                "deps": parsed.get("deps") or [],
                "expression": parsed.get("expression") or "",
            }
        )
    return payloads, reports_index, {metric.code: metric for metric in metrics}


def find_conflicts(db: Session) -> list[dict]:
    metrics, reports_index, _ = collect_inputs(db)
    return graph_analysis.find_conflicts(metrics, reports_index)


def find_cycles(db: Session) -> list[dict]:
    metrics, reports_index, _ = collect_inputs(db)
    return graph_analysis.find_cycles(metrics, reports_index)


def summary(db: Session) -> dict:
    metrics, reports_index, _ = collect_inputs(db)
    return graph_analysis.summarize(metrics, reports_index)


def graph(db: Session) -> dict:
    metrics, reports_index, _ = collect_inputs(db)
    dep_map = graph_analysis.build_dep_map(metrics)
    cycles = graph_analysis.find_cycles(metrics, reports_index)
    in_cycle = {code for cycle in cycles for code in cycle["members"]}
    report_codes: dict[str, list[str]] = {
        code: [report["code"] for report in reports] for code, reports in reports_index.items()
    }
    nodes = [
        {
            "code": metric["code"],
            "name": metric["name"],
            "domain": metric["domain"],
            "domain_label": metric["domain_label"],
            "tier": metric["tier"],
            "version": metric["version"],
            "parse_status": metric["parse_status"],
            "in_cycle": metric["code"] in in_cycle,
            "dep_count": len(dep_map.get(metric["code"], [])),
            "report_count": len(report_codes.get(metric["code"], [])),
            "reports": report_codes.get(metric["code"], []),
        }
        for metric in metrics
    ]
    edges = [
        {"from": code, "to": ref, "kind": "metric"}
        for code in sorted(dep_map)
        for ref in dep_map[code]
    ]
    edges += [
        {"from": code, "to": report, "kind": "report"}
        for code in sorted(report_codes)
        for report in report_codes[code]
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "dep_edges": [edge for edge in edges if edge["kind"] == "metric"],
        "cycles": cycles,
        "stats": {
            "nodes": len(nodes),
            "dep_edges": sum(len(refs) for refs in dep_map.values()),
            "report_edges": sum(len(refs) for refs in report_codes.values()),
            "cycles": len(cycles),
            "cycle_nodes": len(in_cycle),
        },
    }


def impact_for_field(db: Session, field: str) -> dict:
    metrics, reports_index, _ = collect_inputs(db)
    impact = graph_analysis.impact_of_field(field, metrics, reports_index)
    if not impact.get("metric_codes"):
        raise AppError("NOT_FOUND", 404, {"entity": "field", "field": field})
    return impact


def impact_for_metric(db: Session, code: str) -> dict:
    metrics, reports_index, by_code = collect_inputs(db)
    if code not in by_code:
        raise AppError("NOT_FOUND", 404, {"entity": "metric", "code": code})
    return graph_analysis.impact_of_metric(code, metrics, reports_index)
