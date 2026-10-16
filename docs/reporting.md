# Laporan dan dashboard

[Kembali ke dokumentasi](README.md)

## Pilih scope dahulu

Gunakan tombol unit **Hotel / Catering / Consolidated**. Location dan department hanya menampilkan scope yang diizinkan; export mengikuti pemeriksaan akses yang sama.

| Unit | Pemisahan laporan |
| --- | --- |
| Hotel | Department |
| Catering | Work location |
| Consolidated | Gabungan scope yang diizinkan |

Tanggal dan scope harus sama ketika membandingkan laporan, drilldown, dan reconciliation. Dimensi pada journal line mengoverride header; bila tidak ada override, header menjadi sumber dimensi. Opening yang tidak dipetakan ke unit/lokasi tidak dibagi rata secara otomatis.

## Profit & Loss

Halaman utama menyajikan satu statement, tanpa tabel department terpisah di bawahnya. Penyajian manajemen mencakup:

1. Pendapatan.
2. HPP.
3. Gaji operational.
4. Beban operational.
5. Gross Operating Income, profit/loss.
6. Gaji overhead.
7. Beban overhead.
8. GOP/GOL.
9. Under expense.
10. NOP.

Kelompok dan subtotal mengikuti mapping report. Label akun saja tidak menggantikan mapping yang benar. Klik baris untuk membuka account drilldown, termasuk akun terkait bernilai nol. Klik nilai akun untuk menelusuri ledger dengan scope periode yang sesuai.

P&L menggunakan aktivitas periode dan mengecualikan journal closing. Opening neraca bukan pendapatan tahun berjalan.

## Perbandingan periode

| Ukuran | Makna |
| --- | --- |
| MTD current | Aktivitas bulan terpilih sampai cutoff |
| YTD current | Aktivitas dari awal tahun sampai cutoff |
| Budget | Target sesuai budget dan scope yang dipilih |
| Last month | Pembanding bulan sebelumnya dengan cutoff setara |
| Last year | Pembanding periode tahun sebelumnya dengan cutoff setara |

Cutoff pembanding disesuaikan untuk bulan yang lebih pendek. P&L budget merupakan target bulanan penuh. Data pembanding tanpa evidence atau budget yang belum tersedia ditampilkan sebagai dash/blank, bukan nol buatan. Nol berarti nilai yang dihitung memang nol.

## Balance Sheet / Neraca

Neraca menampilkan aset di satu sisi dan liabilities/equity di sisi lain. Saldo dihitung dari opening tahunan manual dan aktivitas posted sampai tanggal laporan.

Credit-normal contra asset mengurangi aset. Hasil tahun berjalan ditampilkan tanpa menggandakan akun/hasil yang sama. Drilldown menggunakan identitas akun yang tepat; gunakan link yang disediakan untuk menelusuri sumber nilai.

Print mendukung KAP header summary dan rincian sesuai pilihan laporan. Akun yang tidak ditampilkan karena setup bukan berarti saldo dikeluarkan dari kontrol total.

Neraca tidak membuat equity otomatis untuk menutupi selisih. Jika total berbeda, telusuri opening, scope, dan transaksi.

## Trial Balance dan General Ledger

Trial Balance memisahkan opening, prior activity bila rentang dipersempit, period debit/credit, dan closing. Opening 2026 adalah closing 2025, bukan akumulasi ulang transaksi Januari–September.

General Ledger menyediakan pencarian dan account selection/range. Header tabel tetap terlihat ketika digeser. Filter supplier pada Journal dan full filtered totals digunakan untuk melihat seluruh hasil filter, bukan hanya halaman aktif.

Status abnormal menguji arah saldo per akun; difference keseluruhan adalah pemeriksaan terpisah.

## Excel dan print

| Output | Isi utama |
| --- | --- |
| P&L Excel | Summary pada sheet awal; detail akun per department Hotel atau per lokasi Catering |
| Neraca Excel | Ringkasan dan detail sesuai scope, termasuk sheet organisasi yang disediakan |
| Opening Balance Excel | Nilai opening yang diinput pada Finance Setup |
| Print laporan | Judul, periode, scope, kolom, subtotal, dan total sesuai layout |

Detail P&L menyertakan akun terkait meskipun nol. Export menggunakan scope laporan, bukan sekadar data yang kebetulan terlihat pada satu halaman tabel.

Preview sebelum print; periksa nama unit, periode, dan organisasi. Total dan angka harus tetap mudah dibandingkan pada satu baris.

## Budget Input

Menu **Finance → Budget Input** menyediakan budget bulanan per account dan dimensi. Save draft, submit, dan approval mengikuti tindakan yang tersedia. Budget approved/locked digunakan pada comparison.

Jika beberapa budget overlap, pilih plan secara eksplisit. Missing budget tidak diperlakukan sebagai actual nol. Target balance sheet adalah saldo month-end, bukan penjumlahan saldo seluruh bulan.

## Statistics

Header **900 Statistik** menggunakan type internal **STATISTIC**, dengan label UI **Statistical**. Header bukan posting account.

Statistical actual dan budget adalah ukuran nonfinansial yang dikelola terpisah dari journal/GL, misalnya ukuran operasional untuk analisis manajemen. Jangan memasukkannya sebagai nilai uang pada neraca atau P&L.

## Dashboard dan Executive View

Dashboard utama mendukung ringkasan pekerjaan dan operasional sesuai akses. Analisis pembelian mencakup item dan supplier menurut periode, jumlah pembelian, dan biaya, jika tersedia pada scope.

**Executive View** adalah menu tersendiri untuk ringkasan owner: posisi, pendapatan, biaya, hasil operasional, dan pembanding. Ini dashboard ringkas, bukan pengganti rincian financial statement. Akses tetap menggunakan permission reports/finance yang diterapkan aplikasi.

## Checklist sebelum membagikan laporan

- Unit, tanggal, location, dan department benar.
- Actual berasal dari sumber POSTED dan opening yang dimaksud.
- Budget serta pembanding unavailable tidak dibaca sebagai nol.
- Detail akun menjelaskan subtotal.
- Data drilldown dan export memakai scope yang sama.
- Selisih yang ditemukan ditelusuri, bukan dihilangkan lewat display setting.
