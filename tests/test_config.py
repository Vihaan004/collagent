from collagent.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "jwt")
    s = Settings(_env_file=None)
    assert s.supabase_url == "https://x.supabase.co"
    assert s.supabase_service_role_key == "svc"
    assert s.supabase_jwt_secret == "jwt"
    assert s.frontend_origin == "http://localhost:3000"  # default
