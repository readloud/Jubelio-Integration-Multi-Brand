# api_monitoring.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional, List
from datetime import datetime, timedelta
import pandas as pd
import os
from database import Database
from logger import logger

app = FastAPI(title="Jubelio Integration API", version="1.0.0")

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database()

# ==================== HEALTH CHECK ====================
@app.get("/api/health")
async def health_check():
    """Check system health"""
    try:
        # Check database
        db.execute_query("SELECT 1")
        db_status = "healthy"
    except:
        db_status = "unhealthy"
    
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "version": "1.0.0"
    }

# ==================== SYNC STATUS ====================
@app.get("/api/sync/status")
async def get_sync_status(
    brand_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get sync history"""
    query = """
        SELECT * FROM sync_logs 
        WHERE ($1::text IS NULL OR brand_id = $1)
        ORDER BY started_at DESC 
        LIMIT $2
    """
    cursor = db.execute_query(query, (brand_id, limit))
    results = cursor.fetchall()
    
    columns = ['id', 'brand_id', 'data_type', 'status', 'records_count', 
               'error_message', 'started_at', 'completed_at']
    
    logs = []
    for row in results:
        logs.append(dict(zip(columns, row)))
    
    return {
        "total": len(logs),
        "logs": logs,
        "filters": {"brand_id": brand_id, "limit": limit}
    }

@app.get("/api/sync/last/{brand_id}")
async def get_last_sync(brand_id: str):
    """Get last sync info for a brand"""
    query = """
        SELECT data_type, status, records_count, completed_at
        FROM sync_logs 
        WHERE brand_id = $1
        ORDER BY completed_at DESC 
        LIMIT 5
    """
    cursor = db.execute_query(query, (brand_id,))
    results = cursor.fetchall()
    
    return {
        "brand_id": brand_id,
        "last_syncs": [
            {
                "data_type": row[0],
                "status": row[1],
                "records_count": row[2],
                "completed_at": row[3].isoformat() if row[3] else None
            }
            for row in results
        ]
    }

# ==================== DASHBOARD STATISTICS ====================
@app.get("/api/stats/summary")
async def get_summary_stats():
    """Get overall statistics"""
    # Total orders per brand (last 30 days)
    orders_query = """
        SELECT 
            brand_id,
            COUNT(*) as total_orders,
            SUM(total_price) as total_revenue,
            COUNT(DISTINCT channel) as channels
        FROM orders 
        WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY brand_id
    """
    orders_cursor = db.execute_query(orders_query)
    orders_stats = orders_cursor.fetchall()
    
    # Total products per brand
    products_query = """
        SELECT brand_id, COUNT(*) as total_products
        FROM products 
        GROUP BY brand_id
    """
    products_cursor = db.execute_query(products_query)
    products_stats = products_cursor.fetchall()
    
    # Sync success rate
    sync_query = """
        SELECT 
            brand_id,
            COUNT(*) as total_syncs,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
        FROM sync_logs 
        WHERE started_at >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY brand_id
    """
    sync_cursor = db.execute_query(sync_query)
    sync_stats = sync_cursor.fetchall()
    
    return {
        "period": "last_30_days",
        "orders": [{"brand_id": row[0], "total": row[1], "revenue": float(row[2]), "channels": row[3]} 
                   for row in orders_stats],
        "products": [{"brand_id": row[0], "total": row[1]} for row in products_stats],
        "sync_success_rate": [
            {
                "brand_id": row[0], 
                "rate": round((row[2] / row[1]) * 100, 2) if row[1] > 0 else 0
            } 
            for row in sync_stats
        ]
    }

@app.get("/api/stats/revenue")
async def get_revenue_stats(
    brand_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365)
):
    """Get revenue statistics"""
    query = """
        SELECT 
            DATE(order_date) as date,
            COALESCE(SUM(total_price), 0) as daily_revenue,
            COUNT(*) as daily_orders
        FROM orders 
        WHERE order_date >= CURRENT_DATE - $1::interval
        AND ($2::text IS NULL OR brand_id = $2)
        GROUP BY DATE(order_date)
        ORDER BY date DESC
    """
    cursor = db.execute_query(query, (f"{days} days", brand_id))
    results = cursor.fetchall()
    
    return {
        "brand_id": brand_id or "all",
        "days": days,
        "data": [
            {"date": row[0].isoformat(), "revenue": float(row[1]), "orders": row[2]}
            for row in results
        ]
    }

# ==================== DATA EXPORT ====================
@app.get("/api/export/orders")
async def export_orders(
    brand_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    format: str = Query("json", regex="^(json|csv|xlsx)$")
):
    """Export orders data"""
    query = """
        SELECT * FROM orders 
        WHERE ($1::text IS NULL OR brand_id = $1)
        AND ($2::date IS NULL OR order_date >= $2)
        AND ($3::date IS NULL OR order_date <= $3)
        ORDER BY order_date DESC
    """
    
    start = start_date if start_date else None
    end = end_date if end_date else None
    
    cursor = db.execute_query(query, (brand_id, start, end))
    results = cursor.fetchall()
    
    if not results:
        raise HTTPException(status_code=404, detail="No data found")
    
    # Get column names
    columns = [desc[0] for desc in cursor.description]
    data = [dict(zip(columns, row)) for row in results]
    
    if format == "json":
        return JSONResponse(content=data)
    
    elif format == "csv":
        df = pd.DataFrame(data)
        csv_file = f"exports/orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs("exports", exist_ok=True)
        df.to_csv(csv_file, index=False)
        return FileResponse(csv_file, media_type="text/csv", filename=os.path.basename(csv_file))
    
    elif format == "xlsx":
        df = pd.DataFrame(data)
        excel_file = f"exports/orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        os.makedirs("exports", exist_ok=True)
        df.to_excel(excel_file, index=False, engine='openpyxl')
        return FileResponse(excel_file, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                          filename=os.path.basename(excel_file))

@app.get("/api/export/products")
async def export_products(
    brand_id: Optional[str] = Query(None),
    format: str = Query("json", regex="^(json|csv|xlsx)$")
):
    """Export products data"""
    query = """
        SELECT brand_id, sku, product_name, price, stock, category, last_sync
        FROM products 
        WHERE ($1::text IS NULL OR brand_id = $1)
        ORDER BY sku
    """
    cursor = db.execute_query(query, (brand_id,))
    results = cursor.fetchall()
    
    if not results:
        raise HTTPException(status_code=404, detail="No data found")
    
    columns = [desc[0] for desc in cursor.description]
    data = [dict(zip(columns, row)) for row in results]
    
    if format == "json":
        return JSONResponse(content=data)
    
    elif format == "csv":
        df = pd.DataFrame(data)
        csv_file = f"exports/products_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs("exports", exist_ok=True)
        df.to_csv(csv_file, index=False)
        return FileResponse(csv_file, media_type="text/csv", filename=os.path.basename(csv_file))
    
    elif format == "xlsx":
        df = pd.DataFrame(data)
        excel_file = f"exports/products_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        os.makedirs("exports", exist_ok=True)
        df.to_excel(excel_file, index=False, engine='openpyxl')
        return FileResponse(excel_file, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          filename=os.path.basename(excel_file))

# ==================== BRAND MANAGEMENT ====================
@app.get("/api/brands")
async def get_brands():
    """Get all brands"""
    query = "SELECT * FROM brands WHERE is_active = true"
    cursor = db.execute_query(query)
    results = cursor.fetchall()
    
    columns = [desc[0] for desc in cursor.description]
    brands = [dict(zip(columns, row)) for row in results]
    
    return {"brands": brands}

@app.post("/api/sync/trigger/{brand_id}")
async def trigger_sync(brand_id: str):
    """Manually trigger sync for a brand"""
    from main import process_brand_by_id
    
    # Run sync in background
    import threading
    thread = threading.Thread(target=process_brand_by_id, args=(brand_id,))
    thread.start()
    
    return {
        "message": f"Sync triggered for brand {brand_id}",
        "status": "processing"
    }

# ==================== WEBHOOK RECEIVER ====================
@app.post("/webhook/jubelio")
async def jubelio_webhook(payload: dict):
    """Receive webhook from Jubelio"""
    logger.info(f"Received webhook from Jubelio: {payload}")
    
    event_type = payload.get("event_type")
    brand_id = payload.get("brand_id")
    data = payload.get("data", {})
    
    if event_type == "order.created":
        # Process new order
        from jubelio_client import JubelioClient
        from config import BRANDS
        
        if brand_id in BRANDS:
            client = JubelioClient(BRANDS[brand_id])
            order_id = data.get("order_id")
            order = await client.get_order_detail(order_id)
            # Save to database
            # ...
    
    elif event_type == "stock.updated":
        # Update stock
        pass
    
    return {"status": "received", "timestamp": datetime.now().isoformat()}

# ==================== ALERTS ====================
@app.get("/api/alerts/recent")
async def get_recent_alerts(limit: int = Query(50, ge=1, le=500)):
    """Get recent alerts from logs"""
    query = """
        SELECT * FROM sync_logs 
        WHERE status = 'failed'
        ORDER BY started_at DESC 
        LIMIT $1
    """
    cursor = db.execute_query(query, (limit,))
    results = cursor.fetchall()
    
    columns = ['id', 'brand_id', 'data_type', 'status', 'error_message', 'started_at']
    alerts = [dict(zip(columns, row)) for row in results]
    
    return {"alerts": alerts}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### `requirements_api.txt` (Python)

```txt
fastapi==0.104.1
uvicorn==0.24.0
pandas==2.1.3
openpyxl==3.1.2
python-multipart==0.0.6
```

---

## B. Node.js Express Version

### `api_monitoring.js` (Node.js Express)

```javascript
// api_monitoring.js
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const path = require('path');
const fs = require('fs');
const Database = require('./database');
const { processBrandById } = require('./index');
const ExcelJS = require('exceljs');

const app = express();
const db = new Database();

app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// ==================== HEALTH CHECK ====================
app.get('/api/health', async (req, res) => {
    try {
        await db.query('SELECT 1');
        res.json({
            status: 'running',
            timestamp: new Date().toISOString(),
            database: 'healthy',
            version: '1.0.0'
        });
    } catch (error) {
        res.json({
            status: 'running',
            timestamp: new Date().toISOString(),
            database: 'unhealthy',
            version: '1.0.0'
        });
    }
});

// ==================== SYNC STATUS ====================
app.get('/api/sync/status', async (req, res) => {
    const { brand_id, limit = 100 } = req.query;
    
    const query = `
        SELECT * FROM sync_logs 
        WHERE ($1::text IS NULL OR brand_id = $1)
        ORDER BY started_at DESC 
        LIMIT $2
    `;
    
    const result = await db.query(query, [brand_id || null, parseInt(limit)]);
    
    res.json({
        total: result.rows.length,
        logs: result.rows,
        filters: { brand_id: brand_id || null, limit: parseInt(limit) }
    });
});

app.get('/api/sync/last/:brand_id', async (req, res) => {
    const { brand_id } = req.params;
    
    const query = `
        SELECT data_type, status, records_count, completed_at
        FROM sync_logs 
        WHERE brand_id = $1
        ORDER BY completed_at DESC 
        LIMIT 5
    `;
    
    const result = await db.query(query, [brand_id]);
    
    res.json({
        brand_id: brand_id,
        last_syncs: result.rows
    });
});

// ==================== DASHBOARD STATISTICS ====================
app.get('/api/stats/summary', async (req, res) => {
    // Orders stats
    const ordersQuery = `
        SELECT 
            brand_id,
            COUNT(*) as total_orders,
            SUM(total_price) as total_revenue,
            COUNT(DISTINCT channel) as channels
        FROM orders 
        WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY brand_id
    `;
    const ordersResult = await db.query(ordersQuery);
    
    // Products stats
    const productsQuery = `
        SELECT brand_id, COUNT(*) as total_products
        FROM products 
        GROUP BY brand_id
    `;
    const productsResult = await db.query(productsQuery);
    
    // Sync success rate
    const syncQuery = `
        SELECT 
            brand_id,
            COUNT(*) as total_syncs,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
        FROM sync_logs 
        WHERE started_at >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY brand_id
    `;
    const syncResult = await db.query(syncQuery);
    
    res.json({
        period: 'last_30_days',
        orders: ordersResult.rows,
        products: productsResult.rows,
        sync_success_rate: syncResult.rows.map(row => ({
            brand_id: row.brand_id,
            rate: row.total_syncs > 0 ? (row.success_count / row.total_syncs) * 100 : 0
        }))
    });
});

app.get('/api/stats/revenue', async (req, res) => {
    const { brand_id, days = 30 } = req.query;
    
    const query = `
        SELECT 
            DATE(order_date) as date,
            COALESCE(SUM(total_price), 0) as daily_revenue,
            COUNT(*) as daily_orders
        FROM orders 
        WHERE order_date >= CURRENT_DATE - $1::interval
        AND ($2::text IS NULL OR brand_id = $2)
        GROUP BY DATE(order_date)
        ORDER BY date DESC
    `;
    
    const result = await db.query(query, [`${days} days`, brand_id || null]);
    
    res.json({
        brand_id: brand_id || 'all',
        days: parseInt(days),
        data: result.rows
    });
});

// ==================== DATA EXPORT ====================
app.get('/api/export/orders', async (req, res) => {
    const { brand_id, start_date, end_date, format = 'json' } = req.query;
    
    let query = `
        SELECT * FROM orders 
        WHERE ($1::text IS NULL OR brand_id = $1)
        AND ($2::date IS NULL OR order_date >= $2)
        AND ($3::date IS NULL OR order_date <= $3)
        ORDER BY order_date DESC
    `;
    
    const result = await db.query(query, [brand_id || null, start_date || null, end_date || null]);
    
    if (result.rows.length === 0) {
        return res.status(404).json({ error: 'No data found' });
    }
    
    if (format === 'json') {
        return res.json(result.rows);
    }
    
    if (format === 'csv') {
        const headers = Object.keys(result.rows[0]);
        const csvRows = [
            headers.join(','),
            ...result.rows.map(row => headers.map(h => JSON.stringify(row[h] || '')).join(','))
        ];
        const csv = csvRows.join('\n');
        
        res.header('Content-Type', 'text/csv');
        res.attachment(`orders_export_${Date.now()}.csv`);
        return res.send(csv);
    }
    
    if (format === 'xlsx') {
        const workbook = new ExcelJS.Workbook();
        const worksheet = workbook.addWorksheet('Orders');
        
        // Add headers
        const headers = Object.keys(result.rows[0]);
        worksheet.addRow(headers);
        
        // Add data
        result.rows.forEach(row => {
            worksheet.addRow(headers.map(h => row[h]));
        });
        
        // Style headers
        worksheet.getRow(1).font = { bold: true };
        
        res.header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        res.attachment(`orders_export_${Date.now()}.xlsx`);
        
        await workbook.xlsx.write(res);
        res.end();
    }
});

app.get('/api/export/products', async (req, res) => {
    const { brand_id, format = 'json' } = req.query;
    
    const query = `
        SELECT brand_id, sku, product_name, price, stock, category, last_sync
        FROM products 
        WHERE ($1::text IS NULL OR brand_id = $1)
        ORDER BY sku
    `;
    
    const result = await db.query(query, [brand_id || null]);
    
    if (result.rows.length === 0) {
        return res.status(404).json({ error: 'No data found' });
    }
    
    if (format === 'json') {
        return res.json(result.rows);
    }
    
    if (format === 'csv') {
        const headers = Object.keys(result.rows[0]);
        const csvRows = [
            headers.join(','),
            ...result.rows.map(row => headers.map(h => JSON.stringify(row[h] || '')).join(','))
        ];
        const csv = csvRows.join('\n');
        
        res.header('Content-Type', 'text/csv');
        res.attachment(`products_export_${Date.now()}.csv`);
        return res.send(csv);
    }
    
    if (format === 'xlsx') {
        const workbook = new ExcelJS.Workbook();
        const worksheet = workbook.addWorksheet('Products');
        
        const headers = Object.keys(result.rows[0]);
        worksheet.addRow(headers);
        
        result.rows.forEach(row => {
            worksheet.addRow(headers.map(h => row[h]));
        });
        
        worksheet.getRow(1).font = { bold: true };
        
        res.header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        res.attachment(`products_export_${Date.now()}.xlsx`);
        
        await workbook.xlsx.write(res);
        res.end();
    }
});

// ==================== BRAND MANAGEMENT ====================
app.get('/api/brands', async (req, res) => {
    const query = "SELECT * FROM brands WHERE is_active = true";
    const result = await db.query(query);
    res.json({ brands: result.rows });
});

app.post('/api/sync/trigger/:brand_id', async (req, res) => {
    const { brand_id } = req.params;
    
    // Run async
    processBrandById(brand_id).catch(console.error);
    
    res.json({
        message: `Sync triggered for brand ${brand_id}`,
        status: 'processing'
    });
});

// ==================== WEBHOOK RECEIVER ====================
app.post('/webhook/jubelio', async (req, res) => {
    const payload = req.body;
    console.log('Received webhook from Jubelio:', payload);
    
    const { event_type, brand_id, data } = payload;
    
    // Process webhook asynchronously
    if (event_type === 'order.created') {
        // Handle new order
        console.log(`New order for brand ${brand_id}:`, data);
    } else if (event_type === 'stock.updated') {
        console.log(`Stock updated for brand ${brand_id}:`, data);
    }
    
    res.json({ status: 'received', timestamp: new Date().toISOString() });
});

// ==================== ALERTS ====================
app.get('/api/alerts/recent', async (req, res) => {
    const { limit = 50 } = req.query;
    
    const query = `
        SELECT id, brand_id, data_type, status, error_message, started_at
        FROM sync_logs 
        WHERE status = 'failed'
        ORDER BY started_at DESC 
        LIMIT $1
    `;
    
    const result = await db.query(query, [parseInt(limit)]);
    res.json({ alerts: result.rows });
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`API Monitoring server running on port ${PORT}`);
});

module.exports = app;