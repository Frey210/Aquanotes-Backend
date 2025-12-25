from fastapi import APIRouter, Depends, HTTPException, Header, status, Response
from sqlalchemy.orm import Session
import os
from app import models, schemas, database
from typing import List, Optional
from datetime import datetime, date
from app.auth import require_roles
from sqlalchemy import func, text

router = APIRouter(prefix="/admin", tags=["Administrator"])

# Dapatkan API Key dari environment variable
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "default-admin-secret")

@router.post("/devices", response_model=schemas.DeviceResponse)
def register_device(
    device: schemas.DeviceRegister,
    db: Session = Depends(database.get_db),
    x_api_key: str = Header(None, alias="X-API-Key")
):
    # Debugging: Cetak key yang diterima
    print(f"Received API Key: {x_api_key}")
    print(f"Expected API Key: {ADMIN_API_KEY}")
    
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key is required",
            headers={"WWW-Authenticate": "APIKey"}
        )
    
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid API Key. Received: {x_api_key}",
            headers={"WWW-Authenticate": "APIKey"}
        )
    
    # Cek apakah UID sudah terdaftar
    existing = db.query(models.Device).filter(
        models.Device.uid == device.uid
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device UID already registered"
        )
    
    # Buat device baru tanpa pemilik
    new_device = models.Device(uid=device.uid)
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    
    return new_device

@router.get("/devices", response_model=List[schemas.AdminDeviceResponse])
def list_devices(
    db: Session = Depends(database.get_db),
    x_api_key: str = Header(None, alias="X-API-Key")
):
    # Validasi API Key
    if not x_api_key or x_api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "APIKey"}
        )
    
    # Dapatkan semua device dengan informasi user
    devices = db.query(
        models.Device.id,
        models.Device.uid,
        models.Device.name,
        models.Device.user_id,
        models.User.name.label("user_name"),
        models.Device.status,
        models.Device.last_seen,
        models.Device.is_active,
        models.Device.deactivate_at
    ).outerjoin(
        models.User, models.Device.user_id == models.User.id
    ).all()
    
    # Format respons
    result = []
    for device in devices:
        result.append({
            "id": device.id,
            "uid": device.uid,
            "name": device.name,
            "user_id": device.user_id,
            "user_name": device.user_name,
            "registered": device.user_id is not None,
            "status": device.status,
            "last_seen": device.last_seen,
            "is_active": device.is_active,
            "deactivate_at": device.deactivate_at
        })
    
    return result


