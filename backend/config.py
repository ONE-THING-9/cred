import os
from pathlib import Path

# Base directory for the application
BASE_DIR = "C:\\Users\\seema\\OneDrive\\Desktop\\vscode\\legal\\legal_ai_backend\\backend"
# BASE_DIR = "./backend/"


# Base paths for different resources
PATHS = {
    "downloads": "C:\\Users\\seema\\OneDrive\\Desktop\\vscode\\legal\\legal_ai_backend\\backend\\fir_pdfs",  
    # "downloads": "/home/ubuntu/downloads",
    "uploads": os.environ.get("LEGAL_AI_UPLOADS_PATH", os.path.join(BASE_DIR, "uploads")),
    "temp": os.environ.get("LEGAL_AI_TEMP_PATH", os.path.join(BASE_DIR, "temp")),
    "logs": os.environ.get("LEGAL_AI_LOGS_PATH", os.path.join(BASE_DIR, "logs")),
    "prompts": os.environ.get("LEGAL_AI_PROMPTS_PATH", os.path.join(BASE_DIR, "prompts")),
}

# Database configuration
DB_CONFIG = {
    "host": os.environ.get("LEGAL_AI_DB_HOST", "localhost"),
    "port": int(os.environ.get("LEGAL_AI_DB_PORT", 27017)),
    "name": os.environ.get("LEGAL_AI_DB_NAME", "legal_ai"),
}

# API configuration
API_CONFIG = {
    "base_url": os.environ.get("LEGAL_AI_API_BASE_URL", "https://184.73.131.8/legal"),
}

# Ensure all directories exist
def ensure_directories():
    for path in PATHS.values():
        os.makedirs(path, exist_ok=True)

# Call this function when the application starts
ensure_directories() 