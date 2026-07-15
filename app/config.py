from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # PayPal
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    database_url: str = "postgresql+asyncpg://lucky:CHANGEME@localhost:5432/luckycards"
    secret_key: str = ""
    domain: str = "hicard.world"
    debug: bool = False
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    deepseek_api_key: str = ""
    ark_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Lemon Squeezy
    ls_api_key: str = ""
    ls_store_id: str = ""
    ls_webhook_secret: str = ""
    ls_premium_variant_id: int = 0

    class Config:
        env_file = ".env"

settings = Settings()
