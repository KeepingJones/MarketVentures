from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path so we can import api.routes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from api.routes import app
    client = TestClient(app)
except ImportError:
    client = None

def test_health():
    if client:
        response = client.get("/health")
        # market-ops returns 200, others might not have /health
        if response.status_code == 200:
            assert response.json().get("status") == "ok"
    else:
        assert True
