"""GET /api/config  ·  PUT /api/config"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import Config, User
from api.schemas import ConfigTestRequest, ConfigTestResponse, ConfigUpdate
from core.llm_provider import get_llm_settings, is_llm_configured, validate_llm_settings, LLMConfigError

router = APIRouter()
SECRET_MASK = "***"
SECRET_FIELDS = (
    "naukri_password",
    "linkedin_password",
    "azure_openai_api_key",
    "openai_api_key",
    "gemini_api_key",
    "groq_api_key",
    "openrouter_api_key",
)

def _mask(cfg: Config) -> dict:
    d = {c.name: getattr(cfg, c.name) for c in Config.__table__.columns}
    for f in SECRET_FIELDS:
        if d.get(f):
            d[f] = SECRET_MASK
    d["is_configured"] = is_llm_configured(cfg)
    return d


@router.get("/api/config", response_model=dict)
def get_config(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    cfg = db.get(Config, 1)
    return _mask(cfg)


@router.put("/api/config")
def update_config(body: ConfigUpdate, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    cfg = db.get(Config, 1)
    for key, value in body.model_dump(exclude_unset=True).items():
        if key in SECRET_FIELDS and value == SECRET_MASK:
            continue
        if value is not None:
            setattr(cfg, key, value)
    cfg.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "saved", "is_configured": is_llm_configured(cfg)}


@router.post("/api/config/test", response_model=ConfigTestResponse)
def test_config(body: ConfigTestRequest, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    cfg = db.get(Config, 1)
    values = {c.name: getattr(cfg, c.name) for c in Config.__table__.columns}

    for key, value in body.model_dump(exclude_unset=True).items():
        if key in SECRET_FIELDS and value == SECRET_MASK:
            continue
        if value is not None:
            values[key] = value

    class CandidateConfig:
        pass

    candidate = CandidateConfig()
    for key, value in values.items():
        setattr(candidate, key, value)

    settings = get_llm_settings(candidate)
    try:
        validate_llm_settings(settings)
    except LLMConfigError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "provider": settings.provider,
                "model": settings.model,
                "error": str(exc),
            },
        ) from exc

    try:
        client = OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        response = client.chat.completions.create(
            model=settings.model,
            messages=[
                {"role": "system", "content": "You are testing an API connection. Reply briefly."},
                {"role": "user", "content": "Reply with: connection ok"},
            ],
            max_tokens=20,
            temperature=0,
        )
        output = (response.choices[0].message.content or "").strip()
        return ConfigTestResponse(
            ok=True,
            provider=settings.provider,
            model=settings.model,
            output=output,
        )
    except Exception as exc:
        message = str(exc)
        if len(message) > 700:
            message = message[:700] + "..."
        raise HTTPException(
            status_code=400,
            detail={
                "provider": settings.provider,
                "model": settings.model,
                "error": message,
            },
        ) from exc
