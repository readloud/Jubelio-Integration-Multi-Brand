**kerangka teknis dan dokumentasi** 

Berikut outputnya:

---

# Dokumentasi Integrasi API Jubelio – Multi-Brand & Token Otomatis

## 1. Tujuan
Menghubungkan data dari Jubelio ke sistem internal dengan:
- Klasifikasi data per brand
- Token otomatis (tanpa input manual berulang)
- Pemisahan data order, produk, stok, transaksi, channel per brand

---

## 2. Alur Integrasi Umum

```
[Jubelio API] 
    ↓ (dengan token otomatis)
[Sistem Internal] 
    ↓ (klasifikasi berdasarkan brand_id)
[Database / Reporting per Brand]
```

---

## 3. Endpoint Utama yang Digunakan (Contoh dari Jubelio)

| Fungsi | Endpoint (Contoh) | Method |
|--------|------------------|--------|
| Login / Ambil token | `/api/auth/login` | POST |
| Refresh token | `/api/auth/refresh` | POST |
| Get orders | `/api/orders` | GET |
| Get products | `/api/products` | GET |
| Get stock | `/api/stocks` | GET |
| Get transactions | `/api/transactions` | GET |
| Get sales channels | `/api/channels` | GET |

> *Catatan: Endpoint sesungguhnya menyesuaikan dokumentasi API Jubelio.*

---

## 4. Mekanisme Token Otomatis

**Langkah:**
1. **Initial login** dengan `api_key` / `username` & `password` → dapat `access_token` + `refresh_token`.
2. Simpan token di **environment variable** atau **database terenkripsi**.
3. Sebelum setiap request, cek masa berlaku token.
4. Jika token hampir habis (misal ≤ 5 menit), lakukan **refresh token** otomatis.
5. Simpan token baru, lanjutkan request.

**Struktur penyimpanan token (contoh JSON):**
```json
{
  "brand_id": "brand_a",
  "access_token": "xxx",
  "refresh_token": "yyy",
  "expires_at": "2025-06-01T12:00:00Z"
}
```

---

## 5. Klasifikasi Data per Brand

Setiap brand memiliki **identitas unik** dalam sistem internal:

| Brand ID | Nama Brand | Jubelio Store ID / Channel ID |
|----------|------------|-------------------------------|
| brand_a  | Toko A     | store_1001                    |
| brand_b  | Toko B     | store_1002                    |
| brand_c  | Toko C     | store_1003                    |

**Strategi klasifikasi:**
- Saat tarik data dari Jubelio, filter berdasarkan `store_id` atau `channel_id`.
- Setiap record diberi kolom tambahan: `brand_id`.
- Simpan di tabel terpisah atau satu tabel dengan indeks brand.

**Contoh struktur database (orders):**
```sql
CREATE TABLE orders (
  id UUID,
  brand_id VARCHAR(50),
  jubelio_order_id VARCHAR(100),
  total_price DECIMAL,
  channel VARCHAR(100),
  created_at TIMESTAMP
);
```

---

## 6. Pengecekan Struktur Data dari Jubelio

Freelancer harus melakukan **sample response check** untuk setiap endpoint, lalu mapping ke struktur internal.

Contoh mapping sederhana:

| Jubelio Field | Internal Field | Brand |
|---------------|----------------|-------|
| order_number  | order_no       | semua |
| product_sku   | sku            | semua |
| qty           | quantity       | semua |
| store_name    | brand_id (lookup) | khusus |

---

## 7. Potensi Error & Penanganan

| Error | Penyebab | Solusi |
|-------|----------|--------|
| 401 Unauthorized | Token expired | Trigger refresh token otomatis, retry request |
| 403 Forbidden | Token invalid | Re-login dengan kredensial utama |
| 429 Too Many Requests | Rate limit | Implementasi retry with backoff (exponential) |
| 404 Not Found | Endpoint berubah | Cek dokumentasi Jubelio terbaru |
| Data tidak konsisten per brand | Salah filter store_id | Logging + alerting jika data brand tercampur |

---

## 8. Monitoring & Logging

- Setiap request/response dicatat (tanpa menyimpan data sensitif berlebih).
- Log token refresh: `[INFO] Token refreshed for brand_a at 2025-06-01 10:00:00`
- Alert jika gagal refresh token > 3x.

---

## 9. Output yang Diserahkan Freelancer

- [ ] Source code (Python/NodeJS/PHP etc.)
- [ ] File konfigurasi environment (contoh `.env`)
- [ ] Script migrasi database (untuk klasifikasi brand)
- [ ] Dokumentasi teknis (file ini + tambahan)
- [ ] Panduan run & monitoring

---

## 10. Kriteria Penerimaan

- [ ] Semua brand bisa login & tarik data sendiri-sendiri
- [ ] Token berjalan otomatis tanpa intervensi manual
- [ ] Data di database sudah terklasifikasi per brand
- [ ] Tidak ada data campur antar brand
- [ ] Laporan sederhana per brand bisa dihasilkan

---

Baik, saya akan buatkan **contoh implementasi kode** untuk integrasi API Jubelio dengan:

1. **Token otomatis** (auto refresh)
2. **Klasifikasi data per brand**
3. **Multi-brand support**

Saya akan gunakan **Python** karena mudah dibaca dan banyak digunakan untuk integrasi semacam ini.

---

## Struktur Proyek

```
jubelio-integration/
├── python-version/
│   ├── config.py
│   ├── token_manager.py
│   ├── jubelio_client.py
│   ├── data_classifier.py
│   ├── database.py
│   ├── logger.py
│   ├── alerting.py
│   ├── scheduler.py
│   ├── main.py
│   ├── requirements.txt
│   └── .env
├── nodejs-version/
│   ├── config.js
│   ├── tokenManager.js
│   ├── jubelioClient.js
│   ├── dataClassifier.js
│   ├── database.js
│   ├── logger.js
│   ├── alerting.js
│   ├── scheduler.js
│   ├── index.js
│   ├── package.json
│   └── .env
├── database/
│   └── schema.sql
├── docker-compose.yml
└── README.md
```
---