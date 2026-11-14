"""导出服务：指标清单 / 冲突与影响面 / 变更单 / 运行记录（CSV，UTF-8 BOM）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import (
    CHANGE_KIND_LABELS,
    CHANGE_STATUS_LABELS,
    CONFLICT_KIND_LABELS,
    METRIC_DOMAIN_LABELS,
    METRIC_TIER_LABELS,
    RUN_STATUS_LABELS,
    SEVERITY_LABELS,
    TRIGGER_LABELS,
)
from src.models.change_request import ChangeRequest
from src.models.metric import Metric
from src.models.run import Run
from src.services import formula_service, graph_service, report_service
from src.utils.csv_export import to_csv


def metrics_csv(db: Session) -> bytes:
    metrics = db.scalars(select(Metric).order_by(Metric.code)).all()
    latest = formula_service.latest_map(db)
    reports_index = report_service.reports_by_metric(db)
    headers = [
        "指标编码", "指标名称", "业务域", "分级", "单位", "负责人", "当前版本",
        "解析状态", "解析错误", "表达式", "字段", "过滤条件", "依赖指标", "下游报表", "报表数", "状态",
    ]
    rows = []
    for metric in metrics:
        formula = latest.get(metric.id)
        parsed = (formula.parsed or {}) if formula else {}
        reports = reports_index.get(metric.code, [])
        rows.append(
            [
                metric.code,
                metric.name,
                METRIC_DOMAIN_LABELS.get(metric.domain, metric.domain),
                METRIC_TIER_LABELS.get(metric.tier, metric.tier),
                metric.unit,
                metric.owner,
                metric.current_version,
                formula.parse_status if formula else "error",
                (formula.parse_error if formula else "缺少口径公式") or "",
                parsed.get("expression") or (formula.dsl_text if formula else ""),
                " | ".join(parsed.get("fields") or []),
                " | ".join(parsed.get("filters") or []),
                " | ".join(parsed.get("deps") or []),
                " | ".join(report["name"] for report in reports),
                len(reports),
                metric.status,
            ]
        )
    return to_csv(headers, rows)


def conflicts_csv(db: Session) -> bytes:
    conflicts = graph_service.find_conflicts(db)
    headers = [
        "同名指标", "冲突编号", "差异类型", "严重度", "影响分", "口径成员", "字段差异",
        "过滤条件差异", "下游报表数", "核心报表数", "下游报表", "建议动作",
    ]
    rows = []
    for item in conflicts:
        diff = item.get("diff") or {}
        impact = item.get("impact") or {}
        rows.append(
            [
                item["name"],
                item["id"],
                CONFLICT_KIND_LABELS.get(item["kind"], item["kind"]),
                SEVERITY_LABELS.get(item["severity"], item["severity"]),
                item["score"],
                " | ".join(metric["code"] for metric in item["metrics"]),
                " | ".join(diff.get("fields_only_first", []) + diff.get("fields_only_others", [])),
                " | ".join(diff.get("filters_only_first", []) + diff.get("filters_only_others", [])),
                impact.get("report_count", 0),
                impact.get("core_count", 0),
                " | ".join(impact.get("report_names", [])),
                item.get("suggestion", ""),
            ]
        )
    return to_csv(headers, rows)


def change_requests_csv(db: Session) -> bytes:
    changes = db.scalars(select(ChangeRequest).order_by(ChangeRequest.id)).all()
    codes = {metric.id: metric.code for metric in db.scalars(select(Metric)).all()}
    headers = [
        "变更单号", "目标", "指标", "类型", "严重度", "影响分", "影响指标数",
        "影响报表数", "核心报表数", "状态", "申请人", "审批人", "原因", "申请时间", "决定时间",
    ]
    rows = [
        [
            change.cr_no,
            change.target_ref,
            codes.get(change.metric_id or -1, ""),
            CHANGE_KIND_LABELS.get(change.change_kind, change.change_kind),
            SEVERITY_LABELS.get(change.severity, change.severity),
            change.impact_score,
            (change.impact or {}).get("metric_count", len((change.impact or {}).get("metric_codes") or [])),
            (change.impact or {}).get("report_count", 0),
            (change.impact or {}).get("core_count", 0),
            CHANGE_STATUS_LABELS.get(change.status, change.status),
            change.requester_email,
            change.approver_email or "",
            change.reason,
            change.created_at.strftime("%Y-%m-%d %H:%M") if change.created_at else "",
            change.decided_at.strftime("%Y-%m-%d %H:%M") if change.decided_at else "",
        ]
        for change in changes
    ]
    return to_csv(headers, rows)


def runs_csv(db: Session) -> bytes:
    runs = db.scalars(select(Run).order_by(Run.id)).all()
    headers = [
        "运行号", "触发方式", "状态", "指标数", "问题数", "冲突数", "环数",
        "解析失败数", "操作人", "开始时间", "结束时间", "日志",
    ]
    rows = [
        [
            run.run_no,
            TRIGGER_LABELS.get(run.trigger, run.trigger),
            RUN_STATUS_LABELS.get(run.status, run.status),
            run.input_count,
            run.output_count,
            (run.metrics or {}).get("conflicts_total", 0),
            (run.metrics or {}).get("cycles_total", 0),
            (run.metrics or {}).get("parse_error_count", 0),
            run.operator_email,
            run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "",
            run.finished_at.strftime("%Y-%m-%d %H:%M") if run.finished_at else "",
            (run.log_text or "").replace("\n", " "),
        ]
        for run in runs
    ]
    return to_csv(headers, rows)
