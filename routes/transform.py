"""
Transform endpoint for converting question‑style statements into declarative challenge
titles using the OpenAI SDK.
"""

from typing import List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from openai import OpenAI
client = OpenAI()

from config import get_settings, Settings

router = APIRouter(prefix="/transform", tags=["transform"])


class TransformRequest(BaseModel):
    category: str = Field(..., description="Category or market name, e.g., 'IPL', 'FIFA'")
    statement: str = Field(..., description="User‑provided question‑style statement")


class TransformResponse(BaseModel):
    statements: List[str] = Field(
        ...,
        description="All possible declarative statements derived from the input question",
    )


def _validate_category_match(category: str, statement: str) -> bool:
    """
    Dynamically determine whether the statement relates to the given category
    using the OpenAI SDK. The model is prompted to answer with a simple "yes"
    or "no". If the OpenAI request fails, a simple fallback heuristic is used.
    """
    # Ensure OpenAI API key is available
    client.api_key = get_settings().openai_api_key

    prompt = f"""You are given a category and a user statement.
Category: {category}
Statement: {statement}

Determine whether the statement is relevant to the given category.
Respond with only "yes" or "no" (lowercase)."""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        answer = response.choices[0].message.content.strip().lower()
        return answer == "yes"
    except Exception:
        # Fallback heuristic: simple substring check
        lowered = statement.lower()
        cat_lower = category.lower()
        return cat_lower in lowered


def _build_prompt(category: str, statement: str) -> str:
    return f"""
        You are an AI that converts prediction questions into clean challenge statements.

        Rules:
        - Convert questions into declarative prediction statements.
        - Generate ALL possible outcomes.
        - Statements must match the given category.
        - Keep statements short and natural.
        - Do not return questions.
        - Return ONLY a valid JSON array of strings.

        Category: {category}
        Input: {statement}

        Example:
        Input: "Who will win, Mumbai or Rajasthan?"
        Output:
        ["Mumbai will win this IPL match", "Rajasthan will win this IPL match"]
    """
    

@router.post("", response_model=TransformResponse)
def transform(
    payload: TransformRequest,
    settings: Settings = Depends(get_settings),
) -> TransformResponse:
    """
    Transform a question‑style statement into one or more declarative challenge titles.

    - Validates that the statement is relevant to the provided category.
    - Calls OpenAI's ChatCompletion API to generate the transformations.
    """
    if not _validate_category_match(payload.category, payload.statement):
        raise HTTPException(
            status_code=400,
            detail="The statement does not match the provided category.",
        )

    # Configure OpenAI client
    client.api_key = settings.openai_api_key

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": _build_prompt(payload.category, payload.statement)}],
            temperature=0.2,
        )
        # The model is instructed to output a JSON array, parse it safely
        import json

        content = response.choices[0].message.content
        statements = json.loads(content)
        if not isinstance(statements, list):
            raise ValueError
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate transformation: {exc}",
        ) from exc

    return TransformResponse(statements=statements)