# migrations

参考建表语句。运行时由 SQLAlchemy 的 `Base.metadata.create_all` 建表（启动时执行），
本目录的 SQL 只用于评审时快速看清表结构与自然键/唯一约束，**不会被执行**。

- 5 个业务实体：`metrics` / `formulas` / `dependencies` / `reports` / `change_requests`
- 横切：`users`（三角色）、`audit_logs`（审计）、`runs`（校验运行）
- 自然键：`metrics.code`、`formulas(metric_id, version)`、`dependencies(from_metric_id, kind, to_ref)`、
  `reports.code`、`change_requests.cr_no`、`runs.run_no`
