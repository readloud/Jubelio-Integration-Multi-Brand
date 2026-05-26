// jubelioClient.js
const axios = require('axios');
const TokenManager = require('./tokenManager');

class JubelioClient {
  constructor(brandConfig) {
    this.brandConfig = brandConfig;
    this.tokenManager = new TokenManager(brandConfig);
    this.baseUrl = brandConfig.api_base_url;
  }

  async makeRequest(method, endpoint, params = null, data = null) {
    const maxRetries = 2;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      const token = await this.tokenManager.getValidToken();
      if (!token) return null;

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      const url = `${this.baseUrl}${endpoint}`;

      try {
        const response = await axios({
          method,
          url,
          headers,
          params,
          data,
          timeout: 30000
        });

        if (response.status === 200) {
          return response.data;
        } else if (response.status === 401) {
          console.log(`Token invalid for ${this.brandConfig.brand_name}, refreshing...`);
          await this.tokenManager.refresh();
          continue;
        } else {
          console.error(`Error ${response.status} for ${this.brandConfig.brand_name}:`, response.data);
          return null;
        }
      } catch (error) {
        console.error(`Request error for ${this.brandConfig.brand_name}:`, error.message);
        return null;
      }
    }
    return null;
  }

  async getOrders(startDate = null, endDate = null) {
    const params = { store_id: this.brandConfig.jubelio_store_id };
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    return this.makeRequest('GET', '/api/orders', params);
  }

  async getProducts() {
    const params = { store_id: this.brandConfig.jubelio_store_id };
    return this.makeRequest('GET', '/api/products', params);
  }

  async getStock() {
    const params = { store_id: this.brandConfig.jubelio_store_id };
    return this.makeRequest('GET', '/api/stocks', params);
  }

  async getTransactions() {
    const params = { store_id: this.brandConfig.jubelio_store_id };
    return this.makeRequest('GET', '/api/transactions', params);
  }
}

module.exports = JubelioClient;