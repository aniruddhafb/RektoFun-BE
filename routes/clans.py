"""Clan chat API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from config import get_supabase
from models.clan import (
    ClanMessageCreate,
    ClanMessageListResponse,
    ClanMessageResponse,
    coerce_clan_message,
)

router = APIRouter(prefix="/clans", tags=["clans"])


@router.get("/{clan_slug}/messages", response_model=ClanMessageListResponse)
def get_clan_messages(
    clan_slug: str,
    supabase: Annotated[Client, Depends(get_supabase)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ClanMessageListResponse:
    """
    Get messages for a clan. Only accessible by clan members.

    Example:
        curl "http://localhost:8000/clans/alpha-syndicate/messages?limit=20"
    """
    # First get the clan by slug
    try:
        clan_result = (
            supabase.table("clans")
            .select("id")
            .eq("slug", clan_slug)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch clan: {exc}",
        ) from exc

    clan_rows = clan_result.data or []
    if not clan_rows:
        raise HTTPException(status_code=404, detail="Clan not found")

    clan_id = clan_rows[0]["id"]

    # Get messages with sender info (username and profile_image)
    try:
        result = (
            supabase.table("clan_messages")
            .select("""
                id,
                clan_id,
                sender_id,
                message,
                created_at,
                sender:users!sender_id (
                    username,
                    profile_image
                )
            """)
            .eq("clan_id", clan_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch messages: {exc}",
        ) from exc

    rows = result.data or []
    messages = []
    for row in rows:
        sender_data = row.pop("sender", None)
        sender_username = sender_data.get("username") if sender_data else None
        sender_avatar = sender_data.get("profile_image") if sender_data else None
        messages.append(ClanMessageResponse(
            id=row["id"],
            clan_id=row["clan_id"],
            sender_id=row["sender_id"],
            message=row["message"],
            created_at=row["created_at"],
            sender_username=sender_username,
            sender_avatar=sender_avatar,
        ))

    return ClanMessageListResponse(messages=messages, count=len(messages))


@router.post("/{clan_slug}/messages", response_model=ClanMessageResponse, status_code=201)
def create_clan_message(
    clan_slug: str,
    message_data: ClanMessageCreate,
    supabase: Annotated[Client, Depends(get_supabase)],
) -> ClanMessageResponse:
    """
    Send a message to a clan chat. User must be a clan member.

    Example:
        curl -X POST http://localhost:8000/clans/alpha-syndicate/messages \
          -H "Content-Type: application/json" \
          -d '{
            "clan_id": "uuid-here",
            "sender_id": "user-uuid-here",
            "message": "Hello clan!"
          }'
    """
    # First get the clan by slug
    try:
        clan_result = (
            supabase.table("clans")
            .select("id")
            .eq("slug", clan_slug)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch clan: {exc}",
        ) from exc

    clan_rows = clan_result.data or []
    if not clan_rows:
        raise HTTPException(status_code=404, detail="Clan not found")

    clan_id = clan_rows[0]["id"]

    # Verify the clan_id in body matches the slug
    if message_data.clan_id != clan_id:
        raise HTTPException(
            status_code=400,
            detail="Clan ID does not match the slug",
        )

    # Insert the message
    try:
        result = (
            supabase.table("clan_messages")
            .insert({
                "clan_id": message_data.clan_id,
                "sender_id": message_data.sender_id,
                "message": message_data.message,
            })
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create message: {exc}",
        ) from exc

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create message")

    # Get sender info
    row = result.data[0]
    sender_result = (
        supabase.table("users")
        .select("username, profile_image")
        .eq("id", message_data.sender_id)
        .limit(1)
        .execute()
    )
    sender_data = sender_result.data[0] if sender_result.data else {}

    return ClanMessageResponse(
        id=row["id"],
        clan_id=row["clan_id"],
        sender_id=row["sender_id"],
        message=row["message"],
        created_at=row["created_at"],
        sender_username=sender_data.get("username"),
        sender_avatar=sender_data.get("profile_image"),
    )


@router.delete("/{clan_slug}/messages/{message_id}", status_code=204)
def delete_clan_message(
    clan_slug: str,
    message_id: str,
    supabase: Annotated[Client, Depends(get_supabase)],
) -> None:
    """
    Delete a message. User must be the sender.

    Example:
        curl -X DELETE http://localhost:8000/clans/alpha-syndicate/messages/message-uuid-here
    """
    try:
        supabase.table("clan_messages").delete().eq("id", message_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete message: {exc}",
        ) from exc