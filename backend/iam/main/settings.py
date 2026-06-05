from functools import lru_cache

from cm_shared.settings import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "iam"
    service_port: int = 1100

    # OAuth 2.0 Web Client ID from Google Cloud Console. Used as the expected
    # `aud` when verifying the Google ID token. Empty disables Google sign-in.
    google_client_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
