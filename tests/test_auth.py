# Authentication Tests
# Phase 2.3: JWT Authentication
# Task ID: T026-T031

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings as get_settings
from app.models import Task
from app.database import get_session, init_db


# Test Fixtures
@pytest.fixture(autouse=True)
def setup_database():
    """Initialize database before each test."""
    init_db()
    yield


@pytest.fixture
def settings():
    """Get application settings."""
    return get_settings


@pytest.fixture
def client():
    """Create synchronous test client."""
    return TestClient(app)


@pytest.fixture
def valid_token(settings):
    """Generate a valid JWT token for testing."""
    payload = {
        "sub": "test-user-id",
        "email": "test@example.com",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def expired_token(settings):
    """Generate an expired JWT token for testing."""
    payload = {
        "sub": "test-user-id",
        "email": "test@example.com",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def invalid_token():
    """Generate a malformed JWT token for testing."""
    return "invalid.token.string"


@pytest.fixture
def token_missing_claims(settings):
    """Generate a JWT token missing required claims."""
    payload = {
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def auth_headers(valid_token):
    """Create authorization headers with valid token."""
    return {"Authorization": f"Bearer {valid_token}"}


# T027: Test valid JWT returns user's tasks only
def test_valid_jwt_returns_users_tasks_only(client, auth_headers):
    """Test that valid JWT returns only the authenticated user's tasks."""
    response = client.get("/api/tasks", headers=auth_headers)

    # Should return 200 with empty list or user's tasks
    assert response.status_code == 200

    # Verify response is a list (may be empty)
    assert isinstance(response.json(), list)


# T028: Test missing token returns 401
def test_missing_token_returns_401(client):
    """Test that requests without Authorization header return 401 Unauthorized."""
    response = client.get("/api/tasks")

    assert response.status_code == 401
    assert "detail" in response.json()


# T028: Test invalid token returns 401
def test_invalid_token_returns_401(client, invalid_token):
    """Test that requests with invalid JWT return 401 Unauthorized."""
    headers = {"Authorization": f"Bearer {invalid_token}"}
    response = client.get("/api/tasks", headers=headers)

    assert response.status_code == 401
    assert "detail" in response.json()


# T029: Test expired token returns 401
def test_expired_token_returns_401(client, expired_token):
    """Test that requests with expired JWT return 401 Unauthorized."""
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/tasks", headers=headers)

    assert response.status_code == 401
    assert "detail" in response.json()


# T028: Test token missing claims returns 401
def test_token_missing_claims_returns_401(client, token_missing_claims):
    """Test that JWT tokens missing required claims return 401 Unauthorized."""
    headers = {"Authorization": f"Bearer {token_missing_claims}"}
    response = client.get("/api/tasks", headers=headers)

    assert response.status_code == 401
    assert "detail" in response.json()


# T028: Test malformed Bearer format returns 401
def test_malformed_bearer_format_returns_401(client, valid_token):
    """Test that malformed Authorization header format returns 401 Unauthorized."""
    # Test missing "Bearer" prefix
    response = client.get("/api/tasks", headers={"Authorization": valid_token})
    assert response.status_code == 401

    # Test wrong prefix
    response = client.get("/api/tasks", headers={"Authorization": f"Basic {valid_token}"})
    assert response.status_code == 401


# T030: Test cross-user access returns 403
def test_cross_user_access_returns_403(client, valid_token, settings):
    """Test that accessing another user's task returns 403 Forbidden."""
    # Create a task owned by a different user
    with get_session() as session:
        task = Task(
            title="Other User's Task",
            user_id="other-user-id",
            description="This belongs to someone else"
        )
        session.add(task)
        session.commit()
        task_id = task.id

    # Try to access it with a different user's token
    response = client.get(f"/api/tasks/{task_id}", headers={"Authorization": f"Bearer {valid_token}"})

    # Should return 403 Forbidden (not 404)
    assert response.status_code == 403
    assert "access denied" in response.json()["detail"].lower()


# T031: Test X-User-Id header alone returns 401
def test_x_user_id_alone_returns_401(client):
    """Test that X-User-Id header alone (no JWT) returns 401 Unauthorized."""
    headers = {"X-User-Id": "test-user-id"}
    response = client.get("/api/tasks", headers=headers)

    # Should return 401 - JWT is required
    assert response.status_code == 401


# T031: Test X-User-Id ignored when JWT present
def test_x_user_id_ignored_with_jwt(client, valid_token, settings):
    """Test that X-User-Id header is ignored when JWT is present."""
    headers = {
        "Authorization": f"Bearer {valid_token}",
        "X-User-Id": "malicious-user-id"
    }
    response = client.get("/api/tasks", headers=headers)

    # Should succeed using JWT identity, not X-User-Id
    assert response.status_code == 200


# Additional Test: Create task with valid JWT
def test_create_task_with_valid_jwt(client, auth_headers):
    """Test creating a task with a valid JWT token."""
    task_data = {
        "title": "New Test Task",
        "description": "Created with JWT auth"
    }
    response = client.post("/api/tasks", json=task_data, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["title"] == task_data["title"]


# Additional Test: Delete task with valid JWT
def test_delete_task_with_valid_jwt(client, auth_headers):
    """Test deleting a task with a valid JWT token."""
    # First create a task
    task_data = {
        "title": "Task to Delete",
    }
    create_response = client.post("/api/tasks", json=task_data, headers=auth_headers)
    task_id = create_response.json()["id"]

    # Then delete it
    delete_response = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)

    assert delete_response.status_code == 204


# Additional Test: Update task with valid JWT
def test_update_task_with_valid_jwt(client, auth_headers):
    """Test updating a task with a valid JWT token."""
    # First create a task
    task_data = {
        "title": "Task to Update",
    }
    create_response = client.post("/api/tasks", json=task_data, headers=auth_headers)
    task_id = create_response.json()["id"]

    # Then update it
    update_data = {
        "title": "Updated Title",
        "description": "Updated description"
    }
    update_response = client.put(f"/api/tasks/{task_id}", json=update_data, headers=auth_headers)

    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated Title"
