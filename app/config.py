from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USERNAME: str
    IMAP_PASSWORD: str
    SSL_VERIFY: bool = True
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
