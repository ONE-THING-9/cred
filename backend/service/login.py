import uuid
import hashlib
import json
from typing import Optional
from datetime import datetime, timedelta
from logger import logger

# In-memory storage for users and sessions (replace with database in production)
users = {}
sessions = {}

def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

async def create_user(user_id: str, password: str) -> bool:
    """Create a new user."""
    try:
        # Check if user already exists
        if user_id in users:
            return False
        
        # Hash password and store user
        hashed_password = hash_password(password)
        users[user_id] = {
            "password": hashed_password,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # In production, save to database instead of memory
        save_users_to_file()
        return True
    
    except Exception as e:
        logger.error("Error creating user", error=str(e), user_id=user_id)
        raise Exception("Failed to create user")

async def authenticate_user(user_id: str, password: str) -> Optional[str]:
    """Authenticate user and return session ID if successful."""
    try:
        # Check if user exists and password matches
        if user_id not in users:
            return None
        
        hashed_password = hash_password(password)
        if users[user_id]["password"] != hashed_password:
            return None
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }
        
        # In production, save to database instead of memory
        save_sessions_to_file()
        return session_id
    
    except Exception as e:
        logger.error("Error authenticating user", error=str(e), user_id=user_id)
        raise Exception("Authentication failed")

async def validate_session(session_id: Optional[str]) -> bool:
    """Validate a session ID."""
    try:
        if not session_id or session_id not in sessions:
            return False
        
        session = sessions[session_id]
        expires_at = datetime.fromisoformat(session["expires_at"])
        
        # Check if session has expired
        if datetime.utcnow() > expires_at:
            del sessions[session_id]
            save_sessions_to_file()
            return False
        
        return True
    
    except Exception as e:
        logger.error("Error validating session", error=str(e), session_id=session_id)
        return False

async def end_session(session_id: str) -> bool:
    """End a user session."""
    try:
        if session_id in sessions:
            del sessions[session_id]
            save_sessions_to_file()
            return True
        return False
    except Exception as e:
        logger.error("Error ending session", error=str(e), session_id=session_id)
        return False

def save_users_to_file():
    """Save users to a JSON file."""
    try:
        with open('users.json', 'w') as f:
            json.dump(users, f)
    except Exception as e:
        logger.error("Error saving users to file", error=str(e))

def save_sessions_to_file():
    """Save sessions to a JSON file."""
    try:
        with open('sessions.json', 'w') as f:
            json.dump(sessions, f)
    except Exception as e:
        logger.error("Error saving sessions to file", error=str(e))

def load_data_from_files():
    """Load users and sessions from JSON files on startup."""
    global users, sessions
    
    try:
        with open('users.json', 'r') as f:
            users = json.load(f)
    except FileNotFoundError:
        users = {}
    except Exception as e:
        logger.error("Error loading users from file", error=str(e))
        users = {}

    try:
        with open('sessions.json', 'r') as f:
            sessions = json.load(f)
    except FileNotFoundError:
        sessions = {}
    except Exception as e:
        logger.error("Error loading sessions from file", error=str(e))
        sessions = {}

# Load data when module is imported
load_data_from_files() 