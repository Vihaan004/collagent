from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    frontend_origin: str = "http://localhost:3000"
    tavily_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
