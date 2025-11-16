# AquaNotes Backend

AquaNotes Backend is a FastAPI service that authenticates aquaculture users, provisions IoT monitoring devices, ingests telemetry, evaluates sensor thresholds, and pushes notifications through Firebase Cloud Messaging. Data is stored in a local SQLite database via SQLAlchemy, while background workers watch for unsafe readings or offline hardware.

## Features
- Token-based authentication with registration, login, logout, and profile or FCM-token management.
- Device provisioning workflow that separates factory registration (API key) from user claiming, renaming, maintenance toggling, and pond assignment.
- Farm modeling with `tambak` (farm) and `kolam` (pond) entities that bind to devices for contextual monitoring.
- Sensor ingestion endpoint that records temperature, pH, DO, TDS, ammonia, and salinity values, then updates device connectivity information.
- Monitoring API that returns latest and historical telemetry snapshots for every pond and device pair.
- CSV export endpoint for ad-hoc analytics.
- Notification center with background workers that create alerts and trigger Firebase push notifications when thresholds are broken or devices go offline.
- Prometheus metrics exposure for runtime observability.

## Architecture Overview
- **FastAPI application (`app/main.py`)** - wires routers, configures permisisve CORS, exposes Prometheus metrics through `prometheus_fastapi_instrumentator`, performs lightweight migrations, and starts background threads on startup.
- **Database layer (`app/database.py`)** - SQLAlchemy engine and session helpers bound to `sqlite:///./aquanotes.db`.
- **ORM models (`app/models.py`)** - define users, auth tokens, tambak, kolam, devices (with threshold columns), sensor data, and notifications with relationships for ownership and cascading queries.
- **Background tasks (`app/background_tasks.py`)** - two daemon threads: one checks telemetry against stored thresholds, the other tracks device heartbeat and connection intervals to flip `online`, `offline`, or `maintenance`.
- **Routers (`app/routers/*.py`)** - REST endpoints for authentication, admin provisioning, device operations, farm management, monitoring, exports, notifications, and threshold configuration.
- **Firebase integration (`app/firebase_service.py`)** - initializes the Firebase Admin SDK the first time it is needed and exposes a helper to send sound-enabled push notifications.

## Technology Stack
- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy ORM + SQLite
- Pydantic v2 schemas
- Passlib (bcrypt) for password hashing
- Firebase Admin SDK for FCM push
- Prometheus FastAPI Instrumentator for metrics

> `requirements.txt` currently lists scientific packages for ML or visualization. You will also need to install `fastapi`, `uvicorn`, `sqlalchemy`, `passlib[bcrypt]`, `python-multipart`, `firebase-admin`, and `prometheus-fastapi-instrumentator` to satisfy the imports used in this project.

## Project Layout
```
app/
  auth.py               # token handling and password utilities
  background_tasks.py   # threshold and device-status workers
  crud.py               # legacy helper functions
  database.py           # SQLAlchemy engine and session helpers
  dependencies.py       # shared FastAPI dependencies
  firebase_service.py   # Firebase Admin bootstrap plus FCM helper
  main.py               # FastAPI entrypoint
  models.py             # SQLAlchemy models
  schemas.py            # Pydantic request and response models
  routers/              # Route modules (admin, devices, tambak, kolam, sensor, monitoring, export, notifications, device_threshold)
generate_db.py          # one-off script to create schema
aquanotes.db            # local SQLite database (sample data)
requirements.txt
```

## Getting Started

### 1. Prerequisites
- Python 3.11 or later
- pip and virtualenv
- Firebase service-account JSON file (see configuration)
- Optional: SQLite browser if you want to inspect the bundled database

### 2. Installation
```powershell
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install fastapi uvicorn sqlalchemy passlib[bcrypt] python-multipart firebase-admin prometheus-fastapi-instrumentator
```

### 3. Database Preparation
- To create the schema from scratch, run `python generate_db.py`.
- A pre-built `aquanotes.db` is already included; delete it first if you want a clean instance.

