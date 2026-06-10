from dataclasses import dataclass


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    base_url: str
    api_key: str
    model: str


def get_llm_settings(cfg) -> LLMSettings:
    provider = (getattr(cfg, "ai_provider", "") or "azure").lower()

    if provider == "openai":
        return LLMSettings(
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key=getattr(cfg, "openai_api_key", "") or "",
            model=getattr(cfg, "openai_model", "") or "gpt-4o-mini",
        )

    if provider == "gemini":
        return LLMSettings(
            provider="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=getattr(cfg, "gemini_api_key", "") or "",
            model=getattr(cfg, "gemini_model", "") or "gemini-2.5-flash",
        )

    if provider == "grok":
        return LLMSettings(
            provider="grok",
            base_url="https://api.x.ai/v1",
            api_key=getattr(cfg, "grok_api_key", "") or "",
            model=getattr(cfg, "grok_model", "") or "grok-3-mini",
        )

    return LLMSettings(
        provider="azure",
        base_url=getattr(cfg, "azure_openai_endpoint", "") or "",
        api_key=getattr(cfg, "azure_openai_api_key", "") or "",
        model=getattr(cfg, "azure_deployment_name", "") or "gpt-4o-mini",
    )


def is_llm_configured(cfg) -> bool:
    settings = get_llm_settings(cfg)
    return bool(settings.base_url and settings.api_key and settings.model)
