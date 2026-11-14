# 指标口径注册与依赖环检测（`metricreg`）

> 数据工程 · 中型多模块项目。原生 HTML/CSS/JS 前端 + Python FastAPI 后端 + Celery worker + PostgreSQL 16 + Redis，5 个容器一键起。
> 视觉方向：**图书馆卡片目录**（墨绿书脊 + 纸黄卡片 + 索引号），登录页像拉开的卡片柜抽屉。

## 1. 场景

- **模拟客户**：星野零售 · 指标体系组（6 人），维护 180 个指标，散落在 6 份 BI 报表与数仓宽表里。
- **现有工作流**：指标定义写在 Word 和群公告里，改一次口径要人肉通知 20 张报表；月会前靠人翻两份文档对口径。
- **三个痛点**：
  1. **同名不同口径**：`gmv`（不含退款）与 `gmv_net`（含退款扣减）都叫「GMV」，月会为它吵了三次；
  2. **指标间循环依赖**没人发现：`cycle_a → cycle_b → cycle_c → cycle_a` 一直跑不出数，也没人定位到环；
  3. **改一个指标的影响面算不清**：改 `dwd.order.amount` 类型，下游到底几个指标、几张报表，全靠猜。
- **上下游**：数仓表 / BI 报表 → **本系统（口径登记 → DSL 解析 → 依赖图 → 冲突与影响面 → 变更单）** → 报表 owner 与月会。
- **一天的工作剧本**：
  1. 09:00 管理员在「指标注册」把 `gmv_net` 的 DSL 改成含退款的写法，先点「解析预览」，确认 `filters` 里出现 `refund_status = 'done'`；
  2. 09:20 数据专员点「跑一次校验」，系统解析 48 条口径、重建 120+ 条依赖边；
  3. 09:21 总览显示 5 处同名冲突、1 个 3 节点环、2 条高风险；
  4. 09:30 在「冲突与影响面」打开「GMV」，两份口径并排对照，差异字段列出来，下游 4 张报表（含 3 张核心）；
  5. 09:40 把冲突一键变成变更单，影响分 10，状态待审批；
  6. 10:00 管理员在「变更单与导出」批准，审计里留下 `change.approve`；
  7. 10:10 导出 `conflicts.csv` 带到月会。

## 2. 角色与权限

| 角色 | 账号 | 权限 | 典型动作 |
|---|---|---|---|
| 指标管理员 `admin` | `admin@metricreg.io` | 指标写 + 口径写 + 批准变更 + 导出 + 审计 | 注册指标、批准变更单、导出、看审计 |
| 指标专员 `analyst` | `analyst@metricreg.io` | 口径写 + 跑校验 + 提交变更 + 导出 | 改口径、跑校验、提变更单、看影响面 |
| 报表只读 `viewer` | `viewer@metricreg.io` | 只读 | 看指标、依赖图、冲突、变更单 |

密码统一 `Demo@2026`。低权角色调用高权接口返回**真实 403**（不是前端隐藏）：
`viewer` 写指标 403、导出 403、审计 403；`analyst` 批准变更 403、审计 403。无 token 401，非法参数 422，重复编码 409。

## 3. 业务模块（6 个）

| # | 模块 | 页面 | 后端 services + controller | 主要 API |
|---|---|---|---|---|
| ① | 指标注册与检索 | 指标注册 | `metric_service` + `metric_controller` | `GET/POST /api/metrics`、`GET/PATCH /api/metrics/{id}` |
| ② | 口径 DSL 解析（算法 A） | 指标注册（抽屉内「解析预览 / 保存新版本」） | `dsl_parser` + `formula_service` + `metric_controller` | `POST /api/metrics/{id}/parse`、`POST /api/metrics/{id}/formulas` |
| ③ | 依赖图与环检测（算法 B） | 依赖图 | `graph_analysis` + `graph_service` + `dependency_service` + `dependency_controller` | `GET /api/graph`、`GET /api/cycles`、`GET /api/dependencies` |
| ④ | 口径冲突与影响面（算法 B） | 冲突与影响面 | `graph_analysis` + `graph_service` + `conflict_controller` | `GET /api/conflicts`、`GET /api/conflicts/{id}`、`GET /api/impact` |
| ⑤ | 变更单与审批 | 变更单与导出 | `change_service` + `change_controller` | `GET/POST /api/change-requests`、`PATCH /api/change-requests/{id}` |
| ⑥ | 报表登记与导出 | 变更单与导出（导出卡片）/ 冲突页导出按钮 | `report_service` + `export_service` + `export_controller` | `GET /api/reports`、`GET /api/exports/{metrics,conflicts,change-requests,runs}.csv` |

