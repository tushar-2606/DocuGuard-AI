def test_register_login_me(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "full_name": "User Name",
            "password": "password12",
            "confirm_password": "password12",
        },
    )
    assert reg.status_code == 201
    body = reg.json()
    assert "access_token" in body
    assert body["user"]["email"] == "user@example.com"

    login = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password12"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"


def test_register_rejects_short_password(client):
    res = client.post(
        "/api/auth/register",
        json={
            "email": "short@example.com",
            "full_name": "Short",
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert res.status_code in (400, 422)


def test_me_requires_auth(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_invalid_login(client, auth_headers):
    res = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrongpassword"},
    )
    assert res.status_code == 401
