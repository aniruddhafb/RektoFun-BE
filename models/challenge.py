"""Models for challenges."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChallengeStatus(str, Enum):
    open = "open"
    locked = "locked"
    resolved = "resolved"
    cancelled = "cancelled"


class EventType(str, Enum):
    binary = "binary"
    multi_outcome = "multi_outcome"
    numeric_range = "numeric_range"


class ChallengeCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    category: str = Field(min_length=1)
    subcategory: str | None = None
    event_type: EventType
    ticker: str | None = None
    mode: str | None = None
    total_pool: int | None = None
    created_by: str | None = None
    resolution_source: str | None = None
    resolution_details: dict | None = None
    expire_time: datetime
    resolve_time: datetime | None = None
    result: dict | None = None
    metadata: dict | None = None


class ChallengeUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    subcategory: str | None = None
    event_type: EventType | None = None
    ticker: str | None = None
    mode: str | None = None
    total_pool: int | None = None
    status: ChallengeStatus | None = None
    resolution_source: str | None = None
    resolution_details: dict | None = None
    expire_time: datetime | None = None
    resolve_time: datetime | None = None
    result: dict | None = None
    metadata: dict | None = None


class ChallengeResponse(BaseModel):
    id: str
    title: str
    description: str | None
    category: str
    subcategory: str | None
    event_type: str
    ticker: str | None
    mode: str | None
    total_pool: int | None
    created_by: str | None
    status: str
    resolution_source: str | None
    resolution_details: dict | None
    expire_time: datetime
    resolve_time: datetime | None
    result: dict | None
    metadata: dict | None
    created_at: datetime | None
    updated_at: datetime | None


class ChallengeListResponse(BaseModel):
    challenges: list[ChallengeResponse]
    count: int