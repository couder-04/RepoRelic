"""Unified LLM client — dispatches to Gemini or OpenAI-compatible APIs based on config."""
from __future__ import annotations

from engine.config import Config
from engine.llm.rate_limiter import RateLimiter


class LLMClient:
    """Thin wrapper that picks the right provider and enforces rate limits."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.limiter = RateLimiter(
            max_rpm=cfg.max_rpm,
            max_tpm=cfg.max_tpm,
            min_delay=cfg.min_delay_seconds,
        )
        self._provider = cfg.llm_provider

        if self._provider == "gemini":
            self._backend = _GeminiBackend(cfg)
        elif self._provider in ("openai", "deepseek"):
            self._backend = _OpenAICompatibleBackend(cfg)
        else:
            raise ValueError(f"Unknown LLM provider: {self._provider}")

    def generate(self, prompt: str, model_role: str = "test") -> str:
        """
        Generate text from the LLM.

        Parameters
        ----------
        prompt     : full prompt string
        model_role : "test" (cheaper/faster) or "diag" (smarter/slower)
        """
        estimated = max(500, len(prompt) // 4)
        self.limiter.wait_if_needed(estimated)
        result = self._backend.generate(prompt, model_role)
        self.limiter.record(estimated)
        return result


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

class _GeminiBackend:
    def __init__(self, cfg: Config):
        from google import genai
        self._client = genai.Client(api_key=cfg.gemini_api_key)
        self._models = {
            "test": cfg.gemini_test_model,
            "diag": cfg.gemini_diag_model,
        }

    def generate(self, prompt: str, model_role: str) -> str:
        model = self._models.get(model_role, self._models["test"])
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
        )
        return response.text


# ---------------------------------------------------------------------------
# OpenAI-compatible backend
# ---------------------------------------------------------------------------

class _OpenAICompatibleBackend:
    def __init__(self, cfg: Config):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI-compatible providers require the 'openai' package. "
                "Run: pip install openai"
            )

        api_key = cfg.openai_api_key if cfg.llm_provider == "openai" else cfg.deepseek_api_key
        base_url = cfg.openai_base_url if cfg.llm_provider == "openai" else cfg.deepseek_base_url

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._models = {
            "test": cfg.openai_test_model if cfg.llm_provider == "openai" else cfg.deepseek_test_model,
            "diag": cfg.openai_diag_model if cfg.llm_provider == "openai" else cfg.deepseek_diag_model,
        }

    def generate(self, prompt: str, model_role: str) -> str:
        model = self._models.get(model_role, self._models["test"])
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""
