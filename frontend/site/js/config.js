/**
 * 项目品牌、导航、角色权限与枚举文案（前端唯一定义处）。
 * 后端对应：backend/src/constants/{roles,enums}.py；README 列出全部出现位置。
 */
export const BRAND = {
  short: 'metricreg',
  title: '指标口径注册与依赖环检测',
  org: '星野零售 · 指标体系组',
  edition: 'CATALOG · 2026',
  subtitle: '把「口径登记 → DSL 解析 → 依赖图 → 冲突与影响面 → 变更单」做成可回查的卡片目录',
  loginLead: '180 个指标散在 6 份 BI 报表里，月会为「GMV 到底含不含退款」吵了三次。这张卡片柜登记每一份口径的出处。',
  loginTabs: [
    ['01', 'A–G', '同名不同口径的指标并排抽出来对照，差异字段与过滤条件逐条列出。'],
    ['02', 'H–R', '依赖环用 Tarjan 求强连通分量，输出真实环路径而不是一句「存在循环」。'],
    ['03', 'S–Z', '改一个字段类型，先看到 3 个指标 / 5 张报表的影响面，再走变更单。'],
  ],
};

export const NAV = [
  { to: '#/overview', no: '01', label: '总览', permission: 'overview:read' },
  { to: '#/metrics', no: '02', label: '指标注册', permission: 'metric:read' },
  { to: '#/graph', no: '03', label: '依赖图', permission: 'dependency:read' },
  { to: '#/conflicts', no: '04', label: '冲突与影响面', permission: 'conflict:read' },
  { to: '#/changes', no: '05', label: '变更单与导出', permission: 'change:read' },
];

export const ROLE_LABELS = {
  admin: '指标管理员',
  analyst: '指标专员',
  viewer: '报表只读',
};

export const PERMISSIONS = {
  admin: [
    'overview:read', 'metric:read', 'metric:write', 'formula:write',
    'dependency:read', 'report:read', 'conflict:read',
    'run:read', 'run:create', 'change:read', 'change:write', 'change:approve',
    'export:read', 'audit:read',
  ],
  analyst: [
    'overview:read', 'metric:read', 'formula:write',
    'dependency:read', 'report:read', 'conflict:read',
    'run:read', 'run:create', 'change:read', 'change:write', 'export:read',
  ],
  viewer: [
    'overview:read', 'metric:read', 'dependency:read', 'report:read', 'conflict:read',
    'run:read', 'change:read',
  ],
};

export const ENUMS = {
  severity: { high: '高', medium: '中', low: '低' },
  conflictKind: {
    filter_diff: '过滤条件不同',
    field_diff: '字段集不同',
    agg_diff: '聚合方式不同',
    dep_diff: '引用指标不同',
  },
  changeKind: {
    field_type: '字段类型变更',
    caliber: '口径调整',
    formula: '公式改写',
  },
  changeStatus: { pending: '待审批', approved: '已批准', rejected: '已驳回' },
  metricDomain: { trade: '交易', traffic: '流量', member: '会员', goods: '商品', finance: '财务' },
  metricTier: { core: '核心', normal: '普通' },
  metricStatus: { draft: '草稿', active: '生效中', deprecated: '已下线' },
  parseStatus: { ok: '解析通过', error: '解析失败' },
  dependencyKind: { metric: '指标引用', field: '字段依赖', report: '报表引用' },
  trigger: { manual: '手动', schedule: '定时', seed: '初始化' },
  runStatus: { queued: '排队中', running: '执行中', success: '成功', partial: '部分成功', failed: '失败' },
};

export function can(role, permission) {
  return (PERMISSIONS[role] || []).includes(permission);
}

export function badgeTone(severity) {
  return { high: 'high', medium: 'medium', low: 'low' }[severity] || 'info';
}

export function changeTone(status) {
  return { pending: 'pending', approved: 'ok', rejected: 'danger' }[status] || 'info';
}

export function parseTone(status) {
  return status === 'ok' ? 'ok' : 'danger';
}
