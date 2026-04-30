"""Challenge Outcome API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from config import get_supabase
from models.challenge_outcome import (
    ChallengeOutcomeCreate,
    ChallengeOutcomeListResponse,
    ChallengeOutcomeResponse,
)
from utils import serialize_payload

router = APIRouter(prefix="/challenge-outcomes", tags=["challenge-outcomes"])


def coerce_challenge_outcome(row: dict) -> ChallengeOutcomeResponse:
    return ChallengeOutcomeResponse.model_validate(row)


@router.post("", response_model=ChallengeOutcomeResponse, status_code=201)
def create_challenge_outcome(
    outcome: ChallengeOutcomeCreate,
    supabase: Annotated[Client, Depends(get_supabase)],
) -> ChallengeOutcomeResponse:
    """
    Create a new challenge outcome.

    Example:
        curl -X POST http://localhost:8000/challenge-outcomes \\
          -H "Content-Type: application/json" \\
          -d '{
            "challenge_id": "123e4567-e89b-12d3-a456-426614174000",
            "outcome_key": "YES",
            "title": "Yes - BTC reaches $100k"
          }'
    """
    # Check if challenge exists
    try:
        challenge = (
            supabase.table("challenges")
            .select("id")
            .eq("id", outcome.challenge_id)
            .limit(1)
            .execute()
        )
        if not challenge.data:
            raise HTTPException(status_code=404, detail="Challenge not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check challenge: {exc}",
        ) from exc

    payload = serialize_payload(outcome.model_dump())

    try:
        result = (
            supabase.table("challenge_outcomes")
            .insert(payload)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to insert challenge outcome: {exc}",
        ) from exc

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to insert challenge outcome")

    return coerce_challenge_outcome(result.data[0])


@router.get("", response_model=ChallengeOutcomeListResponse)
def get_challenge_outcomes(
    supabase: Annotated[Client, Depends(get_supabase)],
    challenge_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChallengeOutcomeListResponse:
    """
    Get a list of challenge outcomes with optional filters.

    Example:
        curl "http://localhost:8000/challenge-outcomes?challenge_id=123e4567-e89b-12d3-a456-426614174000&limit=10"
    """
    query = supabase.table("challenge_outcomes").select("*")

    if challenge_id:
        query = query.eq("challenge_id", challenge_id)

    try:
        result = (
            query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch challenge outcomes: {exc}",
        ) from exc

    rows = result.data or []
    return ChallengeOutcomeListResponse(
        outcomes=[coerce_challenge_outcome(row) for row in rows],
        count=len(rows),
    )


@router.get("/{outcome_id}", response_model=ChallengeOutcomeResponse)
def get_challenge_outcome_by_id(
    outcome_id: str,
    supabase: Annotated[Client, Depends(get_supabase)],
) -> ChallengeOutcomeResponse:
    """
    Get a challenge outcome by its ID.

    Example:
        curl http://localhost:8000/challenge-outcomes/123e4567-e89b-12d3-a456-426614174000
    """
    try:
        result = (
            supabase.table("challenge_outcomes")
            .select("*")
            .eq("id", outcome_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch challenge outcome: {exc}",
        ) from exc

    rows = result.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Challenge outcome not found")

    return coerce_challenge_outcome(rows[0])


@router.delete("/{outcome_id}", status_code=204, response_model=None)
def delete_challenge_outcome(
    outcome_id: str,
    supabase: Annotated[Client, Depends(get_supabase)],
) -> None:
    """
    Delete a challenge outcome by its ID.

    Example:
        curl -X DELETE http://localhost:8000/challenge-outcomes/123e4567-e89b-12d3-a456-426614174000
    """
    # First check if outcome exists
    try:
        existing = (
            supabase.table("challenge_outcomes")
            .select("id")
            .eq("id", outcome_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch challenge outcome: {exc}",
        ) from exc

    if not existing.data:
        raise HTTPException(status_code=404, detail="Challenge outcome not found")

    try:
        supabase.table("challenge_outcomes").delete().eq("id", outcome_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete challenge outcome: {exc}",
        ) from exc