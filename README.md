# SUBAKO Web-PWA · 0.1.0-alpha.1

**by Mikiko Technology · Foundation + dashboard dengan simulated telemetry**

Implementasi ini melanjutkan paket arsitektur Revisi A yang telah disetujui dan tersedia sebagai artefak terpisah. Catatan persetujuan ada di [docs/APPROVAL.md](docs/APPROVAL.md). Source firmware dan engineering baseline dipertahankan.

## Yang sudah bekerja

- Frontend React/TypeScript/Vite, Tailwind, React Router, TanStack Query, Zod, Recharts; tampilan Bahasa Indonesia dan waktu WITA.
- Backend FastAPI, SQLAlchemy, Alembic; REST API dan OpenAPI aktual di `/docs`.
- Login, logout, rotasi sesi cookie HttpOnly, CSRF/Origin protection, rate limit login, Argon2 password hash, permission dan site isolation di backend.
- PostgreSQL runtime roles API/ingestion terpisah, RLS site-scoped, constraints dan append-only triggers. SQLite hanya untuk pengembangan lokal.
- Dashboard, filter site, monitoring, histori grafik, detail pintu/perangkat, peringatan + acknowledgement, Buku Air + verifikasi hash chain, daftar pengguna teknis.
- Simulator dengan tujuh kondisi; pembaruan WebSocket dan GET polling cadangan. Nilai SIMULATION tidak ditampilkan sebagai data lapangan.
- Manifest, ikon 192/512, service worker shell-only, status offline/STALE. Tidak ada API/session cache atau mutation queue offline.
- Compose untuk TimescaleDB, migrasi/seed, FastAPI dan Nginx frontend. Image digest dan dependency versi dikunci.

Foundation belum mengaktifkan LIVE, command aktuasi, signing/HMAC, MQTT/ChirpStack, approval aturan/entitlements, report PDF/XLSX, independent daily ledger seals, push notification, atau manajemen akun lengkap. Itu tetap tahap implementasi selanjutnya. Tidak ada endpoint yang berpura-pura berhasil untuk fitur tersebut.

## Jalankan lokal di Windows

Memerlukan Python 3.12 dan Node.js 24. Untuk instalasi baru, clone repository lalu jalankan setup dari folder repository:

```powershell
git clone https://github.com/bligede/subako-web-apps-by-mikiko.git
cd subako-web-apps-by-mikiko
powershell -ExecutionPolicy Bypass -File tools/setup.ps1
.\.venv\Scripts\python.exe tools/dev.py --built
```

Buka **http://127.0.0.1:5173**. Swagger API: **http://127.0.0.1:8000/docs**. Gunakan `Ctrl+C` untuk menghentikan kedua proses. `tools/dev.py` otomatis menjalankan migrasi, seed idempotent, dan membuat database SQLite di `.local/subako-dev.db`.

Akun SIMULATION: `pekaseh@demo.subako.local`, `operator@demo.subako.local`, `viewer@demo.subako.local`, `admin@demo.subako.local`. Kata sandi acak dibuat saat startup pertama dan tersedia di **`.local/demo-credentials.json`**. Berkas ini tidak masuk Git atau paket distribusi. Viewer hanya memiliki site Sembung; akun lain memiliki dua site. Reload aplikasi tidak mengganti role; keluar dan masuk sebagai akun lain untuk menguji permission.

Untuk hot reload development gunakan `tools/dev.py` tanpa `--built`. Service worker hanya diaktifkan pada build produksi/preview. Bila port 8000/5173 sudah digunakan, hentikan proses SUBAKO sebelumnya; aplikasi tidak mengambil alih port yang sedang dipakai.

Linux/macOS: `python3 -m venv .venv`, `.venv/bin/python -m pip install -r apps/api/requirements.lock`, `npm --prefix apps/web ci`, `npm run build`, lalu `.venv/bin/python tools/dev.py --built`.

## Jalankan Compose SIMULATION

```powershell
python tools/init_secrets.py
docker compose up --build -d
docker compose ps
```

Buka **http://127.0.0.1:8080**. Password demo Compose berada di `.local/secrets/demo_password`, terpisah dari mode SQLite lokal. Secret dibuat sekali dan tidak ditimpa. Database tidak dipublikasikan ke host; port frontend hanya terikat loopback. Mode HTTP/cookie development ini khusus simulasi lokal.

Bootstrap memakai owner database untuk migration, TimescaleDB dan role provisioning. Proses API memakai `subako_api`, simulator memakai koneksi `subako_ingest`; API tidak menerima secret owner. Entry point membaca secret mount lalu menjalankan aplikasi sebagai UID/GID 10001. Jangan menggunakan `docker compose down -v` untuk penghentian biasa karena akan menghapus volume data.

**Status verifikasi:** pengujian SQLite, PostgreSQL biasa/roles/RLS, dan browser tersedia dalam `evidence/`. TimescaleDB revision `0003`, Docker build, dan stack Compose penuh belum dijalankan pada host kerja ini; lihat [TESTING.md](docs/TESTING.md). Konfigurasi ini belum merupakan deployment production/pilot.

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pip install -r apps/api/requirements-test.lock
.\.venv\Scripts\python.exe -m pytest -q apps/api/tests
npm ci
npm run build
npm run test:e2e
```

E2E memerlukan Chrome/Edge yang terpasang, atau `CHROME_PATH` menunjuk executable Chromium. Runner memakai database dan port sementara di `.local/`, membuat password fixture acak dalam process environment, dan menghentikan proses miliknya setelah selesai. File [evidence/openapi-implemented.json](evidence/openapi-implemented.json) mencatat API yang benar-benar tersedia; kontrak target 66 operasi dalam paket review tetap menjadi rencana bertahap.

## Struktur

```text
apps/api/subako/             config, models, identity, domain services, simulator, REST/WS
apps/api/alembic/versions/   0001 schema, 0002 integrity/RLS, 0003 TimescaleDB
apps/api/tests/              backend + real PostgreSQL integration tests
apps/web/src/                React app, shared components, typed API, session and realtime
apps/web/public/             manifest and PWA icons
infra/                      Nginx and container image digest lock
tools/                      setup, local supervisor, Compose bootstrap, E2E
docs/                       approval, implementation status, deployment, user guide, QA
evidence/                   JUnit, OpenAPI actual, browser report and screenshots
```

Titik masuk: [backend](apps/api/subako/main.py), [React](apps/web/src/App.tsx), [database models](apps/api/subako/models.py), [Compose](compose.yaml). Dependency frontend/root ada pada lockfile npm; backend pada `requirements.lock`, test tambahan pada `requirements-test.lock`.

Perubahan dan urutan pekerjaan berikutnya ada di [release notes](docs/RELEASE-NOTES.md). Untuk membuat ZIP source/build/evidence tanpa database dan secret, jalankan `python tools/package_release.py`; target default berada di folder `../output/` dan tidak menimpa paket yang sudah ada. Paket arsitektur serta engineering baseline tersedia terpisah dari ZIP source ini.

Tradition decides. Technology measures. SUBAKO executes.
