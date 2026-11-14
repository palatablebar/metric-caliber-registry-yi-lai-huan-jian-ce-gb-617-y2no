from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChangeIn(BaseModel):
    target_ref: str = Field(min_length=2, max_length=120)
    change_kind: Literal["field_type", "caliber", "formula"] = "caliber"
    metric_code: str | None = Field(default=None, max_length=48)
    reason: str = Field(default="", max_length=1000)
    proposed_dsl: str | None = Field(default=None, max_length=1200)


class DecisionIn(BaseModel):
    status: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)
