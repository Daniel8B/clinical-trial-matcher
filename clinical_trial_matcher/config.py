from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    model_config = SettingsConfigDict(env_file=".env")

    embedding_model_name: str = "all-MiniLM-L6-v2"
    cross_encoder_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    embedding_dimension: int = 384

    app_name: str = "clinical-trial-matcher"

    database_url: str = "postgresql://trials:trials@localhost:5432/trials"


settings = Settings()