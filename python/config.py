# config.py
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class BrandConfig:
    brand_id: str
    brand_name: str
    jubelio_store_id: str  # atau channel_id dari Jubelio
    api_base_url: str
    username: str
    password: str
    # Atau jika pakai api_key:
    # api_key: str

# Daftar brand yang terintegrasi
BRANDS: Dict[str, BrandConfig] = {
    "brand_a": BrandConfig(
        brand_id="brand_a",
        brand_name="Toko A",
        jubelio_store_id="store_1001",
        api_base_url="https://api.jubelio.com/v1",
        username="user_brand_a",
        password="password_a"
    ),
    "brand_b": BrandConfig(
        brand_id="brand_b",
        brand_name="Toko B",
        jubelio_store_id="store_1002",
        api_base_url="https://api.jubelio.com/v1",
        username="user_brand_b",
        password="password_b"
    ),
    "brand_c": BrandConfig(
        brand_id="brand_c",
        brand_name="Toko C",
        jubelio_store_id="store_1003",
        api_base_url="https://api.jubelio.com/v1",
        username="user_brand_c",
        password="password_c"
    ),
}

# Time buffer untuk refresh token (detik)
TOKEN_EXPIRY_BUFFER = 300  # 5 menit sebelum expired