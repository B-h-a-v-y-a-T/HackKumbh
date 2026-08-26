import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Exam Behaviour Monitoring System - Part 4 Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./exam_monitoring.db")
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]
    
    # Privacy Settings
    PRIVACY_MODE_ENABLED: bool = True
    ALLOW_FACIAL_RECOGNITION: bool = False
    ALLOW_BIOMETRICS: bool = False
    ALLOW_AUDIO_SURVEILLANCE: bool = False
    
    # Thresholds
    LOW_VISIBILITY_THRESHOLD: float = 0.50
    RISK_HIGH_THRESHOLD: int = 70
    RISK_CRITICAL_THRESHOLD: int = 85
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
