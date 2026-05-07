import os
import json
from fastapi.testclient import TestClient

# Ensure the OpenAI key is set to a dummy value for testing; the endpoint will be called,
# but the OpenAI request will be mocked by the environment (or you can set OPENAI_API_KEY
# to an invalid key and expect a 500 – for this simple test we only verify request handling
# up to validation).

os.environ["OPENAI_API_KEY"] = "test-key"

from main import app

client = TestClient(app)


def test_transform_valid():
    payload = {
        "category": "IPL",
        "statement": "who will win this ipl match, mumbai or rajasthan?"
    }
    response = client.post("/transform", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "statements" in data
    assert isinstance(data["statements"], list)
    # At least one statement should be returned
    assert len(data["statements"]) >= 1


def test_transform_category_mismatch():
    payload = {
        "category": "IPL",
        "statement": "barcelona will win the fifa world cup"
    }
    response = client.post("/transform", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "The statement does not match the provided category."