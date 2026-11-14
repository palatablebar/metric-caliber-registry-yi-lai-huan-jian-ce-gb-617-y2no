"""报表控制器（只读，报表由 seed 登记）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import report_service


def list_reports(db: Session, **filters) -> dict:
    return report_service.list_reports(db, **filters)
