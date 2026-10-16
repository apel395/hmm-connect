# Finance dan aturan akuntansi

[Kembali ke dokumentasi](README.md)

## Saldo awal, transaksi, dan GL

| Data | Tujuan | Perlakuan |
| --- | --- | --- |
| Opening Balance | Saldo awal tahun dari closing sebelumnya | Input terpisah; tidak membuat jurnal atau contra otomatis |
| Journal Entry | Bukti aktivitas atau koreksi periode berjalan | Header dan banyak account lines, dengan sumber dan dimensi |
| General Ledger | Aktivitas akuntansi yang sudah diposting | Menjadi dasar movement dan penelusuran transaksi |
| Trial Balance | Opening, movement, dan closing per akun | Menampilkan keadaan nyata, termasuk ketidakseimbangan |

Untuk tahun 2026, opening merepresentasikan closing 2025. Seluruh aktivitas 2026 masuk movement. Perubahan tanggal mulai laporan tidak mengubah opening menjadi transaksi: aktivitas sebelum rentang yang dipilih tetap harus diperhitungkan sebagai aktivitas sebelumnya.

**Sistem tidak membuat Modal Awal Disetor atau akun lain untuk mengoreksi selisih opening.** Revisi opening dilakukan secara tercatat saat period dalam tahun tersebut terbuka. Nilai yang diinput tetap menjadi catatan opening.

Status normal pada akun berarti arah saldo sesuai normal balance akun. Semua akun dapat berstatus normal sementara total debit dan credit keseluruhan berbeda. Periksa total dan difference, bukan hanya warna status per akun.

## Accounting period dan tanggal

Posting memeriksa period yang mencakup tanggal transaksi. Period tertutup menolak posting. Backdate yang diizinkan harus mengikuti setting period; membuka kalender tidak menggantikan pemeriksaan server.

Tanggal bisnis menggunakan Asia/Jakarta. Receiving normal mengikuti waktu submit; Historical Entry mempunyai jalur khusus yang dijelaskan pada [purchasing](purchasing-inventory.md).

## AP: receiving sampai pembayaran

Alur normal: receiving → supplier invoice → payment. Payment Voucher adalah dokumen approval internal opsional; voucher sendiri bukan posting GL.

| Peristiwa | Debit | Credit |
| --- | --- | --- |
| Warehouse receiving | Inventory | AP Suspense |
| Direct Use receiving | Expense/COGS tujuan | AP Suspense |
| Supplier invoice atas receiving | AP Suspense; pajak masukan/selisih jika berlaku | Hutang Usaha |
| Payment utang | Hutang Usaha | Cash/Bank |
| Biaya bank pembayaran | Expense biaya bank | Cash/Bank |

Ini ringkasan sisi akuntansi; jumlah, akun pajak, variance, dan dimensi mengikuti sumber dan konfigurasi. Jurnal yang masih DRAFT belum mempunyai efek GL yang sama dengan jurnal POSTED.

### AP Suspense

AP Suspense adalah nilai penerimaan yang belum diselesaikan oleh pencocokan supplier invoice. Saldo tidak harus nol jika masih ada receiving yang belum memiliki invoice.

Untuk memvalidasi:

1. Telusuri receiving dan item sumber, termasuk nilai dan kuantitas yang diterima.
2. Cocokkan item receiving dengan invoice lines dan status posting invoice.
3. Pisahkan sisa yang belum diinvoicing dari ketidaksesuaian nilai atau jurnal.
4. Bandingkan outstanding source tersebut terhadap GL AP Suspense pada tanggal/scope yang sama.

Receiving yang sudah penuh diinvoicing tetapi masih meninggalkan selisih perlu ditelusuri; receiving yang memang menunggu invoice adalah outstanding accrual.

### Supplier invoice dan pajak

Load receiving untuk menggunakan kuantitas, harga, dan dimensi sumber. Periksa invoice supplier, pajak yang benar-benar tercantum, dan total sebelum post.

Taxable flag item tidak cukup untuk menetapkan PPN transaksi. Catatan historis tanpa pajak dan supplier non-PKP tidak boleh dipaksa mempunyai pajak oleh default item. Verifikasi pajak di AP berdasarkan dokumen aktual.

## Payment

