import os
from dotenv import load_dotenv

# Load .env from current directory only
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"Loaded configuration from {env_path}")
else:
    print(f"Warning: No .env file found at {env_path}. Using system environment variables or defaults.")

class Settings:
    """
    Independent configuration for Meta-Analyzer.
    Decoupled from the main project's settings.
    """
    
    # LLM Configuration (OpenAI Compatible)
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    
    # Data Configuration
    # Default to ../../backend/data/history relative to this file
    # Users can override this via DATA_DIR environment variable
    _default_data_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "backend", "data", "history"))
    DATA_DIR = os.getenv("DATA_DIR", _default_data_dir)

    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        missing = []
        if not cls.LLM_API_KEY:
            missing.append("LLM_API_KEY")
        
        if missing:
            return False, f"Missing environment variables: {', '.join(missing)}"
        return True, "Configuration valid"

# Singleton instance
settings = Settings()
