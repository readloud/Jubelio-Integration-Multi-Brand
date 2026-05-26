# main.py
import sys
import argparse
from typing import Dict, List
from config import BRANDS
from jubelio_client import JubelioClient
from data_classifier import DataClassifier
from database import Database
from logger import logger
from alerting import alert_manager
from datetime import datetime

def process_brand_data(brand_id: str, brand_config, data_types: List[str] = None):
    """
    Process single brand data
    
    Args:
        brand_id: Brand identifier
        brand_config: Brand configuration
        data_types: List of data types to sync ('orders', 'products', 'stock', 'transactions')
    """
    if data_types is None:
        data_types = ['orders', 'products', 'stock', 'transactions']
    
    results = {}
    db = Database()
    
    # Initialize client and classifier
    client = JubelioClient(brand_config)
    classifier = DataClassifier(brand_id, brand_config.brand_name)
    
    for data_type in data_types:
        start_time = datetime.now()
        logger.info(f"Syncing {data_type} for {brand_config.brand_name}", brand_id)
        
        try:
            if data_type == 'orders':
                data = client.get_orders()
                if data:
                    classified = classifier.classify_orders(data)
                    db.insert_orders(classified)
                    results['orders'] = len(classified)
                    db.log_sync(brand_id, data_type, 'success', len(classified))
                    alert_manager.alert_sync_success(brand_id, data_type, len(classified))
            
            elif data_type == 'products':
                data = client.get_products()
                if data:
                    classified = classifier.classify_products(data)
                    db.insert_products(classified)
                    results['products'] = len(classified)
                    db.log_sync(brand_id, data_type, 'success', len(classified))
                    alert_manager.alert_sync_success(brand_id, data_type, len(classified))
            
            elif data_type == 'stock':
                data = client.get_stock()
                if data:
                    classified = classifier.classify_stock(data)
                    db.insert_stock_history(classified)
                    results['stock'] = len(classified)
                    db.log_sync(brand_id, data_type, 'success', len(classified))
            
            elif data_type == 'transactions':
                data = client.get_transactions()
                if data:
                    classified = classifier.classify_transactions(data)
                    db.insert_transactions(classified)
                    results['transactions'] = len(classified)
                    db.log_sync(brand_id, data_type, 'success', len(classified))
            
            else:
                logger.warning(f"Unknown data type: {data_type}", brand_id)
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"Synced {data_type} in {elapsed:.2f} seconds", brand_id)
            
        except Exception as e:
            error_msg = f"Failed to sync {data_type}: {str(e)}"
            logger.error(error_msg, brand_id, exc_info=True)
            db.log_sync(brand_id, data_type, 'failed', 0, error_msg)
            alert_manager.alert_sync_failure(brand_id, data_type, str(e))
            results[data_type] = 'failed'
    
    db.close()
    return results

def process_all_brands(data_types: List[str] = None) -> List[Dict]:
    """Process all brands"""
    results = []
    
    for brand_id, brand_config in BRANDS.items():
        logger.info(f"Processing brand: {brand_config.brand_name}", brand_id)
        try:
            result = process_brand_data(brand_id, brand_config, data_types)
            results.append({
                'brand_id': brand_id,
                'status': 'success',
                'data': result
            })
        except Exception as e:
            logger.error(f"Failed to process {brand_id}: {e}", exc_info=True)
            results.append({
                'brand_id': brand_id,
                'status': 'failed',
                'error': str(e)
            })
            alert_manager.alert_sync_failure(brand_id, 'full_sync', str(e))
    
    return results

def process_brand_by_id(brand_id: str, data_types: List[str] = None) -> Dict:
    """Process specific brand by ID"""
    if brand_id not in BRANDS:
        error_msg = f"Brand {brand_id} not found"
        logger.error(error_msg)
        return {'status': 'failed', 'error': error_msg}
    
    try:
        result = process_brand_data(brand_id, BRANDS[brand_id], data_types)
        return {
            'brand_id': brand_id,
            'status': 'success',
            'data': result
        }
    except Exception as e:
        logger.error(f"Failed to process {brand_id}: {e}", exc_info=True)
        return {
            'brand_id': brand_id,
            'status': 'failed',
            'error': str(e)
        }

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Jubelio Integration CLI')
    parser.add_argument('--brand', type=str, help='Specific brand ID to sync')
    parser.add_argument('--types', nargs='+', 
                       choices=['orders', 'products', 'stock', 'transactions'],
                       help='Data types to sync')
    parser.add_argument('--schedule', action='store_true', help='Run scheduler')
    
    args = parser.parse_args()
    
    logger.info("Starting Jubelio Integration")
    
    if args.schedule:
        from scheduler import Scheduler
        scheduler = Scheduler()
        scheduler.schedule_sync_all_brands(interval_minutes=30)
        scheduler.schedule_daily_report(hour=8, minute=0)
        scheduler.run_continuously()
    
    elif args.brand:
        result = process_brand_by_id(args.brand, args.types)
        logger.info(f"Result: {result}")
    
    else:
        results = process_all_brands(args.types)
        logger.info(f"Completed: {results}")

if __name__ == "__main__":
    main()