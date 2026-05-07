from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import Settings, get_settings
from services.challenge_ai import validate_and_transform_statement

router = APIRouter(prefix="/transform", tags=["transform"])


class TransformRequest(BaseModel):
    category: str
    statement: str


class TransformResponse(BaseModel):
    status: str
    valid: bool
    statements: list[str]


@router.post("", response_model=TransformResponse)
def transform(
    payload: TransformRequest,
    settings: Settings = Depends(get_settings),
):
    try:
        result = validate_and_transform_statement(
            category=payload.category,
            statement=payload.statement,
            api_key=settings.openai_api_key,
        )

        return TransformResponse(**result)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Transformation failed: {str(exc)}",
        )