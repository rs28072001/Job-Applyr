"""GET /api/config  ·  PUT /api/config"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from api.auth import get_current_user
from api.database import get_db
from api.models import Config, User
from api.schemas import ConfigUpdate

router = APIRouter()

_REQUIRED_FIELDS = ("azure_openai_endpoint", "azure_openai_api_key")


def _mask(cfg: Config) -> dict:
    d = {c.name: getattr(cfg, c.name) for c in Config.__table__.columns}
    for f in ("naukri_password", "linkedin_password", "azure_openai_api_key"):
        if d.get(f):
            d[f] = "***"
    d["is_configured"] = all(getattr(cfg, f) for f in _REQUIRED_FIELDS)
    return d


@router.get("/api/config", response_model=dict)
def get_config(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    cfg = db.get(Config, 1)
    return _mask(cfg)


@router.put("/api/config")
def update_config(body: ConfigUpdate, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    cfg = db.get(Config, 1)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(cfg, key, value)
    from datetime import datetime, timezone
    cfg.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "saved", "is_configured": all(getattr(cfg, f) for f in _REQUIRED_FIELDS)}
