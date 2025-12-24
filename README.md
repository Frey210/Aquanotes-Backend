# AquaNotes Backend

AquaNotes Backend is a FastAPI service that authenticates aquaculture users, provisions IoT monitoring devices, ingests telemetry, evaluates sensor thresholds, and pushes notifications through Firebase Cloud Messaging. Data is stored in PostgreSQL via SQLAlchemy, with background workers watching for unsafe readings or offline hardware.

## Table of Contents
- Overview
- Architecture
- Technology Stack
- Project Layout
- Configuration
- Authentication and Security
- API Reference
- Data Schemas (Pydantic)
- Database Schema and Relationships
- Background Processing
- Mermaid Diagrams
- Getting Started
- Deployment Notes

## Overview
Key capabilities:
- Token-based authentication with registration, login, logout, and profile or FCM-token management.
- Device provisioning workflow that separates factory registration (admin API key) from user claiming.
- Farm modeling with `tambak` (farm) and `kolam` (pond) entities that bind to devices for contextual monitoring.
- Sensor ingestion endpoint that records temperature, pH, DO, TDS, ammonia, and salinity values.
- Monitoring API that returns latest and historical telemetry per pond.
- CSV export endpoint for ad-hoc analytics.
- Notification center with background workers that create alerts and trigger Firebase push notifications.
- Prometheus metrics exposure for runtime observability.

## Architecture
- FastAPI application (`app/main.py`) wires routers, configures CORS, exposes Prometheus metrics, and starts background threads on startup.
- Database layer (`app/database.py`) provides SQLAlchemy engine and session helpers via `DATABASE_URL`.
- ORM models (`app/models.py`) define users, auth tokens, farms, ponds, devices, sensor data, and notifications with relationships.
- Background tasks (`app/background_tasks.py`) check sensor thresholds and device heartbeat to update status and send FCM alerts.
- Firebase integration (`app/firebase_service.py`) initializes Firebase Admin SDK and sends notifications.

## Technology Stack
- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy ORM + PostgreSQL
- Pydantic v2 schemas
- Passlib (bcrypt) for password hashing
- Firebase Admin SDK for FCM push
- Prometheus FastAPI Instrumentator for metrics

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
  routers/              # Route modules (admin, users, devices, tambak, kolam, sensor, monitoring, export, notifications, device_threshold)
generate_db.py          # one-off script to create schema
aquanotes.db            # legacy SQLite database (sample data for migration)
requirements.txt
```

## Configuration
Environment variables:
| Key | Description | Default |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection string. | `postgresql+psycopg2://postgres:postgres@localhost:5432/aquanotes` |
| `ADMIN_API_KEY` | Required header for `/admin/*` routes. | `default-admin-secret` |
| `FIREBASE_CREDENTIALS` | Path to Firebase service account JSON. | `app/firebase/aqua-notes-firebase-adminsdk-fbsvc-6de08d39b2.json` |

Notes:
- `firebase_service.py` auto-initializes Firebase on import and logs errors if the credential file is missing.
- Device timestamps are accepted as ISO-8601 strings; timezone info is stripped before storage.

## Authentication and Security
- User authentication uses bearer tokens stored in `auth_tokens`.
- Protected routes use `Authorization: Bearer <token>`.
- Admin device provisioning requires `X-API-Key: <ADMIN_API_KEY>`.
- `/sensor` ingestion is unauthenticated and accepts device UID directly.
- `/export/csv` is unauthenticated in code; consider protecting it in production.

## API Reference
Base URL: `/`
Interactive docs: `/docs`
Prometheus metrics: `/metrics`

### Users
- `POST /users/register`  
  Create a user account.
- `POST /users/login`  
  Returns `{ access_token, token_type }`.
- `POST /users/logout` (auth)  
  Invalidates current token.
- `GET /users/me` (auth)  
  Returns the current user.
- `PUT /users/profile` (auth)  
  Update name and/or password (requires old password if changing password).
- `POST /users/fcm-token` (auth)  
  Store or update the user's FCM token.
- `DELETE /users/fcm-token` (auth)  
  Remove the stored FCM token.

### Admin Device Provisioning
- `POST /admin/devices` (X-API-Key)  
  Register a device UID (unassigned).
- `GET /admin/devices` (X-API-Key)  
  List all devices and current ownership.

### Devices
- `POST /devices` (auth)  
  Claim a pre-registered device by UID and set a name.
- `GET /devices` (auth)  
  List devices owned by the current user.
- `DELETE /devices/{device_uid}` (auth)  
  Unclaim a device; resets name and ownership.
- `PUT /devices/{device_id}` (auth)  
  Update name and/or connection interval.
