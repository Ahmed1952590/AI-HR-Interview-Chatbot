from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Interview
from ..security import get_current_user, require_admin, hash_password, verify_password, user_out

router = APIRouter(tags=["Users"])


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    target_role: Optional[str] = None
    experience: Optional[str] = None
    industry: Optional[str] = None
    language: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class AdminUserUpdate(ProfileUpdate):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


def _apply(user: User, data: dict):
    for k, v in data.items():
        if v is not None:
            setattr(user, k, v.strip() if isinstance(v, str) else v)


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return user_out(user)


@router.put("/profile")
def update_profile(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _apply(user, data.model_dump())
    db.commit()
    return user_out(user)


@router.put("/profile/password")
def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "Password changed"}


@router.delete("/profile")
def delete_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _delete_user(db, user)
    return {"message": "Account deleted"}


def _delete_user(db: Session, user: User):
    for iv in db.query(Interview).filter(Interview.user_id == user.id).all():
        db.delete(iv)
    db.delete(user)
    db.commit()


# ---- administrator ----
@router.get("/users")
def list_users(search: str = "", page: int = 1, page_size: int = 20, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(User)
    if search:
        like = f"%{search.lower()}%"
        q = q.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    total = q.count()
    rows = q.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    counts = {u.id: db.query(Interview).filter(Interview.user_id == u.id).count() for u in rows}
    return {"total": total, "items": [{**user_out(u), "interviews": counts[u.id]} for u in rows]}


@router.put("/users/{user_id}")
def admin_update_user(user_id: int, data: AdminUserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    payload = data.model_dump()
    if payload.get("role") not in (None, "admin", "candidate"):
        raise HTTPException(400, "Role must be 'admin' or 'candidate'")
    if user.id == admin.id and (payload.get("is_active") is False or payload.get("role") == "candidate"):
        raise HTTPException(400, "You cannot disable or demote your own account")
    if payload.get("email"):
        payload["email"] = payload["email"].lower()
        other = db.query(User).filter(User.email == payload["email"], User.id != user.id).first()
        if other:
            raise HTTPException(400, "Email already in use")
    _apply(user, payload)
    db.commit()
    return user_out(user)


@router.delete("/users/{user_id}")
def admin_delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot delete your own account")
    _delete_user(db, user)
    return {"message": "User deleted"}
