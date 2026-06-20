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


def test_settings_has_tavily_key_default_empty(monkeypatch):
    # graph.py's load_dotenv may have populated os.environ from the real .env;
    # isolate the var so we're testing the field's declared default, not the dev's key.
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    from collagent.config import Settings
    s = Settings(_env_file=None)
    assert s.tavily_api_key == ""
