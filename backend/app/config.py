from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str
    tmdb_read_access_token: str
    google_books_api_key: str
    database_url: str = "postgresql+asyncpg://gen_user:gen_pass@localhost:5432/gen_app"
    redis_url: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"

settings = Settings()