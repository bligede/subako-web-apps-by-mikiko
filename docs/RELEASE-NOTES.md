# SUBAKO Web-PWA 0.1.0-alpha.1

Rilis foundation SIMULATION setelah persetujuan paket arsitektur. Aplikasi dapat dijalankan lokal dengan frontend, backend, database, login dan telemetry yang benar-benar terhubung. Perubahan berada di folder `web-pwa`; firmware dan engineering baseline tidak diubah.

## Tersedia

Dashboard dan histori grafik, filter site, monitoring, detail pintu baca-saja, peringatan dengan acknowledgement, Buku Air dengan verifikasi SHA-256, daftar perangkat, tujuh skenario simulator untuk admin teknis, serta daftar pengguna teknis. Sesi dan izin divalidasi backend; viewer dibatasi ke satu site. PWA menyimpan shell statis dan menandai data yang menua saat koneksi hilang.

Database memiliki migration, integrity constraints dan append-only ledger/audit; PostgreSQL memakai role terpisah serta RLS. Mode lokal memakai SQLite. Source dilengkapi lockfile, OpenAPI aktual, Dockerfiles/Compose, panduan operasional, tes dan bukti visual.

## Pekerjaan berikutnya

1. **Integrasi deployment:** jalankan Docker/Compose dan Timescale migration `0003`; buktikan backup/restore, secret rotation, observability dan single-worker deployment pada environment integrasi.
2. **Tata kelola air:** lengkapi registry Subak/tempek/anggota, rule/version/approval, referensi Paruman, jadwal dan entitlements; tambahkan workflow backend dan UI sesuai hak akses.
3. **IoT:** hubungkan codec/bridge baseline dengan MQTT/ChirpStack, capability/calibration registry, quarantine data invalid dan ingestion LIVE yang terpisah dari simulasi.
4. **Command service:** bangun signing boundary, grants, outbox, TTL/replay protection, ACK/feedback dan uji interlock sebelum ada aktuasi. Foundation belum mengirim command.
5. **Operasional lanjutan:** report PDF/XLSX, ledger seals independen, account lifecycle/MFA, push preferences, security review, usability dan pilot commissioning.

Urutan integrasi dan gate persetujuan operasional mengikuti roadmap dalam paket arsitektur yang sudah direview. Persetujuan implementasi foundation tidak menggantikan persetujuan aturan air atau pengoperasian perangkat.

## Status rilis

27 tes backend, 15 pemeriksaan browser dan 21 kasus responsive lulus; detail dan batasnya ada pada [TESTING](TESTING.md). Timescale/Compose belum dijalankan pada host kerja. Rilis ini belum dinyatakan siap production/pilot.

ZIP source menyertakan build frontend dan bukti pengujian, dengan manifest SHA-256 setiap file. Dependency terpasang, database, password, `.local/`, `.git/`, dan log runtime dikecualikan. Paket review arsitektur dan firmware baseline merupakan artefak terpisah.