- `POST /devices/{device_id}/move` (auth)  
  Move a device to another `kolam`.
- `GET /devices/status/` (auth)  
  Return counts of online/offline/maintenance and device list.
- `PUT /devices/{device_id}/maintenance` (auth)  
  Force status to `maintenance`.
- `PUT /devices/{device_id}/online` (auth)  
  Force status to `online` and update `last_seen`.
- `PUT /devices/{device_id}/interval?interval=<minutes>` (auth)  
  Update heartbeat interval.
- `PUT /devices/{device_id}/thresholds` (auth)  
  Save per-parameter thresholds.
- `GET /devices/{device_id}/thresholds` (auth)  
  Fetch saved thresholds.

### Tambak (Farm)
- `POST /tambak` (auth)  
  Create a farm.
- `GET /tambak` (auth)  
  List farms owned by the current user.
- `PUT /tambak/{tambak_id}` (auth)  
  Update farm details.
- `DELETE /tambak/{tambak_id}` (auth)  
  Remove a farm.

### Kolam (Pond)
- `POST /kolam` (auth)  
  Create a pond (validates farm ownership and device availability).
- `GET /kolam?tambak_id=<id>` (auth)  
  List ponds for a farm.
- `PUT /kolam/{kolam_id}` (auth)  
  Update pond details, including device assignment.
- `DELETE /kolam/{kolam_id}` (auth)  
  Remove a pond.

### Sensor Data
- `POST /sensor`  
  Ingest telemetry for a device UID and update `last_seen`.
- `GET /sensor?uid=<uid>` (auth)  
  Fetch all sensor records for a device owned by the user.

### Monitoring
- `GET /monitoring?last_n=<int>` (auth)  
  Returns the latest value and last N historical records per device/pond.

### Export
- `POST /export/csv`  
  Generate CSV by `device_id` and date range.  
  Note: no auth in code; protect it if needed.

### Notifications
- `GET /notifications` (auth)  
  List notifications with filters (`days`, `unread_only`, `skip`, `limit`).
- `PUT /notifications/{notification_id}/read` (auth)  
  Mark a notification as read.
- `PUT /notifications/read-all` (auth)  
  Mark all notifications as read.
- `GET /notifications/unread-count` (auth)  
  Return unread count.

## Data Schemas (Pydantic)
Request/response models are defined in `app/schemas.py`.

Highlights:
- `UserCreate`, `UserLogin`, `UserResponse`, `UserProfileUpdate`
- `DeviceRegister`, `DeviceCreate`, `DeviceUpdate`, `DeviceResponse`, `DeviceStatusResponse`
- `TambakCreate`, `TambakUpdate`, `TambakResponse`
- `KolamCreate`, `KolamUpdate`, `KolamResponse`
- `SensorDataCreate`, `SensorDataResponse`, `SensorDataSummary`
- `ThresholdSettings`, `DeviceThresholdResponse`
- `NotificationResponse`
- `ExportRequest`

## Database Schema and Relationships
Defined in `app/models.py`.

Tables:
- `users`: id, name, email, password_hash, created_at, fcm_token
- `auth_tokens`: token (PK), user_id, created_at, expires_at
- `tambak`: id, name, location fields, cultivation_type, user_id
- `kolam`: id, nama, tipe, panjang, lebar, kedalaman, komoditas, tambak_id, device_id (unique)
- `devices`: id, uid (unique), name, user_id, threshold fields, last_seen, status, connection_interval
- `sensor_data`: id, device_id, timestamp, suhu, ph, do, tds, ammonia, salinitas, index `(device_id, timestamp)`
- `notifications`: id, user_id, device_id, message, parameter, threshold_value, current_value, is_read, fcm_sent, timestamp

Relationships:
- User 1..N Tambak
- User 1..N Device (optional ownership)
- User 1..N Notification
- User 1..N AuthToken
- Tambak 1..N Kolam
- Kolam 0..1 Device (unique device assignment)
- Device 1..N SensorData
- Device 1..N Notification

## Background Processing
`app/background_tasks.py` starts two daemon threads on startup:
- `check_thresholds`: polls latest sensor data, compares to device thresholds, writes notifications, and sends FCM alerts.
- `check_device_status`: compares `last_seen` against `connection_interval * 2` to flip online/offline and send status notifications.

## Mermaid Diagrams

### Architecture Diagram
```mermaid
flowchart LR
  subgraph Clients
    Mobile[Mobile App]
    Device[IoT Device]
    Admin[Admin Tool]
  end

  subgraph API
    FastAPI[FastAPI App]
    Routers[Routers]
    Background[Background Tasks]
  end

  subgraph Data
    Postgres[(PostgreSQL)]
    Firebase[Firebase FCM]
  end

  Mobile -->|Bearer Token| FastAPI
  Admin -->|X-API-Key| FastAPI
  Device -->|Telemetry| FastAPI
  FastAPI --> Routers --> Postgres
  Background --> Postgres
  Background --> Firebase
  FastAPI --> Firebase
```

