"""算法 B（依赖环 / 同名冲突 / 影响面）单测：正常 / 边界 / 确定性。"""
from __future__ import annotations

from src.services import graph_analysis


def _metric(code, name, fields, filters=None, deps=None, aggs=None, dims=None, signature=None):
    return {
        "code": code,
        "name": name,
        "domain": "trade",
        "tier": "normal",
        "owner": "测试",
        "signature": signature or f"sig-{code}",
        "parse_status": "ok",
        "aggs": aggs or ["sum"],
        "fields": fields,
        "filters": filters or [],
        "dims": dims or [],
        "deps": deps or [],
        "expression": f"{code} = sum({fields[0] if fields else '*'})",
    }


REPORTS = {
    "gmv": [
        {"code": "r01", "name": "经营日报", "is_core": True, "weight": 3},
        {"code": "r04", "name": "门店周报", "is_core": False, "weight": 1},
    ],
    "gmv_net": [
        {"code": "r01", "name": "经营日报", "is_core": True, "weight": 3},
        {"code": "r03", "name": "财务月结", "is_core": True, "weight": 3},
    ],
}


def test_tarjan_finds_three_node_cycle():
    dep_map = {"a": ["b"], "b": ["c"], "c": ["a"], "d": []}
    components = graph_analysis.tarjan_scc(dep_map)
    assert ["a", "b", "c"] in components
    assert ["d"] in components


def test_cycle_path_is_real_and_closed():
    metrics = [
        _metric("a", "A", ["t.x"], deps=["b"]),
        _metric("b", "B", ["t.y"], deps=["c"]),
        _metric("c", "C", ["t.z"], deps=["a"]),
    ]
    cycles = graph_analysis.find_cycles(metrics, {})
    assert len(cycles) == 1
    path = cycles[0]["path"]
    assert path[0] == path[-1]
    assert path[0] == "a" and path[1] == "b" and path[2] == "c"
    assert cycles[0]["length"] == 3


def test_self_loop_detected():
    metrics = [_metric("solo", "Solo", ["t.x"], deps=["solo"])]
    cycles = graph_analysis.find_cycles(metrics, {})
    assert len(cycles) == 1
    assert cycles[0]["path"] == ["solo", "solo"]


def test_dag_has_no_cycle():
    metrics = [
        _metric("root", "Root", ["t.x"]),
        _metric("leaf", "Leaf", ["t.y"], deps=["root"]),
    ]
    assert graph_analysis.find_cycles(metrics, {}) == []


def test_same_name_different_filter_is_conflict_high():
    metrics = [
        _metric("gmv", "GMV", ["dwd.order.amount"], filters=["order_status = 'paid'"]),
        _metric("gmv_net", "GMV", ["dwd.order.amount"], filters=["order_status = 'paid' and refund = 0"]),
    ]
    conflicts = graph_analysis.find_conflicts(metrics, REPORTS)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict["name"] == "GMV"
    assert conflict["kind"] == "filter_diff"
    # r01 + r04 + r03 = 3 + 1 + 3 = 7 -> medium；再加一张核心报表即 high
    assert conflict["score"] == 7
    assert conflict["severity"] == "medium"
    assert conflict["impact"]["report_count"] == 3


def test_same_name_same_signature_is_not_conflict():
    metrics = [
        _metric("gmv_a", "GMV", ["dwd.order.amount"], signature="same"),
        _metric("gmv_b", "GMV", ["dwd.order.amount"], signature="same"),
    ]
    assert graph_analysis.find_conflicts(metrics, REPORTS) == []


def test_field_impact_counts_metrics_and_reports():
    metrics = [
        _metric("gmv", "GMV", ["dwd.order.amount"]),
        _metric("gmv_net", "GMV", ["dwd.order.amount"], filters=["refund = 0"]),
        _metric("aov", "客单价", ["dwd.order.amount"]),
        _metric("other", "其他", ["dwd.sku.id"]),
    ]
    impact = graph_analysis.impact_of_field("dwd.order.amount", metrics, REPORTS)
    assert impact["metric_count"] == 3
    assert impact["report_count"] == 3
    assert impact["score"] == 7
    assert impact["severity"] == "medium"
    assert impact["metric_codes"] == ["aov", "gmv", "gmv_net"]


def test_severity_thresholds():
    assert graph_analysis.severity_of(0) == "low"
    assert graph_analysis.severity_of(3) == "medium"
    assert graph_analysis.severity_of(8) == "high"


def test_deterministic_output():
    metrics = [
        _metric("gmv", "GMV", ["dwd.order.amount"], filters=["a = 1"]),
        _metric("gmv_net", "GMV", ["dwd.order.amount", "dwd.refund.amount"]),
        _metric("a", "A", ["t.x"], deps=["b"]),
        _metric("b", "B", ["t.y"], deps=["a"]),
    ]
    first = (graph_analysis.find_conflicts(metrics, REPORTS), graph_analysis.find_cycles(metrics, REPORTS))
    second = (graph_analysis.find_conflicts(metrics, REPORTS), graph_analysis.find_cycles(metrics, REPORTS))
    assert first == second
