// retryHandler.js
const logger = require('./logger');
const alertManager = require('./alerting');

class RetryStrategy {
    static EXPONENTIAL = 'exponential';
    static LINEAR = 'linear';
    static FIBONACCI = 'fibonacci';
    static RANDOM = 'random';
}

class RetryConfig {
    constructor(options = {}) {
        this.maxRetries = options.maxRetries || 3;
        this.baseDelay = options.baseDelay || 1000; // milliseconds
        this.maxDelay = options.maxDelay || 60000;
        this.strategy = options.strategy || RetryStrategy.EXPONENTIAL;
        this.backoffMultiplier = options.backoffMultiplier || 2;
        this.jitter = options.jitter !== false;
        this.retryOnStatusCodes = options.retryOnStatusCodes || [408, 429, 500, 502, 503, 504];
        this.retryOnErrors = options.retryOnErrors || [
            'ECONNRESET', 'ETIMEDOUT', 'ECONNREFUSED', 'ENOTFOUND'
        ];
        this.maxTotalTime = options.maxTotalTime || 120000; // 2 minutes
    }
}

class RetryContext {
    constructor(operationName, config) {
        this.operationName = operationName;
        this.config = config;
        this.attempts = 0;
        this.startTime = Date.now();
        this.lastError = null;
        this.retryDelays = [];
    }
    
    shouldRetry(error, statusCode = null) {
        if (this.attempts >= this.config.maxRetries) return false;
        
        const elapsed = Date.now() - this.startTime;
        if (elapsed >= this.config.maxTotalTime) return false;
        
        if (error && error.code && this.config.retryOnErrors.includes(error.code)) {
            return true;
        }
        
        if (statusCode && this.config.retryOnStatusCodes.includes(statusCode)) {
            return true;
        }
        
        return false;
    }
    
    calculateNextDelay() {
        let delay;
        
        switch (this.config.strategy) {
            case RetryStrategy.EXPONENTIAL:
                delay = this.config.baseDelay * Math.pow(this.config.backoffMultiplier, this.attempts);
                break;
            case RetryStrategy.LINEAR:
                delay = this.config.baseDelay * (this.attempts + 1);
                break;
            case RetryStrategy.FIBONACCI:
                delay = this.config.baseDelay * this._fibonacci(this.attempts + 2);
                break;
            case RetryStrategy.RANDOM:
                delay = Math.random() * (this.config.maxDelay - this.config.baseDelay) + this.config.baseDelay;
                break;
            default:
                delay = this.config.baseDelay;
        }
        
        if (this.config.jitter) {
            const jitter = 0.8 + Math.random() * 0.4;
            delay = delay * jitter;
        }
        
        delay = Math.min(delay, this.config.maxDelay);
        this.retryDelays.push(delay);
        
        return delay;
    }
    
    _fibonacci(n) {
        if (n <= 1) return n;
        let a = 0, b = 1;
        for (let i = 2; i <= n; i++) {
            [a, b] = [b, a + b];
        }
        return b;
    }
}

class AdvancedRetryHandler {
    constructor() {
        this.circuitBreakers = new Map();
        this.failureCounts = new Map();
        this.lastFailureTime = new Map();
    }
    
    async retry(func, config = null, options = {}) {
        const retryConfig = config || new RetryConfig();
        const context = new RetryContext(func.name || 'anonymous', retryConfig);
        
        while (true) {
            try {
                // Check circuit breaker
                if (this.isCircuitOpen(func.name)) {
                    throw new Error(`Circuit breaker is open for ${func.name}`);
                }
                
                const result = await func();
                this._recordSuccess(func.name);
                return result;
                
            } catch (error) {
                context.lastError = error;
                context.attempts++;
                
                const statusCode = error.response?.status;
                
                if (!context.shouldRetry(error, statusCode)) {
                    this._recordFailure(func.name);
                    
                    if (options.onFailure) {
                        options.onFailure(func.name, context.attempts, error);
                    }
                    
                    if (context.attempts >= retryConfig.maxRetries) {
                        this._sendFailureAlert(func.name, context.attempts, error);
                    }
                    
                    throw error;
                }
                
                const delay = context.calculateNextDelay();
                
                logger.warn(
                    `Retry ${context.attempts}/${retryConfig.maxRetries} for ${func.name} ` +
                    `after ${delay}ms (error: ${error.message})`
                );
                
                if (options.onRetry) {
                    options.onRetry(func.name, context.attempts, delay, error);
                }
                
                await this._sleep(delay);
            }
        }
    }
    
