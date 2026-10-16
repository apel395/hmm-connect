# Purchasing dan inventory

[Kembali ke dokumentasi](README.md)

## Item Master

Hotel Items dan Catering Items adalah katalog terpisah. Barang BUY dipisahkan dari item SELL. Item yang dibeli sebagai aset tetap tetap harus ada di BUY Item Master, lalu terhubung ke register Fixed Assets.

Urutan setup:

1. Pilih katalog dan jenis item yang benar.
2. Pilih group dan subgroup yang sudah disepakati. Kode item dipreview setelah pilihan tersebut; server mengalokasikan kode ketika save.
3. Isi nama dan unit/UOM. Pengguna dapat mengetik unit yang dibutuhkan; konversi antarunit tetap perlu konsisten.
4. Tentukan treatment dan pemetaan akun terkait.
5. Isi referensi harga dan tax profile sebagai referensi, bukan bukti pajak transaksi.

Harga referensi dapat berasal dari pembelian terakhir atau rata-rata dan dapat disesuaikan saat PO/receiving. Harga tersebut tidak otomatis menjadi nilai perolehan aset atau saldo stock.

| Treatment | Tujuan | Dampak fisik |
| --- | --- | --- |
| STOCK | Persediaan pada warehouse sesuai lokasi | Kuantitas dan nilai gudang berubah pada proses posting |
| DIRECT_USE | Pemakaian langsung ke department/expense | Tidak membuat warehouse IN/OUT |
| FIXED_ASSET | Akuisisi aset dan register | Mengikuti integrasi aset, bukan pemakaian stock biasa |

Barang seperti sayuran atau makanan siap konsumsi tidak boleh dikelompokkan sebagai furniture hanya karena kode lama. Klasifikasi harus mengikuti identitas dan penggunaan barang. Perubahan master tidak otomatis memperbaiki histori stock/jurnal yang sudah diposting.

## Rantai dokumen

~~~mermaid
flowchart TD
  PR["Purchase Requisition"] --> PO["Purchase Order"]
  ML["Market List disetujui"] --> PO
  ML --> RR["Receiving"]
  PO --> RR
  RR --> SI["Supplier Invoice"]
  SI --> PAY["Payment"]
~~~

Market List dapat diterima langsung tanpa membuat PO tambahan. Supplier dan organisasi sumber tetap harus jelas. Alokasi kuantitas ML dibagi dengan PO yang belum dibatalkan dan direct receiving agar tidak diterima dua kali.

## PR, ML, dan PO

**PR** mencatat kebutuhan dari pemohon/department. **ML** melayani pembelian market list. **PO** mencatat pesanan supplier, harga, kuantitas, dan estimasi pengiriman.

PR/ML/PO mengikuti approval yang dikonfigurasi. PO dari PR tidak boleh bertanggal sebelum request PR; tanggal yang sama diperbolehkan.

Saat membuat PO:

1. Pilih sumber jika berasal dari PR atau ML.
2. Periksa supplier, unit, lokasi, department, dan estimasi pengiriman.
3. Periksa item, UOM, kuantitas, referensi harga, dan harga yang disepakati.
4. Save, submit, dan selesaikan approval.
5. Gunakan sisa pesanan sebagai dasar receiving.

Riwayat harga membantu pembanding; pengguna tetap bertanggung jawab atas harga dokumen yang disimpan.

## Receiving normal

Calon receiving dari PO memperlihatkan estimasi pengiriman dan sisa item. Kuantitas dari PO dibatasi oleh sisa yang diizinkan, termasuk toleransi yang berlaku.

1. Pilih PO atau ML yang memenuhi syarat, atau sumber yang didukung.
2. Periksa supplier dan dimensi sumber.
3. Tujuan setiap baris otomatis mengikuti treatment Item Master. Ikon Special Case pada baris dapat mengubah Warehouse/Direct Use untuk kondisi khusus, disertai alasan. Pilihan tersebut hanya berlaku pada penerimaan ini dan tidak mengubah master. Untuk Direct Use, periksa department dan akun expense tujuan.
4. Warehouse receiving memerlukan warehouse pada work location yang sama.
5. Simpan dan submit. **Receiving normal mengambil tanggal server saat submit**, dengan tanggal bisnis Asia/Jakarta.
6. Selesaikan approval oleh **dua approver berbeda**.
7. Jalankan tindakan posting sesuai permission dan alur finance.

Posting receiving dan posting jurnal sumber adalah tahap yang perlu dilihat terpisah. Integrasi receiving dapat menyiapkan jurnal DRAFT; pastikan status jurnal sumber sebelum menganggap nilai sudah masuk GL.