横切能力（不计入业务模块）：登录（JWT）、审计、限流、worker 心跳、总览。

## 4. 五个领域实体

| 实体 | 表 | model | schema | service | controller / route | 前端 |
|---|---|---|---|---|---|---|
| `Metric` 指标 | `metrics` | `models/metric.py` | `schemas/metric.py` | `metric_service` | `metric_controller` / `routes/metrics.py` | `pages/metrics.js` + `api.js` |
| `Formula` 口径公式 | `formulas` | `models/formula.py` | `schemas/metric.py`（`FormulaIn`/`ParseIn`） | `formula_service` + `dsl_parser` | `metric_controller` / `routes/metrics.py` | `pages/metrics.js` 抽屉 |
| `Dependency` 依赖边 | `dependencies` | `models/dependency.py` | 只读出参（dict） | `dependency_service` | `dependency_controller` / `routes/dependencies.py` | `pages/graph.js` |
| `Report` 报表 | `reports` | `models/report.py` | 只读出参（dict） | `report_service` | `report_controller` / `routes/reports.py` | `pages/graph.js` / `pages/conflicts.js` |
| `ChangeRequest` 变更单 | `change_requests` | `models/change_request.py` | `schemas/change.py` | `change_service` | `change_controller` / `routes/change_requests.py` | `pages/changes.js` |

横切表：`users`、`audit_logs`、`runs`（校验运行）。

## 5. 两个算法（Python 真算，结果进页面与导出）

### 算法 A｜指标 DSL 解析（`backend/src/services/dsl_parser.py`）

语法：`name = agg(field) [ - agg(field) ] [where cond] [group by dim, dim]`
聚合 `sum / count / distinct_count / avg`；聚合参数可以是 `dwd.order.amount`、`*`（仅 count）或 `@gmv`（指标引用 → 依赖边）。

产出 `{aggs, fields, filters, dims, deps, expression, signature}`；不合法返回
`{code, message, position, column, snippet}`，错误码：`EMPTY_DSL / DSL_TOO_LONG / SYNTAX / UNKNOWN_AGG /
UNBALANCED_PAREN / SELF_REFERENCE / NO_FIELD`。
签名 = 归一后字段集/过滤/聚合/维度/引用的 sha256 前 16 位，供同名口径比对。

### 算法 B｜依赖环与冲突（`backend/src/services/graph_analysis.py`）

- 图 `metric -> 引用指标`，**迭代式 Tarjan** 求 SCC；SCC 长度 > 1 或自环 → 环，并用 BFS 还原**真实环路径**（等长取字典序）；
- **冲突**：同名指标（`name` 相同）但签名不同 → `filter_diff / field_diff / agg_diff / dep_diff`；
- **影响面** = 下游报表按权重求和（核心报表 ×3），`score >= 8` high、`>= 3` medium、否则 low；
- 字段影响面：`impact_of_field('dwd.order.amount')` → 3 个指标 / 5 张报表 / 11 分 / high（验收数字）。

## 6. 页面（6）

| # | 路由 | 说明 |
|---|---|---|
| 1 | `#/login` | 登录：卡片柜抽屉 + 索书单表单 |
| 2 | `#/overview` | 总览：指标 / 报表 / 同名冲突 / 依赖环 / 高风险 / 待审批，按等级与类型的条形、环路径、最近运行、7 天趋势 |
| 3 | `#/metrics` | 指标注册：筛选 + 目录列表 + 详情抽屉（DSL 编辑、算法 A 解析预览、保存新版本、注册新指标） |
| 4 | `#/graph` | 依赖图：节点/边统计、SCC 环路径卡、节点表 + 展开抽屉、依赖边清单（可按边类型筛选） |
| 5 | `#/conflicts` | 冲突与影响面：严重度/类型筛选、两份口径并排对照、差异明细、影响面、一键提交变更单 |
| 6 | `#/changes` | 变更单与导出：跑校验、变更单列表 + 审批抽屉、4 张 CSV 导出、审计尾迹（admin） |

