from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_
import uuid
from app import models, schemas, database
from app.auth import (
    get_password_hash,
    verify_password,
    security,
    get_current_user,
    create_auth_token,
    require_roles
)
from fastapi.security import HTTPAuthorizationCredentials
from typing import Optional

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/register", response_model=schemas.UserResponse)
def register(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db)
):
    existing = db.query(models.User).filter(
        models.User.email == user.email
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    is_first_user = db.query(models.User).count() == 0
    new_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=get_password_hash(user.password),
        role="admin" if is_first_user else "operator"
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=schemas.Token)
def login(
    login_data: schemas.UserLogin,
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(
        models.User.email == login_data.email
    ).first()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    token = create_auth_token(db, user.id)
    return {"access_token": token, "token_type": "bearer"}

@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    token = credentials.credentials
    
    db.query(models.AuthToken).filter(
        models.AuthToken.token == token
    ).delete()
    
    db.commit()
    return {
        "message": "Successfully logged out",
        "success": True
    }

@router.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(
    current_user: models.User = Depends(get_current_user)
):
    return current_user

@router.get("/", response_model=list[schemas.UserResponse])
def list_users(
    response: Response,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    role: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: Optional[str] = "desc",
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    query = db.query(models.User)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                models.User.name.ilike(like),
                models.User.email.ilike(like)
            )
        )
    if role:
        query = query.filter(models.User.role == role)

    total = query.count()
    response.headers["X-Total-Count"] = str(total)

    sort_field_map = {
        "created_at": models.User.created_at,
        "name": models.User.name,
        "email": models.User.email,
        "role": models.User.role
    }
    sort_field = sort_field_map.get(sort_by or "created_at", models.User.created_at)
    if sort_dir == "asc":
        query = query.order_by(sort_field.asc())
    else:
        query = query.order_by(sort_field.desc())

    return query.offset(skip).limit(limit).all()

@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=schemas.UserResponse)
def admin_create_user(
    user: schemas.UserAdminCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    existing = db.query(models.User).filter(
        models.User.email == user.email
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    new_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=get_password_hash(user.password),
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.put("/{user_id}", response_model=schemas.UserResponse)
def admin_update_user(
    user_id: int,
    update: schemas.UserAdminUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if update.email and update.email != user.email:
        existing = db.query(models.User).filter(
            models.User.email == update.email
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        user.email = update.email

    if update.name is not None:
        user.name = update.name
    if update.password:
        user.password_hash = get_password_hash(update.password)
    if update.role:
        user.role = update.role
    if update.notification_cooldown_minutes is not None:
        user.notification_cooldown_minutes = update.notification_cooldown_minutes

    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_roles("admin"))
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the current user"
        )
    db.delete(user)
    db.commit()
    return None

@router.post("/fcm-token", status_code=status.HTTP_200_OK)
def update_fcm_token(
    token_data: schemas.FCMTokenUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update FCM token untuk notifikasi push
    
    Args:
        token_data: Objek berisi token FCM
        
    Returns:
        Konfirmasi update berhasil
    """
    # Validasi token tidak kosong
    if not token_data.token or len(token_data.token) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid FCM token"
        )
    
    # Update token di database
    current_user.fcm_token = token_data.token
    db.commit()
    
    return {
        "message": "FCM token updated successfully",
        "new_token": token_data.token[:10] + "..."  # Return partial token for security
    }

@router.delete("/fcm-token", status_code=status.HTTP_200_OK)
def remove_fcm_token(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Hapus FCM token (saat logout atau uninstall app)
    """
    current_user.fcm_token = None
    db.commit()
    return {"message": "FCM token removed successfully"}

@router.put("/profile", response_model=schemas.UserResponse)
def update_user_profile(
    profile_data: schemas.UserProfileUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update profil user (nama, password)
    """
    # Update nama jika ada
    if profile_data.name:
        current_user.name = profile_data.name
    
    # Update password jika ada
    if profile_data.new_password:
        # Verifikasi password lama
        if not verify_password(profile_data.old_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect current password"
            )
        
        # Update password baru
        current_user.password_hash = get_password_hash(profile_data.new_password)

    # Update cooldown notifikasi jika ada
    if profile_data.notification_cooldown_minutes is not None:
        current_user.notification_cooldown_minutes = profile_data.notification_cooldown_minutes
    
    db.commit()
    db.refresh(current_user)
    return current_user
