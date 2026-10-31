# Troubleshooting alpha.1

| Gejala | Pemeriksaan dan tindakan |
|---|---|
| `Database belum dimigrasi` | Jalankan `tools/dev.py --prepare-only`, atau tunggu service bootstrap Compose berhasil. Jangan memakai `metadata.create_all` untuk melewati migration. |
| Port 8000/5173 digunakan | Hentikan supervisor SUBAKO sebelumnya dengan Ctrl+C; periksa PID yang menggunakan port. Jangan hentikan proses lain tanpa mengetahui pemiliknya. |
| Login gagal | Gunakan email `@demo.subako.local` dan password dari file environment yang sama. Password SQLite lokal dan Compose berbeda. Seed tidak mereset akun yang sudah ada. |
| Origin/CSRF ditolak | Buka URL loopback yang didokumentasikan. Untuk host lain, konfigurasi origin secara eksplisit; jangan memakai wildcard. Reload sesi setelah rotasi cookie. |
| Terlalu banyak login | Tunggu sedikitnya satu menit; login rate limit berlaku per akun/IP dan IP aggregate. Jangan menonaktifkan limiter untuk memperbaiki kredensial salah. |
| Viewer hanya melihat satu site | Ini grant seed yang disengaja untuk membuktikan site isolation. Gunakan akun lain untuk mengevaluasi dua lokasi. |
| Nilai `—` | Periksa quality, freshness dan scenario simulator. BAD/MISSING/FROZEN tidak ditampilkan sebagai nol. |
| FAULT tetap tampil | Lihat skenario admin pada Perangkat. Mengakui alert tidak mengubah mode. Pemulihan fake device hanya melalui skenario Normal; tidak ada fault reset hardware. |
| WebSocket terputus | UI memakai GET polling cadangan. Periksa `/ws` proxy, origin, session expiry dan site grant. Rilis ini satu API worker. |
| Reload offline kosong pada build lama | Muat build baru saat online. Worker saat ini mencocokkan public precache assets tanpa `Vary: Origin`; API tetap network-only. Bila menguji upgrade, tutup tab lama lalu buka lagi. |
| Backend tidak kembali setelah offline | Tunggu GET bootstrap sesi (hingga ±5 detik saat server tidak tersedia), atau muat ulang saat koneksi pulih. Tidak ada POST otomatis dari recovery. |
| PWA tidak menawarkan instalasi | Gunakan build produksi, bukan Vite dev, dan secure context/localhost. Periksa manifest/icon/service worker pada DevTools. Dukungan browser berbeda. |
| `timescaledb` extension tidak tersedia | Gunakan image TimescaleDB yang dikunci. PostgreSQL tertanam untuk tes hanya menjalankan revision 0001/0002; jangan memalsukan keberhasilan revision 0003. |
| Compose bootstrap gagal | Periksa log bootstrap tanpa mencetak secret. Pastikan secret files ada dan image/platform tersedia. Jangan hapus volume untuk menyembunyikan migration error. |
| Ledger MISMATCH | Simpan bukti dan hentikan asumsi integritas. Jangan mengubah entry/hash secara manual. Bandingkan backup/anchor dan lakukan investigasi; koreksi normal nantinya memakai compensation. |

Untuk pelaporan bug, sertakan versi aplikasi, route, waktu WITA, environment SIMULATION, request ID dan langkah reproduksi. Jangan menyertakan password, cookie, `.env`, DSN, atau isi secret files.
