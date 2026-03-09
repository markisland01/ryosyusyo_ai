from datetime import datetime

from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    rule_type: str
    document_type: str | None = None
    pattern: str = Field(min_length=1, max_length=255)
    target_value: str = Field(min_length=1, max_length=64)
    priority: int = 100
    enabled: bool = True
    notes: str | None = None


class RuleUpdate(BaseModel):
    rule_type: str | None = None
    document_type: str | None = None
    pattern: str | None = Field(default=None, min_length=1, max_length=255)
    target_value: str | None = Field(default=None, min_length=1, max_length=64)
    priority: int | None = None
    enabled: bool | None = None
    notes: str | None = None


class RuleResponse(BaseModel):
    id: int
    rule_type: str
    document_type: str | None
    pattern: str
    target_value: str
    priority: int
    enabled: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RuleListResponse(BaseModel):
    rules: list[RuleResponse]
    total: int
