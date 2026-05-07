import json

from openai import OpenAI

client = OpenAI()


def validate_and_transform_statement(
    category: str,
    statement: str,
    api_key: str,
):
    client.api_key = api_key

    prompt = f"""
You are an AI that validates and transforms prediction challenge titles.

Your tasks:

1. Check whether the statement matches the category.
2. Check whether the statement is already a proper prediction statement.
3. If already valid → return it unchanged.
4. If unclear/question-like → generate corrected prediction statements.
5. Support messy human language.

Rules:
- Return ONLY valid JSON.
- No markdown.
- No explanations.
- Statements must sound like challenge predictions.

Response JSON format:

{{
  "status": "ok" | "suggestions" | "invalid_category",
  "valid": true | false,
  "statements": ["..."]
}}

Examples:

Category: IPL
Input: "Who will win Mumbai or Rajasthan?"
Output:
{{
  "status": "suggestions",
  "valid": false,
  "statements": [
    "Mumbai Indians will win this IPL match",
    "Rajasthan Royals will win this IPL match"
  ]
}}

Category: cricket
Input: "Mumbai Indians will win"
Output:
{{
  "status": "ok",
  "valid": true,
  "statements": [
    "Mumbai Indians will win"
  ]
}}

Category: IPL
Input: "Barcelona will win FIFA World Cup"
Output:
{{
  "status": "invalid_category",
  "valid": false,
  "statements": []
}}

Now process:

Category: {category}
Input: {statement}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    content = response.choices[0].message.content

    return json.loads(content)