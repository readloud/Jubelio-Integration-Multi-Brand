# webhook_handler.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib
import hmac
import os
from database import Database
from logger import logger
from alerting import alert_manager
from jubelio_client import JubelioClient
from config import BRANDS

app = FastAPI()

db = Database()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your_webhook_secret_here")

# Models
class OrderWebhook(BaseModel):
    event_type: str
    brand_id: str
    order_id: str
    order_number: str
    status: str
    total_price: float
    created_at: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

class StockWebhook(BaseModel):
    event_type: str
    brand_id: str
    sku: str
    product_name: str
    old_quantity: int
    new_quantity: int
    warehouse: str
    updated_at: str

class ProductWebhook(BaseModel):
    event_type: str
    brand_id: str
    sku: str
    product_name: str
    price: float
    stock: int
    action: str  # create, update, delete

# Verification function
def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify webhook signature from Jubelio"""
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)

# Webhook handlers
async def handle_order_created(data: Dict[str, Any]):
    """Handle new order created"""
    logger.info(f"New order created: {data['order_id']} for brand {data['brand_id']}")
    
    # Save to database
    query = """
        INSERT INTO orders (brand_id, jubelio_order_id, order_number, total_price, 
                            status, customer_name, customer_phone, order_date, raw_data)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (jubelio_order_id) DO NOTHING
    """
    
    db.execute_query(query, (
        data['brand_id'],
        data['order_id'],
        data['order_number'],
        data['total_price'],
        data['status'],
        data.get('customer_name'),
        data.get('customer_phone'),
        data['created_at'],
        data
    ))
    
    # Send notification
    await alert_manager.send_slack(
        f"🆕 *New Order Created*\n"
        f"Brand: {data['brand_id']}\n"
        f"Order: {data['order_number']}\n"
        f"Amount: Rp {data['total_price']:,.0f}\n"
        f"Customer: {data.get('customer_name', 'N/A')}"
    )

async def handle_order_updated(data: Dict[str, Any]):
    """Handle order status update"""
    logger.info(f"Order updated: {data['order_id']} - New status: {data['status']}")
    
    # Update database
    query = """
        UPDATE orders 
        SET status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE jubelio_order_id = %s AND brand_id = %s
    """
    
    db.execute_query(query, (data['status'], data['order_id'], data['brand_id']))
    
    # Send alert for important status changes
    if data['status'] in ['cancelled', 'refunded']:
        await alert_manager.send_slack(
            f"⚠️ *Order {data['status'].upper()}*\n"
            f"Brand: {data['brand_id']}\n"
            f"Order: {data['order_number']}",
            color="warning"
        )

async def handle_stock_updated(data: Dict[str, Any]):
    """Handle stock update"""
    logger.info(f"Stock updated: {data['sku']} - {data['old_quantity']} → {data['new_quantity']}")
    
    # Save to stock history
    query = """
        INSERT INTO stock_history (brand_id, sku, quantity, warehouse, recorded_at, raw_data)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    
    db.execute_query(query, (
        data['brand_id'],
        data['sku'],
        data['new_quantity'],
        data['warehouse'],
        datetime.now(),
        data
    ))
    
    # Update products table
    update_query = """
        UPDATE products 
        SET stock = %s, last_sync = CURRENT_TIMESTAMP
        WHERE brand_id = %s AND sku = %s
    """
    
    db.execute_query(update_query, (data['new_quantity'], data['brand_id'], data['sku']))
    
    # Alert if stock is low (<= 5)
    if data['new_quantity'] <= 5 and data['new_quantity'] > 0:
        await alert_manager.send_slack(
            f"⚠️ *Low Stock Alert*\n"
            f"Brand: {data['brand_id']}\n"
            f"Product: {data['product_name']}\n"
            f"SKU: {data['sku']}\n"
            f"Stock: {data['new_quantity']} remaining",
            color="warning"
        )
    elif data['new_quantity'] == 0:
        await alert_manager.send_slack(
            f"❌ *Out of Stock*\n"
            f"Brand: {data['brand_id']}\n"
            f"Product: {data['product_name']}\n"
            f"SKU: {data['sku']}",
            color="danger"
        )

async def handle_product_created(data: Dict[str, Any]):
    """Handle new product created"""
    logger.info(f"New product created: {data['sku']} for brand {data['brand_id']}")
    
    query = """
        INSERT INTO products (brand_id, sku, product_name, price, stock, category, last_sync, raw_data)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
        ON CONFLICT (sku) DO UPDATE SET
            product_name = EXCLUDED.product_name,
            price = EXCLUDED.price,
            stock = EXCLUDED.stock,
            last_sync = CURRENT_TIMESTAMP
    """
    
    db.execute_query(query, (
        data['brand_id'],
        data['sku'],
        data['product_name'],
        data['price'],
        data['stock'],
        data.get('category'),
        data
    ))

# Main webhook endpoint
@app.post("/webhook/jubelio")
async def jubelio_webhook(
    background_tasks: BackgroundTasks,
    payload: dict,
    x_signature: Optional[str] = None
):
    """
    Receive webhook from Jubelio
    """
    # Verify signature (optional but recommended)
    # if x_signature:
    #     import json
    #     if not verify_signature(json.dumps(payload).encode(), x_signature):
    #         raise HTTPException(status_code=401, detail="Invalid signature")
    
    event_type = payload.get("event_type")
    
    logger.info(f"Received webhook: {event_type} from brand {payload.get('brand_id')}")
    
    # Route to appropriate handler
    if event_type == "order.created":
        background_tasks.add_task(handle_order_created, payload)
    elif event_type == "order.updated":
        background_tasks.add_task(handle_order_updated, payload)
    elif event_type == "stock.updated":
        background_tasks.add_task(handle_stock_updated, payload)
    elif event_type == "product.created":
        background_tasks.add_task(handle_product_created, payload)
    elif event_type == "product.updated":
        background_tasks.add_task(handle_product_created, payload)  # Reuse same handler
    else:
        logger.warning(f"Unknown event type: {event_type}")
    
    return {
        "status": "received",
        "event_type": event_type,
        "timestamp": datetime.now().isoformat()
    }

# Webhook status endpoint
@app.get("/webhook/status")
async def webhook_status():
    """Get webhook processing status"""
    query = """
        SELECT event_type, COUNT(*) as count, 
               MIN(created_at) as first_event, 
               MAX(created_at) as last_event
        FROM webhook_logs
        WHERE created_at >= CURRENT_DATE - INTERVAL '24 hours'
        GROUP BY event_type
    """
    
    try:
        cursor = db.execute_query(query)
        results = cursor.fetchall()
        
        return {
            "status": "active",
            "statistics": [
                {
                    "event_type": row[0],
                    "count": row[1],
                    "first_event": row[2],
                    "last_event": row[3]
                }
                for row in results
            ]
        }
    except:
        # Table might not exist yet
        return {"status": "active", "statistics": []}

# Create webhook_logs table
def create_webhook_table():
    """Create table for webhook logs if not exists"""
    query = """
        CREATE TABLE IF NOT EXISTS webhook_logs (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(50),
            brand_id VARCHAR(50),
            payload JSONB,
            processed BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP
        )
    """
    db.execute_query(query)

# Initialize
create_webhook_table()