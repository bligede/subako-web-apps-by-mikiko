# Deployment, upgrade dan pemulihan foundation

## Development lokal

Gunakan setup dan supervisor dalam README. Mode lokal memakai SQLite yang terpisah dari engineering platform dan Compose volume. Password acak hanya berada di `.local/demo-credentials.json`. Jangan menyalin `.local/`, `.env`, database, atau secret files ke repository/paket rilis.

Instance pratinjau yang dimulai oleh agen dapat berjalan tersembunyi dengan PID supervisor dicatat pada `.local/dev-supervisor.pid`. Untuk menghentikan instance tersebut beserta proses anaknya di Windows, jalankan `powershell -ExecutionPolicy Bypass -File tools/stop-local.ps1`. Script memeriksa executable dan command line sebelum menghentikan proses yang dicatat; proses aplikasi lain tidak dipilih berdasarkan nomor port.

## Compose SIMULATION

`tools/init_secrets.py` membuat secret tanpa mencetak nilai. Compose menjalankan TimescaleDB → bootstrap migration/role/seed → API + simulator → Nginx. API dan database hanya diakses melalui jaringan Compose; frontend dipetakan ke loopback 8080. Swagger dapat diakses pada `http://127.0.0.1:8080/docs` hanya bila route docs ditambahkan secara sengaja pada proxy; default dokumentasi API aktual disimpan di `evidence/openapi-implemented.json` dan Swagger tersedia langsung pada mode lokal port 8000.

Untuk inspeksi container: `docker compose ps`, `docker compose logs --tail 100 api`, dan health endpoint `/health/ready`. Jangan membagikan `docker inspect`, environment dump, atau secret mount contents; DSN runtime mengandung password yang dibangun di memory.

Digest image dikunci di `infra/image-lock.json` dan Dockerfile/Compose. Dependency backend/runtime dikunci `requirements.lock`, test tools `requirements-test.lock`, dan npm lockfile per package. Bila upgrade dependency, lakukan compatibility tests serta rebuild image dan simpan digest baru pada release yang berbeda.

## Upgrade dan rollback

1. Simpan release source/lockfiles/image digests dan catat Alembic revision saat ini.
2. Ambil backup dan verifikasi restore ke database baru.
3. Jalankan migration melalui bootstrap pada staging/integration terlebih dahulu.
4. Upgrade API/frontend setelah migration berhasil; periksa health, login/RBAC, satu tick telemetry, WS dan ledger verify.
5. Jika aplikasi perlu rollback dan schema masih compatible, kembalikan image sebelumnya. Migrasi integrity/Timescale menolak destructive downgrade. Bila schema tidak compatible, gunakan cutback/restore ke database baru dengan bukti hash dan approval operasional yang relevan.

Tidak ada command queue di foundation. Saat command service dibangun nanti, restore harus mengarantina outbox command sebelum dispatcher diaktifkan; ini tetap gate integrasi berikutnya.

## Backup SQLite lokal

```powershell
python tools/backup_local.py
```

Script memakai SQLite backup API sehingga konsisten saat WAL aktif. Hasil berada di `.local/backups/`; tidak mengambil password file. Catat bahwa backup database tetap berisi data akun/hash dan harus dilindungi.

Restore ke **nama database baru**, tanpa menimpa file berjalan:

```powershell
python tools/backup_local.py --restore .local/backups/NAMA-BACKUP.db --target .local/subako-restored.db
```

Periksa integritas sebelum mengarahkan `SUBAKO_DATABASE_URL` ke file hasil restore. Jangan menghapus database lama sampai hasil restore diverifikasi. Kredensial seed tetap berlaku bila password file berasal dari environment yang sama.

## Backup PostgreSQL/TimescaleDB

Dengan Compose aktif, tulis archive binary di dalam container agar redirection PowerShell tidak mengubah bytes:

```powershell
docker compose exec -T db pg_dump -U subako_owner -d subako -Fc -f /tmp/subako-foundation.dump
docker compose cp db:/tmp/subako-foundation.dump .local/backups/subako-foundation.dump
```

Simpan archive terenkripsi di penyimpanan terpisah bersama release metadata, migration revision dan prosedur pemulihan secret. Untuk restore, buat database baru dengan extension TimescaleDB sesuai versi image, salin archive ke container pemulihan dan ikuti [prosedur logical backup/restore Timescale](https://www.tigerdata.com/docs/deploy/self-hosted/backup-and-restore/logical-backup), termasuk `timescaledb_pre_restore()` dan `timescaledb_post_restore()`. Jangan gunakan parallel restore `pg_restore -j` untuk prosedur ini. Validasi jumlah data, grants/RLS, head ledger dan login sebelum cutover. Prosedur Timescale dan target RPO/RTO belum diuji pada host ini; timed restore wajib sebelum staging/pilot.

## Gate staging/production

Compose yang disediakan khusus development SIMULATION via HTTP loopback. Sebelum staging: jalankan seluruh stack/Timescale migration, TLS/reverse proxy dengan host/origin yang benar, Secure cookies, proxy-aware rate limiting, backup/restore nyata, secret custody/rotation, monitoring/log retention, account provisioning/MFA, dan review security. Live data/hardware tidak diterima rilis foundation ini. PostgreSQL migration owner tidak dipakai sebagai runtime API principal.
