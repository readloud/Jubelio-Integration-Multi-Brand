// index.js
const { brands } = require('./config');
const JubelioClient = require('./jubelioClient');
const Database = require('./database');
const AlertManager = require('./alerting');

class DataClassifier {
  constructor(brandId, brandName) {
    this.brandId = brandId;
    this.brandName = brandName;
  }

  classifyOrders(orders) {
    return orders.map(order => ({
      brand_id: this.brandId,
      brand_name: this.brandName,
      jubelio_order_id: order.id,
      order_number: order.order_number,
      total_price: parseFloat(order.total_price || 0),
      status: order.status,
      channel: order.channel_name,
      customer_name: order.customer_name,
      customer_phone: order.customer_phone,
      order_date: order.created_at,
      raw_data: order
    }));
  }

  classifyProducts(products) {
    return products.map(product => ({
      brand_id: this.brandId,
      brand_name: this.brandName,
      sku: product.sku,
      product_name: product.name,
      price: parseFloat(product.price || 0),
      stock: product.stock || 0,
      category: product.category,
      raw_data: product
    }));
  }

  classifyStock(stockData) {
    return stockData.map(stock => ({
      brand_id: this.brandId,
      brand_name: this.brandName,
      sku: stock.sku,
      quantity: parseInt(stock.quantity || 0),
      warehouse: stock.warehouse,
      raw_data: stock
    }));
  }
}

async function processBrandData(brandId, brandConfig, dataTypes = ['orders', 'products', 'stock']) {
  const db = new Database();
  const client = new JubelioClient(brandConfig);
  const classifier = new DataClassifier(brandId, brandConfig.brand_name);
  const alertManager = new AlertManager();
  
  const results = {};
  
  for (const dataType of dataTypes) {
    console.log(`Syncing ${dataType} for ${brandConfig.brand_name}`);
    
    try {
      if (dataType === 'orders') {
        const data = await client.getOrders();
        if (data) {
          const classified = classifier.classifyOrders(data);
          await db.insertOrders(classified);
          results.orders = classified.length;
          await db.logSync(brandId, dataType, 'success', classified.length);
          await alertManager.alertSyncSuccess(brandId, dataType, classified.length);
        }
      } else if (dataType === 'products') {
        const data = await client.getProducts();
        if (data) {
          const classified = classifier.classifyProducts(data);
          await db.insertProducts(classified);
          results.products = classified.length;
          await db.logSync(brandId, dataType, 'success', classified.length);
        }
      } else if (dataType === 'stock') {
        const data = await client.getStock();
        if (data) {
          const classified = classifier.classifyStock(data);
          await db.insertStockHistory(classified);
          results.stock = classified.length;
          await db.logSync(brandId, dataType, 'success', classified.length);
        }
      }
    } catch (error) {
      console.error(`Failed to sync ${dataType}:`, error);
      await db.logSync(brandId, dataType, 'failed', 0, error.message);
      await alertManager.alertSyncFailure(brandId, dataType, error.message);
      results[dataType] = 'failed';
    }
  }
  
  await db.close();
  return results;
}

async function processAllBrands() {
  const results = [];
  
  for (const [brandId, brandConfig] of Object.entries(brands)) {
    console.log(`Processing brand: ${brandConfig.brand_name}`);
    try {
      const result = await processBrandData(brandId, brandConfig);
      results.push({ brand_id: brandId, status: 'success', data: result });
    } catch (error) {
      console.error(`Failed to process ${brandId}:`, error);
      results.push({ brand_id: brandId, status: 'failed', error: error.message });
    }
  }
  
  return results;
}

async function processBrandById(brandId) {
  if (!brands[brandId]) {
    return { status: 'failed', error: `Brand ${brandId} not found` };
  }
  
  try {
    const result = await processBrandData(brandId, brands[brandId]);
    return { brand_id: brandId, status: 'success', data: result };
  } catch (error) {
    return { brand_id: brandId, status: 'failed', error: error.message };
  }
}

// CLI handler
if (require.main === module) {
  const args = process.argv.slice(2);
  
  if (args.includes('--sync-all')) {
    processAllBrands().then(results => {
      console.log('Sync completed:', results);
      process.exit(0);
    }).catch(error => {
      console.error('Sync failed:', error);
      process.exit(1);
    });
  } else if (args.includes('--brand')) {
    const brandIndex = args.indexOf('--brand');
    const brandId = args[brandIndex + 1];
    if (brandId) {
      processBrandById(brandId).then(result => {
        console.log('Sync completed:', result);
        process.exit(0);
      }).catch(error => {
        console.error('Sync failed:', error);
        process.exit(1);
      });
    }
  } else {
    console.log('Usage: node index.js --sync-all');
    console.log('       node index.js --brand <brand_id>');
  }
}

module.exports = { processAllBrands, processBrandById, processBrandData };