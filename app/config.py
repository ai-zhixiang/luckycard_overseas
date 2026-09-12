from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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

    # PayPal — Live
    paypal_client_id_live: str = ""
    paypal_client_secret_live: str = ""
    paypal_webhook_id_live: str = ""

    # PayPal — Sandbox
    paypal_client_id_sandbox: str = ""
    paypal_client_secret_sandbox: str = ""
    paypal_webhook_id_sandbox: str = ""

    # PayPal — Mode (true=sandbox, false=live)
    paypal_sandbox: bool = True

    # Dev helper: allow test point grants (wallet/grant). Disable in production.
    dev_grant: bool = False

    # Cloud-browser master switch (server-side headless browser for the IE window).
    # The 2G server cannot feed a Chromium instance — keep OFF unless upgraded to 4G+.
    # Any cloud-browser code path MUST check this before launching a browser.
    ie_cloud_browser_enabled: bool = False
    hicard_key_pepper: str = ""          # API key (lc-) HMAC pepper

    @property
    def paypal_client_id(self) -> str:
        return self.paypal_client_id_sandbox if self.paypal_sandbox else self.paypal_client_id_live

    @property
    def paypal_client_secret(self) -> str:
        return self.paypal_client_secret_sandbox if self.paypal_sandbox else self.paypal_client_secret_live

    @property
    def paypal_webhook_id(self) -> str:
        return self.paypal_webhook_id_sandbox if self.paypal_sandbox else self.paypal_webhook_id_live

    @property
    def paypal_api_base(self) -> str:
        return "https://api-m.sandbox.paypal.com" if self.paypal_sandbox else "https://api-m.paypal.com"

    class Config:
        env_file = ".env"


settings = Settings()
