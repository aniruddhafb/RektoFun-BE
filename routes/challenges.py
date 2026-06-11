"""
Challenge API routes for CRUD operations.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from models.challenge import (
    ChallengeCreate,
    ChallengeUpdate,
    ChallengeResponse,
    ChallengeListResponse,
    ChallengeStatus
)
from services.database import get_db_client
from services.challenge_service import get_challenge_service, ChallengeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.post(
    "",
    response_model=ChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new challenge",
    description="Create a new challenge with the provided data"
)
async def create_challenge(
    challenge_data: ChallengeCreate,
    db: Client = Depends(get_db_client)
):
    """
    Create a new challenge.
    
    - **statement**: The challenge statement/question (optional)
    - **initial_bet**: Initial bet amount (optional)
    - **pool_size**: Total pool size (optional)
    - **resolution_source**: Source for resolving the challenge (optional)
    - **metadata**: Additional metadata as JSON (optional)
    - **creator**: ID of the user who created the challenge (optional)
    - **resolution_method**: Method for resolving the challenge (optional)
    - **participants**: Number of participants (optional)
    - **status**: Challenge status (default: OPEN)
    - **mode**: Challenge mode - PVP or Team (optional)
    - **result**: Result side if resolved (optional)
    """
    service = get_challenge_service(db)
    try:
        return await service.create_challenge(challenge_data)
    except Exception as e:
        logger.error(f"Failed to create challenge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create challenge"
        )


@router.get(
    "",
    response_model=ChallengeListResponse,
    summary="List all challenges",
    description="Get a paginated list of all challenges"
)
async def list_challenges(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of challenges to return"),
    offset: int = Query(0, ge=0, description="Number of challenges to skip"),
    db: Client = Depends(get_db_client)
):
    """
    List all challenges with pagination.
    
    - **limit**: Maximum number of challenges to return (default: 100, max: 1000)
    - **offset**: Number of challenges to skip for pagination (default: 0)
    """
    service = get_challenge_service(db)
    try:
        challenges = await service.list_challenges(limit=limit, offset=offset)
        total = await service.count_challenges()
        return ChallengeListResponse(challenges=challenges, total=total)
    except Exception as e:
        logger.error(f"Failed to list challenges: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve challenges"
        )


@router.get(
    "/{challenge_id}",
    response_model=ChallengeResponse,
    summary="Get challenge by ID",
    description="Retrieve a specific challenge by its ID"
)
async def get_challenge(
    challenge_id: int,
    db: Client = Depends(get_db_client)
):
    """
    Get a challenge by its ID.
    
    - **challenge_id**: The unique ID of the challenge
    """
    service = get_challenge_service(db)
    try:
        challenge = await service.get_challenge(challenge_id)
        if not challenge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Challenge with ID {challenge_id} not found"
            )
        return challenge
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get challenge {challenge_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve challenge"
        )


@router.get(
    "/by-creator/{creator_id}",
    response_model=list[ChallengeResponse],
    summary="Get challenges by creator",
    description="Retrieve all challenges created by a specific user"
)
async def get_challenges_by_creator(
    creator_id: int,
    db: Client = Depends(get_db_client)
):
    """
    Get all challenges created by a specific user.
    
    - **creator_id**: The ID of the user who created the challenges
    """
    service = get_challenge_service(db)
    try:
        challenges = await service.get_challenges_by_creator(creator_id)
        return challenges
    except Exception as e:
        logger.error(f"Failed to get challenges by creator {creator_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve challenges"
        )


@router.get(
    "/by-status/{status}",
    response_model=list[ChallengeResponse],
    summary="Get challenges by status",
    description="Retrieve all challenges with a specific status"
)
async def get_challenges_by_status(
    status: ChallengeStatus,
    db: Client = Depends(get_db_client)
):
    """
    Get all challenges with a specific status.
    
    - **status**: The status to filter by (OPEN, EXPIRED, RESOLVED, CANCELLED)
    """
    service = get_challenge_service(db)
    try:
        challenges = await service.get_challenges_by_status(status)
        return challenges
    except Exception as e:
        logger.error(f"Failed to get challenges by status {status}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve challenges"
        )


@router.patch(
    "/{challenge_id}",
    response_model=ChallengeResponse,
    summary="Update challenge",
    description="Update an existing challenge's data"
)
async def update_challenge(
    challenge_id: int,
    challenge_data: ChallengeUpdate,
    db: Client = Depends(get_db_client)
):
    """
    Update a challenge by ID. Only provided fields will be updated.
    
    - **challenge_id**: The unique ID of the challenge to update
    - **statement**: New challenge statement (optional)
    - **initial_bet**: New initial bet amount (optional)
    - **pool_size**: New pool size (optional)
    - **resolution_source**: New resolution source (optional)
    - **metadata**: New metadata (optional)
    - **creator**: New creator ID (optional)
    - **resolution_method**: New resolution method (optional)
    - **participants**: New participant count (optional)
    - **status**: New status (optional)
    - **mode**: New mode (optional)
    - **result**: New result (optional)
    """
    service = get_challenge_service(db)
    try:
        challenge = await service.update_challenge(challenge_id, challenge_data)
        if not challenge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Challenge with ID {challenge_id} not found"
            )
        return challenge
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update challenge {challenge_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update challenge"
        )


@router.delete(
    "/{challenge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete challenge",
    description="Delete a challenge by its ID"
)
async def delete_challenge(
    challenge_id: int,
    db: Client = Depends(get_db_client)
):
    """
    Delete a challenge by its ID.
    
    - **challenge_id**: The unique ID of the challenge to delete
    """
    service = get_challenge_service(db)
    try:
        deleted = await service.delete_challenge(challenge_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Challenge with ID {challenge_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete challenge {challenge_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete challenge"
        )