"""
config.py — Central configuration for fin-chatbot.

Reads API key from st.secrets first (for Streamlit Community Cloud),
then falls back to environment variables or .env.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root if present
_project_root = Path(__file__).parent.resolve()
load_dotenv(_project_root / ".env")

# ── API Key Resolution (st.secrets -> os.environ -> .env) ──────────────────────
def get_gemini_api_key() -> str:
    # 1. Try Streamlit secrets (Community Cloud)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    # 2. Try OS environment or .env
    return os.environ.get("GEMINI_API_KEY", "")


GEMINI_API_KEY: str = get_gemini_api_key()
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# ── Currency & locale ─────────────────────────────────────────────────────────
CURRENCY: str = os.environ.get("CURRENCY", "INR")
CURRENCY_SYMBOL: str = os.environ.get("CURRENCY_SYMBOL", "₹")

# ── RAG ───────────────────────────────────────────────────────────────────────
RAG_MIN_SCORE: float = float(os.environ.get("RAG_MIN_SCORE", "0.35"))
RAG_TOP_K: int = int(os.environ.get("RAG_TOP_K", "4"))
CHUNK_SIZE_TOKENS: int = int(os.environ.get("CHUNK_SIZE_TOKENS", "500"))
CHUNK_OVERLAP_TOKENS: int = int(os.environ.get("CHUNK_OVERLAP_TOKENS", "50"))

# ── Paths ─────────────────────────────────────────────────────────────────────
CHROMA_PATH: Path = Path(os.environ.get("CHROMA_PATH", str(_project_root / "chroma_db")))
DOCS_PATH: Path = Path(os.environ.get("DOCS_PATH", str(_project_root / "data" / "docs")))
PROFILE_PATH: Path = Path(os.environ.get("PROFILE_PATH", str(_project_root / "profile.json")))

# ── Embedding model (local) ───────────────────────────────────────────────────
EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ── Chat history & Cost Safeguards ────────────────────────────────────────────
MAX_HISTORY_TURNS: int = int(os.environ.get("MAX_HISTORY_TURNS", "20"))
MAX_TOOL_ITERATIONS: int = int(os.environ.get("MAX_TOOL_ITERATIONS", "5"))
MAX_MESSAGES_PER_SESSION: int = int(os.environ.get("MAX_MESSAGES_PER_SESSION", "30"))

# ── Guardrails ────────────────────────────────────────────────────────────────
FLAGGED_RESPONSE_PHRASES: list[str] = ["guaranteed", "risk-free", "no risk", "assured returns"]
CRISIS_HELPLINE: str = "iCall: 9152987821 | Vandrevala Foundation: 1860-2662-345 (24×7)"
