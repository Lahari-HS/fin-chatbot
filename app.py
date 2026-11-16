"""
app.py — Streamlit UI for the AI-Powered Financial Chatbot (Artha).

Features:
- Chat interface with user & assistant turns.
- Deterministic calculation results with collapsible calculation breakdown.
- Conceptual answers show retrieved source docs.
- Sidebar: Profile management (view & edit), reset button, model / currency status.
- Example clickable prompts for fast demonstration.
- Cost Safeguards: Per-session message counter with configurable limit.
- Auto-RAG Ingestion on startup if ChromaDB index does not exist.
- Footer disclaimer.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Explicitly ensure current file's directory is the first entry in sys.path
_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
if _FILE_DIR not in sys.path:
    sys.path.insert(0, _FILE_DIR)

import re
import streamlit as st

from config import (
    CURRENCY,
    CURRENCY_SYMBOL,
    GEMINI_MODEL,
    MAX_MESSAGES_PER_SESSION,
    PROFILE_PATH,
    CHROMA_PATH,
    get_gemini_api_key,
)
from chatbot.profile import ProfileManager
from chatbot.prompts import EXAMPLE_PROMPTS
from chatbot.guardrails import pre_check
import chatbot.tools as tools_module

# ─────────────────────────────────────────────────────────────────────────────
# Streamlit Page Configuration (MUST BE FIRST STREAMLIT CALL)
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Artha — AI Financial Chatbot",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Auto-RAG Ingestion at startup (cached)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def init_rag_store():
    """Runs idempotent ingest if chroma_db is empty or uninitialized."""
    try:
        from chatbot import rag
        rag.ingest()
    except Exception:
        pass

init_rag_store()

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        font-size: 0.8rem;
        font-weight: 600;
        border-radius: 9999px;
        background-color: #E0E7FF;
        color: #3730A3;
        margin-right: 0.4rem;
    }
    .footer-note {
        font-size: 0.8rem;
        color: #9CA3AF;
        text-align: center;
        margin-top: 3rem;
        border-top: 1px solid #E5E7EB;
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Session State Initialization
# ─────────────────────────────────────────────────────────────────────────────

if "profile_manager" not in st.session_state:
    st.session_state.profile_manager = ProfileManager(persist_path=PROFILE_PATH)

if "message_count" not in st.session_state:
    st.session_state.message_count = 0

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "👋 Namaste! I am **Artha**, your personal finance assistant for India.\n\n"
                "I can help you calculate EMIs, plan SIP investments, build emergency funds, "
                "or budget using the 50/30/20 rule. I use pure deterministic calculators for all numbers, "
                "so there is zero calculation hallucination.\n\n"
                "How can I help you today?"
            ),
            "tool_calls": [],
            "sources": [],
            "flags": [],
        }
    ]

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar: User Profile & Session Controls
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/money-bag-rupee.png", width=64)
    st.markdown("### User Financial Profile")
    st.caption("Shared details act as defaults in calculations without retyping.")

    prof = st.session_state.profile_manager.profile

    with st.form("profile_form"):
        income_val = st.number_input(
            f"Monthly Take-home ({CURRENCY_SYMBOL})",
            value=float(prof.monthly_income or 0.0),
            step=5000.0,
            min_value=0.0,
        )
        expense_val = st.number_input(
            f"Monthly Expenses ({CURRENCY_SYMBOL})",
            value=float(prof.monthly_expenses or 0.0),
            step=5000.0,
            min_value=0.0,
        )
        age_val = st.number_input(
            "Age",
            value=int(prof.age or 25),
            min_value=18,
            max_value=100,
        )
        risk_opts = ["low", "medium", "high"]
        curr_risk = prof.risk_tolerance if prof.risk_tolerance in risk_opts else "medium"
        risk_val = st.selectbox("Risk Tolerance", options=risk_opts, index=risk_opts.index(curr_risk))

        submitted = st.form_submit_button("Update Profile")
        if submitted:
            st.session_state.profile_manager.update({
                "monthly_income": income_val if income_val > 0 else None,
                "monthly_expenses": expense_val if expense_val > 0 else None,
                "age": age_val,
                "risk_tolerance": risk_val,
            })
            st.success("Profile saved!")

    st.markdown("---")
    st.markdown("### System Status")
    st.markdown(f"<span class='badge'>Model: {GEMINI_MODEL}</span>", unsafe_allow_html=True)
    st.markdown(f"<span class='badge'>Locale: {CURRENCY} ({CURRENCY_SYMBOL})</span>", unsafe_allow_html=True)
    st.markdown(
        f"<span class='badge'>Session Queries: {st.session_state.message_count}/{MAX_MESSAGES_PER_SESSION}</span>",
        unsafe_allow_html=True,
    )

    if st.button("🔄 Reset Conversation", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Conversation has been reset. What would you like to calculate or discuss?",
                "tool_calls": [],
                "sources": [],
                "flags": [],
            }
        ]
        st.session_state.profile_manager.reset()
        st.session_state.message_count = 0
        if "llm_session" in st.session_state:
            del st.session_state.llm_session
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Main Chat Header & Quick Prompts
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("<div class='main-title'>🪙 Artha — Financial AI Assistant</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-title'>Deterministic calculation engine & vetted Indian personal finance guidance.</div>",
    unsafe_allow_html=True,
)

st.markdown("##### ⚡ Quick Example Queries:")
cols = st.columns(3)
selected_prompt = None

for i, prompt in enumerate(EXAMPLE_PROMPTS):
    with cols[i % 3]:
        if st.button(prompt, key=f"ex_{i}", use_container_width=True):
            selected_prompt = prompt

# ─────────────────────────────────────────────────────────────────────────────
# Render Chat History
# ─────────────────────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Display Tool Call breakdown if any
        if msg.get("tool_calls"):
            with st.expander("🔍 Calculation Details (Pure Mathematical Proof)", expanded=False):
                for tc in msg["tool_calls"]:
                    st.markdown(f"**Calculator Executed:** `{tc.get('name')}`")
                    st.json({
                        "Inputs Received": tc.get("args"),
                        "Formula Applied": tc.get("result", {}).get("formula", "N/A"),
                        "Assumptions": tc.get("result", {}).get("assumptions", []),
                        "Exact Output": tc.get("result", {}).get("result", {}),
                    })

        # Display Sources if conceptual
        if msg.get("sources"):
            with st.expander("📚 Knowledge Base Citations", expanded=False):
                for s in msg["sources"]:
                    st.markdown(f"- 📄 `{s}`")

        # Display Guardrail Flags if any
        if msg.get("flags"):
            for flag in msg["flags"]:
                st.warning(flag)


# ─────────────────────────────────────────────────────────────────────────────
# Message Processing Loop
# ─────────────────────────────────────────────────────────────────────────────

user_input = st.chat_input("Ask about loans, SIPs, budgeting, or savings...") or selected_prompt

if user_input:
    # Check session limit safeguard
    if st.session_state.message_count >= MAX_MESSAGES_PER_SESSION:
        st.warning(
            f"⚠️ You have reached the session query limit ({MAX_MESSAGES_PER_SESSION} messages). "
            "Please click **Reset Conversation** in the sidebar to start a fresh session."
        )
    else:
        st.session_state.message_count += 1

        # 1. Append user turn
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 2. Run Pre-guardrail check
        with st.chat_message("assistant"):
            with st.spinner("Calculating & analyzing..."):
                g_check = pre_check(user_input)

                if not g_check.allowed:
                    resp = {
                        "content": g_check.message,
                        "tool_calls": [],
                        "sources": [],
                        "flags": [],
                    }
                else:
                    api_key = get_gemini_api_key()
                    if not api_key or api_key.startswith("your_"):
                        resp = {
                            "content": (
                                "⚠️ **Gemini API Key Missing:** Please add your key to `.env` as "
                                "`GEMINI_API_KEY=your_key` or in Streamlit Cloud Secrets to enable full AI responses."
                            ),
                            "tool_calls": [],
                            "sources": [],
                            "flags": [],
                        }
                    else:
                        try:
                            from chatbot.llm import ChatSession
                            from chatbot import rag

                            if "llm_session" not in st.session_state:
                                st.session_state.llm_session = ChatSession(
                                    profile_manager=st.session_state.profile_manager
                                )

                            chat_resp = st.session_state.llm_session.chat(
                                g_check.scrubbed_text or user_input,
                                rag_retrieve_fn=rag.retrieve,
                            )
                            resp = {
                                "content": chat_resp.answer,
                                "tool_calls": [
                                    {"name": tc.name, "args": tc.args, "result": tc.result}
                                    for tc in chat_resp.tool_calls
                                ],
                                "sources": chat_resp.sources,
                                "flags": chat_resp.flags,
                            }
                        except Exception as err:
                            resp = {
                                "content": (
                                    f"⚠️ **Service Notice:** Unable to reach Gemini API at the moment (`{str(err)}`). "
                                    "Please verify your API key and connection."
                                ),
                                "tool_calls": [],
                                "sources": [],
                                "flags": [],
                            }

                # Render assistant message
                st.markdown(resp["content"])

                if resp.get("tool_calls"):
                    with st.expander("🔍 Calculation Details (Pure Mathematical Proof)", expanded=False):
                        for tc in resp["tool_calls"]:
                            st.markdown(f"**Calculator Executed:** `{tc.get('name')}`")
                            st.json({
                                "Inputs Received": tc.get("args"),
                                "Formula Applied": tc.get("result", {}).get("formula", "N/A"),
                                "Assumptions": tc.get("result", {}).get("assumptions", []),
                                "Exact Output": tc.get("result", {}).get("result", {}),
                            })

                if resp.get("sources"):
                    with st.expander("📚 Knowledge Base Citations", expanded=False):
                        for s in resp["sources"]:
                            st.markdown(f"- 📄 `{s}`")

                # Save in history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": resp["content"],
                    "tool_calls": resp.get("tool_calls", []),
                    "sources": resp.get("sources", []),
                    "flags": resp.get("flags", []),
                })


# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    "<div class='footer-note'>"
    "⚠️ <b>Educational Disclaimer:</b> Artha provides financial calculations and educational information only. "
    "It does not offer SEBI-registered investment advice or individual tax opinions. "
    "Consult a certified financial planner for high-stakes decisions."
    "</div>",
    unsafe_allow_html=True,
)
