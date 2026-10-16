# Operasional teknis

[Kembali ke dokumentasi](README.md)

## Arsitektur production

~~~mermaid
flowchart TD
  Browser["Browser React/Vite"] --> UI["Vercel frontend: main"]
  Browser --> API["AWS Lambda API: backend"]
  API --> DB["PostgreSQL pada EC2"]
  API --> Queue["Job dan SSM trigger"]
  Queue --> Worker["EC2 worker"]
  Worker --> DB
  Worker --> S3["Private S3"]
  Browser --> S3
~~~

Frontend, API, dan worker harus kompatibel dengan schema yang sama. Lambda menangani request API; EC2 menjalankan PostgreSQL, migrasi, dan pekerjaan Excel/import yang berat. File besar menggunakan private S3 dan URL berjangka.

| Source branch | Dampak release |
| --- | --- |
| main | Deployment frontend Vercel |
| backend | Deployment API Lambda melalui GitHub Actions |
| Feature branch | Persiapan/review; tidak berarti sudah ada di production |

## Backend lokal

Checkout branch backend pada working directory terpisah dari frontend.

~~~bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-worker.txt
cp .env.example .env
~~~

Isi konfigurasi lokal, lalu:

~~~bash
alembic upgrade head
uvicorn app.main:app --reload
~~~

Perintah migrasi di atas untuk database existing yang memiliki base schema. Fresh database menggunakan prosedur bootstrap di bawah.

Health: GET /health. OpenAPI: /docs. Endpoint aplikasi berada di /api/v1.

## Konfigurasi

| Konfigurasi | Fungsi |
| --- | --- |
| VITE_API_URL | Base API frontend, termasuk prefix versi |
| SECRET_KEY | Signing secret backend, minimum 32 karakter |
| DATABASE_URL atau DB_* | Koneksi PostgreSQL |
| CORS_ORIGINS | Origin browser yang diizinkan |
| S3_BUCKET / S3_PREFIX | Penyimpanan dokumen |
| AWS_REGION | Region layanan AWS |
| EXPORT_EC2_INSTANCE_ID | EC2 worker yang dikelola SSM |
| EXPORT_WORKDIR / EXPORT_PYTHON_BIN | Checkout dan interpreter worker |
| EXPORT_S3_BUCKET / EXPORT_S3_PREFIX | Penyimpanan hasil export |
| JOURNAL_IMPORT_S3_PREFIX | Prefix upload import journal |

Nama dan default lengkap berada di app/core/config.py pada backend. Gunakan konfigurasi environment yang disetujui; jangan mencetak .env atau credentials saat diagnosis.

## Migrasi dan deployment

Sebelum release:

1. Tinjau migration graph dan perubahan schema.
2. Siapkan release commit atau feature ref yang benar-benar ada di remote.
3. Terapkan migrasi dari kode release tersebut di EC2, memakai .env dan .venv yang benar.
4. Periksa hasil dan checker read-only yang relevan.
5. Merge backend untuk deployment Lambda; sinkronkan worker ke revisi yang kompatibel.
6. Deploy frontend yang menggunakan kontrak tersebut.
7. Periksa health, login, satu alur baca, dan fitur yang berubah.

Untuk update checkout EC2 yang bersih setelah release backend:

~~~bash
cd /opt/hmm-connect
git status --short
git fetch origin
git pull --ff-only origin backend
.venv/bin/alembic current
~~~

Jika release membutuhkan migrasi yang belum diterapkan:

~~~bash
.venv/bin/alembic upgrade head
.venv/bin/alembic current
~~~

Jika git menolak karena perubahan lokal, inspeksi dahulu atau gunakan worktree. Jangan menjalankan reset/clean untuk menghapus file import, backup, atau perubahan lokal tanpa mengetahui isinya.

Contoh worktree terpisah dari remote backend:

