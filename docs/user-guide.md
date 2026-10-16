# Panduan pengguna

[Kembali ke dokumentasi](README.md)

## Login dan sesi

Buka [MMH Connect](https://connect.mutiaramerdekahotel.com) dan login dengan akun yang diberikan administrator. Akun, role, permission, dan lokasi kerja menentukan data yang dapat diakses.

Satu akun mempunyai satu sesi aktif. Login administrator mengakhiri sesi sebelumnya secara otomatis. Pengguna lain yang terputus dapat memilih **Sign in and end previous session** setelah memasukkan kredensial yang benar. Sesi lama tidak dapat menghapus sesi penggantinya.

Jika menu atau lokasi tidak muncul, minta administrator memeriksa permission dan penempatan akun. Jangan menggunakan akun bersama untuk melewati pembatasan lokasi.

## Navigasi dan tampilan

- Desktop menggunakan sidebar ikon yang tetap kecil. Arahkan kursor atau fokus keyboard untuk melihat nama modul.
- Klik ikon modul untuk membuka pilihan submodul; pilih submodul untuk masuk ke halaman.
- Bar atas menampilkan modul aktif dan menu terkait. **Open tabs** menampilkan daftar tab yang bisa dicari.
- **Back** menutup tab aktif dan kembali ke tab sebelumnya. Dashboard tetap tersedia.
- Gunakan menu tab untuk menutup tab lain atau membuka kembali tab terakhir. Shortcut membuka kembali: **Ctrl+Shift+T**.
- Pada layar kecil, gunakan tombol **Open modules** di header.
- Ikon filter membuka pilihan pencarian lanjutan. Gunakan refresh setelah ada perubahan dari pengguna lain.
- Tabel menggunakan baris ringkas. Pada workspace yang mendukungnya, pilihan kolom, kepadatan baris, dan jumlah baris disimpan di browser.
- Header dan kolom identitas tertentu tetap terlihat ketika tabel digeser.

Mengubah filter tidak membuat tab modul baru. Dokumen dengan ID berbeda dapat dibuka sebagai tab tersendiri.

## Memilih unit dan organisasi

Pilih Hotel, Catering, atau Consolidated pada laporan yang menyediakan pilihan unit. Kemudian pilih lokasi atau department yang tersedia. Scope laporan dan export tetap mengikuti akses akun.

| Dimensi | Arti |
| --- | --- |
| Business unit | Kelompok usaha, misalnya Hotel atau Project Catering |
| Work location | Lokasi kerja tempat aktivitas terjadi |
| Department | Bagian yang bertanggung jawab atas aktivitas atau biaya |
| Warehouse | Tempat penyimpanan fisik, terhubung ke lokasi kerja |

Warehouse bukan pengganti department atau work location. Dokumen dan jurnal perlu dimensi organisasi yang sesuai agar laporan per unit benar.

## Memulai pekerjaan

| Pekerjaan | Menu utama | Hasil |
| --- | --- | --- |
| Mengelola barang beli | Master Data → Hotel Items / Catering Items | Klasifikasi, UOM, perlakuan, dan referensi harga |
| Mengajukan pembelian | Purchasing → Purchase Requisition / Market List | Permintaan untuk approval |
| Memesan supplier | Purchasing → Purchase Order | Pesanan dan sisa kuantitas yang dapat diterima |
| Mencatat barang diterima | Purchasing → Receiving | Bukti penerimaan dan proses posting sesuai tujuan item |
| Memeriksa saldo barang | Inventory → Stock / Stock Movement | Saldo, nilai, dan histori IN/OUT |
| Meminta barang gudang | Inventory → Store Request | Permintaan, approval, dan pengeluaran gudang |
| Menghitung fisik | Inventory → Stock Opname | Input hitung, review, dan penyesuaian setelah posting |
| Mencatat invoice supplier | Finance → Accounts Payable | Invoice, saldo utang, dan payment |
| Mencatat jurnal manual | Finance → Journal | Draft dan posting jurnal sesuai akses |
| Melihat laporan | Reports | Neraca, laba rugi, arus kas, serta laporan operasional |
| Melihat ringkasan owner | Executive View | Ringkasan kinerja dan posisi keuangan |

## Draft, submit, approve, dan post

**Save draft** menyimpan dokumen. **Submit** mengirim ke alur approval. **Approve** menyatakan persetujuan sesuai langkah yang berlaku. **Post** menjalankan dampak operasional atau akuntansi sesuai jenis dokumen.

Tidak semua dokumen menggunakan status dan tombol yang sama. Ikuti tindakan yang tersedia pada dokumen; tombol disediakan berdasarkan status, permission, dan dependency. Jangan menganggap status APPROVED selalu berarti GL sudah terbentuk.

Approval Center mengumpulkan dokumen yang memerlukan keputusan pengguna. Periksa sumber, jumlah, tanggal, dan dimensi sebelum menyetujui. Riwayat approval tetap melekat pada dokumen.

## Input yang belum disimpan

Form yang mendukung draft recovery, seperti journal dan beberapa form finance, menyimpan input lokal per akun dan dokumen. Jika form tertutup tanpa sengaja, buka kembali untuk memulihkan input. Save berhasil atau tindakan discard menghapus recovery terkait.

Recovery bukan dokumen tersimpan di server dan tidak menjalankan submit atau post otomatis. Jangan mengandalkannya untuk seluruh form atau setelah data browser dibersihkan.

## Print dan Excel

Gunakan tombol aplikasi agar scope, format, dan penomoran print sesuai dokumen. Purchasing print menampilkan creator, waktu pembuatan, approver dan waktu persetujuan, serta ruang tanda tangan.

Print count menghitung permintaan print aplikasi. Membatalkan dialog browser tetap dapat menghitung satu permintaan. Preview tidak menambah hitungan; Ctrl+P di luar aplikasi tidak termasuk tracking.

Export dapat diproses oleh worker. Tunggu sampai file siap; jika gagal, catat nomor job atau pesan error untuk administrator.

## Jika ada masalah

| Gejala | Langkah pertama |
| --- | --- |
| Tidak bisa login karena sesi aktif | Gunakan penggantian sesi pada halaman login |
| Menu atau tombol hilang | Periksa role, permission, lokasi, dan status dokumen |
| Tanggal lama ditolak | Periksa accounting period dan pengaturan backdate; gunakan Historical Entry jika sesuai |
| Invoice sudah mempunyai payment draft lain | Buka, edit, atau void payment yang sudah ada; jangan membuat duplikat |
| Laporan kosong | Periksa unit, tanggal, lokasi, department, serta status POSTED sumber |
| Nilai source berbeda dengan GL | Buka Reconciliation dan lanjutkan ke modul sumber |
| Item tidak ditemukan | Periksa Hotel/Catering, BUY/SELL, filter aktif, serta kode dan nama |

Saat melaporkan masalah, sertakan nomor dokumen, langkah, tanggal/scope, pesan error, dan screenshot yang relevan.