@router.get("/overview", response_model=schemas.AdminOverview)
def get_admin_overview(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    total_users = db.query(func.count(models.User.id)).scalar() or 0
    total_devices = db.query(func.count(models.Device.id)).scalar() or 0
    total_tambak = db.query(func.count(models.Tambak.id)).scalar() or 0
    total_kolam = db.query(func.count(models.Kolam.id)).scalar() or 0
    total_notifications = db.query(func.count(models.Notification.id)).scalar() or 0

    online_devices = db.query(func.count(models.Device.id)).filter(models.Device.status == "online").scalar() or 0
    offline_devices = db.query(func.count(models.Device.id)).filter(models.Device.status == "offline").scalar() or 0
    maintenance_devices = db.query(func.count(models.Device.id)).filter(models.Device.status == "maintenance").scalar() or 0
    inactive_devices = db.query(func.count(models.Device.id)).filter(models.Device.is_active == False).scalar() or 0

    database_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    return schemas.AdminOverview(
        total_users=total_users,
        total_devices=total_devices,
        total_tambak=total_tambak,
        total_kolam=total_kolam,
        total_notifications=total_notifications,
        online_devices=online_devices,
        offline_devices=offline_devices,
        maintenance_devices=maintenance_devices,
        inactive_devices=inactive_devices,
        database_ok=database_ok
    )


@router.get("/devices/all", response_model=List[schemas.AdminDeviceResponse])
def list_all_devices(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    devices = db.query(
        models.Device.id,
        models.Device.uid,
        models.Device.name,
        models.Device.user_id,
        models.User.name.label("user_name"),
        models.Device.status,
        models.Device.last_seen,
        models.Device.is_active,
        models.Device.deactivate_at
    ).outerjoin(
        models.User, models.Device.user_id == models.User.id
    ).all()

    result = []
    for device in devices:
        result.append({
            "id": device.id,
            "uid": device.uid,
            "name": device.name,
            "user_id": device.user_id,
            "user_name": device.user_name,
            "registered": device.user_id is not None,
            "status": device.status,
            "last_seen": device.last_seen,
            "is_active": device.is_active,
            "deactivate_at": device.deactivate_at
        })

    return result


@router.put("/devices/{device_id}/status", response_model=schemas.AdminDeviceResponse)
def admin_update_device_status(
    device_id: int,
    payload: schemas.AdminDeviceStatusUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.status = payload.status
    if payload.status == "offline":
        device.last_seen = None
    db.commit()
    db.refresh(device)

    return {
        "id": device.id,
        "uid": device.uid,
        "name": device.name,
        "user_id": device.user_id,
        "user_name": device.owner.name if device.owner else None,
        "registered": device.user_id is not None,
        "status": device.status,
        "last_seen": device.last_seen,
        "is_active": device.is_active,
        "deactivate_at": device.deactivate_at
    }


@router.put("/devices/{device_id}/deactivate", response_model=schemas.AdminDeviceResponse)
def admin_deactivate_device(
    device_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.is_active = False
    device.status = "offline"
    device.last_seen = None
    device.deactivate_at = None
    db.commit()
    db.refresh(device)

    return {
        "id": device.id,
        "uid": device.uid,
        "name": device.name,
        "user_id": device.user_id,
        "user_name": device.owner.name if device.owner else None,
        "registered": device.user_id is not None,
        "status": device.status,
        "last_seen": device.last_seen,
        "is_active": device.is_active,
        "deactivate_at": device.deactivate_at
    }


@router.put("/devices/{device_id}/activate", response_model=schemas.AdminDeviceResponse)
def admin_activate_device(
    device_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.is_active = True
    device.deactivate_at = None
    db.commit()
    db.refresh(device)

    return {
        "id": device.id,
        "uid": device.uid,
        "name": device.name,
        "user_id": device.user_id,
        "user_name": device.owner.name if device.owner else None,
        "registered": device.user_id is not None,
        "status": device.status,
        "last_seen": device.last_seen,
        "is_active": device.is_active,
        "deactivate_at": device.deactivate_at
    }


@router.put("/devices/{device_id}/schedule", response_model=schemas.AdminDeviceResponse)
def admin_schedule_deactivation(
    device_id: int,
    payload: schemas.AdminDeviceDeactivateSchedule,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if payload.deactivate_at is not None and payload.deactivate_at <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="deactivate_at must be in the future (UTC)"
        )

    device.deactivate_at = payload.deactivate_at
    db.commit()
    db.refresh(device)

    return {
        "id": device.id,
        "uid": device.uid,
        "name": device.name,
        "user_id": device.user_id,
        "user_name": device.owner.name if device.owner else None,
        "registered": device.user_id is not None,
        "status": device.status,
        "last_seen": device.last_seen,
        "is_active": device.is_active,
        "deactivate_at": device.deactivate_at
    }


@router.get("/sensor", response_model=List[schemas.SensorDataResponse])
def admin_get_sensor_data(
    response: Response,
    uid: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 500,
    sort_dir: Optional[str] = "desc",
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    device = db.query(models.Device).filter(models.Device.uid == uid).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    query = db.query(models.SensorData).filter(
        models.SensorData.device_id == device.id
    )
    if start_date:
        query = query.filter(
            models.SensorData.timestamp >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        query = query.filter(
            models.SensorData.timestamp <= datetime.combine(end_date, datetime.max.time())
        )

    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    if sort_dir == "asc":
        query = query.order_by(models.SensorData.timestamp.asc())
    else:
        query = query.order_by(models.SensorData.timestamp.desc())

    return query.offset(skip).limit(limit).all()
