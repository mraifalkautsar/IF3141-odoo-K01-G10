# SAFAGO Odoo - IF3141 K01 G10

Repository ini berisi implementasi MVP SAFAGO untuk Milestone 4 IF3141 Sistem Informasi. Sistem berjalan di atas Docker Odoo 17 dengan modul kustom pada folder `custom_addons/`.

## Modul Kustom

- `safago_roll_kain`: master data roll kain dan sisa stok yard.
- `safago_spk`: ekstensi Manufacturing Order/SPK dan status produksi SAFAGO.
- `safago_qc`: laporan kain cacat, validasi stok, notifikasi Telegram, sequence laporan, dan akses QC.
- `safago_staf`: ekstensi data staf dengan Telegram ID.

## Prasyarat

- Docker Desktop
- Docker Compose v2
- Git
- WSL Ubuntu untuk Windows sangat disarankan

Catatan IDE: import seperti `from odoo import models, fields` bisa terbaca error oleh VS Code/Pylance karena Odoo berjalan di dalam Docker, bukan di virtual environment lokal. Selama container Odoo berjalan dan modul bisa di-upgrade, warning import tersebut boleh diabaikan.

## Setup Awal

1. Clone repository.

   ```bash
   git clone <url-repository>
   cd IF3141-odoo-K01-G10
   ```

2. Buat file `.env` dari template dan import db

   ```bash
   ./scripts/import_db.sh
   cp .env.example .env
   ```

3. Isi token Telegram di `.env`.

   ```env
   SAFAGO_TELEGRAM_BOT_TOKEN=isi_token_baru_dari_botfather
   ```

   File `.env` tidak boleh di-commit. Token lama yang pernah masuk repo harus dianggap bocor dan sebaiknya di-rotate lewat BotFather.

4. Jalankan Odoo dan PostgreSQL.

   ```bash
   docker compose up -d
   ```

5. Buka Odoo.

   - URL: http://localhost:8069
   - Login default: `admin`
   - Password default: `admin`

6. Aktifkan Developer Mode.

   Masuk ke **Settings**, lalu aktifkan **Developer Mode**.

7. Update daftar aplikasi.

   Masuk ke **Apps**, klik **Update Apps List**.

8. Install modul SAFAGO.

   Install modul berikut dari menu **Apps**:

   - Safago Roll Kain
   - Safago Staf Extension
   - Safago SPK Extension
   - Safago Quality Control

   Kalau modul sudah pernah di-install dan ada perubahan kode, lakukan upgrade modul, bukan install ulang.

## Upgrade Modul Setelah Edit Kode

Setelah mengubah file Python/XML di `custom_addons/`, jalankan upgrade modul terkait:

```bash
docker compose run --rm web odoo \
  --db_host=db \
  --db_port=5432 \
  --db_user=odoo \
  --db_password=password \
  -d postgres \
  -u safago_roll_kain,safago_staf,safago_spk,safago_qc \
  --stop-after-init
```

Setelah upgrade, restart/recreate web bila perubahan menyangkut `.env` atau Docker config:

```bash
docker compose up -d --force-recreate web
```

Untuk perubahan biasa pada modul, refresh browser atau logout-login sudah cukup.

## Setup Telegram

1. Buat bot Telegram lewat BotFather dan ambil token baru.
2. Masukkan token ke `.env` pada `SAFAGO_TELEGRAM_BOT_TOKEN`.
3. Recreate container web:

   ```bash
   docker compose up -d --force-recreate web
   ```

4. Pastikan staf yang dipilih pada laporan kain cacat punya `Telegram ID`.

   `telegram_id` harus berupa `chat_id`, bukan username. Untuk chat pribadi, user harus pernah mengirim `/start` ke bot. Untuk grup, gunakan chat ID grup, biasanya diawali `-` atau `-100`.

Notifikasi Telegram dikirim saat laporan kain cacat baru dibuat. Mengedit laporan lama tidak mengirim notifikasi ulang.

## Role dan Akses

Modul `safago_qc` menambahkan group:

- `SAFAGO QC User`
- `SAFAGO QC Manager`

`SAFAGO QC Manager` otomatis membawa akses Inventory dan Manufacturing yang dibutuhkan untuk membuka data SPK, Production Order, dan Bill of Material. Admin Odoo juga otomatis diberi akses manager SAFAGO saat modul `safago_qc` di-upgrade.

Jika setelah upgrade masih muncul Access Error, lakukan:

```bash
docker compose up -d --force-recreate web
```

Lalu logout-login ulang di browser.

## Testing

Jalankan test Odoo untuk modul QC:

```bash
docker compose run --rm web odoo \
  --db_host=db \
  --db_port=5432 \
  --db_user=odoo \
  --db_password=password \
  -d postgres \
  -u safago_spk,safago_qc \
  --test-enable \
  --stop-after-init \
  --log-level=test
```

Ekspektasi hasil:

```text
0 failed, 0 error(s)
```

## Backup dan Restore Database

Export database dan filestore:

```bash
./scripts/export_db.sh
```

Import backup terbaru dari folder `dump/`:

```bash
./scripts/import_db.sh
```

Import backup tertentu:

```bash
./scripts/import_db.sh dump/nama_file.dump
```

## Troubleshooting

### Telegram tidak masuk

Cek log:

```bash
docker compose logs --tail=120 web
```

Jika muncul `Token Telegram SAFAGO QC belum dikonfigurasi`, pastikan `.env` terisi dan container web sudah di-recreate:

```bash
docker compose up -d --force-recreate web
```

### Access Error Manufacturing atau Inventory

Upgrade modul security dan recreate web:

```bash
docker compose run --rm web odoo --db_host=db --db_port=5432 --db_user=odoo --db_password=password -d postgres -u safago_qc --stop-after-init
docker compose up -d --force-recreate web
```

Lalu logout-login ulang.

### Docker Compose warning `version is obsolete`

Warning ini dari format Compose terbaru dan tidak mengganggu aplikasi. Boleh diabaikan untuk pengerjaan ini.

## Batasan MVP

Implementasi saat ini adalah MVP Odoo internal form. Fitur Telegram chatbot berbasis QR, validasi barcode kamera, sinkronisasi Accurate, dashboard monitoring, dan early warning masih menjadi ruang lingkup lanjutan.

sebelum push jalanin export_db.sh dulu ya ges