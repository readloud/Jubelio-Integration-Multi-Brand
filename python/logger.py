# logger.py
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

class Logger:
    """Centralized logging system"""
    
    def __init__(self, name: str = 'jubelio_integration'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))
        
        # File handler dengan rotasi
        log_file = os.getenv('LOG_FILE', 'logs/jubelio_integration.log')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=10
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str, brand_id: str = None):
        msg = f"[{brand_id}] {message}" if brand_id else message
        self.logger.info(msg)
    
    def error(self, message: str, brand_id: str = None, exc_info: bool = False):
        msg = f"[{brand_id}] {message}" if brand_id else message
        self.logger.error(msg, exc_info=exc_info)
    
    def warning(self, message: str, brand_id: str = None):
        msg = f"[{brand_id}] {message}" if brand_id else message
        self.logger.warning(msg)
    
    def debug(self, message: str, brand_id: str = None):
        msg = f"[{brand_id}] {message}" if brand_id else message
        self.logger.debug(msg)

# Global logger instance
logger = Logger()