1. Pilih supplier dan invoice POSTED yang masih dapat dialokasikan.
2. Periksa jumlah settlement, account funding, work location, dan tanggal.
3. Jika pembayaran berbeda dari saldo invoice, isi alasan yang diperlukan.
4. Pisahkan bank charge dan short/over dari alokasi invoice.
5. Save draft → approve → siapkan/periksa jurnal → post sesuai tindakan yang tersedia.

Total funding memperhitungkan **settlement + bank charge + signed short/over**. Short/over positif menambah cash keluar, negatif menguranginya. Jangan mengubah invoice allocation hanya untuk menyembunyikan biaya bank.

Aplikasi memeriksa payment lain yang sudah menggunakan invoice untuk mencegah pembayaran ganda. Edit payment harus memperbarui ID dokumen yang sama.

| Tindakan | Ketentuan utama |
| --- | --- |
| Edit draft | Sesuai permission dan validasi alokasi aktif |
| Reopen approved | Untuk payment approved yang belum posted; kembali ke draft dan menangani jurnal terkait |
| Void | Draft atau approved yang belum posted |
| Unpost posted | Akses administrator dan pemeriksaan period/source |
| Cancel posted | Administrator; unpost dan void terkoordinasi, menyimpan riwayat |

Jangan hanya mengubah status jurnal lewat SQL. Pembatalan payment harus menangani paid amount, allocation, status sumber, jurnal, dan GL bersama-sama. SQL repair historis bukan pengganti tombol lifecycle aplikasi.

AP-role biasa hanya melihat payment yang dibuatnya sendiri; scope lain tetap mengikuti hak akses server.

## Journal Entry manual

Satu jurnal adalah **satu header dengan beberapa baris akun**, bukan satu pasangan dua baris yang harus bersebelahan. Nomor jurnal resmi dihasilkan sistem; nomor dokumen adalah referensi sumber/pengelompokan.

Isi posting date, document number, description, unit/location, lalu account, line department jika diperlukan, debit atau credit, dan line description.

Manual entry dapat menyimpan keadaan tidak seimbang sesuai aturan aplikasi. Sistem tidak menciptakan balancing line. Jurnal otomatis dari dokumen sumber tetap mempunyai pemeriksaan keseimbangan. Statistik bukan akun finansial untuk jurnal/GL.

Copy journal ditujukan untuk journal entry manual, bukan untuk menggandakan journal sumber receiving/payment/closing.

Account revenue tidak dikunci hanya pada literal nomor 400. Persyaratan active posting account, type, normal balance, permission, dan hierarchy tetap berlaku. Penyajian ringkas Pendapatan di laporan bukan alasan untuk mengubah histori akun.

## Bulk import journal

Download template terbaru dari aplikasi. Kolomnya:

| Kolom | Isi |
| --- | --- |
| posting_date | Tanggal jurnal |
| document_number | Pengelompokan satu dokumen jurnal |
| description | Deskripsi header |
| business_unit_code | Opsional bila dapat diinferensikan dari lokasi |
| location_code | Kode lokasi kerja yang diizinkan |
| line_department_code | Department tiap baris; opsional |
| account_code | Nomor active posting account |
| line_description | Deskripsi baris |
| debit / credit | Satu sisi positif per baris |

Ulangi document_number untuk baris milik jurnal yang sama, walaupun terpisah oleh dokumen lain. Header kosong melanjutkan jurnal sebelumnya. File tanpa document number diperlakukan sebagai satu jurnal dengan nomor import yang dihasilkan sistem.

**journal_group tidak diperlukan pada template baru.** Template lama tetap dapat dibaca. Department baris kosong tetap unassigned, tidak menyalin department baris sebelumnya.

Import memvalidasi jumlah debit dan credit **per dokumen lengkap**, bukan pasangan baris berdekatan. Jalur bulk import saat ini tetap menolak dokumen yang tidak seimbang. Ini berbeda dari kelonggaran manual entry; tidak ada balancing line otomatis pada keduanya.

Periksa hasil validasi, perbaiki baris error, lalu pilih import draft atau posting sesuai izin dan period. Worker memproses file di EC2 dan menyimpan audit batch/baris.

## Reconciliation

