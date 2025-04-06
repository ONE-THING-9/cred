import logging
import json
from datetime import datetime
import os
from typing import Any, Dict, Optional

class CustomJSONFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()
        
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
            
        return json.dumps(log_data)

def setup_logger(name: str = "app_logger", log_level: int = logging.INFO) -> logging.Logger:
    """
    Setup and configure the logger
    
    Args:
        name (str): Name of the logger
        log_level (int): Logging level
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CustomJSONFormatter())
    logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(f"logs/{name}.log")
    file_handler.setFormatter(CustomJSONFormatter())
    logger.addHandler(file_handler)
    
    return logger

# Create a default logger instance
logger = setup_logger()

def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs):
    """
    Log a message with additional context
    
    Args:
        logger (logging.Logger): Logger instance
        level (str): Log level (debug, info, warning, error, critical)
        message (str): Log message
        **kwargs: Additional context fields
    """
    log_func = getattr(logger, level.lower())
    extra = {"extra_fields": kwargs}
    log_func(message, extra=extra) 