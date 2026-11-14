"""审计动作 -> 中文标签。"""
from __future__ import annotations

ACTIONS: dict[str, str] = {
    "auth.login": "登录",
    "metric.create": "注册指标",
    "metric.update": "修改指标",
    "formula.parse": "解析口径 DSL",
    "formula.save": "保存口径版本",
    "run.create": "发起校验运行",
    "run.complete": "校验运行完成",
    "change.create": "提交变更单",
    "change.approve": "批准变更单",
    "change.reject": "驳回变更单",
    "export.metrics": "导出指标清单",
    "export.conflicts": "导出冲突与影响面",
    "export.changes": "导出变更单",
    "export.runs": "导出运行记录",
    "http.mutation": "写请求",
}