Halaman reconciliation adalah overview module: source balance, GL balance, difference, dan akses ke modul detail. Akun dapat dibuka ketika diperlukan. Koreksi tetap dilakukan di modul sumber atau melalui tindakan finance yang dapat ditelusuri.

| Area | Sumber pembanding |
| --- | --- |
| AP | Opening, posted invoice, payment, dan adjustment |
| AP Suspense | Receiving yang belum diselesaikan invoice |
| Inventory | Nilai stock, movement yang dicosting, dan inventory GL |
| AR | Subledger receivable jika mapping dan sumber tersedia |

Bandingkan tanggal, unit, lokasi, department, dan status posting yang sama. Tidak configured atau tidak available bukan nol yang sudah terverifikasi.

## AR, cashier, dan petty cash

AR mencakup customer invoice, penerimaan pembayaran, dan saldo piutang. Template client seperti PHR dipilih sesuai konfigurasi customer; periksa hasil preview dan export.

General Cashier dan Petty Cash tersedia pada Finance. Gunakan jenis transaksi, account, dimensi, dan sumber yang tepat. Jangan mencatat sumber yang sama lagi sebagai jurnal manual jika sudah diposting oleh modul asal.

SELL service charge disimpan sebagai snapshot rate/amount transaksi dan dipisahkan dari pajak. Mengubah master tidak menulis ulang snapshot penjualan lama.

## Fixed assets dan amortization

Barang BUY FIXED_ASSET terhubung ke Item Master dan register:

- **PENDING_REGISTRATION**: registrasi dari master belum mempunyai data perolehan lengkap.
- **PENDING_SETUP**: aset sudah mempunyai sumber perolehan tetapi setup belum lengkap.
- Pengaktifan memerlukan data organisasi, perolehan, category, dan kebijakan yang sesuai.

Mendaftarkan master tidak otomatis menciptakan biaya perolehan, saldo awal, depresiasi, atau jurnal pembelian kedua.

### Category dan aktivasi

Pilih account aset, kebijakan depreciable/non-depreciable, useful life, accumulated depreciation, dan expense. Akun tangible umumnya dari 100-600; operating equipment dari 100-900. Tanah biasa menggunakan kebijakan non-depreciable.

Category yang sudah digunakan tidak menulis ulang snapshot aset. Untuk perubahan kebijakan/account setelah digunakan, buat category terpisah sesuai batasan aplikasi.

Aktivasi tanpa acquisition journal adalah default. Sumber yang telah dicatat melalui invoice/receiving tidak boleh diposting sebagai acquisition dua kali. Acquisition cost bukan harga referensi Item Master.

### Depresiasi, amortisasi, transfer, disposal

Depresiasi straight-line dihitung per bulan. Tanggal mulai hari pertama masuk bulan tersebut; tanggal selain hari pertama mulai bulan berikutnya. Tidak ada prorata harian. Bulan terakhir menyerap pembulatan sampai residual value.

Buat run per unit dan lokasi, calculate, review, lalu post. Bulan outstanding sebelumnya harus diselesaikan terlebih dahulu. Unpost latest memerlukan period terbuka dan tidak boleh melewati aktivitas lanjutan yang menghalangi.

Amortization memakai actual cost, start date, dan useful life. Prepaid cost 100-400 dapat mengcredit akun aset yang sama; intangible lain menggunakan accumulated account yang sesuai. Tangible assets tetap menggunakan Fixed Assets.

Transfer dapat memindahkan cost dan accumulated depreciation antardimensi; physical register-only adalah pilihan eksplisit. Disposal/write-off menghapus cost dan accumulated depreciation serta mencatat proceeds/gain/loss bila berlaku. Histori cost tetap tersedia.

## Closing otomatis

Menutup period membuat jurnal penutup per unit/location/department pada tanggal akhir period dan memindahkan hasil ke akun current-year earnings yang dikonfigurasi. Period kemudian dikunci. Period kosong tidak menghasilkan jurnal nol.

Reopen melalui proses period membatalkan jurnal penutup dan efek GL terkait dengan audit tetap tersedia. Jurnal penutup tidak di-unpost manual. P&L mengecualikan closing journals agar aktivitas operasional tidak hilang dari laporan.

Closing tidak mengoreksi opening balance yang tidak seimbang.