~~~bash
cd /opt/hmm-connect
git fetch origin
TASK_DIR=$(mktemp -d /tmp/mmh-release.XXXXXX)
git worktree add --detach "$TASK_DIR" origin/backend
cd "$TASK_DIR"
ln -s /opt/hmm-connect/.env .env
export PYTHONPATH="$TASK_DIR"
/opt/hmm-connect/.venv/bin/alembic current
~~~

Jalankan upgrade hanya terhadap release/schema yang sudah ditinjau. Checkout sementara tetap memerlukan environment dan import path; memakai interpreter .venv saja tidak menyediakan SECRET_KEY.

## Fresh database

Migration chain hasil recovery mengasumsikan legacy base tables. Untuk database yang benar-benar kosong, gunakan bootstrap khusus:

~~~bash
python -m scripts.bootstrap_database --confirm-empty-database
~~~

Perintah menolak database yang sudah mempunyai public tables, membuat schema saat ini, memvalidasi core tables, lalu stamp head. Setelah itu gunakan migrasi biasa. Jangan bootstrap ulang database berisi data.

## Worker Excel dan import

Export async: API membuat job → EC2 menghasilkan workbook → upload private S3 → frontend polling → presigned download.

Journal bulk import: browser upload file ke private S3 → API trigger worker melalui SSM → worker validasi → import/post pilihan pengguna → audit batch dan baris.

~~~bash
sudo systemctl status hmm-connect-export-worker --no-pager
sudo journalctl -u hmm-connect-export-worker -n 100 --no-pager
~~~

Setelah update worker yang kompatibel:

~~~bash
sudo systemctl restart hmm-connect-export-worker
sudo systemctl status hmm-connect-export-worker --no-pager
~~~

Spreadsheet parser seperti openpyxl adalah dependency worker, bukan request runtime Lambda. Lambda dan EC2 memerlukan izin SSM/S3 yang terbatas sesuai tugas. Browser upload memerlukan CORS S3 yang benar.

Konfigurasi lengkap:

- [Deployment Lambda](https://github.com/apel395/hmm-connect/blob/backend/docs/aws-lambda-deployment.md)
- [Async export wiring](https://github.com/apel395/hmm-connect/blob/backend/docs/AWS_ASYNC_EXPORT_WIRING.md)
- [Async journal import wiring](https://github.com/apel395/hmm-connect/blob/backend/docs/AWS_ASYNC_JOURNAL_IMPORT_WIRING.md)

Dokumen wiring menjelaskan infrastruktur; format import terbaru mengikuti [panduan finance](finance-accounting.md) dan template aplikasi.

## Diagnosis gangguan

| Gejala | Yang diperiksa |
| --- | --- |
| Frontend tampil tetapi API gagal | Network response, VITE_API_URL, CORS, Lambda health/log |
| UndefinedColumn / missing relation | Revisi API, Alembic current/head, schema EC2 |
| SECRET_KEY required di worktree | .env pada working directory dan konfigurasi environment |
| ModuleNotFoundError app pada script | Jalankan dari repository root dan set PYTHONPATH |
| Export/import tertahan | Status job, worker log, SSM, IAM, S3, DB connectivity |
| File siap tetapi download gagal | Expiry presigned URL, S3 object dan izin |
| Report serialize error | Traceback API dan tipe field; jangan mengubah saldo untuk memperbaiki format |
| Selisih finance | Source document, jurnal, GL, opening, tanggal, dan dimensi yang sama |

Diagnosis database dilakukan dengan query read-only terlebih dahulu. Jika perlu data produksi, minta operator menjalankan Python/SQL dari EC2 dan membagikan hasil yang relevan tanpa credentials.

## Repair, seed, dan rollback

Script seed/repair bersifat spesifik pada source hash, ID, tanggal, dan kondisi historis. Jangan menjalankan ulang sekadar karena nama script mirip masalah saat ini. Gunakan dry-run, cocokkan target, dan periksa idempotency.

Tentukan rollback aplikasi dan dampak schema sebelum deployment. Revert kode tidak otomatis membalik transaksi atau perubahan database. Pembatalan dokumen menggunakan lifecycle aplikasi; perbaikan data harus eksplisit dan dapat ditelusuri.
