import pytest

from src.supabase_archive_store import (
    SupabaseArchiveConfig,
    SupabaseConfigurationError,
    sign_in_supabase_user,
)


def test_supabase_config_requires_url_and_key():
    with pytest.raises(SupabaseConfigurationError):
        SupabaseArchiveConfig(url="", anon_key="anon").validate()

    with pytest.raises(SupabaseConfigurationError):
        SupabaseArchiveConfig(url="https://example.supabase.co").validate()


def test_supabase_config_detects_user_session():
    config = SupabaseArchiveConfig(
        url="https://example.supabase.co",
        anon_key="anon",
        access_token="access",
        refresh_token="refresh",
    )

    assert config.api_key == "anon"
    assert config.uses_user_session is True


def test_sign_in_supabase_user_returns_session_tokens(monkeypatch):
    class FakeSession:
        access_token = "access-token"
        refresh_token = "refresh-token"

    class FakeUser:
        email = "equipe@example.com"

    class FakeAuth:
        def sign_in_with_password(self, payload):
            assert payload == {"email": "equipe@example.com", "password": "senha"}
            return type("Response", (), {"session": FakeSession(), "user": FakeUser()})()

    class FakeClient:
        auth = FakeAuth()

    monkeypatch.setattr(
        "src.supabase_archive_store._load_supabase_factory",
        lambda: lambda url, key: FakeClient(),
    )

    session = sign_in_supabase_user("https://example.supabase.co", "anon", "equipe@example.com", "senha")

    assert session == {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "email": "equipe@example.com",
    }
