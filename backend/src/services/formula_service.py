"""口径公式服务：版本读取、算法 A 预解析、保存新版本。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import ParseStatus
from src.models.formula import Formula
from src.models.metric import Metric
from src.services import dsl_parser
from src.utils.errors import AppError
from src.utils.timeutil import iso_utc


def serialize(formula: Formula) -> dict:
    return {
        "id": formula.id,
        "metric_id": formula.metric_id,
        "version": formula.version,
        "dsl_text": formula.dsl_text,
        "parse_status": formula.parse_status,
        "parse_error": formula.parse_error,
        "parsed": formula.parsed or {},
        "signature": formula.signature,
        "author_email": formula.author_email,
        "note": formula.note,
        "created_at": iso_utc(formula.created_at),
    }


def latest_map(db: Session) -> dict[int, Formula]:
    """每个指标取版本号最大的一条公式。"""
    rows = db.scalars(select(Formula).order_by(Formula.metric_id, Formula.version.desc())).all()
    latest: dict[int, Formula] = {}
    for row in rows:
        latest.setdefault(row.metric_id, row)
    return latest


def latest_for(db: Session, metric: Metric) -> Formula | None:
    return db.scalar(
        select(Formula)
        .where(Formula.metric_id == metric.id)
        .order_by(Formula.version.desc())
        .limit(1)
    )


def parse_preview(dsl_text: str, metric_code: str | None = None) -> dict:
    return dsl_parser.parse_dsl(dsl_text, metric_code)


def apply_parse(formula: Formula, parsed: dict) -> Formula:
    formula.parsed = {
        key: parsed.get(key)
        for key in ("name", "aggs", "fields", "filters", "dims", "deps", "expression", "where_text", "error")
    }
    if parsed["status"] == "ok":
        formula.parse_status = ParseStatus.OK.value
        formula.parse_error = None
        formula.signature = parsed["signature"]
    else:
        formula.parse_status = ParseStatus.ERROR.value
        error = parsed.get("error") or {}
        formula.parse_error = f"{error.get('code')} @{error.get('column')}: {error.get('message')}"
        formula.signature = ""
    return formula


def save_version(
    db: Session,
    metric: Metric,
    *,
    dsl_text: str,
    author_email: str,
    note: str | None = None,
    seed_key: str | None = None,
) -> Formula:
    parsed = parse_preview(dsl_text, metric.code)
    if parsed["status"] != "ok":
        error = parsed["error"]
        raise AppError(
            "VALIDATION",
            422,
            {
                "code": error["code"],
                "message": error["message"],
                "position": error["position"],
                "column": error["column"],
                "snippet": error["snippet"],
            },
            message=f"DSL 解析失败：{error['message']}",
        )
    next_version = (
        db.scalar(select(func.max(Formula.version)).where(Formula.metric_id == metric.id)) or 0
    ) + 1
    formula = Formula(
        metric_id=metric.id,
        version=next_version,
        dsl_text=dsl_text.strip(),
        author_email=author_email,
        note=note,
        seed_key=seed_key,
    )
    apply_parse(formula, parsed)
    db.add(formula)
    metric.current_version = next_version
    db.flush()
    return formula


def version_count(db: Session, metric_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Formula).where(Formula.metric_id == metric_id)) or 0
