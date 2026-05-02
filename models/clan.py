"""Models for clan chat messages."""

from datetime import datetime

from pydantic import BaseModel, Field


class ClanMessageCreate(BaseModel):
    clan_id: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=2000)


class ClanMessageResponse(BaseModel):
    id: str
    clan_id: str
    sender_id: str
    message: str
    created_at: datetime
    sender_username: str | None = None
    sender_avatar: str | None = None


class ClanMessageListResponse(BaseModel):
    messages: list[ClanMessageResponse]
    count: int


def coerce_clan_message(row: dict) -> ClanMessageResponse:
    return ClanMessageResponse.model_validate(row)