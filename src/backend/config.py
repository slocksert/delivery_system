from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    app_name: str = "Delivery System"
    version: str = "1.0.0"
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    allow_origins: List[str] = ["*"]

    core_data_path: str = "../core/data"
    upload_path: str = "./uploads"

    secret_key: Optional[str] = "40dd74351200de7f808a2badede3de1cb077fd322bc9493fc08555466086a5e9"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    class Config:
        env_file = ".env"

settings = Settings()