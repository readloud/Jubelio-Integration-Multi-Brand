# data_classifier.py
from typing import Dict, List, Any
from datetime import datetime
import json

class DataClassifier:
    """
    Mengklasifikasikan data dari Jubelio dengan menambahkan brand_id
    """
    
    def __init__(self, brand_id: str, brand_name: str):
        self.brand_id = brand_id
        self.brand_name = brand_name
    
    def classify_orders(self, orders: List[Dict]) -> List[Dict]:
        """Tambahkan brand_id ke setiap order"""
        classified = []
        for order in orders:
            classified.append({
                "brand_id": self.brand_id,
                "brand_name": self.brand_name,
                "jubelio_order_id": order.get("id"),
                "order_number": order.get("order_number"),
                "total_price": float(order.get("total_price", 0)),
                "status": order.get("status"),
                "channel": order.get("channel_name"),
                "created_at": order.get("created_at"),
                "raw_data": json.dumps(order)  # simpan raw jika perlu
            })
        return classified
    
    def classify_products(self, products: List[Dict]) -> List[Dict]:
        """Tambahkan brand_id ke setiap produk"""
        classified = []
        for product in products:
            classified.append({
                "brand_id": self.brand_id,
                "brand_name": self.brand_name,
                "sku": product.get("sku"),
                "product_name": product.get("name"),
                "price": float(product.get("price", 0)),
                "stock": product.get("stock", 0),
                "category": product.get("category"),
                "raw_data": json.dumps(product)
            })
        return classified
    
    def classify_stock(self, stocks: List[Dict]) -> List[Dict]:
        """Tambahkan brand_id ke setiap data stok"""
        classified = []
        for stock in stocks:
            classified.append({
                "brand_id": self.brand_id,
                "brand_name": self.brand_name,
                "sku": stock.get("sku"),
                "product_name": stock.get("product_name"),
                "quantity": int(stock.get("quantity", 0)),
                "warehouse": stock.get("warehouse"),
                "last_updated": datetime.now().isoformat(),
                "raw_data": json.dumps(stock)
            })
        return classified
    
    def classify_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """Tambahkan brand_id ke setiap transaksi"""
        classified = []
        for transaction in transactions:
            classified.append({
                "brand_id": self.brand_id,
                "brand_name": self.brand_name,
                "transaction_id": transaction.get("id"),
                "order_id": transaction.get("order_id"),
                "amount": float(transaction.get("amount", 0)),
                "payment_method": transaction.get("payment_method"),
                "transaction_date": transaction.get("transaction_date"),
                "raw_data": json.dumps(transaction)
            })
        return classified