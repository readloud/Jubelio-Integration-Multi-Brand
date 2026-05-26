# token_manager.py
import time
import requests
from typing import Optional
from config import BrandConfig
from database import Database
from logger import logger
from alerting import alert_manager

class TokenManager:
    """Manage tokens with database persistence and auto-refresh"""
    
    def __init__(self, brand_config: BrandConfig):
        self.brand_config = brand_config
        self.db = Database()
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at: float = 0
        self._load_from_db()
    
    def _load_from_db(self):
        """Load token dari database"""
        token_data = self.db.get_token(self.brand_config.brand_id)
        if token_data:
            self.access_token = token_data['access_token']
            self.refresh_token = token_data['refresh_token']
            self.expires_at = token_data['expires_at']
            logger.info(f"Token loaded from DB for {self.brand_config.brand_name}", 
                       self.brand_config.brand_id)
    
    def _save_to_db(self):
        """Save token ke database"""
        self.db.save_token(
            self.brand_config.brand_id,
            self.access_token,
            self.refresh_token,
            self.expires_at
        )
    
    def _login(self) -> bool:
        """Login ke Jubelio"""
        url = f"{self.brand_config.api_base_url}/api/auth/login"
        payload = {
            "username": self.brand_config.username,
            "password": self.brand_config.password
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.expires_at = time.time() + 3600  # 1 hour
                self._save_to_db()
                logger.info(f"Login successful for {self.brand_config.brand_name}", 
                           self.brand_config.brand_id)
                return True
            else:
                error_msg = f"Login failed: {response.text}"
                logger.error(error_msg, self.brand_config.brand_id)
                alert_manager.alert_sync_failure(
                    self.brand_config.brand_id, 
                    "auth", 
                    error_msg
                )
                return False
        except Exception as e:
            logger.error(f"Login error: {e}", self.brand_config.brand_id, exc_info=True)
            return False
    
    def _refresh(self) -> bool:
        """Refresh token"""
        if not self.refresh_token:
            return self._login()
        
        url = f"{self.brand_config.api_base_url}/api/auth/refresh"
        payload = {"refresh_token": self.refresh_token}
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.expires_at = time.time() + 3600
                self._save_to_db()
                logger.info(f"Token refreshed for {self.brand_config.brand_name}", 
                           self.brand_config.brand_id)
                return True
            else:
                logger.warning(f"Refresh failed, trying login: {response.text}", 
                              self.brand_config.brand_id)
                return self._login()
        except Exception as e:
            logger.error(f"Refresh error: {e}", self.brand_config.brand_id, exc_info=True)
            return self._login()
    
    def get_valid_token(self) -> Optional[str]:
        """Get valid token, auto-refresh if needed"""
        TOKEN_EXPIRY_BUFFER = 300  # 5 minutes
        
        if not self.access_token:
            if not self._login():
                alert_manager.alert_token_expired(self.brand_config.brand_id)
                return None
        
        if time.time() >= (self.expires_at - TOKEN_EXPIRY_BUFFER):
            if not self._refresh():
                alert_manager.alert_token_expired(self.brand_config.brand_id)
                return None
        
        return self.access_token