### ER Diagram (Database Relationships)
```mermaid
erDiagram
  USERS ||--o{ AUTH_TOKENS : has
  USERS ||--o{ TAMBAK : owns
  USERS ||--o{ DEVICES : owns
  USERS ||--o{ NOTIFICATIONS : receives
  TAMBAK ||--o{ KOLAM : contains
  DEVICES ||--o{ SENSOR_DATA : reports
  DEVICES ||--o{ NOTIFICATIONS : triggers
  DEVICES ||--o| KOLAM : assigned_to

  USERS {
    int id PK
    string name
    string email
    string password_hash
    datetime created_at
    string fcm_token
  }
  AUTH_TOKENS {
    string token PK
    int user_id FK
    datetime created_at
    datetime expires_at
  }
  TAMBAK {
    int id PK
    string name
    string country
    string province
    string city
    string district
    string village
    string address
    string cultivation_type
    int user_id FK
  }
  KOLAM {
    int id PK
    string nama
    string tipe
    float panjang
    float lebar
    float kedalaman
    string komoditas
    int tambak_id FK
    int device_id FK
  }
  DEVICES {
    int id PK
    string uid
    string name
    int user_id FK
    datetime last_seen
    string status
    int connection_interval
  }
  SENSOR_DATA {
    int id PK
    int device_id FK
    datetime timestamp
    float suhu
    float ph
    float do
    float tds
    float ammonia
    float salinitas
  }
  NOTIFICATIONS {
    int id PK
    int user_id FK
    int device_id FK
    string message
    string parameter
    float threshold_value
    float current_value
    bool is_read
    bool fcm_sent
    datetime timestamp
  }
```

### Device Provisioning Flow
```mermaid
flowchart TD
  A[Factory/Admin] -->|POST /admin/devices + X-API-Key| B[Device UID registered]
  B --> C[Device unassigned]
  C -->|POST /devices - auth| D[User claims device]
  D -->|Optional| E[Assign device to kolam]
```

### Sensor Ingestion Flow
```mermaid
sequenceDiagram
  participant Device as IoT Device
  participant API as FastAPI
  participant DB as PostgreSQL

  Device->>API: POST /sensor (uid, timestamp, readings)
  API->>DB: Update device last_seen + status
  API->>DB: Insert sensor_data row
  API-->>Device: 200 OK
```

### Monitoring Flow
```mermaid
flowchart LR
  User[User App] -->|GET /monitoring| API[FastAPI]
  API --> DB[(PostgreSQL)]
  DB --> API
  API --> User
```

### Threshold Check Flow
```mermaid
flowchart TD
  T[Background: check_thresholds] --> D[Load devices with owner]
  D --> S[Fetch latest sensor_data]
  S --> C{Thresholds set?}
  C -->|No| N[Skip]
  C -->|Yes| V{Value violates threshold?}
  V -->|No| N
  V -->|Yes| R[Write notification]
  R --> F[Send FCM if token exists]
```

### Device Status Flow
```mermaid
flowchart TD
  T[Background: check_device_status] --> L[Load devices]
  L --> M{Maintenance?}
  M -->|Yes| S[Skip device]
  M -->|No| H[Compare last_seen to threshold]
  H -->|Old| O[Set offline + notify]
  H -->|Fresh| I[Set online + notify]
```

## Getting Started
### 1. Prerequisites
- Python 3.11 or later
- PostgreSQL 14+
- Firebase service-account JSON file

### 2. Installation
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and edit the connection string, admin API key, and Firebase credential path.

### 3. Database Preparation
```sql
CREATE DATABASE aquanotes;
CREATE USER aquanotes WITH PASSWORD 'your-strong-password';
GRANT ALL PRIVILEGES ON DATABASE aquanotes TO aquanotes;
```

Set `DATABASE_URL`:
```powershell
setx DATABASE_URL "postgresql+psycopg2://aquanotes:your-strong-password@localhost:5432/aquanotes"
```

Create tables:
```powershell
python generate_db.py
```

### 4. Run the server
```powershell
uvicorn app.main:app --reload
```

## Deployment Notes
- Docker, Docker Compose, and Kubernetes manifests are provided in `Dockerfile`, `docker-compose.yml`, and `k8s/`.
- `migrate_sqlite_to_postgres.py` can copy data from `aquanotes.db` into PostgreSQL.
