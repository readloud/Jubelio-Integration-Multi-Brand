# alerting.py
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import List, Dict
from datetime import datetime
from logger import logger

class AlertManager:
    """Send alerts via Email and Slack"""
    
    def __init__(self):
        self.smtp_config = {
            'host': os.getenv('SMTP_HOST'),
            'port': int(os.getenv('SMTP_PORT', 587)),
            'user': os.getenv('SMTP_USER'),
            'password': os.getenv('SMTP_PASSWORD')
        }
        self.alert_email = os.getenv('ALERT_EMAIL')
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
    
    def send_email(self, subject: str, body: str, is_html: bool = False):
        """Send email alert"""
        if not all(self.smtp_config.values()) or not self.alert_email:
            logger.warning("Email config incomplete, skipping email alert")
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['user']
            msg['To'] = self.alert_email
            msg['Subject'] = subject
            
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port'])
            server.starttls()
            server.login(self.smtp_config['user'], self.smtp_config['password'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email alert sent: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    def send_slack(self, message: str, color: str = "good"):
        """Send Slack alert"""
        if not self.slack_webhook:
            logger.warning("Slack webhook not configured")
            return
        
        try:
            payload = {
                "attachments": [{
                    "color": color,
                    "text": message,
                    "footer": "Jubelio Integration",
                    "ts": int(datetime.now().timestamp())
                }]
            }
            response = requests.post(self.slack_webhook, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Slack alert sent")
            else:
                logger.warning(f"Slack alert failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    def alert_sync_success(self, brand_id: str, data_type: str, records: int):
        """Alert when sync successful"""
        message = f"✅ *Sync Success*\nBrand: {brand_id}\nType: {data_type}\nRecords: {records}"
        self.send_slack(message, "good")
        
        # Email untuk ringkasan harian (bisa di-cron terpisah)
        if records > 1000:
            self.send_email(
                f"[Jubelio] Large sync: {brand_id} - {data_type}",
                f"Synced {records} records for {brand_id}/{data_type}"
            )
    
    def alert_sync_failure(self, brand_id: str, data_type: str, error: str):
        """Alert when sync fails"""
        message = f"❌ *Sync Failed*\nBrand: {brand_id}\nType: {data_type}\nError: {error}"
        self.send_slack(message, "danger")
        
        # Always send email on failure
        self.send_email(
            f"[URGENT] Jubelio Sync Failed: {brand_id} - {data_type}",
            f"Error: {error}\nTime: {datetime.now()}"
        )
    
    def alert_token_expired(self, brand_id: str):
        """Alert when token cannot be refreshed"""
        message = f"⚠️ *Token Issue*\nBrand: {brand_id}\nCannot refresh token, need manual intervention"
        self.send_slack(message, "warning")
        self.send_email(
            f"[CRITICAL] Token expired for {brand_id}",
            f"Token refresh failed for brand {brand_id}. Please check credentials."
        )

alert_manager = AlertManager()