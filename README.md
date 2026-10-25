# MMH Connect ERP

ERP untuk **Hotel Mutiara Merdeka** dan **Project Catering**: purchasing, receiving, inventory, finance, fixed assets, reporting, approvals, dan audit.

Production: [connect.mutiaramerdekahotel.com](https://connect.mutiaramerdekahotel.com)

## Dokumentasi

Mulai dari [indeks dokumentasi](docs/README.md).

| Pembaca | Panduan |
| --- | --- |
| Pengguna aplikasi | [Login, navigasi, akses, dan pekerjaan harian](docs/user-guide.md) |
| Purchasing dan warehouse | [Item Master, purchasing, receiving, stock, dan opname](docs/purchasing-inventory.md) |
| Finance dan accounting | [Opening, AP/AR, payment, jurnal, aset, dan closing](docs/finance-accounting.md) |
| Finance dan owner | [Laporan, drilldown, Excel, budget, dan Executive View](docs/reporting.md) |
| Administrator teknis | [Deployment, migrasi, worker, dan troubleshooting](docs/operations.md) |
| Developer | [Arsitektur kode, API, validasi, dan maintenance](docs/development.md) |

Dokumentasi ditinjau pada **16 Oktober 2026**. [Catatan implementasi terdahulu](docs/reference/implementation-history.md) disimpan sebagai arsip; aturan aplikasi saat ini dijelaskan dalam panduan di atas.

## Repository dan deployment

| Komponen | Source | Runtime |
| --- | --- | --- |
| Frontend React/Vite | main | Vercel |
| API FastAPI/SQLAlchemy | backend | AWS Lambda |
| Database dan pekerjaan berat | Backend checkout | PostgreSQL dan worker di EC2 |

Push/merge ke backend men-trigger deployment Lambda. Migrasi database dilakukan di EC2 sebelum aplikasi yang membutuhkan schema baru dirilis. EC2 bukan tempat menjalankan API production.

## Aturan bisnis utama

- **Hotel:** laporan dipisahkan per department.
- **Catering:** laporan dipisahkan per location.
- Opening balance adalah saldo awal tahunan manual, terpisah dari jurnal transaksi, tanpa auto-contra.
- Aktivitas 2026 masuk movement; receiving sebelum 2026 tidak menjadi transaksi operasional baru.
- STOCK, DIRECT_USE, dan FIXED_ASSET mempunyai alur berbeda. Direct Use tidak menciptakan histori gudang buatan.
- Akses berdasarkan permission dan penempatan organisasi; server memeriksa scope pada data, tindakan, dan export.
- Reconciliation menunjukkan keadaan nyata. Sistem tidak menghilangkan selisih dengan koreksi saldo otomatis.
- Statistical account dikelola sebagai Actual/Budget nonfinansial, bukan journal/GL.

## Frontend lokal

Gunakan Node.js 22 seperti CI. Set VITE_API_URL ke base API yang sesuai, termasuk /api/v1.

~~~bash
npm ci
npm run dev
~~~

Validasi perubahan aplikasi:

~~~bash
npm run lint
npm run build
npm run test:finance
npm run test:workspace
npm run test:inventory-print
~~~

Backend memiliki dependensi, migrasi, dan prosedur deployment sendiri. Lihat [panduan operasional](docs/operations.md) dan [README backend](https://github.com/apel395/hmm-connect/blob/backend/README.md).

## Pemeliharaan dokumentasi

Saat mengubah workflow, permission, accounting rule, report, atau deployment, perbarui panduan terkait dalam PR yang sama. Bedakan fitur yang sudah ada, konfigurasi yang masih diperlukan, dan data yang belum selesai dimigrasikan. Jangan menyimpan password, token, atau nilai .env production dalam dokumentasi.


## Hotel POS operations (feature review)

[Outlet tables, cashier shifts and daily reports](docs/hotel-pos-operations-1024.md) extend the existing POS and `department_outlets` master. Requires companion backend Phase 2 and additive migration `20261024_pos_operations` before an approved release. Hotel orders stay separated by outlet; accounting and AR remain integrated with the existing finance flow.
