// config.js
require('dotenv').config();

const brands = {
  brand_a: {
    brand_id: 'brand_a',
    brand_name: 'Toko A',
    jubelio_store_id: 'store_1001',
    api_base_url: 'https://api.jubelio.com/v1',
    username: 'user_brand_a',
    password: 'password_a'
  },
  brand_b: {
    brand_id: 'brand_b',
    brand_name: 'Toko B',
    jubelio_store_id: 'store_1002',
    api_base_url: 'https://api.jubelio.com/v1',
    username: 'user_brand_b',
    password: 'password_b'
  },
  brand_c: {
    brand_id: 'brand_c',
    brand_name: 'Toko C',
    jubelio_store_id: 'store_1003',
    api_base_url: 'https://api.jubelio.com/v1',
    username: 'user_brand_c',
    password: 'password_c'
  }
};

const dbConfig = {
  host: process.env.DB_HOST,
  port: process.env.DB_PORT,
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD
};

const tokenExpiryBuffer = 300; // 5 minutes

module.exports = { brands, dbConfig, tokenExpiryBuffer };