    async retryWithBackoff(func, maxRetries = 3, baseDelay = 1000) {
        const config = new RetryConfig({
            maxRetries: maxRetries,
            baseDelay: baseDelay,
            strategy: RetryStrategy.EXPONENTIAL,
            jitter: true
        });
        
        return this.retry(func, config);
    }
    
    _recordSuccess(operation) {
        this.failureCounts.set(operation, 0);
    }
    
    _recordFailure(operation) {
        const currentCount = this.failureCounts.get(operation) || 0;
        this.failureCounts.set(operation, currentCount + 1);
        this.lastFailureTime.set(operation, Date.now());
        
        // Open circuit breaker if 5 consecutive failures
        if (currentCount + 1 >= 5) {
            this._openCircuitBreaker(operation);
        }
    }
    
    _openCircuitBreaker(operation) {
        this.circuitBreakers.set(operation, {
            state: 'open',
            openedAt: Date.now(),
            resetAt: Date.now() + 60000 // Reset after 60 seconds
        });
        
        alertManager.sendSlack(
            `🔌 *Circuit Breaker Opened*\n` +
            `Operation: ${operation}\n` +
            `Reason: ${this.failureCounts.get(operation)} consecutive failures\n` +
            `Will reset at: ${new Date(Date.now() + 60000).toLocaleTimeString()}`,
            'warning'
        );
    }
    
    isCircuitOpen(operation) {
        const breaker = this.circuitBreakers.get(operation);
        if (!breaker) return false;
        
        if (breaker.state === 'open') {
            if (Date.now() >= breaker.resetAt) {
                breaker.state = 'half_open';
                logger.info(`Circuit breaker for ${operation} is now half-open`);
                return false;
            }
            return true;
        }
        
        return false;
    }
    
    _sendFailureAlert(operation, attempts, error) {
        const failureCount = this.failureCounts.get(operation) || 0;
        
        alertManager.sendSlack(
            `❌ *Persistent Failure Detected*\n` +
            `Operation: ${operation}\n` +
            `Attempts: ${attempts}\n` +
            `Consecutive failures: ${failureCount}\n` +
            `Error: ${error.message}\n` +
            `Action: Manual intervention may be required`,
            'danger'
        );
        
        alertManager.sendEmail(
            `[URGENT] Persistent failure: ${operation}`,
            `Operation ${operation} failed after ${attempts} attempts.\n\n` +
            `Error: ${error.message}\n\n` +
            `Please check the system.`
        );
    }
    
    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Create retry wrapper for axios
const axios = require('axios');

class RetryableAxiosClient {
    constructor(baseURL, retryConfig = null) {
        this.client = axios.create({ baseURL, timeout: 30000 });
        this.retryHandler = new AdvancedRetryHandler();
        this.defaultConfig = retryConfig || new RetryConfig();
    }
    
    async request(method, url, data = null, config = {}) {
        const makeRequest = async () => {
            const response = await this.client.request({
                method,
                url,
                data,
                ...config
            });
            
            if (response.status >= 500 || [408, 429].includes(response.status)) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            return response.data;
        };
        
        return this.retryHandler.retry(makeRequest, this.defaultConfig);
    }
    
    async get(url, config = {}) {
        return this.request('GET', url, null, config);
    }
    
    async post(url, data, config = {}) {
        return this.request('POST', url, data, config);
    }
    
    async put(url, data, config = {}) {
        return this.request('PUT', url, data, config);
    }
    
    async delete(url, config = {}) {
        return this.request('DELETE', url, null, config);
    }
}

module.exports = {
    AdvancedRetryHandler,
    RetryConfig,
    RetryStrategy,
    RetryableAxiosClient,
    retryHandler: new AdvancedRetryHandler()
};