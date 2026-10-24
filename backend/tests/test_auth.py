from conftest import auth


def test_register_login_profile(client):
    r = client.post("/register", json={"name": "Ayşe Demir", "email": "ayse@example.com", "password": "secret1"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "candidate" and "hashed_password" not in body["user"]
    h = auth(body["access_token"])

    assert client.get("/profile", headers=h).json()["email"] == "ayse@example.com"
    assert client.get("/validate-token", headers=h).json()["valid"] is True

    r = client.put("/profile", headers=h, json={"target_role": "DevOps Engineer", "experience": "Fresher",
                                                "industry": "Fintech", "language": "Turkish"})
    assert r.status_code == 200 and r.json()["language"] == "Turkish"

    r = client.put("/profile/password", headers=h, json={"current_password": "wrong", "new_password": "newsecret"})
    assert r.status_code == 400
    r = client.put("/profile/password", headers=h, json={"current_password": "secret1", "new_password": "newsecret"})
    assert r.status_code == 200
    assert client.post("/login", json={"email": "ayse@example.com", "password": "secret1"}).status_code == 401
    assert client.post("/login", json={"email": "ayse@example.com", "password": "newsecret"}).status_code == 200


def test_register_validation(client):
    assert client.post("/register", json={"name": "A", "email": "bad", "password": "x"}).status_code == 422
    client.post("/register", json={"name": "Dup User", "email": "dup@example.com", "password": "secret1"})
    r = client.post("/register", json={"name": "Dup User", "email": "DUP@example.com", "password": "secret1"})
    assert r.status_code == 400  # emails are case-insensitive


def test_password_is_bcrypt_hashed(client):
    client.post("/register", json={"name": "Hash User", "email": "hash@example.com", "password": "secret1"})
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == "hash@example.com").first()
        assert u.hashed_password.startswith("$2") and "secret1" not in u.hashed_password
    finally:
        db.close()


def test_logout_revokes_token(client):
    t = client.post("/register", json={"name": "Logout User", "email": "logout@example.com", "password": "secret1"}).json()["access_token"]
    assert client.get("/profile", headers=auth(t)).status_code == 200
    assert client.post("/logout", headers=auth(t)).status_code == 200
    assert client.get("/profile", headers=auth(t)).status_code == 401


def test_forgot_and_reset_password(client):
    client.post("/register", json={"name": "Reset User", "email": "reset@example.com", "password": "secret1"})
    r = client.post("/forgot-password", json={"email": "reset@example.com"}).json()
    token = r["reset_token"]
    assert client.post("/reset-password", json={"token": "nope", "new_password": "abcdef"}).status_code == 400
    assert client.post("/reset-password", json={"token": token, "new_password": "abcdef"}).status_code == 200
    assert client.post("/reset-password", json={"token": token, "new_password": "abcdef"}).status_code == 400  # one use only
    assert client.post("/login", json={"email": "reset@example.com", "password": "abcdef"}).status_code == 200
    assert "reset_token" not in client.post("/forgot-password", json={"email": "nobody@example.com"}).json()


def test_role_protection(client, candidate, admin):
    assert client.get("/users").status_code == 401
    assert client.get("/users", headers=candidate).status_code == 403
    assert client.get("/analytics", headers=candidate).status_code == 403
    assert client.get("/users", headers=admin).status_code == 200
