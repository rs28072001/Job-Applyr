"""POST /api/cv/parse  ·  GET /api/cv/profile  ·  PUT /api/cv/profile"""
import os
import pathlib

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import CVProfile, User
from api.schemas import CVProfileRead, CVProfileUpdate

router = APIRouter()

CV_DIR = pathlib.Path(os.getenv("CV_UPLOAD_DIR", "./data/cv"))


@router.post("/api/cv/parse", response_model=CVProfileRead)
async def parse_cv_endpoint(cv_file: UploadFile = File(...), db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    CV_DIR.mkdir(parents=True, exist_ok=True)
    dest = CV_DIR / "uploaded_resume.pdf"

    # Save uploaded PDF
    content = await cv_file.read()
    dest.write_bytes(content)

    # Load config from DB for LLM credentials
    from api.models import Config as ConfigModel
    from core.llm_provider import get_llm_settings, is_llm_configured
    cfg = db.get(ConfigModel, 1)
    if not cfg or not is_llm_configured(cfg):
        raise HTTPException(400, "LLM credentials not configured. Complete setup first.")
    llm_settings = get_llm_settings(cfg)

    # Run blocking parse
    try:
        from core.cv_parser import parse_cv, CVParseError
        cv_data = parse_cv(
            str(dest),
            llm_settings.base_url,
            llm_settings.api_key,
            llm_settings.model,
        )
    except Exception as e:
        raise HTTPException(422, f"CV parse failed: {e}")

    # Mark all existing profiles inactive
    db.query(CVProfile).update({"is_active": False})

    # Save new active profile
    profile = CVProfile(
        name=cv_data.name, email=cv_data.email, phone=cv_data.phone,
        raw_text=cv_data.raw_text, skills=cv_data.skills,
        job_titles=cv_data.job_titles, experience_years=cv_data.experience_years,
        education=cv_data.education, summary=cv_data.summary,
        pdf_path=str(dest), is_active=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/api/cv/profile", response_model=CVProfileRead)
def get_profile(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    profile = db.query(CVProfile).filter_by(is_active=True).order_by(CVProfile.id.desc()).first()
    if not profile:
        raise HTTPException(404, "No CV profile found. Upload a CV first.")
    return profile


@router.put("/api/cv/profile", response_model=CVProfileRead)
def update_profile(body: CVProfileUpdate, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    profile = db.query(CVProfile).filter_by(is_active=True).order_by(CVProfile.id.desc()).first()
    if not profile:
        raise HTTPException(404, "No CV profile found.")
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile
