-- 核心表结构参考（PostgreSQL 语法，运行时不执行；建表由 SQLAlchemy create_all 完成）

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(160) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(80)  NOT NULL,
    role            VARCHAR(20)  NOT NULL,
    org             VARCHAR(120),
    created_at      TIMESTAMP    NOT NULL
);

CREATE TABLE metrics (
    id                  SERIAL PRIMARY KEY,
    code                VARCHAR(48)  NOT NULL UNIQUE,   -- 自然键，如 gmv_net
    name                VARCHAR(80)  NOT NULL,          -- 同名指标由算法 B 分组检冲突
    domain              VARCHAR(20)  NOT NULL,          -- trade/traffic/member/goods/finance
    tier                VARCHAR(12)  NOT NULL,          -- core/normal
    unit                VARCHAR(20)  NOT NULL,
    owner               VARCHAR(80)  NOT NULL,
    description         TEXT,
    status              VARCHAR(16)  NOT NULL,          -- draft/active/deprecated
    current_version     INTEGER      NOT NULL DEFAULT 1,
    core_report_count   INTEGER      NOT NULL DEFAULT 0,
    enabled             BOOLEAN      NOT NULL DEFAULT TRUE,
    created_by          VARCHAR(160),
    seed_key            VARCHAR(120) UNIQUE,
    created_at          TIMESTAMP    NOT NULL,
    updated_at          TIMESTAMP    NOT NULL
);
CREATE INDEX ix_metrics_name ON metrics (name);

CREATE TABLE formulas (
    id              SERIAL PRIMARY KEY,
    metric_id       INTEGER      NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    version         INTEGER      NOT NULL,
    dsl_text        TEXT         NOT NULL,
    parse_status    VARCHAR(12)  NOT NULL,              -- ok/error（算法 A）
    parse_error     TEXT,
    parsed          JSON,                               -- {aggs,fields,filters,dims,deps,expression,error}
    signature       VARCHAR(64)  NOT NULL DEFAULT '',   -- 归一签名，用于同名口径比对
    author_email    VARCHAR(160) NOT NULL,
    note            TEXT,
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_formulas_metric_version UNIQUE (metric_id, version)
);

CREATE TABLE dependencies (
    id              SERIAL PRIMARY KEY,
    from_metric_id  INTEGER      NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    kind            VARCHAR(12)  NOT NULL,              -- metric/field/report
    to_ref          VARCHAR(120) NOT NULL,              -- 指标编码 / 数仓字段 / 报表编码
    to_metric_id    INTEGER,
    weight          INTEGER      NOT NULL DEFAULT 1,
    note            VARCHAR(200),
    created_at      TIMESTAMP    NOT NULL,
    CONSTRAINT uq_dependencies_edge UNIQUE (from_metric_id, kind, to_ref)
);

CREATE TABLE reports (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(24)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    owner           VARCHAR(80)  NOT NULL,
    channel         VARCHAR(40)  NOT NULL,
    is_core         BOOLEAN      NOT NULL DEFAULT FALSE,
    weight          INTEGER      NOT NULL DEFAULT 1,   -- 核心报表 ×3
    metric_codes    JSON,
    refresh_cron    VARCHAR(40),
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL
);

CREATE TABLE change_requests (
    id              SERIAL PRIMARY KEY,
    cr_no           VARCHAR(40)  NOT NULL UNIQUE,
    metric_id       INTEGER      REFERENCES metrics(id) ON DELETE SET NULL,
    target_ref      VARCHAR(120) NOT NULL,
    change_kind     VARCHAR(20)  NOT NULL,              -- field_type/caliber/formula
    reason          TEXT,
    proposed_dsl    TEXT,
    impact          JSON,                               -- 算法 B 影响面快照
    severity        VARCHAR(12)  NOT NULL,
    impact_score    INTEGER      NOT NULL DEFAULT 0,
    status          VARCHAR(16)  NOT NULL,              -- pending/approved/rejected
    requester_email VARCHAR(160) NOT NULL,
    approver_email  VARCHAR(160),
    decision_note   TEXT,
    decided_at      TIMESTAMP,
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL
);

CREATE TABLE runs (
    id              SERIAL PRIMARY KEY,
    run_no          VARCHAR(40)  NOT NULL UNIQUE,
    trigger         VARCHAR(20)  NOT NULL,
    status          VARCHAR(20)  NOT NULL,
    operator_email  VARCHAR(160) NOT NULL,
    input_count     INTEGER      NOT NULL DEFAULT 0,
    output_count    INTEGER      NOT NULL DEFAULT 0,
    metrics         JSON,
    log_text        TEXT,
    seed_key        VARCHAR(120) UNIQUE,
    started_at      TIMESTAMP    NOT NULL,
    finished_at     TIMESTAMP
);

CREATE TABLE audit_logs (
    id              SERIAL PRIMARY KEY,
    actor_email     VARCHAR(160) NOT NULL,
    actor_role      VARCHAR(20)  NOT NULL,
    action          VARCHAR(64)  NOT NULL,
    entity          VARCHAR(40)  NOT NULL,
    entity_id       VARCHAR(64),
    detail          JSON,
    layer           VARCHAR(16)  NOT NULL DEFAULT 'domain',
    ip              VARCHAR(64),
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL
);
