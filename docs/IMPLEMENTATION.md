# Status implementasi dan keputusan foundation

Rilis `0.1.0-alpha.1` mengerjakan foundation dan dashboard simulasi setelah G0. Ini bukan deklarasi bahwa seluruh acceptance SUBAKO v0.1 sudah terpenuhi.

| Area | Implementasi alpha.1 | Tahap berikutnya |
|---|---|---|
| Identity | Argon2, hashed session ID, CSRF token, login/logout/refresh, session revoke | Reset/invite channel, MFA, user write workflows, session administration |
| Access | Backend permission + site grants; PG API role + RLS; SQLite app checks | Governance-specific permissions saat rule registry dibuat |
| Data | 17 tabel migration, composite FK device/site, normalized metrics, raw source/hash | Subak/member/tempek, rule/approval, capability/calibration history |
| Telemetry | Simulator → Pydantic → raw/readings/latest → REST/WS; duplicate event conflict handling | Binary baseline bridge, MQTT TLS/ACL, ChirpStack, invalid raw quarantine |
| Safety | LIVE tidak diterima schema; tidak ada layanan command/hardware | Signing boundary, grants, outbox/ACK/feedback, TTL/replay/interlock suite |
| Ledger | Full SHA-256 chain per site, row locking, append-only triggers, verification | Edge chain import, compensation, daily seals/independent anchor, archive |
| Alerts | Threshold/fault simulator evidence dan immutable acknowledgement | Resolution history, assigned owners, statistical advisory, push |
| UI | Dashboard, monitor, gates read-only, devices/simulator, alerts, ledger, technical user list, settings | Governance forms, reports, full administration and field usability tests |
| PWA | Static shell precache, icons/manifest, offline read-only memory, no mutation replay | Optional minimal read snapshots, update prompt, push preference lifecycle |
| Operations | Dev supervisor, Dockerfiles/Compose, exact locks, health endpoints | Full Compose/Timescale validation, observability, timed DR, staging hardening |

## Penyesuaian terukur dari target arsitektur

1. **Modular monolith foundation, satu worker.** Simulator in-process memakai engine/credential ingestion tersendiri pada Compose. Version notifications WebSocket berada dalam process memory. Jangan menambah worker/replika sebelum fan-out shared dan simulator worker terpisah diimplementasikan.
2. **SQLite dev-only.** Local supervisor tidak memerlukan Docker. SQLite bukan pengganti PostgreSQL/TimescaleDB untuk integrasi/staging. PostgreSQL RLS diuji menggunakan runtime role sebenarnya; RLS tidak diklaim ada pada SQLite.
3. **Timescale revision terpisah.** Migrasi `0001/0002` diuji pada PostgreSQL tertanam; `0003` membutuhkan extension TimescaleDB. Pada SQLite `0003` adalah no-op, bukan emulasi hypertable. Raw telemetry tetap ordinary table dengan unique source event; normalized sensor history menjadi hypertable saat `0003` berjalan di PostgreSQL.
4. **Belum ada retention delete.** Jangan drop data historis sebelum arsip raw/retention policy diimplementasikan dan disetujui. Tidak ada janji kapasitas/retensi produksi pada alpha ini.
5. **Session DTO bertambah konteks.** Response memakai `user`, `sites[{roles,permissions}]`, csrf token dan expiry, agar role dapat berbeda per site. Ini evolusi kontrak foundation yang tercatat pada OpenAPI aktual, bukan penerapan seluruh target kontrak review sekaligus.
6. **Ledger anchor lokal.** VERIFIED berarti chain konsisten dengan head database saat diperiksa. Tidak memberikan jaminan terhadap DBA yang dapat mengganti seluruh chain + head. UI menyatakan batas ini; external sealing masih backlog.
7. **Tidak ada data sensitif offline persisten.** Snapshot terakhir hanya berada dalam memory selama sesi yang masih terbuka. Cold start offline membuka shell/login dengan penjelasan koneksi. Logout menghapus query cache; service worker tidak pernah menyimpan API/session.
8. **Input simulator bukan parameter hardware final.** Batas numerik dalam schema telemetry alpha.1 memvalidasi data fake devices. Ingestion LIVE nantinya harus memakai capability/calibration registry yang disahkan, bukan mengadopsi batas simulasi sebagai spesifikasi sensor lapangan.

## Permission foundation

Semua role dapat membaca data site yang diberikan. Operator dan Pekaseh dapat acknowledge alert. Hanya admin teknis memiliki `simulation.manage`, `users.read`, dan `audit.read`. Permission governance/command belum diberikan karena layanannya belum dibangun. Tidak ada wildcard admin. Role dan daftar site berasal dari backend, bukan dropdown pratinjau.

## Referensi implementasi

- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/) — session/dependency dan lifecycle socket.
- [SQLAlchemy session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) — session/transaction per request dan task.
- [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) — frozen schema migrations.
- [Vite](https://vite.dev/guide/) dan [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite) — build yang menghasilkan asset hashed dan shell worker.
- [MDN Cache.match](https://developer.mozilla.org/en-US/docs/Web/API/Cache/match) — `ignoreVary` hanya dipakai untuk public same-origin precache assets agar header Origin pada module request tidak menghalangi offline shell; API tetap dikecualikan.

Kode dependency dikunci berdasarkan paket yang benar-benar diinstal dan diperiksa. Source image digest berasal dari manifest registry Docker Hub resmi; digest lock tidak berarti image sudah dijalankan atau lulus security review staging.
