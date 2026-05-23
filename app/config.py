from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://lucky:lucky_pass@localhost:5432/luckycards"
    secret_key: str = "luckycards-overseas-2026"
    domain: str = "hicard.world"
    debug: bool = False
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    deepseek_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    
    class Config:
        env_file = ".env"

settings = Settings()
