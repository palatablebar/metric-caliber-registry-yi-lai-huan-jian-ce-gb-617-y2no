"""共享枚举（后端唯一定义处）。前端副本见 frontend/site/js/config.js。

README「共享枚举出现位置」一节列出全部出现点，改动需两侧同步。
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class MetricDomain(StrEnum):
    """指标所属业务域。"""

    TRADE = "trade"
    TRAFFIC = "traffic"
    MEMBER = "member"
    GOODS = "goods"
    FINANCE = "finance"


METRIC_DOMAIN_LABELS: dict[str, str] = {
    MetricDomain.TRADE.value: "交易",
    MetricDomain.TRAFFIC.value: "流量",
    MetricDomain.MEMBER.value: "会员",
    MetricDomain.GOODS.value: "商品",
    MetricDomain.FINANCE.value: "财务",
}


class MetricTier(StrEnum):
    """指标分级：核心指标口径变更必须走变更单。"""

    CORE = "core"
    NORMAL = "normal"


METRIC_TIER_LABELS: dict[str, str] = {
    MetricTier.CORE.value: "核心",
    MetricTier.NORMAL.value: "普通",
}


class MetricStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


METRIC_STATUS_LABELS: dict[str, str] = {
    MetricStatus.DRAFT.value: "草稿",
    MetricStatus.ACTIVE.value: "生效中",
    MetricStatus.DEPRECATED.value: "已下线",
}


class ParseStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


PARSE_STATUS_LABELS: dict[str, str] = {
    ParseStatus.OK.value: "解析通过",
    ParseStatus.ERROR.value: "解析失败",
}


class DependencyKind(StrEnum):
    """依赖边类型：指标引用指标 / 指标引用数仓字段 / 报表引用指标。"""

    METRIC = "metric"
    FIELD = "field"
    REPORT = "report"


DEPENDENCY_KIND_LABELS: dict[str, str] = {
    DependencyKind.METRIC.value: "指标引用",
    DependencyKind.FIELD.value: "字段依赖",
    DependencyKind.REPORT.value: "报表引用",
}


class ChangeKind(StrEnum):
    FIELD_TYPE = "field_type"
    CALIBER = "caliber"
    FORMULA = "formula"


CHANGE_KIND_LABELS: dict[str, str] = {
    ChangeKind.FIELD_TYPE.value: "字段类型变更",
    ChangeKind.CALIBER.value: "口径调整",
    ChangeKind.FORMULA.value: "公式改写",
}


class ChangeStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


CHANGE_STATUS_LABELS: dict[str, str] = {
    ChangeStatus.PENDING.value: "待审批",
    ChangeStatus.APPROVED.value: "已批准",
    ChangeStatus.REJECTED.value: "已驳回",
}

CHANGE_STATUS_ORDER: list[str] = [
    ChangeStatus.PENDING.value,
    ChangeStatus.APPROVED.value,
    ChangeStatus.REJECTED.value,
]


class ConflictKind(StrEnum):
    """同名指标口径差异的类型。"""

    FILTER_DIFF = "filter_diff"
    FIELD_DIFF = "field_diff"
    AGG_DIFF = "agg_diff"
    DEP_DIFF = "dep_diff"


CONFLICT_KIND_LABELS: dict[str, str] = {
    ConflictKind.FILTER_DIFF.value: "过滤条件不同",
    ConflictKind.FIELD_DIFF.value: "字段集不同",
    ConflictKind.AGG_DIFF.value: "聚合方式不同",
    ConflictKind.DEP_DIFF.value: "引用指标不同",
}


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


SEVERITY_LABELS: dict[str, str] = {
    Severity.HIGH.value: "高",
    Severity.MEDIUM.value: "中",
    Severity.LOW.value: "低",
}

SEVERITY_ORDER: list[str] = [Severity.HIGH.value, Severity.MEDIUM.value, Severity.LOW.value]


class TriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    SEED = "seed"


TRIGGER_LABELS: dict[str, str] = {
    TriggerKind.MANUAL.value: "手动",
    TriggerKind.SCHEDULE.value: "定时",
    TriggerKind.SEED.value: "初始化",
}


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


RUN_STATUS_LABELS: dict[str, str] = {
    RunStatus.QUEUED.value: "排队中",
    RunStatus.RUNNING.value: "执行中",
    RunStatus.SUCCESS.value: "成功",
    RunStatus.PARTIAL.value: "部分成功",
    RunStatus.FAILED.value: "失败",
}

# 报表权重：核心报表 ×3
REPORT_WEIGHT_CORE = 3
REPORT_WEIGHT_NORMAL = 1
