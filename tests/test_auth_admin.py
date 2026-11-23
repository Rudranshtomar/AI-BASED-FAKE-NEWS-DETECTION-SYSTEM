"""Unit and integration tests for authentication, authorization, admin controls, and user isolation."""

from datetime import datetime, timezone
import pytest
from bson import ObjectId
from werkzeug.security import generate_password_hash
import app as news_app


@pytest.fixture
def test_client():
    news_app.app.config["TESTING"] = True
    news_app.app.config["WTF_CSRF_ENABLED"] = False
    with news_app.app.test_client() as client:
        yield client


class MockCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        new_doc = dict(doc)
        if "_id" not in new_doc:
            new_doc["_id"] = ObjectId()
        self.docs.append(new_doc)
        class InsertResult:
            def __init__(self, inserted_id):
                self.inserted_id = inserted_id
        return InsertResult(new_doc["_id"])

    def find_one(self, filter_dict):
        for doc in self.docs:
            match = True
            for k, v in filter_dict.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return doc
        return None

    def find(self, filter_dict=None, projection=None):
        docs = self.docs
        if filter_dict:
            filtered = []
            for doc in docs:
                match = True
                for k, v in filter_dict.items():
                    if k.startswith("$"):
                        continue
                    if doc.get(k) != v:
                        match = False
                        break
                if match:
                    filtered.append(doc)
            docs = filtered

        class MockCursor(list):
            def sort(self, *args, **kwargs):
                return self
            def skip(self, n):
                return MockCursor(self[n:])
            def limit(self, n):
                return MockCursor(self[:n])
        return MockCursor(docs)

    def count_documents(self, filter_dict=None):
        if not filter_dict:
            return len(self.docs)
        count = 0
        for doc in self.docs:
            match = True
            for k, v in filter_dict.items():
                if k.startswith("$"):
                    continue
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                count += 1
        return count

    def update_one(self, filter_dict, update_dict):
        doc = self.find_one(filter_dict)
        if doc and "$set" in update_dict:
            doc.update(update_dict["$set"])

    def delete_one(self, filter_dict):
        doc = self.find_one(filter_dict)
        if doc:
            self.docs.remove(doc)
            class DelResult:
                deleted_count = 1
            return DelResult()
        class DelResult:
            deleted_count = 0
        return DelResult()

    def delete_many(self, filter_dict=None):
        if not filter_dict:
            self.docs.clear()
            return
        self.docs = [d for d in self.docs if any(d.get(k) != v for k, v in filter_dict.items())]

    def aggregate(self, pipeline):
        return []

    def create_index(self, *args, **kwargs):
        pass


