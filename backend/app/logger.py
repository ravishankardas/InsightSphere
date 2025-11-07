import logging
import sys
from datetime import datetime
import os

class FastAPIStyleFormatter(logging.Formatter):
    """Formatter that mimics FastAPI's beautiful colored output"""
    
    # ANSI color codes
    grey = "\x1b[38;20m"
    green = "\x1b[32;1m"  # Bright green like FastAPI
    yellow = "\x1b[33;1m"  # Bright yellow
    red = "\x1b[31;1m"    # Bright red
    blue = "\x1b[34;1m"   # Bright blue
    magenta = "\x1b[35;1m" # Bright magenta
    cyan = "\x1b[36;1m"   # Bright cyan
    reset = "\x1b[0m"
    
    # Level name mappings with colors and icons
    LEVEL_STYLES = {
        logging.DEBUG: (grey, "🐛"),
        logging.INFO: (green, "ℹ️"),
        logging.WARNING: (yellow, "⚠️"),
        logging.ERROR: (red, "❌"),
        logging.CRITICAL: (red, "💥")
    }
    
    def format(self, record):
        color, icon = self.LEVEL_STYLES.get(record.levelno, (self.green, "ℹ️"))
        
        # Create formatted message
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        levelname = f"{color}{record.levelname:8}{self.reset}"
        
        # Format the main message
        formatted_message = f"{timestamp} {levelname} {icon}  {record.getMessage()}"
        
        # Add file location for DEBUG and above
        if record.levelno >= logging.DEBUG:
            formatted_message += f" {self.grey}[{record.filename}:{record.lineno}]{self.reset}"
        
        return formatted_message

def setup_logger(name: str = "InsightSphere", log_level: str = "INFO"):
    """
    Setup logger with FastAPI-style colored output
    """
    # Create logs directory
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Generate log filename
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"app_{timestamp}.log")
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Avoid duplicate handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # FastAPI-style Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(FastAPIStyleFormatter())
    
    # File Handler (plain text)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    file_handler.setFormatter(file_formatter)
    
    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # Prevent propagation
    logger.propagate = False
    
    return logger

# Create default logger instance
logger = setup_logger()