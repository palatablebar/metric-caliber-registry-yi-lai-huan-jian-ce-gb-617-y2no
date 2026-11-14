from __future__ import annotations

from pydantic import BaseModel, Field

CODE_PATTERN = r"^[a-z][a-z0-9_]{1,47}$"


class MetricIn(BaseModel):
    code: str = Field(min_length=2, max_length=48, pattern=CODE_PATTERN)
    name: str = Field(min_length=1, max_length=80)
    domain: str = Field(default="trade", max_length=20)
    tier: str = Field(default="normal", max_length=12)
    unit: str = Field(default="元", max_length=20)
    owner: str | None = Field(default=None, max_length=80)
    description: str = Field(default="", max_length=2000)
    status: str = Field(default="active", max_length=16)
    dsl_text: str | None = Field(default=None, max_length=1200)


class MetricPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    domain: str | None = Field(default=None, max_length=20)
    tier: str | None = Field(default=None, max_length=12)
    unit: str | None = Field(default=None, max_length=20)
    owner: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, max_length=16)
    enabled: bool | None = None


class ParseIn(BaseModel):
    dsl_text: str = Field(min_length=1, max_length=1200)


class FormulaIn(BaseModel):
    dsl_text: str = Field(min_length=1, max_length=1200)
    note: str | None = Field(default=None, max_length=500)
