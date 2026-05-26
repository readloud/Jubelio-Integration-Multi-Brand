# database.py
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        """Koneksi ke PostgreSQL"""
        try:
            self.conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                database=os.getenv('DB_NAME', 'jubelio_integration'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', '')
            )
            self.conn.autocommit = False
            print("Database connected successfully")
        except Exception as e:
            print(f"Database connection error: {e}")
            raise
    
    def execute_query(self, query: str, params: tuple = None):
        """Eksekusi query dengan transaction"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(query, params)
            self.conn.commit()
            return cursor
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def insert_orders(self, orders: List[Dict]):
        """Insert orders ke database"""
        query = """
            INSERT INTO orders 
            (brand_id, jubelio_order_id, order_number, total_price, status, 
             channel, customer_name, customer_phone, order_date, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (jubelio_order_id) DO UPDATE SET
                status = EXCLUDED.status,
                total_price = EXCLUDED.total_price,
                updated_at = CURRENT_TIMESTAMP
        """
        
        cursor = self.conn.cursor()
        try:
            for order in orders:
                cursor.execute(query, (
                    order['brand_id'],
                    order['jubelio_order_id'],
                    order['order_number'],
                    order['total_price'],
                    order['status'],
                    order['channel'],
                    order.get('customer_name'),
                    order.get('customer_phone'),
                    order.get('order_date'),
                    Json(order.get('raw_data', {}))
                ))
            self.conn.commit()
            print(f"Inserted/Updated {len(orders)} orders")
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def insert_products(self, products: List[Dict]):
        """Insert products ke database"""
        query = """
            INSERT INTO products 
            (brand_id, sku, product_name, price, stock, category, last_sync, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (sku) DO UPDATE SET
                product_name = EXCLUDED.product_name,
                price = EXCLUDED.price,
                stock = EXCLUDED.stock,
                last_sync = EXCLUDED.last_sync,
                raw_data = EXCLUDED.raw_data
        """
        
        cursor = self.conn.cursor()
        try:
            for product in products:
                cursor.execute(query, (
                    product['brand_id'],
                    product['sku'],
                    product['product_name'],
                    product['price'],
                    product['stock'],
                    product['category'],
                    datetime.now(),
                    Json(product.get('raw_data', {}))
                ))
            self.conn.commit()
            print(f"Inserted/Updated {len(products)} products")
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def insert_stock_history(self, stock_data: List[Dict]):
        """Insert stock history ke database"""
        query = """
            INSERT INTO stock_history 
            (brand_id, sku, quantity, warehouse, recorded_at, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        cursor = self.conn.cursor()
        try:
            for stock in stock_data:
                cursor.execute(query, (
                    stock['brand_id'],
                    stock['sku'],
                    stock['quantity'],
                    stock.get('warehouse'),
                    datetime.now(),
                    Json(stock.get('raw_data', {}))
                ))
            self.conn.commit()
            print(f"Inserted {len(stock_data)} stock records")
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def insert_transactions(self, transactions: List[Dict]):
        """Insert transactions ke database"""
        query = """
            INSERT INTO transactions 
            (brand_id, transaction_id, order_id, amount, payment_method, transaction_date, raw_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (transaction_id) DO NOTHING
        """
        
        cursor = self.conn.cursor()
        try:
            for trans in transactions:
                cursor.execute(query, (
                    trans['brand_id'],
                    trans['transaction_id'],
                    trans.get('order_id'),
                    trans['amount'],
                    trans.get('payment_method'),
                    trans.get('transaction_date'),
                    Json(trans.get('raw_data', {}))
                ))
            self.conn.commit()
            print(f"Inserted {len(transactions)} transactions")
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def log_sync(self, brand_id: str, data_type: str, status: str, 
                 records_count: int = 0, error_message: str = None):
        """Catat log sinkronisasi"""
        query = """
            INSERT INTO sync_logs 
            (brand_id, data_type, status, records_count, error_message, started_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        self.execute_query(query, (
            brand_id, data_type, status, records_count, error_message,
            datetime.now(), datetime.now()
        ))
    
    def save_token(self, brand_id: str, access_token: str, refresh_token: str, expires_at: int):
        """Simpan token ke database"""
        query = """
            INSERT INTO tokens (brand_id, access_token, refresh_token, expires_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (brand_id) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                updated_at = CURRENT_TIMESTAMP
        """
        self.execute_query(query, (brand_id, access_token, refresh_token, expires_at, datetime.now()))
    
    def get_token(self, brand_id: str) -> Optional[Dict]:
        """Ambil token dari database"""
        query = "SELECT access_token, refresh_token, expires_at FROM tokens WHERE brand_id = %s"
        cursor = self.execute_query(query, (brand_id,))
        result = cursor.fetchone()
        if result:
            return {
                'access_token': result[0],
                'refresh_token': result[1],
                'expires_at': result[2]
            }
        return None
    
    def close(self):
        if self.conn:
            self.conn.close()