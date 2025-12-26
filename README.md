# AquaNotes Backend

Backend layanan AquaNotes berbasis FastAPI untuk autentikasi pengguna, provisioning perangkat IoT, ingest data sensor, evaluasi threshold, dan push notifikasi via Firebase Cloud Messaging. Data disimpan di PostgreSQL (SQLAlchemy) dan proses monitoring berjalan di background thread.

## Ringkasan Fitur
- Auth token (register/login/logout, profil, FCM token).
- Provisioning device via admin key dan klaim perangkat oleh user.
- Manajemen tambak/kolam serta pengikatan device.
- Ingest telemetry sensor dan monitoring data historis.
- Notifikasi ambang batas + status perangkat (online/offline/maintenance).
- Ekspor CSV dan endpoint metrik Prometheus.

## Arsitektur
- `app/main.py`: FastAPI entrypoint, CORS, router, metrics, dan startup hooks.
- `app/database.py`: engine dan session SQLAlchemy.
- `app/models.py`: ORM models dan relasi.
- `app/background_tasks.py`: checker threshold dan status perangkat.
- `app/firebase_service.py`: inisialisasi Firebase Admin SDK.

## Teknologi
- Python 3.11+, FastAPI, Uvicorn
- PostgreSQL + SQLAlchemy ORM
- Pydantic v2
- Firebase Admin SDK (FCM)
- Prometheus FastAPI Instrumentator

## Struktur Proyek
```
app/
  auth.py
  background_tasks.py
  crud.py
  database.py
  dependencies.py
  firebase_service.py
  main.py
  migrations.py
  models.py
  schemas.py
  routers/
generate_db.py
requirements.txt
migrations/
k8s/
```

## Konfigurasi
Environment variables:
| Key | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection string. | `postgresql+psycopg2://postgres:postgres@localhost:5432/aquanotes` |
| `ADMIN_API_KEY` | Required header for `/admin/*` routes. | `default-admin-secret` |
| `FIREBASE_CREDENTIALS` | Path ke service account JSON. | `app/firebase/aqua-notes-firebase-adminsdk-fbsvc-6de08d39b2.json` |

Catatan:
- Firebase akan diinisialisasi saat import `firebase_service.py`.
- Timestamp sensor menerima ISO-8601 dan akan disimpan tanpa timezone.

## Autentikasi & Keamanan
- Token tersimpan di tabel `auth_tokens`.
- Route protected memakai `Authorization: Bearer <token>`.
- Admin provisioning memakai `X-API-Key: <ADMIN_API_KEY>`.
- `/sensor` dan `/export/csv` belum proteksi auth (amankan di production).

## Endpoint Utama
- Docs: `/docs`
- Metrics: `/metrics`

### Users
- `POST /users/register`
- `POST /users/login`
- `POST /users/logout` (auth)
- `GET /users/me` (auth)
- `PUT /users/profile` (auth)
- `POST /users/fcm-token` (auth)
- `DELETE /users/fcm-token` (auth)

### Admin Device Provisioning
- `POST /admin/devices` (X-API-Key)
- `GET /admin/devices` (X-API-Key)

### Devices
- `POST /devices` (auth)
- `GET /devices` (auth)
- `DELETE /devices/{device_uid}` (auth)
- `PUT /devices/{device_id}` (auth)
- `POST /devices/{device_id}/move` (auth)
- `GET /devices/status/` (auth)
- `PUT /devices/{device_id}/maintenance` (auth)
- `PUT /devices/{device_id}/online` (auth)
- `PUT /devices/{device_id}/interval?interval=<minutes>` (auth)
- `PUT /devices/{device_id}/thresholds` (auth)
- `GET /devices/{device_id}/thresholds` (auth)

### Tambak
- `POST /tambak` (auth)
- `GET /tambak` (auth)
- `PUT /tambak/{tambak_id}` (auth)
- `DELETE /tambak/{tambak_id}` (auth)

### Kolam
- `POST /kolam` (auth)
- `GET /kolam?tambak_id=<id>` (auth)
- `PUT /kolam/{kolam_id}` (auth)
- `DELETE /kolam/{kolam_id}` (auth)

### Sensor Data
- `POST /sensor`
- `GET /sensor?uid=<uid>` (auth)

### Monitoring
- `GET /monitoring?last_n=<int>` (auth)

### Export
- `POST /export/csv`

### Notifications
- `GET /notifications` (auth)
- `PUT /notifications/{notification_id}/read` (auth)
- `PUT /notifications/read-all` (auth)
- `GET /notifications/unread-count` (auth)

## Database & Migrasi
- Tabel dibuat otomatis pada startup (`Base.metadata.create_all`).
- `app/migrations.py` menjalankan migrasi ringan (kolom baru) saat startup.
- SQL migration tambahan ada di `migrations/` dan bisa dijalankan manual via `psql`.

## Menjalankan Lokal
1) Buat venv dan install deps:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```
2) Copy env:
```powershell
Copy-Item .env.example .env
```
3) Siapkan database:
```sql
CREATE DATABASE aquanotes;
CREATE USER aquanotes WITH PASSWORD 'your-strong-password';
GRANT ALL PRIVILEGES ON DATABASE aquanotes TO aquanotes;
```
4) Jalankan API:
```powershell
uvicorn app.main:app --reload
```

## Docker (Local)
```powershell
docker build -t aquanotes-api .
docker run -p 8000:8000 --env-file .env aquanotes-api
```

## Kubernetes (K3s)
Manifests ada di `k8s/`. Untuk cluster Raspberry Pi, gunakan image `linux/arm64`.

1) Namespace:
```bash
kubectl apply -f k8s/namespace.yaml
```
2) Secrets (contoh):
```bash
kubectl -n aquanotes create secret generic aquanotes-db-secret \
  --from-literal=POSTGRES_DB=aquanotes \
  --from-literal=POSTGRES_USER=aquanotes \
  --from-literal=POSTGRES_PASSWORD=<password>
```
```bash
kubectl -n aquanotes create secret generic aquanotes-api-secret \
  --from-literal=DATABASE_URL=postgresql+psycopg2://aquanotes:<password>@postgres:5432/aquanotes \
  --from-literal=ADMIN_API_KEY=<admin-key> \
  --from-literal=FIREBASE_CREDENTIALS=/app/app/firebase/serviceAccount.json
```
```bash
kubectl -n aquanotes create secret generic firebase-credentials \
  --from-file=serviceAccount.json=/path/to/firebase-service-account.json
```
3) Apply Postgres dan API:
```bash
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/api.yaml
```

## Cloudflare Tunnel (Opsional)
Jika expose ke publik, arahkan `api.<domain>` ke Service `aquanotes-api` melalui Cloudflare Tunnel.

## Observability
- `/metrics` untuk Prometheus.
- Log aplikasi standard output (gunakan `kubectl logs`).

## Monitoring & Alerting
- Prometheus: `https://prometheus.inkubasistartupunhas.id`
- Grafana: `https://grafana.inkubasistartupunhas.id`
- Alertmanager: `https://alertmanager.inkubasistartupunhas.id`

Telegram alerting & bot:
- Group: Aquanotes Server Alert System
- Bot commands: `/status`, `/pods`, `/alerts`, `/help`

## Database Admin (pgAdmin)
- URL: `https://aquanotes-pgadmin.inkubasistartupunhas.id`
- Credentials diset via Secret `db-tools/pgadmin-admin`.
- Server pre-registration diset via Secret `db-tools/pgadmin-servers`.