## Historical Entry

Historical Entry mencatat penerimaan lama yang sah sejak **1 Januari 2026** dan sebelum hari ini. Memerlukan permission receiving.post, tanggal yang pasti, serta accounting period terbuka sesuai kebijakan backdate.

Alur khususnya adalah **Draft → Post**, tanpa approval receiving normal. Ini bukan cara melewati period yang sudah ditutup. Receiving tahun 2025 tetap tidak dimasukkan.

Tanggal invoice historis dapat mendahului atau mengikuti kedatangan barang. Saat seed, tanggal atau mapping yang belum jelas harus dilaporkan; jangan menebak supplier, unit conversion, atau lokasi.

## Tax dan invoice supplier

Tax profile item adalah referensi. Receiving tidak boleh memaksa PPN hanya karena item ditandai taxable. Bukti dan jumlah pajak aktual diverifikasi di AP/Supplier Invoice. Jika catatan historis tidak mencantumkan pajak, jangan menciptakan angka pajak.

Supplier non-PKP tidak otomatis diperlakukan sebagai pemungut PPN. Pastikan tax treatment transaksi mengikuti dokumen yang tersedia.

## Stock dan Stock Movement

Stock menampilkan saldo kuantitas, average cost, dan nilai. Gunakan warehouse, akun inventory, item, serta rentang tanggal sesuai kebutuhan. Account total membantu mencocokkan nilai persediaan.

Stock Movement adalah histori item:

| Kolom | Arti |
| --- | --- |
| Item code / name | Identitas barang pada kolom terpisah |
| Event | IN atau OUT |
| Source document | Dokumen penyebab movement |
| Quantity | Kuantitas event |
| Cost / value | Nilai yang terkait event |
| Remaining | Saldo berjalan item per warehouse |

Remaining dihitung dari histori lengkap; menyempitkan filter tanggal/sumber tidak mengulang saldo dari nol. Buka stock card untuk penelusuran item dan warehouse.

Stock age dan age class tidak ditampilkan di daftar Stock utama. Analisis aging memperkirakan sisa lapisan FIFO: fast sampai 30 hari, slow setelahnya sampai enam bulan kalender, dead lebih dari enam bulan. Ini estimasi umur stock, bukan bukti lot fisik atau ukuran frekuensi penjualan. Pembelian baru tidak menghapus umur sisa barang lama.

## Store Request dan pengeluaran gudang

Request Date adalah tanggal permintaan; Issue Date adalah tanggal barang benar-benar dikeluarkan gudang. Request saja tidak mengurangi stock.

1. Buat request dengan item, kuantitas, department, dan tanggal.
2. Submit dan selesaikan approval.
3. Warehouse memeriksa ketersediaan dan tanggal pengeluaran.
4. Posting Store Issue mengubah stock, jurnal, dan GL dalam transaksi yang sama.

Posting ganda ditolak. Tanggal mundur mengikuti accounting period/backdate policy, bukan bebas diubah setelah barang keluar.

## Stock Opname

Department wajib dipilih. Pengguna dengan lokasi terbatas memasukkan **blind count**: system quantity, nilai cost, dan variance tidak dikirim pada response dan print yang mereka akses. Reviewer yang memiliki akses lokasi tanpa pembatasan dapat melihat pembanding.

Alur: input hasil fisik → submit/approval → review → post.

- Shortage: debit COGS/expense yang dipetakan, credit inventory.
- Surplus: sisi sebaliknya.
- Tidak ada variance: tidak membuat jurnal nol.
- Snapshot stock/cost yang sudah berubah, mapping kosong, atau cost tidak valid dapat menghentikan posting.
- Unpost yang memenuhi syarat mengembalikan stock dan membatalkan dampak GL sumber. Aktivitas stock lanjutan dapat mencegah reversal yang tidak aman.

Print stock opname tidak menampilkan Officer. Blind count juga berlaku pada print.

## Dokumen gagal dan penutupan

Accounting Periods menampilkan dokumen purchasing yang belum selesai. Informasi tersebut tidak otomatis mengoreksi saldo.

Purchasing Reports menyediakan Unfinished/Archive. Arsip hanya berlaku pada dokumen gagal/dibatalkan yang tidak memiliki bukti downstream. Restore mempertahankan status dan audit; archive bukan penghapusan fisik.

## Checklist akhir hari

Periksa receiving yang menunggu approval/posting, jurnal receiving yang masih draft, selisih stock card terhadap stock, issue yang belum diposting, dan dokumen yang belum memiliki supplier invoice. Gunakan source link untuk memeriksa penyebab sebelum membuat koreksi.
