# Jubelio Integration - Multi-Brand System

## Complete Integration Solution for Jubelio API

- ✅ Multi-brand data classification
- ✅ Automatic token management with refresh
- ✅ PostgreSQL database for persistent storage
- ✅ Email & Slack alerting
- ✅ Job scheduler for automated sync
- ✅ Python & Node.js implementations
- ✅ Docker support
- ✅ Complete logging system

### Quick Start Setup

```bash
# 1. Clone repository
git clone https://github.com/readloud/jubelio-integration
cd jubelio-integration

# 2. Setup environment variables
cp .env.example .env
# Edit .env with your credentials
```

#### Using Docker

```bash
docker-compose up -d
```
or
```bash
docker-compose -f docker-compose-full.yml up -d
```

#### Python
```bash
cd python
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python main.py --sync-all
```

#### Node.js
```bash
npm install
cp .env.example .env
# Edit .env with your credentials
node index.js --sync-all
```

#### Access:

- [] Dashboard: http://localhost

- [] API: http://localhost/api

- [] Webhook: http://localhost/webhook/jubelio

## Testing Webhook:

```bash
# Test webhook locally
curl -X POST http://localhost:3001/webhook/jubelio \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "order.created",
    "brand_id": "brand_a",
    "data": {
      "order_id": "TEST001",
      "order_number": "ORD-2025-001",
      "total_price": 500000,
      "status": "pending",
      "customer_name": "Test Customer"
    }
  }'
```

---

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DB_HOST` | PostgreSQL host |
| `DB_NAME` | Database name |
| `SMTP_HOST` | Email SMTP server |
| `SLACK_WEBHOOK_URL` | Slack webhook URL |
| `LOG_LEVEL` | Logging level (INFO/DEBUG/ERROR) |

### Monitoring

- Logs: `logs/jubelio_integration.log`
- Database: Check `sync_logs` table
- Alerts: Slack #alerts channel & email

### Troubleshooting

1. **Token expired**: System auto-refreshes, check credentials
2. **Database connection**: Verify PostgreSQL is running
3. **Rate limiting**: Implemented exponential backoff

---

# Feature

SLA Monitoring	
- Timeout alerts	
- Performance tracking	
- Trend analysis	
- Daily summaries	
- Dashboard API	
Enhanced Retry	
- Exponential backoff	
- Fibonacci backoff	
- Random jitter	
- Circuit breaker	
- Failure tracking	
- Retry callbacks	
Integration	
- Decorator support	
- Async support	
- SLA monitoring wrapper	
