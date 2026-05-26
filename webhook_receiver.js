// webhook_receiver.js
const express = require('express');
const crypto = require('crypto');
const Database = require('./database');
const { processBrandById } = require('./index');

const app = express();
const db = new Database();
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || 'your_webhook_secret';

app.use(express.json());

// Verify signature
function verifySignature(payload, signature) {
    const expected = crypto
        .createHmac('sha256', WEBHOOK_SECRET)
        .update(JSON.stringify(payload))
        .digest('hex');
    
    return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
}

// Webhook endpoint
app.post('/webhook/jubelio', async (req, res) => {
    const signature = req.headers['x-signature'];
    const payload = req.body;
    
    // Verify signature
    // if (!verifySignature(payload, signature)) {
    //     return res.status(401).json({ error: 'Invalid signature' });
    // }
    
    const { event_type, brand_id, data } = payload;
    
    console.log(`Received webhook: ${event_type} for brand ${brand_id}`);
    
    // Process asynchronously
    setImmediate(() => processWebhook(event_type, brand_id, data));
    
    res.json({ 
        status: 'received', 
        event_type, 
        timestamp: new Date().toISOString() 
    });
});

async function processWebhook(eventType, brandId, data) {
    try {
        // Log webhook
        await db.query(
            `INSERT INTO webhook_logs (event_type, brand_id, payload, created_at)
             VALUES ($1, $2, $3, $4)`,
            [eventType, brandId, data, new Date()]
        );
        
        switch (eventType) {
            case 'order.created':
                await handleOrderCreated(brandId, data);
                break;
            case 'order.updated':
                await handleOrderUpdated(brandId, data);
                break;
            case 'stock.updated':
                await handleStockUpdated(brandId, data);
                break;
            case 'product.created':
            case 'product.updated':
                await handleProductUpdated(brandId, data);
                break;
            default:
                console.log(`Unknown event type: ${eventType}`);
        }
        
        // Mark as processed
        await db.query(
            `UPDATE webhook_logs SET processed = true, processed_at = $1 
             WHERE event_type = $2 AND brand_id = $3 AND created_at = $4`,
            [new Date(), eventType, brandId, new Date()]
        );
        
    } catch (error) {
        console.error(`Error processing webhook:`, error);
    }
}

async function handleOrderCreated(brandId, data) {
    const query = `
        INSERT INTO orders (brand_id, jubelio_order_id, order_number, total_price, 
                            status, customer_name, customer_phone, order_date, raw_data)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (jubelio_order_id) DO NOTHING
    `;
    
    await db.query(query, [
        brandId,
        data.order_id,
        data.order_number,
        data.total_price,
        data.status,
        data.customer_name,
        data.customer_phone,
        data.created_at,
        data
    ]);
    
    console.log(`Order ${data.order_number} saved for brand ${brandId}`);
}

async function handleStockUpdated(brandId, data) {
    // Save to stock history
    await db.query(
        `INSERT INTO stock_history (brand_id, sku, quantity, warehouse, recorded_at, raw_data)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [brandId, data.sku, data.new_quantity, data.warehouse, new Date(), data]
    );
    
    // Update products table
    await db.query(
        `UPDATE products SET stock = $1, last_sync = CURRENT_TIMESTAMP
         WHERE brand_id = $2 AND sku = $3`,
        [data.new_quantity, brandId, data.sku]
    );
}

async function handleProductUpdated(brandId, data) {
    const query = `
        INSERT INTO products (brand_id, sku, product_name, price, stock, category, last_sync, raw_data)
        VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP, $7)
        ON CONFLICT (sku) DO UPDATE SET
            product_name = EXCLUDED.product_name,
            price = EXCLUDED.price,
            stock = EXCLUDED.stock,
            category = EXCLUDED.category,
            last_sync = CURRENT_TIMESTAMP,
            raw_data = EXCLUDED.raw_data
    `;
    
    await db.query(query, [
        brandId, data.sku, data.product_name, data.price, 
        data.stock, data.category, data
    ]);
}

const PORT = process.env.WEBHOOK_PORT || 3001;
app.listen(PORT, () => {
    console.log(`Webhook receiver running on port ${PORT}`);
});

module.exports = app;