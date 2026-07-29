from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    model_path: str = "model.joblib"
    app_name: str = "clinical-trial-matcher"


settings = Settings()