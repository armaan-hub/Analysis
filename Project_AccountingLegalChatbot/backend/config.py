"""
Central configuration for the Accounting & Legal AI Chatbot.
Reads settings from .env file and exposes them as typed attributes.
"""

import os
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path, interpolate=False)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Active Provider ──────────────────────────────────────────────
    llm_provider: str = "nvidia"  # nvidia | openai | claude | mistral | ollama

    # ── NVIDIA NIM ───────────────────────────────────────────────────
    nvidia_api_key: str = ""
    nvidia_model: str = "mistralai/mistral-large-3-675b-instruct-2512"  # general-purpose chat model
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_embed_model: str = "nvidia/nv-embedqa-e5-v5"
    nvidia_fast_model: str = "mistralai/devstral-2-123b-instruct-2512"
    # Fallback when fast model is DEGRADED on NVIDIA NIM (automatic, no user action needed)
    nvidia_fast_fallback_model: str = "mistralai/mistral-small-4-119b-2603"
    # Separate API key for fast mode (optional — falls back to nvidia_api_key if blank)
    nvidia_fast_api_key: str = ""
    # NVIDIA NIM Mistral models only support "high" and "none" for reasoning_effort
    nvidia_fast_reasoning_effort: Literal["none", "high"] = "high"

    # ── OpenAI ───────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # ── Anthropic Claude ─────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # ── Mistral ──────────────────────────────────────────────────────
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"

    # ── Groq (free tier, OpenAI-compatible) ──────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # ── Ollama (local) ───────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # ── Brave Search ─────────────────────────────────────────────────
    brave_search_api_key: str = ""

    # ── Embedding ────────────────────────────────────────────────────
    embedding_provider: str = "nvidia"  # nvidia | openai
    openai_embed_model: str = "text-embedding-3-small"  # 1536-dim, same as NIM

    # ── Database ─────────────────────────────────────────────────────
    database_url: str = "sqlite:///./data/chatbot.db"

    # ── File Storage ─────────────────────────────────────────────────
    upload_dir: str = "./uploads"
    vector_store_dir: str = "./vector_store_v2"
    graph_store_dir: str = "./graph_store"

    # ── Server ───────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8001   # run_project.ps1 default; override via PORT in .env

    # ── Monitoring ───────────────────────────────────────────────────
    monitor_interval_hours: int = 6

    # ── PDF OCR Fallback (for scanned/image-only PDFs) ──────────────
    pdf_ocr_enabled: bool = True
    pdf_ocr_languages: str = "ara+eng"
    pdf_ocr_dpi: int = 300
    pdf_ocr_min_chars: int = 20
    pdf_ocr_tessdata_dir: str = ""
    pdf_ocr_tesseract_cmd: str = ""

    # ── RAG Settings ─────────────────────────────────────────────────
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 8               # default for analyst / deep_research modes
    max_tokens: Optional[int] = 15649    # deep/analyst: deepseek-v3.2 spec
    fast_top_k: int = 15                 # fast mode: higher retrieval budget
    fast_max_tokens: Optional[int] = 12385   # fast mode: deepseek-v3.1-terminus spec
    temperature: float = 0.10                # low temperature for precise legal/accounting answers
    fast_temperature: float = 0.20           # fast mode temperature (DeepSeek terminus: 0.2)
    deep_temperature: float = 1.00           # deep research / analyst temperature (DeepSeek v3.2: 1.0)
    rag_min_score: float = Field(
        default=0.30,
        gt=0.0,
        lt=1.0,
        description="Drop RAG chunks below this cosine-similarity threshold.",
    )

    model_config = SettingsConfigDict(case_sensitive=False)

    @model_validator(mode="before")
    @classmethod
    def _resolve_relative_paths(cls, values: dict) -> dict:
        """Convert relative paths to absolute, anchored to backend/ directory."""
        _backend_dir = Path(__file__).resolve().parent

        def _abs(p: str) -> str:
            if p.startswith("sqlite:///"):
                raw = p[len("sqlite:///"):]
                rel = Path(raw)
                if not rel.is_absolute():
                    return f"sqlite:///{(_backend_dir / raw).resolve()}"
                return p
            path = Path(p)
            if not path.is_absolute():
                return str((_backend_dir / path).resolve())
            return p

        for key in ("database_url", "upload_dir", "vector_store_dir", "graph_store_dir"):
            if key in values and isinstance(values[key], str):
                values[key] = _abs(values[key])
        return values

    # ── Helper Properties ────────────────────────────────────────────

    @property
    def active_api_key(self) -> str:
        """Return the API key for the currently active provider."""
        key_map = {
            "nvidia": self.nvidia_api_key,
            "openai": self.openai_api_key,
            "claude": self.anthropic_api_key,
            "mistral": self.mistral_api_key,
            "groq": self.groq_api_key,
            "ollama": "",  # Ollama is local, no key needed
        }
        return key_map.get(self.llm_provider, "")

    @property
    def active_model(self) -> str:
        """Return the model name for the currently active provider."""
        model_map = {
            "nvidia": self.nvidia_model,
            "openai": self.openai_model,
            "claude": self.anthropic_model,
            "mistral": self.mistral_model,
            "groq": self.groq_model,
            "ollama": self.ollama_model,
        }
        return model_map.get(self.llm_provider, "")

    def ensure_dirs(self):
        """Create required directories if they don't exist."""
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        Path(self.vector_store_dir).mkdir(parents=True, exist_ok=True)
        Path(self.graph_store_dir).mkdir(parents=True, exist_ok=True)
        db_raw = self.database_url
        if db_raw.startswith("sqlite:///"):
            db_raw = db_raw[len("sqlite:///"):]
        Path(db_raw).parent.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
settings.ensure_dirs()