### 4. Configuration
| Key | Description | Default |
| --- | ----------- | ------- |
| `ADMIN_API_KEY` | Required header for `/admin/*` device provisioning routes. | `default-admin-secret` |
| Firebase service-account JSON | Place under `app/firebase/<file>.json` and update the path in `firebase_service.py` if needed. | none |
| `DATABASE_URL` | Change in `app/database.py` if you move away from SQLite. | `sqlite:///./aquanotes.db` |

Additional notes:
- Background threads rely on a working Firebase configuration to deliver alerts; without the credential file they will log errors but continue running.
- Device timestamps must be ISO-8601 strings; the ingestion endpoint strips timezone info before storage.

### 5. Running the Development Server
```powershell
uvicorn app.main:app --reload
```

Key endpoints:
- Interactive docs: `http://localhost:8000/docs`
- Prometheus metrics: `http://localhost:8000/metrics`

## Key Components and Flows

### Authentication and Users (`app/routers/users.py`)
- `POST /users/register` - create account with hashed password.
- `POST /users/login` - returns bearer token stored in `auth_tokens` (default expiry is 720 hours).
- `POST /users/logout` - deletes current token.
- `GET /users/me` - fetch profile; `PUT /users/profile` updates name or password after verifying the old password.
- `POST/DELETE /users/fcm-token` - manage per-user FCM token for push notifications.

### Device Provisioning and Management
- Factory or admin workflow uses `/admin/devices` with `X-API-Key` to create unassigned devices by UID.
- End users call `/devices` to claim by UID, rename, change connection intervals, move devices between kolam, or toggle maintenance or online status.
- `/devices/status` summarizes online and offline counts; `/devices/{id}/thresholds` stores per-parameter limits.

### Farm Structure
- `/tambak` manages farms; `/kolam` manages ponds under a farm and ensures exclusive device assignment.
- Move devices across ponds with `/devices/{id}/move` while validating ownership.

### Sensor Ingestion and Monitoring
- Devices POST sensor payloads (UID, timestamp, and readings) to `/sensor`.
- `last_seen` and status flip to `online` on every ingestion; the background worker will revert to `offline` if no updates arrive based on `connection_interval`.
- `/sensor?uid=` and `/monitoring` provide authenticated access to historical data, including a configurable `last_n` window per device.
- `/export/csv` generates downloadable CSV between `start_date` and `end_date`.

### Notifications and Thresholds
- `check_thresholds` inspects each owned device's latest reading against saved thresholds (temperature, pH, DO, TDS, ammonia, salinity) and writes a `notifications` row if violated.
- `check_device_status` compares `last_seen` to a derived threshold to set devices offline or online and sends push notifications when status changes.
- `/notifications` supplies filters for time range, unread-only, pagination, and endpoints to mark single or all alerts as read; `/notifications/unread-count` returns an integer badge value.

## Database Entities
| Table | Purpose |
| ----- | ------- |
| `users` | Account information, hashed passwords, FCM tokens. |
| `auth_tokens` | Bearer tokens with expiry for stateless authentication. |
| `tambak` / `kolam` | Farm or pond hierarchy tied to a user, with optional device binding. |
| `devices` | Hardware registry (UID, name, owner, thresholds, last_seen, status, connection intervals). |
| `sensor_data` | Time-series telemetry with compound index `(device_id, timestamp)`. |
| `notifications` | Alert records storing parameter, threshold value, measured value, read status, and FCM delivery flag. |

## Observability and Maintenance
- Prometheus endpoint is exposed automatically through `Instrumentator` inside `app/main.py`.
- Logging uses the standard library `logging` module; adjust levels if required.
- Background threads log threshold or status changes routinely; monitor logs for Firebase errors or DB rollbacks.

## Development Tips
- Prefer using the FastAPI dependency injection helpers (`Depends(get_db)` and `get_current_user`) for consistent session and token handling.
- When modifying schemas or background logic, ensure the included SQLite database is dropped or migrated to keep columns in sync (`migrate_database()` currently adds `last_seen`, `status`, and `connection_interval` if missing).
- Keep `requirements.txt` aligned with actual imports to simplify deployment automation.
- Consider adding automated tests (for example, pytest plus httpx AsyncClient) for routers and background workers when write access is available.
