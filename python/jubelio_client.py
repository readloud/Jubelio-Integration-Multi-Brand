# jubelio_client.py
import requests
from typing import Dict, List, Optional
from config import BrandConfig
from token_manager import TokenManager

class JubelioClient:
    """
    Client untuk mengakses API Jubelio dengan token otomatis
    """
    
    def __init__(self, brand_config: BrandConfig):
        self.brand_config = brand_config
        self.token_manager = TokenManager(brand_config)
        self.base_url = brand_config.api_base_url
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Optional[Dict]:
        """Melakukan request dengan retry jika token expired"""
        max_retries = 2
        
        for attempt in range(max_retries):
            token = self.token_manager.get_valid_token()
            if not token:
                return None
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}{endpoint}"
            
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    # Token invalid, force refresh
                    print(f"[{self.brand_config.brand_name}] Token invalid, mencoba refresh...")
                    self.token_manager._refresh()
                    continue
                else:
                    print(f"[{self.brand_config.brand_name}] Error {response.status_code}: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"[{self.brand_config.brand_name}] Request error: {e}")
                return None
        
        return None
    
    def get_orders(self, start_date: str = None, end_date: str = None) -> Optional[List[Dict]]:
        """Ambil daftar order"""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        # Filter berdasarkan store_id brand
        params["store_id"] = self.brand_config.jubelio_store_id
        
        return self._make_request("GET", "/api/orders", params=params)
    
    def get_products(self) -> Optional[List[Dict]]:
        """Ambil daftar produk"""
        params = {"store_id": self.brand_config.jubelio_store_id}
        return self._make_request("GET", "/api/products", params=params)
    
    def get_stock(self) -> Optional[List[Dict]]:
        """Ambil data stok"""
        params = {"store_id": self.brand_config.jubelio_store_id}
        return self._make_request("GET", "/api/stocks", params=params)
    
    def get_transactions(self) -> Optional[List[Dict]]:
        """Ambil data transaksi"""
        params = {"store_id": self.brand_config.jubelio_store_id}
        return self._make_request("GET", "/api/transactions", params=params)
    
    def get_channels(self) -> Optional[List[Dict]]:
        """Ambil channel penjualan"""
        return self._make_request("GET", "/api/channels")