"""Health check endpoints."""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    """
    Example:
        curl http://localhost:8000/
    """
    return {"message": "RektoFun API is running", "version": "1.0.0"}


@router.get("/health/supabase-env")
def health():
    return {
        "SUPABASE_URL_set": bool(os.getenv("SUPABASE_URL")),
        "SUPABASE_SERVICE_ROLE_KEY_set": bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
        "SUPABASE_ANON_KEY_set": bool(os.getenv("SUPABASE_ANON_KEY")),
    }