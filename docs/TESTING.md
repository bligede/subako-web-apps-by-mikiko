# Hasil verifikasi alpha.1

Verifikasi lokal terakhir: **31 Oktober 2026, WITA**. Ini hasil implementasi foundation SIMULATION, bukan penerimaan seluruh SUBAKO v0.1 atau commissioning perangkat lapangan.

| Pemeriksaan | Hasil | Bukti |
|---|---|---|
| Backend SQLite + PostgreSQL nyata | **27 passed**, 0 failed, 0 skipped; 33,11 detik | [JUnit](../evidence/backend-junit.xml) |
| Browser end-to-end | **15 pemeriksaan lulus** | [Laporan JSON](../evidence/e2e-results.json) |
| Responsive runtime | **21 kasus lulus**, 7 halaman × lebar 360/390/768 px | Tercakup dalam laporan E2E |
| Build frontend | Lulus TypeScript dan Vite production build | Build tersedia dalam paket rilis |
| Kontrak API aktual | **22 operasi HTTP**; WebSocket site-scoped terpisah | [OpenAPI](../evidence/openapi-implemented.json) |

## Cakupan backend

Tes mencakup session rotation/logout, Origin dan CSRF, rate limit, akun nonaktif, permission dan akses lintas site yang ditolak, acknowledgement idempotent, penolakan mode LIVE, histori/pagination, validasi telemetry, sequence wrap, duplicate/conflicting event, observasi lama yang tidak menimpa latest, tujuh kondisi simulator, append-only ledger dan deteksi perubahan, serta pembatasan WebSocket dan pencabutan sesi.

Tiga tes PostgreSQL memakai server PostgreSQL nyata dari `pgserver`, bukan SQLite yang menyerupai PostgreSQL. Migrasi `0001/0002`, role `subako_api`/`subako_ingest`, default-deny RLS, reset context per transaksi, permission database, transaksi API/simulator, serta delapan append ledger konkuren diverifikasi. Extension TimescaleDB tidak disertakan dalam server pengujian ini.

Satu warning nonfatal berasal dari deprecation integrasi httpx pada Starlette TestClient; tidak ada tes yang dilewati. Dependency test dicatat dalam `apps/api/requirements-test.lock`.

## Cakupan browser

Chrome menjalankan frontend hasil build dan backend dengan database sementara serta password fixture acak. Tes melakukan login nyata, menerima beberapa event WebSocket setelah commit, mengganti site, membuka detail pintu, memverifikasi chain ledger, menyimpan acknowledgement, memeriksa akun viewer, dan menerapkan skenario overcurrent sebagai admin teknis.

Service worker diperiksa agar hanya menyimpan sembilan resource statis. Respons API/session tidak masuk Cache Storage. Saat offline, data yang masih ada di memory diberi penanda dan status koneksi menua secara lokal sampai OFFLINE; hitungan perangkat terhubung turun. Reload dingin offline membuka shell/login. Reconnect memulihkan GET/WS tanpa replay POST. Mode operasi terakhir tetap dilabeli sebagai data terakhir, bukan dianggap berubah akibat putus jaringan.

E2E mempercepat simulator menjadi 1 detik, STALE 3 detik dan OFFLINE 6 detik agar transisi dapat diuji. Konfigurasi lokal normal memakai interval 10 detik, STALE 30 detik dan OFFLINE 90 detik. Manifest, ikon dan service worker aktif diperiksa; dialog pemasangan PWA pada setiap OS belum diuji.

Contoh bukti visual: [dashboard](../evidence/desktop-dashboard.png), [offline](../evidence/desktop-offline.png), [simulator fault](../evidence/desktop-simulator-fault.png), [mobile](../evidence/mobile-dashboard.png). Screenshot berasal dari data simulasi fixture.

## Batas verifikasi

- Docker CLI tersedia, tetapi plugin Compose tidak tersedia dan engine Docker tidak aktif pada host kerja. Docker build, `docker compose config/up`, migrasi Timescale `0003` dan backup/restore Timescale **belum dieksekusi**. Berkas Compose bukan bukti bahwa stack tersebut sudah lulus integrasi.
- Pengujian PostgreSQL biasa tidak membuktikan kompatibilitas hypertable Timescale, performa jangka panjang, kapasitas atau RPO/RTO.
- MQTT, ChirpStack, firmware bridge, HMAC/signing, command/ACK perangkat dan hardware belum diaktifkan atau diuji oleh aplikasi ini.
- Review security staging, account recovery/MFA, seal ledger independen dan uji lapangan pengguna tetap pekerjaan berikutnya.
- Tidak ada klaim cache API persisten atau kemampuan menulis saat offline. Mutasi memerlukan koneksi dan tidak diantrikan untuk replay.

## Ulangi tes

Ikuti perintah pengujian pada [README](../README.md). Simpan JUnit dengan `python -m pytest -q apps/api/tests --junitxml=evidence/backend-junit.xml`. E2E membutuhkan build terbaru dan Chrome/Edge, atau executable Chromium melalui `CHROME_PATH`. Runner membersihkan proses miliknya, sedangkan fixture database tetap terisolasi dalam `.local/` yang diabaikan Git.

Pemeriksaan paket, dependency, backup/restore SQLite dan health aplikasi lokal dicatat terpisah dalam [release-checks.json](../evidence/release-checks.json). Laporan ini tidak memuat password atau salinan database.
