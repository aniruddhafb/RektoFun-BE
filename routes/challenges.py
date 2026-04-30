"""Challenge API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from config import get_supabase
from models.challenge import (
    ChallengeCreate,
    ChallengeListResponse,
    ChallengeResponse,
    ChallengeStatus,
    ChallengeUpdate,
)
from utils import serialize_payload

router = APIRouter(prefix="/challenges", tags=["challenges"])


def coerce_challenge(row: dict) -> ChallengeResponse:
    return ChallengeResponse.model_validate(row)


@router.post("", response_model=ChallengeResponse, status_code=201)
def create_challenge(
    challenge: ChallengeCreate,
    supabase: Annotated[Client, Depends(get_supabase)],
) -> ChallengeResponse:
    """
    Create a new challenge.

    Example:
        curl -X POST http://localhost:8000/challenges \\
          -H "Content-Type: application/json" \\
          -d '{
            "title": "Will BTC reach $100k by end of 2025?",
            "description": "Binary prediction market for Bitcoin price",
            "category": "crypto",
            "subcategory": "btc",
            "event_type": "binary",
            "ticker": "BTC",
            "created_by": "user-uuid-here",
            "expire_time": "2025-12-31T23:59:59Z",
            "resolve_time": "2026-01-01T12:00:00Z"
          }'
    """
    payload = serialize_payload({
        **challenge.model_dump(),
        "status": ChallengeStatus.open.value,
    })

    try:
        result = (
            supabase.table("challenges")
            .insert(payload)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to insert challenge: {exc}",
        ) from exc

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to insert challenge")

    return coerce_challenge(result.data[0])


@router.get("", response_model=ChallengeListResponse)
def get_challenges(
    supabase: Annotated[Client, Depends(get_supabase)],
    status: ChallengeStatus | None = None,
    category: str | None = None,
    ticker: str | None = None,
    created_by: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChallengeListResponse:
    """
    Get a list of challenges with optional filters.

    Example:
        curl "http://localhost:8000/challenges?status=open&category=crypto&ticker=BTC&limit=10&offset=0"
    """
    query = supabase.table("challenges").select("*")

    if status is not None:
        query = query.eq("status", status.value)
    if category:
        query = query.eq("category", category)
    if ticker:
        query = query.eq("ticker", ticker)
    if created_by:
        query = query.eq("created_by", created_by)

    try:
        result = (
            query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch challenges: {exc}",
        ) from exc

    rows = result.data or []
    return ChallengeListResponse(
        challenges=[coerce_challenge(row) for row in rows],
        count=len(rows),
    )


@router.get("/{challenge_id}", response_model=ChallengeResponse)
def get_challenge_by_id(
    challenge_id: str,
    supabase: Annotated[Client, Depends(get_supabase)],
) -> ChallengeResponse:
    """
    Get a challenge by its ID.

    Example:
        curl http://localhost:8000/challenges/123e4567-e89b-12d3-a456-426614174000
    """
    try:
        result = (
            supabase.table("challenges")
            .select("*")
            .eq("id", challenge_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch challenge: {exc}",
        ) from exc

    rows = result.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Challenge not found")

    return coerce_challenge(rows[0])


@router.patch("/{challenge_id}", response_model=ChallengeResponse)
def update_challenge(
    challenge_id: str,
    challenge_update: ChallengeUpdate,
    supabase: Annotated[Client, Depends(get_supabase)],
) -> ChallengeResponse:
    """
    Update a challenge.

    Example:
        curl -X PATCH http://localhost:8000/challenges/123e4567-e89b-12d3-a456-426614174000 \\
          -H "Content-Type: application/json" \\
          -d '{"status": "resolved", "result": {"outcome": "YES"}}'
    """
    # First check if challenge exists
    try:
        existing = (
            supabase.table("challenges")
            .select("*")
            .eq("id", challenge_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch challenge: {exc}",
        ) from exc

    if not existing.data:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Build update payload (only non-None fields)
    update_payload = {k: v for k, v in challenge_update.model_dump().items() if v is not None}
    update_payload = serialize_payload(update_payload)

    if not update_payload:
        raise HTTPException(
            status_code=422,
            detail="No fields to update",
        )

    try:
        result = (
            supabase.table("challenges")
            .update(update_payload)
            .eq("id", challenge_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update challenge: {exc}",
        ) from exc

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update challenge")

    return coerce_challenge(result.data[0])


@router.delete("/{challenge_id}", status_code=204, response_model=None)
def delete_challenge(
    challenge_id: str,
    supabase: Annotated[Client, Depends(get_supabase)],
) -> None:
    """
    Delete a challenge by its ID.

    Example:
        curl -X DELETE http://localhost:8000/challenges/123e4567-e89b-12d3-a456-426614174000
    """
    # First check if challenge exists
    try:
        existing = (
            supabase.table("challenges")
            .select("id")
            .eq("id", challenge_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch challenge: {exc}",
        ) from exc

    if not existing.data:
        raise HTTPException(status_code=404, detail="Challenge not found")

    try:
        supabase.table("challenges").delete().eq("id", challenge_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete challenge: {exc}",
        ) from exc