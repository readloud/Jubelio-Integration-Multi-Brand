# 1. Run complete stack
docker-compose -f docker-compose-full.yml up -d

# 2. Access endpoints:
# - Dashboard: http://localhost
# - SLA API: http://localhost/api/sla/metrics
# - Webhook: http://localhost/webhook/jubelio

# 3. Test retry mechanism
python -c "
from retry_handler import AdvancedRetryHandler, RetryConfig
import time

handler = AdvancedRetryHandler()

@handler.retry(config=RetryConfig(max_retries=3, base_delay=0.5))
def failing_function():
    print(f'Attempt at {time.time()}')
    raise Exception('Temporary failure')

try:
    failing_function()
except:
    print('All retries exhausted')
"

# 4. Monitor SLA compliance
curl http://localhost:8000/api/sla/dashboard?days=7