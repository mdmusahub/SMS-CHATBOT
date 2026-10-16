import os

from .config import Settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def build_llm(settings: Settings, model: str | None = None):
    """Provider is chosen from .env (LLM_PROVIDER) so it can be swapped without touching the agent.
    `model` overrides LLM_MODEL (used for the LLM_FALLBACK_MODELS backups, same provider)."""
    provider = settings.llm_provider
    model = model or settings.llm_model
    retries = 0 if settings.llm_fallback_models else 2   # with backups, fail over at once instead of retrying

    if provider == "groq":                      # Groq is OpenAI-compatible and supports tool calling
        from langchain_openai import ChatOpenAI
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set")
        return ChatOpenAI(model=model, temperature=0, api_key=key, base_url=GROQ_BASE_URL, max_retries=retries)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set")
        return ChatOpenAI(model=model, temperature=0, max_retries=retries,
                          base_url=os.environ.get("OPENAI_BASE_URL") or None)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        return ChatAnthropic(model=model, max_tokens=1024, max_retries=retries)  # no temperature: newer models reject it

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not set")

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=0,
            google_api_key=key,
            max_retries=retries,
        )

    raise RuntimeError(f"Unknown LLM_PROVIDER '{provider}' (use groq, openai , anthropic or gemini)")
