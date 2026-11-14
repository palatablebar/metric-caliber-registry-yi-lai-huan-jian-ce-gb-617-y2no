"""角色 -> 权限点映射。README 与前端 site/js/config.js 同步。

角色键固定为 admin / analyst / viewer，展示名按「指标体系组」职责命名。
"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "指标管理员",
    Role.ANALYST.value: "指标专员",
    Role.VIEWER.value: "报表只读",
}

ROLE_DUTIES: dict[str, str] = {
    Role.ADMIN.value: "注册指标、批准口径变更、导出与审计",
    Role.ANALYST.value: "提交口径变更、跑校验运行、看影响面",
    Role.VIEWER.value: "只读查看指标口径、冲突与依赖图",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "metric:read", "metric:write",
        "formula:write",
        "dependency:read", "report:read", "conflict:read",
        "run:read", "run:create",
        "change:read", "change:write", "change:approve",
        "export:read", "audit:read", "overview:read",
    },
    Role.ANALYST.value: {
        "metric:read",
        "formula:write",
        "dependency:read", "report:read", "conflict:read",
        "run:read", "run:create",
        "change:read", "change:write",
        "export:read", "overview:read",
    },
    Role.VIEWER.value: {
        "metric:read", "dependency:read", "report:read", "conflict:read",
        "run:read", "change:read", "overview:read",
    },
}

METRIC_WRITE_ROLES = (Role.ADMIN.value,)
FORMULA_WRITE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
RUN_CREATE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
CHANGE_WRITE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
CHANGE_APPROVE_ROLES = (Role.ADMIN.value,)
EXPORT_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
AUDIT_ROLES = (Role.ADMIN.value,)
READ_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.VIEWER.value)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
