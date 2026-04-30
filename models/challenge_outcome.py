"""Models for challenge outcomes."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChallengeOutcomeCreate(BaseModel):
    challenge_id: str = Field(min_length=1)
    outcome_key: str = Field(min_length=1)
    title: str = Field(min_length=1)
    metadata: dict | None = None


class ChallengeOutcomeResponse(BaseModel):
    id: str
    challenge_id: str
    outcome_key: str
    title: str
    metadata: dict | None
    created_at: datetime | None


class ChallengeOutcomeListResponse(BaseModel):
    outcomes: list[ChallengeOutcomeResponse]
    count: int