共享组件（`site/js/ui.js`）：`table` / `drawer` / `filterBar` 同时被指标注册、依赖图、冲突、变更单四页复用。

## 7. 共享枚举出现位置

| 枚举组 | 后端 | 前端 | 使用位置 |
|---|---|---|---|
| 业务域 `trade/traffic/member/goods/finance` | `constants/enums.py::MetricDomain` | `js/config.js::ENUMS.metricDomain` | 指标注册页筛选/表单、总览域名分布、导出 |
| 分级 `core/normal` | `MetricTier` | `ENUMS.metricTier` | 指标表徽标、详情、导出 |
| 解析状态 `ok/error` | `ParseStatus` | `ENUMS.parseStatus` | 指标表/抽屉、依赖图节点、导出 |
| 依赖边类型 `metric/field/report` | `DependencyKind` | `ENUMS.dependencyKind` | 依赖边清单筛选、导出 |
| 冲突类型 `filter/field/agg/dep_diff` | `ConflictKind` | `ENUMS.conflictKind` | 冲突页筛选、总览差异类型、导出 |
| 变更类型/状态 | `ChangeKind` / `ChangeStatus` | `ENUMS.changeKind` / `ENUMS.changeStatus` | 变更单页筛选、抽屉、导出 |
| 严重度 `high/medium/low` | `Severity` | `ENUMS.severity` | 冲突/环/变更单徽标、总览 |
| 角色 `admin/analyst/viewer` | `Role` + `constants/roles.py` | `js/config.js::PERMISSIONS` | 导航、按钮、403 |

## 8. seed 口径（`SEED_SUMMARY` 字段映射）

`backend/scripts/seed_demo.py` 幂等（自然键 upsert，不覆盖审批状态），连续两次输出逐字一致：

```text
SEED_SUMMARY brand=metricreg users=3 sources=48 runs=1 findings=6 pending=6
```

| 字段 | 本项目口径 |
|---|---|
| `users` | 3 个账号 |
| `sources` | **指标登记数 48**（校验运行的输入集合是全部指标） |
| `runs` | 校验运行次数 1（`seed-run-validate-1`） |
| `findings` | 检出问题 = 5 处同名冲突 + 1 个依赖环 + 0 条解析失败 |
| `pending` | 待审批变更单 6 张 |

另有 12 张报表（4 张核心）、依赖边由校验运行按当前口径重建。

## 9. 快速启动

```bash
cp .env.example .env
docker compose up -d --build
# 等 5/5 healthy
open http://localhost:18206
```

首次启动 backend 自动建表并执行一次 seed（`SEED_DEMO=true`）。手动重跑：

```bash
docker compose exec -T backend python -m scripts.seed_demo
docker compose exec -T backend python -m pytest tests -q
```

## 10. 访问地址

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:18206 |
| 后端 API 文档 | http://localhost:19206/docs |
| 健康检查 | http://localhost:19206/api/health |
| 数据库映射 | localhost:17706 |

## 11. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | 原生 HTML5 + CSS（oklch 令牌 / 卡片目录版式）+ ES Modules；无框架、无打包器；仅 Google Fonts |
| 字体 | Fraunces（display）+ Noto Serif SC（body）+ JetBrains Mono（索引号） |
| 后端 | Python 3.11、FastAPI 0.115、SQLAlchemy 2.0、PyJWT、passlib(bcrypt) |
| 异步 | Celery 5.4 + Redis（10s 心跳、每日 07:40 自动校验） |
| 数据库 | PostgreSQL 16 |
| 部署 | Docker Compose，恰好 5 服务（frontend / backend / worker / db / redis） |

## 12. 目录

```text
backend/
  src/{config,constants,controllers,middlewares,models,routes,schemas,services,utils}
    services/dsl_parser.py        # 算法 A
    services/graph_analysis.py    # 算法 B
  scripts/{seed_demo.py,demo_config.py,worker_healthcheck.sh}
  migrations/  tests/
frontend/site/{index.html,css/{tokens,app}.css,js/{config,api,store,ui,app}.js,js/pages/*.js}
docker-compose.yml  .env  .env.example  README.md
```

测试产物在 `batch-20261114/test-artifacts/gb-617/`（`TESTING.md`、`tests/`、`screenshots/`、`logs/`），源码目录不含截图与日志。
