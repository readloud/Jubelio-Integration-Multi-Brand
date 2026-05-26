# scheduler.py
import schedule
import time
import threading
from datetime import datetime
from main import process_all_brands, process_brand_by_id
from logger import logger
from alerting import alert_manager

class Scheduler:
    """Job scheduler untuk otomatisasi sync"""
    
    def __init__(self):
        self.jobs = []
        self.running = False
    
    def schedule_sync_all_brands(self, interval_minutes: int = 30):
        """Schedule sync untuk semua brand"""
        job = schedule.every(interval_minutes).minutes.do(self.run_sync_all)
        self.jobs.append(job)
        logger.info(f"Scheduled sync all brands every {interval_minutes} minutes")
    
    def schedule_sync_brand(self, brand_id: str, interval_minutes: int = 60):
        """Schedule sync untuk brand tertentu"""
        job = schedule.every(interval_minutes).minutes.do(
            self.run_sync_brand, brand_id=brand_id
        )
        self.jobs.append(job)
        logger.info(f"Scheduled sync for {brand_id} every {interval_minutes} minutes")
    
    def schedule_daily_report(self, hour: int = 8, minute: int = 0):
        """Schedule daily report"""
        job = schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(self.run_daily_report)
        self.jobs.append(job)
        logger.info(f"Scheduled daily report at {hour:02d}:{minute:02d}")
    
    def run_sync_all(self):
        """Run sync untuk semua brand"""
        logger.info("Starting scheduled sync for all brands")
        try:
            results = process_all_brands()
            
            # Send summary alert
            success_count = sum(1 for r in results if r['status'] == 'success')
            fail_count = len(results) - success_count
            
            alert_manager.send_slack(
                f"📊 *Scheduled Sync Complete*\n"
                f"Total Brands: {len(results)}\n"
                f"✅ Success: {success_count}\n"
                f"❌ Failed: {fail_count}\n"
                f"Time: {datetime.now()}"
            )
        except Exception as e:
            logger.error(f"Scheduled sync failed: {e}", exc_info=True)
            alert_manager.alert_sync_failure("ALL", "scheduled_sync", str(e))
    
    def run_sync_brand(self, brand_id: str):
        """Run sync untuk brand tertentu"""
        logger.info(f"Starting scheduled sync for brand {brand_id}")
        try:
            result = process_brand_by_id(brand_id)
            if result['status'] == 'success':
                logger.info(f"Sync success for {brand_id}")
            else:
                alert_manager.alert_sync_failure(brand_id, "scheduled_sync", result.get('error', 'Unknown'))
        except Exception as e:
            logger.error(f"Sync failed for {brand_id}: {e}", exc_info=True)
            alert_manager.alert_sync_failure(brand_id, "scheduled_sync", str(e))
    
    def run_daily_report(self):
        """Generate and send daily report"""
        logger.info("Generating daily report")
        # Implement report generation
        from database import Database
        db = Database()
        
        # Get summary from database
        query = """
            SELECT 
                brand_id,
                COUNT(DISTINCT jubelio_order_id) as total_orders,
                SUM(total_price) as total_revenue
            FROM orders 
            WHERE order_date >= CURRENT_DATE - INTERVAL '1 day'
            GROUP BY brand_id
        """
        
        cursor = db.execute_query(query)
        results = cursor.fetchall()
        
        # Format report
        report = "📈 *Daily Report - Jubelio Integration*\n\n"
        for row in results:
            report += f"*{row[0]}*: {row[1]} orders, Rp {row[2]:,.0f}\n"
        
        alert_manager.send_slack(report)
        
        # Also send email
        alert_manager.send_email(
            f"Jubelio Daily Report - {datetime.now().strftime('%Y-%m-%d')}",
            report.replace('*', ''),
            is_html=False
        )
    
    def run_continuously(self):
        """Run scheduler continuously"""
        self.running = True
        logger.info("Scheduler started")
        
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def stop(self):
        """Stop scheduler"""
        self.running = False
        logger.info("Scheduler stopped")

# Contoh penggunaan
if __name__ == "__main__":
    scheduler = Scheduler()
    
    # Schedule jobs
    scheduler.schedule_sync_all_brands(interval_minutes=30)
    scheduler.schedule_daily_report(hour=8, minute=0)
    
    # Run scheduler
    scheduler.run_continuously()