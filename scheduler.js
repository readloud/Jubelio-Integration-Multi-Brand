// scheduler.js
const schedule = require('node-schedule');
const { processAllBrands, processBrandById } = require('./index');
const { brands } = require('./config');
const AlertManager = require('./alerting');

class Scheduler {
  constructor() {
    this.alertManager = new AlertManager();
    this.jobs = [];
  }

  scheduleSyncAllBrands(intervalMinutes = 30) {
    const rule = `*/${intervalMinutes} * * * *`;
    const job = schedule.scheduleJob(rule, async () => {
      console.log(`Running scheduled sync for all brands at ${new Date()}`);
      const results = await processAllBrands();
      
      const successCount = results.filter(r => r.status === 'success').length;
      const failCount = results.length - successCount;
      
      await this.alertManager.sendSlack(
        `📊 *Scheduled Sync Complete*\n` +
        `Total Brands: ${results.length}\n` +
        `✅ Success: ${successCount}\n` +
        `❌ Failed: ${failCount}\n` +
        `Time: ${new Date()}`
      );
    });
    
    this.jobs.push(job);
    console.log(`Scheduled sync all brands every ${intervalMinutes} minutes`);
  }

  scheduleDailyReport(hour = 8, minute = 0) {
    const job = schedule.scheduleJob(`${minute} ${hour} * * *`, async () => {
      console.log(`Running daily report at ${new Date()}`);
      await this.generateDailyReport();
    });
    
    this.jobs.push(job);
    console.log(`Scheduled daily report at ${hour}:${minute}`);
  }

  async generateDailyReport() {
    const Database = require('./database');
    const db = new Database();
    
    const query = `
      SELECT 
        brand_id,
        COUNT(DISTINCT jubelio_order_id) as total_orders,
        SUM(total_price) as total_revenue
      FROM orders 
      WHERE order_date >= CURRENT_DATE - INTERVAL '1 day'
      GROUP BY brand_id
    `;
    
    const result = await db.query(query);
    await db.close();
    
    let report = "📈 *Daily Report - Jubelio Integration*\n\n";
    for (const row of result.rows) {
      report += `*${row.brand_id}*: ${row.total_orders} orders, Rp ${row.total_revenue.toLocaleString()}\n`;
    }
    
    await this.alertManager.sendSlack(report);
  }

  start() {
    console.log('Scheduler started');
  }
}

if (require.main === module) {
  const scheduler = new Scheduler();
  scheduler.scheduleSyncAllBrands(30);
  scheduler.scheduleDailyReport(8, 0);
  scheduler.start();
}

module.exports = Scheduler;