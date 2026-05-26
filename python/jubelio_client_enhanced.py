# jubelio_client_enhanced.py
from retry_handler import AdvancedRetryHandler, RetryConfig, RetryStrategy, monitor_sla
from sla_monitor import get_sla_monitor
from typing import Optional, Dict, List
import requests

class EnhancedJubelioClient:
    """Enhanced Jubelio client with retry and SLA monitoring"""
    
    def __init__(self, brand_config):
        self.brand_config = brand_config
        self.retry_handler = AdvancedRetryHandler()
        self.sla_monitor = get_sla_monitor()
        
        # Configure retry for different operations
        self.retry_configs = {
            "critical": RetryConfig(
                max_retries=5,
                base_delay=1.0,
                max_delay=30.0,
                strategy=RetryStrategy.EXPONENTIAL,
                jitter=True,
                max_total_time=120
            ),
            "normal": RetryConfig(
                max_retries=3,
                base_delay=0.5,
                max_delay=15.0,
                strategy=RetryStrategy.LINEAR,
                jitter=True
            ),
            "fast": RetryConfig(
                max_retries=2,
                base_delay=0.2,
                max_delay=5.0,
                strategy=RetryStrategy.RANDOM,
                jitter=True
            )
        }
    
    @monitor_sla("api.orders.sync")
    def get_orders_with_retry(self, start_date: str = None, end_date: str = None) -> Optional[List[Dict]]:
        """Get orders with automatic retry and SLA monitoring"""
        
        @self.retry_handler.retry(config=self.retry_configs["normal"])
        def _fetch():
            # Actual API call
            response = requests.get(
                f"{self.brand_config.api_base_url}/api/orders",
                params={
                    "store_id": self.brand_config.jubelio_store_id,
                    "start_date": start_date,
                    "end_date": end_date
                },
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=30
            )
            
            if response.status_code == 429:
                raise Exception("Rate limit exceeded")
            
            response.raise_for_status()
            return response.json()
        
        try:
            return _fetch()
        except Exception as e:
            self.sla_monitor.record_duration("api.orders.sync", 0)  # Record failure
            raise e
    
    @monitor_sla("token.refresh")
    def refresh_token_with_retry(self) -> bool:
        """Refresh token with aggressive retry"""
        
        @self.retry_handler.retry(config=self.retry_configs["critical"])
        def _refresh():
            response = requests.post(
                f"{self.brand_config.api_base_url}/api/auth/refresh",
                json={"refresh_token": self.refresh_token},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        
        try:
            data = _refresh()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            return True
        except Exception as e:
            logger.error(f"Token refresh failed after retries: {e}")
            return False