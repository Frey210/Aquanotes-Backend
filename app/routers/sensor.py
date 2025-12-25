from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from datetime import datetime, date
from app import models, schemas, database
from typing import List, Optional

router = APIRouter(prefix="/sensor", tags=["Sensor Data"])

from datetime import datetime
from fastapi import HTTPException

@router.post("/", response_model=schemas.SensorDataResponse)
def create_sensor_data(
    data: schemas.SensorDataCreate,
    db: Session = Depends(database.get_db)
):
    device = db.query(models.Device).filter(
        models.Device.uid == data.uid
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.deactivate_at and device.deactivate_at <= datetime.utcnow():
        device.is_active = False
        device.status = "offline"
        device.last_seen = None
        db.add(device)
        db.commit()
    if device.is_active is False:
        raise HTTPException(status_code=403, detail="Device is inactive")
    
    try:
        # Parse timestamp dari device TANPA konversi timezone
        device_timestamp = datetime.fromisoformat(data.timestamp.replace('Z', '+00:00'))
        
        # Jika timestamp memiliki timezone, strip informasi timezone-nya
        if device_timestamp.tzinfo is not None:
            device_timestamp = device_timestamp.replace(tzinfo=None)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid timestamp format. Gunakan format ISO 8601 (contoh: 2025-07-18T06:00:00)"
        )
    
    # Update last_seen device (tetap gunakan waktu server untuk internal tracking)
    device.last_seen = datetime.utcnow()
    device.status = 'online'
    db.add(device)
    
    # Simpan timestamp persis seperti dari device (tanpa timezone)
    sensor_data = models.SensorData(
        device_id=device.id,
        timestamp=device_timestamp,  # Gunakan langsung timestamp device
        suhu=data.suhu,
        ph=data.ph,
        do=data.do,
        tds=data.tds,
        ammonia=data.ammonia,
        salinitas=data.salinitas
    )
    
    db.add(sensor_data)
    db.commit()
    db.refresh(sensor_data)
    
    return sensor_data

from fastapi import Depends, HTTPException, status
from app.auth import get_current_user

@router.get("/", response_model=List[schemas.SensorDataResponse])
def get_sensor_data(
    response: Response,
    uid: str = Query(..., description="UID perangkat"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000),
    sort_dir: Optional[str] = Query("desc"),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)  # Verifikasi token
):
    """
    Mendapatkan data sensor DENGAN otorisasi.
    Hanya pemilik device yang bisa akses datanya.
    """
    
    # 1. Cari device dan verifikasi kepemilikan
    device = db.query(models.Device).filter(
        models.Device.uid == uid,
        models.Device.user_id == current_user.id  # Pastikan device milik user
    ).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device tidak ditemukan atau tidak memiliki akses"
        )

    # 2. Query data
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

    sensor_data = query.offset(skip).limit(limit).all()

    return sensor_data
