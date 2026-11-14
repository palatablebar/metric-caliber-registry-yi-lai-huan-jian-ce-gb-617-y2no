"""算法 A（指标 DSL 解析）单测：正常 / 边界 / 确定性。"""
from __future__ import annotations

from src.services import dsl_parser

GMV_DSL = "gmv = sum(dwd.order.amount) where order_status = 'paid' group by dt"


def test_parse_aggregation_fields_filters_dims():
    result = dsl_parser.parse_dsl(GMV_DSL, "gmv")
    assert result["status"] == "ok"
    assert result["aggs"] == ["sum"]
    assert result["fields"] == ["dwd.order.amount"]
    assert result["dims"] == ["dt"]
    assert result["filters"] == ["order_status = 'paid'"]
    assert result["error"] is None


def test_parse_two_terms_and_metric_reference():
    dsl = "gmv_net = sum(dwd.order.amount) - sum(@gmv) where refund_status = 'done' group by dt"
    result = dsl_parser.parse_dsl(dsl, "gmv_net")
    assert result["status"] == "ok"
    assert result["aggs"] == ["sum", "sum"]
    assert result["fields"] == ["dwd.order.amount"]
    assert result["deps"] == ["gmv"]
    assert result["filters"] == ["refund_status = 'done'"]


def test_signature_ignores_term_order():
    first = dsl_parser.parse_dsl("x = sum(a.b) - sum(c.d) where k = 1", "x")
    second = dsl_parser.parse_dsl("x = sum(c.d) - sum(a.b) where k = 1", "x")
    assert first["signature"] == second["signature"]


def test_unknown_aggregation_reports_position():
    result = dsl_parser.parse_dsl("m = median(dwd.order.amount)", "m")
    assert result["status"] == "error"
    assert result["error"]["code"] == "UNKNOWN_AGG"
    assert result["error"]["column"] == 5  # 1 基列号：median 从第 5 列开始


def test_unbalanced_parenthesis():
    result = dsl_parser.parse_dsl("m = sum(dwd.order.amount", "m")
    assert result["status"] == "error"
    assert result["error"]["code"] == "UNBALANCED_PAREN"
    assert result["error"]["position"] == len("m = sum(dwd.order.amount")


def test_self_reference_rejected():
    result = dsl_parser.parse_dsl("a = sum(@a)", "a")
    assert result["status"] == "error"
    assert result["error"]["code"] == "SELF_REFERENCE"


def test_empty_dsl_and_count_star():
    empty = dsl_parser.parse_dsl("   ", "x")
    assert empty["status"] == "error" and empty["error"]["code"] == "EMPTY_DSL"
    star = dsl_parser.parse_dsl("x = count(*) where dt >= '2026-01-01'", "x")
    assert star["status"] == "ok"
    assert star["fields"] == []


def test_deterministic_repeat():
    first = dsl_parser.parse_dsl(GMV_DSL, "gmv")
    second = dsl_parser.parse_dsl(GMV_DSL, "gmv")
    assert first == second
    assert len(first["signature"]) == 16
