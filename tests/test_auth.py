"""
AnomaFlow v2.0 — Tests des endpoints d'authentification
Couvre : register, login, logout, me, PUT /users/me
"""
import pytest


class TestRegister:
    def test_register_success(self, client):
        res = client.post("/auth/register", json={
            "email": "new@test.io",
            "password": "password123",
            "full_name": "New User",
        })
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client):
        payload = {"email": "dup@test.io", "password": "password123"}
        client.post("/auth/register", json=payload)
        res = client.post("/auth/register", json=payload)
        assert res.status_code == 409
        assert "déjà utilisé" in res.json()["detail"].lower()

    def test_register_weak_password(self, client):
        res = client.post("/auth/register", json={
            "email": "short@test.io",
            "password": "123",      # < 8 caractères
        })
        assert res.status_code == 422

    def test_register_invalid_email(self, client):
        res = client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "password123",
        })
        assert res.status_code == 422

    def test_register_without_full_name(self, client):
        """full_name est optionnel."""
        res = client.post("/auth/register", json={
            "email": "noname@test.io",
            "password": "password123",
        })
        assert res.status_code == 201


class TestLogin:
    def test_login_success(self, client):
        client.post("/auth/register", json={"email": "login@test.io", "password": "password123"})
        res = client.post("/auth/login", json={"email": "login@test.io", "password": "password123"})
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={"email": "wrong@test.io", "password": "password123"})
        res = client.post("/auth/login", json={"email": "wrong@test.io", "password": "wrongpass"})
        assert res.status_code == 401

    def test_login_unknown_email(self, client):
        res = client.post("/auth/login", json={"email": "ghost@test.io", "password": "password123"})
        assert res.status_code == 401

    def test_login_returns_bearer_type(self, client):
        client.post("/auth/register", json={"email": "type@test.io", "password": "password123"})
        res = client.post("/auth/login", json={"email": "type@test.io", "password": "password123"})
        assert res.json()["token_type"] == "bearer"


class TestLogout:
    def test_logout_success(self, client, auth_headers):
        """Logout doit retourner 204 No Content."""
        res = client.post("/auth/logout", headers=auth_headers)
        assert res.status_code == 204

    def test_token_revoked_after_logout(self, client, auth_headers):
        """Après logout, le token ne doit plus être accepté."""
        client.post("/auth/logout", headers=auth_headers)
        res = client.get("/users/me", headers=auth_headers)
        assert res.status_code == 401

    def test_logout_without_token(self, client):
        """Logout sans token doit retourner 403 ou 401."""
        res = client.post("/auth/logout")
        assert res.status_code in (401, 403)

    def test_double_logout_rejected(self, client, auth_headers):
        """Un second logout avec le même token doit échouer."""
        client.post("/auth/logout", headers=auth_headers)
        res = client.post("/auth/logout", headers=auth_headers)
        assert res.status_code == 401


class TestGetMe:
    def test_get_me_authenticated(self, client, auth_headers):
        res = client.get("/users/me", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "email" in data
        assert "id" in data
        assert "is_active" in data

    def test_get_me_unauthenticated(self, client):
        res = client.get("/users/me")
        assert res.status_code in (401, 403)

    def test_get_me_invalid_token(self, client):
        res = client.get("/users/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert res.status_code == 401


class TestUpdateMe:
    def test_update_full_name(self, client, auth_headers):
        res = client.put("/users/me", json={"full_name": "Updated Name"}, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["full_name"] == "Updated Name"

    def test_update_password(self, client):
        """Après changement de mot de passe, l'ancien ne doit plus fonctionner."""
        client.post("/auth/register", json={"email": "pwchange@test.io", "password": "oldpassword1"})
        login_res = client.post("/auth/login", json={"email": "pwchange@test.io", "password": "oldpassword1"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        client.put("/users/me", json={"password": "newpassword1"}, headers=headers)

        # Ancien mot de passe refusé
        old_login = client.post("/auth/login", json={"email": "pwchange@test.io", "password": "oldpassword1"})
        assert old_login.status_code == 401

        # Nouveau mot de passe accepté
        new_login = client.post("/auth/login", json={"email": "pwchange@test.io", "password": "newpassword1"})
        assert new_login.status_code == 200

    def test_update_empty_body_is_noop(self, client, auth_headers):
        """Un body vide ne doit pas effacer les données existantes."""
        me_before = client.get("/users/me", headers=auth_headers).json()
        res = client.put("/users/me", json={}, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["email"] == me_before["email"]

    def test_update_requires_auth(self, client):
        res = client.put("/users/me", json={"full_name": "Hacker"})
        assert res.status_code in (401, 403)

    def test_update_password_too_short(self, client, auth_headers):
        res = client.put("/users/me", json={"password": "short"}, headers=auth_headers)
        assert res.status_code == 422
