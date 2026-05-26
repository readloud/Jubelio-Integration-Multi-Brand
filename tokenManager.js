// tokenManager.js
const axios = require('axios');
const Database = require('./database');
const { tokenExpiryBuffer } = require('./config');

class TokenManager {
  constructor(brandConfig) {
    this.brandConfig = brandConfig;
    this.db = new Database();
    this.accessToken = null;
    this.refreshToken = null;
    this.expiresAt = 0;
  }

  async loadFromDb() {
    const tokenData = await this.db.getToken(this.brandConfig.brand_id);
    if (tokenData) {
      this.accessToken = tokenData.access_token;
      this.refreshToken = tokenData.refresh_token;
      this.expiresAt = tokenData.expires_at;
      console.log(`Token loaded from DB for ${this.brandConfig.brand_name}`);
    }
  }

  async saveToDb() {
    await this.db.saveToken(
      this.brandConfig.brand_id,
      this.accessToken,
      this.refreshToken,
      this.expiresAt
    );
  }

  async login() {
    const url = `${this.brandConfig.api_base_url}/api/auth/login`;
    const payload = {
      username: this.brandConfig.username,
      password: this.brandConfig.password
    };

    try {
      const response = await axios.post(url, payload, { timeout: 30000 });
      if (response.status === 200) {
        this.accessToken = response.data.access_token;
        this.refreshToken = response.data.refresh_token;
        this.expiresAt = Date.now() / 1000 + 3600; // 1 hour
        await this.saveToDb();
        console.log(`Login successful for ${this.brandConfig.brand_name}`);
        return true;
      }
      return false;
    } catch (error) {
      console.error(`Login error for ${this.brandConfig.brand_name}:`, error.message);
      return false;
    }
  }

  async refresh() {
    if (!this.refreshToken) {
      return this.login();
    }

    const url = `${this.brandConfig.api_base_url}/api/auth/refresh`;
    const payload = { refresh_token: this.refreshToken };

    try {
      const response = await axios.post(url, payload, { timeout: 30000 });
      if (response.status === 200) {
        this.accessToken = response.data.access_token;
        this.refreshToken = response.data.refresh_token;
        this.expiresAt = Date.now() / 1000 + 3600;
        await this.saveToDb();
        console.log(`Token refreshed for ${this.brandConfig.brand_name}`);
        return true;
      }
      return this.login();
    } catch (error) {
      console.error(`Refresh error for ${this.brandConfig.brand_name}:`, error.message);
      return this.login();
    }
  }

  async getValidToken() {
    await this.loadFromDb();

    if (!this.accessToken) {
      if (!await this.login()) return null;
    }

    const currentTime = Date.now() / 1000;
    if (currentTime >= (this.expiresAt - tokenExpiryBuffer)) {
      if (!await this.refresh()) return null;
    }

    return this.accessToken;
  }
}

module.exports = TokenManager;