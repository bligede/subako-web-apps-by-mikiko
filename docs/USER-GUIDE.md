# Panduan pengguna alpha.1 — SIMULATION

## Masuk dan konteks data

Buka URL yang dicetak `tools/dev.py` atau Compose. Masuk dengan akun demo dan password lokal yang dibuat saat setup. Tidak ada pemilih role yang mengganti izin di browser. Untuk meninjau role lain, keluar lalu masuk menggunakan akun tersebut. Identitas dan site access diverifikasi backend.

Semua halaman menampilkan **SIMULATION**. Angka berasal dari fake devices yang menghasilkan telemetry, bukan perangkat fisik di Bali. Waktu UI menggunakan WITA; UTC tetap digunakan dalam API dan database.

## Dashboard dan monitoring

Pilih lokasi dari topbar. Dashboard menghitung KPI dari node ONLINE dengan quality yang sesuai. Nilai tidak tersedia ditampilkan `—`, bukan nol. Klik Muka air/Debit untuk mengganti grafik; rentang 12/24 jam mengambil histori dari server. Tombol Unduh CSV mengekspor ringkasan SIMULATION yang sedang terlihat, bukan laporan distribusi air sah.

Label **Terhubung** menunjukkan WebSocket aplikasi. Label ONLINE/STALE/OFFLINE pada perangkat berasal dari usia telemetry, sehingga keduanya berbeda. Mode AUTO/MANUAL/HOLD/FAULT tetap nilai terlapor, bukan status yang ditebak dari koneksi.

Monitoring memakai skema jaringan ilustratif, bukan peta hasil survei. Klik node atau tombol detail untuk membaca kualitas, firmware, baterai, RSSI/SNR dan timestamp. Detail pintu tidak menyatakan interlock fisik aman karena bukti itu belum tersedia pada foundation.

## Peringatan

Buka Peringatan untuk membaca evidence dan rekomendasi. Operator/Pekaseh/admin yang berhak dapat memilih Akui peringatan, mengisi catatan dan menyimpan acknowledgement. Backend merekam identitas, site dan audit. Viewer hanya membaca.

Acknowledgement tidak mengirim ACK_FAULT, tidak mereset fault, dan tidak menggerakkan motor. Workflow assigned owner/resolution belum tersedia pada alpha.1; alert yang telah diakui tetap dihitung sebagai belum selesai.

## Buku Air

Buku Air menampilkan event simulasi yang append-only dengan previous/current SHA-256. Buka detail hash untuk melihat bukti raw/device bila tersedia. Verifikasi integritas menghitung rantai pada backend. VERIFIED berarti cocok terhadap head database saat ini; independent sealing dan bukti edge ledger belum diimplementasikan. Tidak ada edit/delete normal di UI/API.

Tidak ada angka volume aktual yang disimpulkan dari bukaan pintu. Hak distribusi/Paruman dan aturan operasional nyata belum diterbitkan oleh foundation.

## Lab simulasi — admin teknis

Masuk sebagai admin, buka Perangkat dan pilih kondisi Normal, Sensor error, Device offline, Baterai rendah, Overcurrent, Posisi tidak sesuai, atau Gangguan komunikasi. Terapkan skenario dan tunggu satu interval simulator (default 10 detik). Kondisi offline berhenti menghasilkan telemetry; sensor BAD menampilkan nilai kosong; overcurrent/mismatch menghasilkan mode FAULT dari fake device.

Ini perubahan skenario SIMULATION, bukan command hardware. Pilih Normal untuk memulihkan fake device; histori dan peringatan sebelumnya tetap disimpan.

## PWA dan offline

Build produksi menyertakan manifest dan ikon. Pada browser yang mendukung, gunakan menu Instal aplikasi/Tambah ke layar utama; pengaturan menampilkan tombol instal bila event browser tersedia. HTTPS diperlukan di deployment biasa; localhost dapat dipakai untuk pengembangan.

Saat koneksi hilang, sesi yang masih terbuka menampilkan data terakhir di memory dan banner OFFLINE/STALE. Tindakan dinonaktifkan. Reload offline membuka shell dengan penjelasan koneksi; data akun/API tidak dipersistenkan. Setelah koneksi pulih, aplikasi mengambil sesi/data melalui GET dan berlangganan kembali ke WebSocket. Tidak ada antrean mutation untuk dikirim otomatis.

Keluar saat terhubung untuk mencabut sesi dan menghapus query cache. Push permission tidak diminta pada alpha.1.

## Batas tahap ini

Alokasi/approval aturan, command aktuasi, MQTT/ChirpStack, full user management, report PDF/XLSX dan LIVE commissioning belum tersedia. Rilis ini dapat dipakai untuk evaluasi foundation dan pelatihan awal pada data simulasi.
