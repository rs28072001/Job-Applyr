from dataclasses import dataclass


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    base_url: str
    api_key: str
    model: str


class LLMConfigError(Exception):
    pass


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

    if provider == "groq":
        return LLMSettings(
            provider="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key=getattr(cfg, "groq_api_key", "") or "",
            model=getattr(cfg, "groq_model", "") or "openai/gpt-oss-120b",
        )

    if provider == "openrouter":
        return LLMSettings(
            provider="openrouter",
            base_url=(getattr(cfg, "openrouter_base_url", "") or "https://openrouter.ai/api/v1").rstrip("/"),
            api_key=getattr(cfg, "openrouter_api_key", "") or "",
            model=getattr(cfg, "openrouter_model", "") or "openai/gpt-oss-120b",
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


def validate_llm_settings(settings: LLMSettings) -> None:
    if not settings.api_key:
        raise LLMConfigError(f"{settings.provider} API key is missing.")
    if not settings.model:
        raise LLMConfigError(f"{settings.provider} model is missing.")
    if not settings.base_url:
        raise LLMConfigError(f"{settings.provider} endpoint is missing.")
    if settings.provider == "azure" and "/openai/v1" not in settings.base_url.rstrip("/"):
        raise LLMConfigError(
            "Azure OpenAI endpoint must include '/openai/v1/', for example "
            "https://your-resource.openai.azure.com/openai/v1/"
        )
