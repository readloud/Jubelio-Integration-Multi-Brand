// alerting.js
const nodemailer = require('nodemailer');
const { IncomingWebhook } = require('@slack/webhook');

class AlertManager {
  constructor() {
    this.slackWebhook = process.env.SLACK_WEBHOOK_URL ? 
      new IncomingWebhook(process.env.SLACK_WEBHOOK_URL) : null;
    
    this.emailTransporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST,
      port: parseInt(process.env.SMTP_PORT),
      secure: false,
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASSWORD
      }
    });
    
    this.alertEmail = process.env.ALERT_EMAIL;
  }

  async sendSlack(message, color = 'good') {
    if (!this.slackWebhook) {
      console.log('Slack webhook not configured');
      return;
    }

    try {
      await this.slackWebhook.send({
        attachments: [{
          color: color,
          text: message,
          footer: 'Jubelio Integration',
          ts: Math.floor(Date.now() / 1000)
        }]
      });
      console.log('Slack alert sent');
    } catch (error) {
      console.error('Failed to send Slack alert:', error.message);
    }
  }

  async sendEmail(subject, body) {
    if (!this.emailTransporter || !this.alertEmail) {
      console.log('Email not configured');
      return;
    }

    try {
      await this.emailTransporter.sendMail({
        from: process.env.SMTP_USER,
        to: this.alertEmail,
        subject: subject,
        text: body
      });
      console.log('Email alert sent');
    } catch (error) {
      console.error('Failed to send email:', error.message);
    }
  }

  async alertSyncSuccess(brandId, dataType, records) {
    const message = `✅ *Sync Success*\nBrand: ${brandId}\nType: ${dataType}\nRecords: ${records}`;
    await this.sendSlack(message, 'good');
  }

  async alertSyncFailure(brandId, dataType, error) {
    const message = `❌ *Sync Failed*\nBrand: ${brandId}\nType: ${dataType}\nError: ${error}`;
    await this.sendSlack(message, 'danger');
    await this.sendEmail(
      `[URGENT] Jubelio Sync Failed: ${brandId} - ${dataType}`,
      `Error: ${error}\nTime: ${new Date()}`
    );
  }
}

module.exports = AlertManager;