import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'feedback.db'}")
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "school-feedback-secure-key-2026")
    DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    
    # Rate Limiting
    RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("RATE_LIMIT_MAX_ATTEMPTS", "5"))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "300")) # 5 minutes
    
    # K-Anonymity privacy threshold for teacher reports
    MIN_RESPONSES_FOR_REPORT = int(os.getenv("MIN_RESPONSES_FOR_REPORT", "5"))
    
    # Defaults
    DEFAULT_CLASSES = list(range(6, 13))
    DEFAULT_SECTIONS = ["A", "B", "C", "D", "E"]
    DEFAULT_STREAMS = ["General", "Science", "Commerce", "Humanities"]
    DEFAULT_DEPARTMENTS = ["Academic", "Science", "Mathematics", "Languages", "Social Sciences", "Sports", "Arts & Music", "Computer Science"]
