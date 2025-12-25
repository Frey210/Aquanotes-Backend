from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    admin,
    users, 
    devices, 
    tambak, 
    kolam, 
    sensor, 
    monitoring, 
    export,
    device_threshold,
    notifications
)
from app.background_tasks import start_background_task
from app.database import engine, Base
from app.migrations import (
    ensure_user_role_column,
    ensure_user_notification_cooldown_column,
    ensure_device_is_active_column,
    ensure_device_deactivate_at_column
)
import logging
from prometheus_fastapi_instrumentator import Instrumentator

logger = logging.getLogger(__name__)

app = FastAPI(title="AquaNotes API", version="2.0.0")

# Prometheus Instrumentation
Instrumentator().instrument(app).expose(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(devices.router)
app.include_router(tambak.router)
app.include_router(kolam.router)
app.include_router(sensor.router)
app.include_router(monitoring.router)
app.include_router(export.router)
app.include_router(device_threshold.router)
app.include_router(notifications.router)

# Create tables and start background task on startup
@app.on_event("startup")
async def startup_event():
    # Buat semua tabel
    Base.metadata.create_all(bind=engine)
    ensure_user_role_column(engine)
    ensure_user_notification_cooldown_column(engine)
    ensure_device_is_active_column(engine)
    ensure_device_deactivate_at_column(engine)
    
    # Jalankan background tasks
    start_background_task()
    logger.info("Application startup complete")
