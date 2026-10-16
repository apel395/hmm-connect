# Dokumentasi MMH Connect ERP

Panduan aplikasi Hotel Mutiara Merdeka dan Project Catering. Ditinjau pada **16 Oktober 2026** berdasarkan frontend main dan backend backend.

## Mulai dari sini

| Kebutuhan | Dokumen |
| --- | --- |
| Login, navigasi, akses, dan pekerjaan harian | [Panduan pengguna](user-guide.md) |
| Item Master, PR, ML, PO, receiving, dan gudang | [Purchasing dan inventory](purchasing-inventory.md) |
| Opening balance, AP, AR, payment, jurnal, dan aset | [Finance dan aturan akuntansi](finance-accounting.md) |
| Neraca, laba rugi, budget, statistik, dan export | [Laporan dan dashboard](reporting.md) |
| Deployment, migrasi, worker, dan penanganan gangguan | [Operasional teknis](operations.md) |
| Struktur kode, API, dan aturan pengembangan | [Panduan developer](development.md) |

Panduan ini menjelaskan perilaku aplikasi, bukan bukti bahwa seluruh data produksi telah direkonsiliasi. Hak akses dan konfigurasi approval dapat membuat tombol atau pilihan berbeda antar pengguna.

## Aturan inti

1. Hotel dipisahkan menurut **department**; Catering dipisahkan menurut **location**. Consolidated menggabungkan scope yang diizinkan.
2. Opening balance adalah saldo awal tahunan yang diinput pengguna. Sistem tidak membuat jurnal atau contra untuk menyeimbangkannya.
3. Transaksi 2026 masuk movement. Receiving sebelum 1 Januari 2026 tidak diimpor sebagai aktivitas operasional.
4. Item STOCK, DIRECT_USE, dan FIXED_ASSET mengikuti perlakuan berbeda. Direct Use tidak boleh dibuat seolah-olah masuk lalu keluar gudang.
5. Reconciliation menyajikan data dan selisih. Koreksi dilakukan dengan tindakan finance yang jelas, bukan penyesuaian otomatis tersembunyi.
6. Posting bergantung pada accounting period, permission, lokasi, dan kondisi dokumen sumber.

## Cakupan dan versi

Basis pemeriksaan: [frontend 9c180ec](https://github.com/apel395/hmm-connect/tree/9c180ec995e6eec8d5d4390fbb3ce53b9b0363b4) dan [backend 1dc191f](https://github.com/apel395/hmm-connect/tree/1dc191f1684503778e6ae308431f3758b687e928). Perubahan sesudah versi ini perlu diperiksa pada source dan release yang bersangkutan.

Dokumentasi berlaku untuk fitur yang ada di kode pada tanggal peninjauan. Persiapan atau keberhasilan sebagian seed tidak berarti seluruh katalog atau transaksi sudah selesai dimigrasikan. File repair dan seed di backend adalah pekerjaan khusus, bukan instruksi rutin pengguna.

Detail implementasi backend tersedia di [folder docs branch backend](https://github.com/apel395/hmm-connect/tree/backend/docs). Catatan README lama dipertahankan di [arsip implementasi](reference/implementation-history.md); gunakan panduan saat ini untuk perilaku aplikasi.
