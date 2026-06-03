"""POST /api/auth/signup  ·  POST /api/auth/login  ·  GET /api/auth/me"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session as DBSession

from api.auth import hash_password, verify_password, create_access_token, get_current_user
from api.database import get_db
from api.models import User, Config

router = APIRouter(prefix="/api/auth")


class SignUpRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str = ""
    # Azure config collected at signup — saves user a step
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_deployment_name: str = "gpt-4o-mini"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    full_name: str


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignUpRequest, db: DBSession = Depends(get_db)):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    db.flush()  # get user.id before committing

    # Store Azure config in the Config row (created by init_db)
    cfg = db.get(Config, 1)
    if cfg and body.azure_openai_endpoint:
        cfg.azure_openai_endpoint = body.azure_openai_endpoint
        cfg.azure_openai_api_key  = body.azure_openai_api_key
        cfg.azure_deployment_name = body.azure_deployment_name or "gpt-4o-mini"

    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DBSession = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "user_id":   current_user.id,
        "email":     current_user.email,
        "full_name": current_user.full_name,
    }


@router.get("/check-setup")
def check_setup(db: DBSession = Depends(get_db)):
    """Public endpoint — tells the frontend whether any users exist yet."""
    has_users = db.query(User).count() > 0
    return {"has_users": has_users}
