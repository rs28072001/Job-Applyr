"""POST /api/cv/parse  ·  GET /api/cv/profile  ·  PUT /api/cv/profile  ·  POST /api/cv/ats-analyze  ·  POST /api/cv/suggest-keywords"""
import os
import pathlib

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel

from api.auth import get_current_user
from api.database import get_db
from api.models import CVProfile, User
from api.schemas import CVProfileRead, CVProfileUpdate

router = APIRouter()

CV_DIR = pathlib.Path(os.getenv("CV_UPLOAD_DIR", "./data/cv"))


class ATSAnalysisResponse(BaseModel):
    score: int
    strengths: list[str]
    improvements: list[str]
    overall_feedback: str


@router.post("/api/cv/parse", response_model=CVProfileRead)
async def parse_cv_endpoint(cv_file: UploadFile = File(...), db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    CV_DIR.mkdir(parents=True, exist_ok=True)
    dest = CV_DIR / "uploaded_resume.pdf"

    # Save uploaded PDF
    content = await cv_file.read()
    dest.write_bytes(content)

    # Load config from DB for LLM credentials
    from api.models import Config as ConfigModel
    from core.llm_provider import get_llm_settings, is_llm_configured, validate_llm_settings, LLMConfigError
    cfg = db.get(ConfigModel, 1)
    llm_settings = get_llm_settings(cfg) if cfg else None

    # Fuzzy (no-AI) mode: extract with regex/keyword heuristics, no credentials.
    if llm_settings and llm_settings.provider == "fuzzy":
        try:
            from core.cv_parser import parse_cv_fuzzy
            cv_data = parse_cv_fuzzy(str(dest))
        except Exception as e:
            raise HTTPException(422, f"CV parse failed: {str(e) or type(e).__name__}")
        db.query(CVProfile).update({"is_active": False})
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

    if not cfg or not is_llm_configured(cfg):
        raise HTTPException(400, "LLM credentials not configured. Complete setup first.")
    try:
        validate_llm_settings(llm_settings)
    except LLMConfigError as e:
        raise HTTPException(400, str(e))

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
        msg = str(e) or type(e).__name__
        if "Connection error" in msg:
            msg = (
                f"Could not reach {llm_settings.provider} at {llm_settings.base_url}. "
                "Check the active provider, endpoint, API key, and model."
            )
        raise HTTPException(422, f"CV parse failed: {msg}")

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


@router.post("/api/cv/ats-analyze", response_model=ATSAnalysisResponse)
def analyze_ats(db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    profile = db.query(CVProfile).filter_by(is_active=True).order_by(CVProfile.id.desc()).first()
    if not profile:
        raise HTTPException(404, "No CV profile found. Upload a CV first.")

    # Load config from DB for LLM credentials
    from api.models import Config as ConfigModel
    from core.llm_provider import get_llm_settings, is_llm_configured, validate_llm_settings, LLMConfigError
    from openai import OpenAI

    cfg = db.get(ConfigModel, 1)
    llm_settings = get_llm_settings(cfg) if cfg else None
    if llm_settings and llm_settings.provider == "fuzzy":
        raise HTTPException(400, "Know Your ATS needs an AI provider. Select one in Settings (fuzzy/no-AI mode can't analyze resumes).")
    if not cfg or not is_llm_configured(cfg):
        raise HTTPException(400, "LLM credentials not configured. Complete setup first.")
    try:
        validate_llm_settings(llm_settings)
    except LLMConfigError as e:
        raise HTTPException(400, str(e))

    # Build CV text for analysis
    cv_text = f"""
Name: {profile.name}
Email: {profile.email}
Phone: {profile.phone}
Experience: {profile.experience_years} years
Job Titles: {', '.join(profile.job_titles)}
Skills: {', '.join(profile.skills)}
Education: {', '.join(profile.education)}
Summary: {profile.summary}
Full Resume Text: {profile.raw_text}
"""

    # ATS analysis prompt
    system_prompt = """You are an expert ATS (Applicant Tracking System) analyzer. Analyze the following resume and provide:

1. An ATS score from 0-100 based on:
   - Keyword optimization
   - Format and structure
   - Content completeness
   - Skills relevance
   - Experience presentation

2. A list of 3-5 strengths (what the resume does well)

3. A list of 3-5 specific improvements (what should be added/changed)

4. Overall feedback (2-3 sentences summary)

Respond in JSON format with this exact structure:
{
  "score": <number 0-100>,
  "strengths": ["strength1", "strength2", ...],
  "improvements": ["improvement1", "improvement2", ...],
  "overall_feedback": "summary text"
}"""

    user_prompt = "Resume to analyze:\n" + cv_text

    try:
        client = OpenAI(
            base_url=llm_settings.base_url,
            api_key=llm_settings.api_key,
        )
        
        response = client.chat.completions.create(
            model=llm_settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        import json
        import re
        text = response.choices[0].message.content.strip()
        # Clean up JSON response if it has markdown code blocks
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        
        result = json.loads(text)
        return ATSAnalysisResponse(
            score=result.get("score", 70),
            strengths=result.get("strengths", []),
            improvements=result.get("improvements", []),
            overall_feedback=result.get("overall_feedback", "Resume analysis complete"),
        )
    except Exception as e:
        print(f"ATS analysis error: {e}")
        raise HTTPException(500, f"ATS analysis failed: {str(e)}")


class SuggestKeywordsRequest(BaseModel):
    cv_text: str


class SuggestKeywordsResponse(BaseModel):
    keywords: list[str]


@router.post("/api/cv/suggest-keywords", response_model=SuggestKeywordsResponse)
def suggest_keywords(body: SuggestKeywordsRequest, db: DBSession = Depends(get_db), _: User = Depends(get_current_user)):
    if not body.cv_text or not body.cv_text.strip():
        raise HTTPException(400, "CV text is empty")

    from api.models import Config as ConfigModel
    from core.llm_provider import get_llm_settings, is_llm_configured, validate_llm_settings, LLMConfigError
    from openai import OpenAI

    cfg = db.get(ConfigModel, 1)
    llm_settings = get_llm_settings(cfg) if cfg else None

    if llm_settings and llm_settings.provider == "fuzzy":
        raise HTTPException(400, "Keyword suggestion needs an AI provider. Use non-fuzzy mode in Settings.")
    if not cfg or not is_llm_configured(cfg):
        raise HTTPException(400, "LLM credentials not configured. Complete setup first.")
    try:
        validate_llm_settings(llm_settings)
    except LLMConfigError as e:
        raise HTTPException(400, str(e))

    system_prompt = """You are an expert recruiter and career coach. Analyze the provided resume and suggest 3-5 relevant job titles/keywords that this candidate should target when job searching.

Focus on:
- Primary job titles that match their experience level and skills
- Common industry role variations and synonyms
- Emerging titles in their field
- Entry points for skill transitions

Return ONLY a JSON object with "keywords" as an array of strings. Example:
{"keywords": ["QA Engineer", "Test Automation Engineer", "SDET", "Quality Assurance Lead"]}"""

    user_prompt = f"Resume:\n\n{body.cv_text}\n\nSuggest relevant job titles this candidate should target."

    try:
        client = OpenAI(
            base_url=llm_settings.base_url,
            api_key=llm_settings.api_key,
        )

        response = client.chat.completions.create(
            model=llm_settings.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )

        import json
        import re
        text = response.choices[0].message.content.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        result = json.loads(text)
        keywords = result.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = [str(keywords)]

        return SuggestKeywordsResponse(keywords=keywords[:10])
    except Exception as e:
        print(f"Keyword suggestion error: {e}")
        raise HTTPException(500, f"Keyword suggestion failed: {str(e)}")