def test_registration_success(test_client, monkeypatch):
    mock_users = MockCollection()
    monkeypatch.setattr(news_app, "users_collection", mock_users)

    response = test_client.post(
        "/register",
        data={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert mock_users.count_documents({"email": "jane@example.com"}) == 1
    user = mock_users.find_one({"email": "jane@example.com"})
    assert user["name"] == "Jane Doe"
    assert user["role"] == "user"
    assert user["password_hash"] != "Password123!"  # Must be hashed


def test_registration_rejects_weak_password(test_client, monkeypatch):
    mock_users = MockCollection()
    monkeypatch.setattr(news_app, "users_collection", mock_users)

    response = test_client.post(
        "/register",
        data={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "weak",
            "confirm_password": "weak",
        },
    )

    assert response.status_code == 200
    assert b"Password must be at least 8 characters long" in response.data
    assert mock_users.count_documents({}) == 0


def test_registration_prevents_duplicate_email(test_client, monkeypatch):
    mock_users = MockCollection()
    mock_users.insert_one({
        "name": "Existing",
        "email": "taken@example.com",
        "password_hash": generate_password_hash("Secret123!"),
        "role": "user",
        "is_active": True,
    })
    monkeypatch.setattr(news_app, "users_collection", mock_users)

    response = test_client.post(
        "/register",
        data={
            "name": "Duplicate User",
            "email": "taken@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )

    assert response.status_code == 200
    assert b"already exists" in response.data


def test_login_success_and_logout(test_client, monkeypatch):
    mock_users = MockCollection()
    hashed = generate_password_hash("MySecret123!")
    user_id = mock_users.insert_one({
        "name": "John Doe",
        "email": "john@example.com",
        "password_hash": hashed,
        "role": "user",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }).inserted_id
    monkeypatch.setattr(news_app, "users_collection", mock_users)

    # Attempt valid login
    response = test_client.post(
        "/login",
        data={"email": "john@example.com", "password": "MySecret123!"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Welcome back, John Doe" in response.data

    # Test logout
    logout_res = test_client.get("/logout", follow_redirects=True)
    assert logout_res.status_code == 200
    assert b"successfully signed out" in logout_res.data


def test_login_rejects_invalid_password(test_client, monkeypatch):
    mock_users = MockCollection()
    hashed = generate_password_hash("CorrectPass123!")
    mock_users.insert_one({
        "name": "John Doe",
        "email": "john@example.com",
        "password_hash": hashed,
        "role": "user",
        "is_active": True,
    })
    monkeypatch.setattr(news_app, "users_collection", mock_users)

    response = test_client.post(
        "/login",
        data={"email": "john@example.com", "password": "WrongPassword999!"},
    )

    assert response.status_code == 200
    assert b"Invalid email address or password" in response.data


def test_dashboard_requires_login(test_client):
    response = test_client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_admin_dashboard_rejects_non_admin(test_client):
    with test_client.session_transaction() as sess:
        sess["user_id"] = "mock_user_123"
        sess["user_name"] = "Regular User"
        sess["user_email"] = "user@example.com"
        sess["user_role"] = "user"

    response = test_client.get("/admin")
    assert response.status_code == 403


def test_admin_dashboard_allows_admin(test_client, monkeypatch):
    mock_users = MockCollection()
    mock_preds = MockCollection()
    monkeypatch.setattr(news_app, "users_collection", mock_users)
    monkeypatch.setattr(news_app, "collection", mock_preds)

    with test_client.session_transaction() as sess:
        sess["user_id"] = "admin_user_123"
        sess["user_name"] = "Root Admin"
        sess["user_email"] = "admin@truthlens.ai"
        sess["user_role"] = "admin"

    response = test_client.get("/admin")
    assert response.status_code == 200
    assert b"Enterprise Administration" in response.data
    assert b"ADMIN CONSOLE" in response.data


def test_user_history_isolation(test_client, monkeypatch):
    mock_preds = MockCollection()
    # Record for Alice
    mock_preds.insert_one({
        "news": "Alice confidential article text",
        "prediction": "REAL",
        "confidence": 88.0,
        "user_email": "alice@example.com",
        "created_at": datetime.now(timezone.utc),
    })
    # Record for Bob
    mock_preds.insert_one({
        "news": "Bob private article text",
        "prediction": "FAKE",
        "confidence": 92.0,
        "user_email": "bob@example.com",
        "created_at": datetime.now(timezone.utc),
    })
    monkeypatch.setattr(news_app, "collection", mock_preds)

    # Sign in as Alice
    with test_client.session_transaction() as sess:
        sess["user_id"] = "alice_id"
        sess["user_name"] = "Alice"
        sess["user_email"] = "alice@example.com"
        sess["user_role"] = "user"

    response = test_client.get("/dashboard")
    assert response.status_code == 200
    assert b"Alice confidential article text" in response.data
    # Alice must NOT see Bob's records
    assert b"Bob private article text" not in response.data


def test_csrf_rejection_when_active(monkeypatch):
    monkeypatch.setattr(news_app, "collection", None)
    # Simulate a client where TESTING is false and PYTEST_CURRENT_TEST is unset for CSRF check
    news_app.app.config["TESTING"] = False
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    client = news_app.app.test_client()

    response = client.post("/predict", data={"news": "Sample content without CSRF token"})
    assert response.status_code == 400
    assert b"CSRF validation failed" in response.data

