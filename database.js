// database.js
const { Pool } = require('pg');
const { dbConfig } = require('./config');

class Database {
  constructor() {
    this.pool = new Pool(dbConfig);
  }

  async query(sql, params) {
    const client = await this.pool.connect();
    try {
      const result = await client.query(sql, params);
      return result;
    } finally {
      client.release();
    }
  }

  async insertOrders(orders) {
    const query = `
      INSERT INTO orders 
      (brand_id, jubelio_order_id, order_number, total_price, status, 
       channel, customer_name, customer_phone, order_date, raw_data)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
      ON CONFLICT (jubelio_order_id) DO UPDATE SET
        status = EXCLUDED.status,
        total_price = EXCLUDED.total_price,
        updated_at = CURRENT_TIMESTAMP
    `;

    for (const order of orders) {
      await this.query(query, [
        order.brand_id,
        order.jubelio_order_id,
        order.order_number,
        order.total_price,
        order.status,
        order.channel,
        order.customer_name,
        order.customer_phone,
        order.order_date,
        order.raw_data
      ]);
    }
    console.log(`Inserted/Updated ${orders.length} orders`);
  }

  async insertProducts(products) {
    const query = `
      INSERT INTO products 
      (brand_id, sku, product_name, price, stock, category, last_sync, raw_data)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
      ON CONFLICT (sku) DO UPDATE SET
        product_name = EXCLUDED.product_name,
        price = EXCLUDED.price,
        stock = EXCLUDED.stock,
        last_sync = EXCLUDED.last_sync,
        raw_data = EXCLUDED.raw_data
    `;

    for (const product of products) {
      await this.query(query, [
        product.brand_id,
        product.sku,
        product.product_name,
        product.price,
        product.stock,
        product.category,
        new Date(),
        product.raw_data
      ]);
    }
    console.log(`Inserted/Updated ${products.length} products`);
  }

  async insertStockHistory(stockData) {
    const query = `
      INSERT INTO stock_history 
      (brand_id, sku, quantity, warehouse, recorded_at, raw_data)
      VALUES ($1, $2, $3, $4, $5, $6)
    `;

    for (const stock of stockData) {
      await this.query(query, [
        stock.brand_id,
        stock.sku,
        stock.quantity,
        stock.warehouse,
        new Date(),
        stock.raw_data
      ]);
    }
    console.log(`Inserted ${stockData.length} stock records`);
  }

  async saveToken(brandId, accessToken, refreshToken, expiresAt) {
    const query = `
      INSERT INTO tokens (brand_id, access_token, refresh_token, expires_at, updated_at)
      VALUES ($1, $2, $3, $4, $5)
      ON CONFLICT (brand_id) DO UPDATE SET
        access_token = EXCLUDED.access_token,
        refresh_token = EXCLUDED.refresh_token,
        expires_at = EXCLUDED.expires_at,
        updated_at = CURRENT_TIMESTAMP
    `;
    await this.query(query, [brandId, accessToken, refreshToken, expiresAt, new Date()]);
  }

  async getToken(brandId) {
    const result = await this.query(
      'SELECT access_token, refresh_token, expires_at FROM tokens WHERE brand_id = $1',
      [brandId]
    );
    return result.rows[0] || null;
  }

  async logSync(brandId, dataType, status, recordsCount = 0, errorMessage = null) {
    const query = `
      INSERT INTO sync_logs 
      (brand_id, data_type, status, records_count, error_message, started_at, completed_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
    `;
    await this.query(query, [
      brandId, dataType, status, recordsCount, errorMessage,
      new Date(), new Date()
    ]);
  }

  async close() {
    await this.pool.end();
  }
}

module.exports = Database;