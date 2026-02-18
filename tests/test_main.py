import os
import pytest
from fastapi.testclient import TestClient

# Set required environment variables before importing main
# This prevents the app from exiting due to missing keys
os.environ["GOOGLE_API_KEY"] = "dummy_key_for_testing"
os.environ["JWKS_URL"] = "http://localhost/jwks"
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/testdb"

# Import app after setting env vars
from main import app

client = TestClient(app)

def test_app_startup():
    """
    Test that the FastAPI app can start up and handle a request.
    Since we don't have a root endpoint, we expect a 404, 
    but getting a response means the app is running.
    """
    # The lifespan manager runs automatically with TestClient
    with TestClient(app) as client:
        response = client.get("/docs")
        assert response.status_code == 200
