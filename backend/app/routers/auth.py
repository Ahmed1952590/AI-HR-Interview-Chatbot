import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, utcnow
from ..security import (hash_password, verify_password, create_token, user_out, bearer, REVOKED_TOKENS, get_current_user)

router = APIRouter(tags=["Authentication"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)


@router.post("/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "This email is already registered")
    user = User(name=data.name.strip(), email=email, hashed_password=hash_password(data.password), role="candidate")
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": create_token(user), "token_type": "bearer", "user": user_out(user)}


@router.post("/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "This account has been disabled")
    user.last_login = utcnow()
    db.commit()
    return {"access_token": create_token(user), "token_type": "bearer", "user": user_out(user)}


@router.get("/validate-token")
def validate_token(user: User = Depends(get_current_user)):
    return {"valid": True, "user": user_out(user)}


@router.post("/logout")
def logout(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if creds:
        REVOKED_TOKENS.add(creds.credentials)
    return {"message": "Logged out"}


@router.post("/forgot-password")
def forgot_password(data: ForgotIn, db: Session = Depends(get_db)):
    """No mail server in this project: the reset token is returned directly (demo mode)."""
    user = db.query(User).filter(User.email == data.email.lower()).first()
    result = {"message": "If the email exists, a reset token has been generated."}
    if user:
        user.reset_token = secrets.token_urlsafe(24)
        user.reset_expires = utcnow() + timedelta(minutes=30)
        db.commit()
        result["reset_token"] = user.reset_token
    return result


@router.post("/reset-password")
def reset_password(data: ResetIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == data.token).first()
    if not user or not user.reset_expires or user.reset_expires < utcnow():
        raise HTTPException(400, "Reset token is invalid or expired")
    user.hashed_password = hash_password(data.new_password)
    user.reset_token = None
    user.reset_expires = None
    db.commit()
    return {"message": "Password updated. You can log in now."}
