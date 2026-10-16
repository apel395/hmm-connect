# Panduan developer

[Kembali ke dokumentasi](README.md)

## Struktur source

Repository yang sama memiliki dua branch aplikasi:

| Branch | Tanggung jawab | Lokasi penting |
| --- | --- | --- |
| main | React, TypeScript, Vite, UI | src/modules, src/components, src/router, src/api, src/store |
| backend | FastAPI, SQLAlchemy, Alembic, worker | app/api/v1, app/services, app/models, app/schemas, alembic/versions, tests |

Gunakan checkout/worktree terpisah. Jangan menggabungkan seluruh tree frontend ke backend atau sebaliknya untuk mengirim satu fitur.

## Frontend

| Lokasi | Peran |
| --- | --- |
| src/router/routes.tsx | Halaman dan route aplikasi |
| src/components/navigation/navigationConfig.ts | Menu, ikon, permission, dan route aliases |
| src/layouts/AppLayout.tsx | Shell aplikasi |
| src/store/workspaceTabs.ts | Siklus tab dan penyimpanan workspace |
| src/components/workspace | Tabel/workspace, filter, dan alat compact |
| src/modules | Fitur domain |
| src/api/client.ts | Base URL dan session-aware interceptor |

Tambahkan menu melalui konfigurasi bersama agar sidebar, mobile launcher, dan top navigation tetap konsisten. Jangan hanya menyembunyikan tombol sebagai kontrol keamanan; endpoint harus memvalidasi permission dan lokasi.

Query/filter modul menggunakan tab yang sama. Dokumen dengan ID berbeda menggunakan tab berbeda. Back harus menutup tab, bukan memaksa pengguna mengulang navigasi browser.

## Backend

Request API melewati authentication/authorization, schema validation, domain service, lalu transaksi database. Source document, stock, jurnal, GL, dan audit harus konsisten pada perubahan state.

| Area | Source utama pada backend |
| --- | --- |
| Receiving | app/api/v1/goods_receipts.py; app/services/goods_receipt_service.py |
| Payment | app/api/v1/payments.py; app/services/payment_charges.py |
| Journal | app/api/v1/journals.py; app/services/general_ledger.py |
| Opening | app/services/opening_balance_service.py |
| Reporting | app/services/financial_reporting_service.py |
| Closing | app/services/period_closing_service.py |
| Fixed assets | app/services/fixed_asset_service.py; app/services/asset_posting.py |
| Async import | app/api/v1/journal_imports.py; app/scripts/journal_import_worker.py |
| Environment | app/core/config.py |

## Peta API

Semua path di bawah relatif terhadap /api/v1. Gunakan OpenAPI runtime untuk method, payload, pagination, dan response schema lengkap.

| Path | Kegunaan |
| --- | --- |
| /auth/login | Login dan penggantian sesi |
| /goods-receipts | Receiving dan tindakan workflow |
| /payments | Payment, allocation, dan lifecycle |
| /journal-entries | Journal entry dan sumber |
| /journal-imports | Template, upload, validasi, dan import jobs |
| /general-ledger | Ledger dan filter akun |
| /opening-balances | Nilai awal tahunan |
| /ap-movement | Opening, activity, running/closing AP |
| /financial-reports | Setup, comparison, dan export |
| /fiscal-periods | Open/close/reopen period |
| /fixed-assets | Register, setup, dan tindakan aset |
| /statistics | Statistical actual/budget |
| /exports | Async export job |

Referensi OpenAPI adalah kontrak field terbaru. Nomor account memakai account_number pada model COA; beberapa report memakai field output account_code. Jangan menyalin nama field report sebagai nama kolom SQL.

## Invariant yang harus dipertahankan

- Opening input tidak membuat journal, contra, atau auto-balance.
- Manual journal boleh tidak seimbang; source journal dan bulk import mempunyai validasi keseimbangan sendiri.
- Account identity memakai ID; mengubah nomor akun tidak menggandakan account atau memutus histori line.
- Revenue tidak dibatasi oleh literal account number 400. Mapping report ringkas tidak mengubah validasi posting akun.
- Statistical account tidak masuk financial GL.
- Direct Use tidak membuat warehouse movement fiktif.
- Unpost/cancel menangani sumber, stock/paid amount, jurnal, dan GL secara terkoordinasi.
- Closing menggunakan scope organisasi dan tanggal period end; tidak diulang menjadi jurnal aktif duplikat.
- Location access berlaku pada list, detail, actions, totals, drilldown, export, dan print.
- Filter/page size tidak mengubah makna total keseluruhan.
- Missing/unavailable evidence tidak diserialisasi sebagai nol palsu.
- Print tracking menghitung permintaan print, bukan bukti kertas benar-benar tercetak.

## Validasi perubahan

Frontend:

~~~bash
npm ci
npm run lint
npm run build
npm run test:finance
npm run test:workspace
npm run test:inventory-print
~~~

Backend, dengan environment test yang benar:

~~~bash
PYTHONPATH=. .venv/bin/python -m pytest -q tests
.venv/bin/alembic heads
~~~

Jalankan uji sesuai perubahan. Perubahan UI perlu pemeriksaan desktop/mobile, tabel panjang, keyboard, dan akses terbatas. Perubahan finance perlu kasus posting/unpost, pengulangan tindakan, scope, dan kesesuaian source-journal-GL. Gunakan fixture; jangan menguji mutation terhadap production.

Dokumentasi saja diverifikasi melalui link, route/source reference, dan konsistensi aturan; tidak memerlukan perubahan saldo atau schema.

## Kontribusi dan release

1. Mulai dari remote head branch yang sesuai.
2. Baca aturan domain dan kode sumber yang sedang berlaku.
3. Buat perubahan terbatas dan hindari membawa file repair/data lokal tanpa sengaja.
4. Jika schema berubah, sediakan migration dan rencana urutan release.
5. Jalankan pemeriksaan yang relevan; jelaskan hasil dan keterbatasannya pada PR.
6. Perbarui dokumentasi pengguna bila perilaku berubah.
7. Tinjau/merge ke branch deployment yang benar dan verifikasi deployment.

Jangan menyimpan .env, production dump, token, atau credentials di git. Data seed pribadi tidak menjadi dependency runtime.
