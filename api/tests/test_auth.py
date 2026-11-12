from tests.conftest import auth, make_user


def test_login_returns_token_and_user(client, alice):
    response = client.post(
        "/api/auth/login", json={"email": "alice@example.test", "password": "secret123"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": alice.id,
        "email": "alice@example.test",
        "name": "Alice",
        "role": "user",
    }
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["email"] == "alice@example.test"


def test_login_rejects_wrong_password(client, alice):
    response = client.post(
        "/api/auth/login", json={"email": "alice@example.test", "password": "nope"}
    )

    assert response.status_code == 401


def test_login_rejects_inactive_user(client, db, alice):
    alice.is_active = False
    db.commit()

    response = client.post(
        "/api/auth/login", json={"email": "alice@example.test", "password": "secret123"}
    )

    assert response.status_code == 401


def test_endpoints_require_a_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/companies").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_admin_creates_users_and_sales_users_cannot(client, admin, alice):
    payload = {"email": "new@example.test", "name": "New", "password": "secret123", "role": "user"}

    assert client.post("/api/users", json=payload, headers=auth(alice)).status_code == 403
    created = client.post("/api/users", json=payload, headers=auth(admin))
    assert created.status_code == 201
    assert "password" not in created.text
    assert client.post("/api/users", json=payload, headers=auth(admin)).status_code == 409


def test_any_user_can_list_users_for_owner_pickers(client, db, alice):
    make_user(db, "zed@example.test")

    response = client.get("/api/users", headers=auth(alice))

    assert [user["name"] for user in response.json()] == ["Alice", "Zed"]
    assert "password_hash" not in response.text
