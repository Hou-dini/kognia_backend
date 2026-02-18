import os
from unittest import mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def test_settings():
    """
    Provide dummy environment variables for testing.
    This ensures that module-level environment variable lookups
    in main.py (or its imports) don't fail or connect to real services.
    """
    mock_env = {
        "GOOGLE_API_KEY": "dummy_key_for_testing",
        "JWKS_URL": "http://localhost/jwks",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb",
        "JWT_AUDIENCE": "authenticated",
        "JWT_ISSUER": "http://localhost/auth"
    }
    # Using patch.dict ensures environment is restored after tests finish
    with mock.patch.dict(os.environ, mock_env):
        yield

@pytest.fixture
def client(test_settings):
    """
    Initialize the TestClient. 
    We import 'app' locally to ensure the environment mock is active 
    before the main module is evaluated.
    """
    from main import app
    with TestClient(app) as c:
        yield c

def test_app_startup(client):
    """
    Verify that the FastAPI app starts successfully and serves the docs.
    """
    response = client.get("/docs")
    assert response.status_code == 200
