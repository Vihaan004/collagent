from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    frontend_origin: str = "http://localhost:3000"
    tavily_api_key: str = ""
    # Major-map extraction launches headless Chromium (Playwright) during onboarding.
    # Disabled by default for the RAM-light demo deploy; set MAJOR_MAP_ENABLED=true
    # (on a host with enough RAM + Chromium installed) to restore the feature.
    major_map_enabled: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
