from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    firebase_credentials_json: str = ""

    # --- RevenueCat (v1.1 monetization) ---
    # Shared secret configured in the RevenueCat dashboard webhook Authorization
    # header; the secret REST API key (v1) for the /subscribers fallback; and the
    # entitlement identifier that grants premium.
    revenuecat_webhook_secret: str = ""
    revenuecat_api_key: str = ""
    revenuecat_entitlement_id: str = "premium"

    # --- Admin & scheduled jobs (v1.2 notifications) ---
    # Shared key to authorize admin writes (e.g. POST /summaries), and the secret
    # Vercel Cron sends in the Authorization header for scheduled endpoints.
    admin_api_key: str = ""
    cron_secret: str = ""

    cors_origins: str = "*"
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
