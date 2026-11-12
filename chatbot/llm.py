"""
llm.py — Chat loop and tool-call orchestration with Gemini.

Flow per turn:
  1. Pre-guardrail check (rule-based, fast)
  2. RAG retrieve (conceptual queries)
  3. LLM call with tool schemas
  4. Tool-call loop (max MAX_TOOL_ITERATIONS)
     └─ Catch ValueError → let model ask user for corrected inputs
  5. Final LLM response
  6. Post-guardrail check
  7. Return ChatResponse

History is kept as a list of Gemini Content objects, trimmed to MAX_HISTORY_TURNS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import google.generativeai as genai

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_HISTORY_TURNS,
    MAX_TOOL_ITERATIONS,
)
from chatbot.guardrails import GuardrailResult, pre_check, post_check
from chatbot.profile import ProfileManager
from chatbot.prompts import SYSTEM_PROMPT, rag_context_block, tool_result_injection
from chatbot.tool_schemas import TOOL_DECLARATIONS
import chatbot.tools as tools_module


# ─────────────────────────────────────────────────────────────────────────────
# Configure Gemini
# ─────────────────────────────────────────────────────────────────────────────

if not GEMINI_API_KEY:
    raise EnvironmentError(
        "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
    )

genai.configure(api_key=GEMINI_API_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# Tool dispatcher
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_FN_MAP: dict[str, Any] = {
    "loan_emi": tools_module.loan_emi,
    "loan_amortization": tools_module.loan_amortization,
    "compound_interest": tools_module.compound_interest,
    "sip_future_value": tools_module.sip_future_value,
    "savings_goal_timeline": tools_module.savings_goal_timeline,
    "required_monthly_saving": tools_module.required_monthly_saving,
    "budget_split_50_30_20": tools_module.budget_split_50_30_20,
    "debt_payoff": tools_module.debt_payoff,
    "retirement_projection": tools_module.retirement_projection,
    "emergency_fund_target": tools_module.emergency_fund_target,
    "inflation_adjusted_value": tools_module.inflation_adjusted_value,
    # update_profile is handled specially (needs profile_manager)
}


def _dispatch_tool(name: str, args: dict, profile_manager: ProfileManager) -> dict:
    """Execute a tool call and return its result dict."""
    if name == "update_profile":
        return profile_manager.update(args)

    fn = _TOOL_FN_MAP.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}

    try:
        return fn(**args)
    except (ValueError, TypeError) as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Response type
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ToolCallRecord:
    name: str
    args: dict
    result: dict


@dataclass
class ChatResponse:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    guardrail_message: str = ""
    guardrail_category: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# History helpers
# ─────────────────────────────────────────────────────────────────────────────

def _trim_history(history: list, max_turns: int) -> list:
    """Keep the last max_turns user+model pairs."""
    # Each turn = 1 user + 1 model message = 2 items
    max_items = max_turns * 2
    if len(history) > max_items:
        return history[-max_items:]
    return history


def _build_gemini_tools() -> list:
    """Convert TOOL_DECLARATIONS list into Gemini Tool objects."""
    function_declarations = []
    for schema in TOOL_DECLARATIONS:
        function_declarations.append(
            genai.protos.FunctionDeclaration(
                name=schema["name"],
                description=schema["description"],
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        k: _param_to_schema(v)
                        for k, v in schema["parameters"].get("properties", {}).items()
                    },
                    required=schema["parameters"].get("required", []),
                ),
            )
        )
    return [genai.protos.Tool(function_declarations=function_declarations)]


def _param_to_schema(param: dict) -> genai.protos.Schema:
    """Convert a JSON Schema parameter dict to a Gemini Schema proto."""
    type_map = {
        "string": genai.protos.Type.STRING,
        "number": genai.protos.Type.NUMBER,
        "integer": genai.protos.Type.INTEGER,
        "boolean": genai.protos.Type.BOOLEAN,
        "array": genai.protos.Type.ARRAY,
        "object": genai.protos.Type.OBJECT,
    }
    ptype = type_map.get(param.get("type", "string"), genai.protos.Type.STRING)

    kwargs: dict = {
        "type": ptype,
        "description": param.get("description", ""),
    }

    if "enum" in param:
        kwargs["enum"] = param["enum"]

    if ptype == genai.protos.Type.ARRAY and "items" in param:
        kwargs["items"] = _param_to_schema(param["items"])

    if ptype == genai.protos.Type.OBJECT and "properties" in param:
        kwargs["properties"] = {
            k: _param_to_schema(v) for k, v in param["properties"].items()
        }
        if "required" in param:
            kwargs["required"] = param["required"]

    return genai.protos.Schema(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Main chat session
# ─────────────────────────────────────────────────────────────────────────────

class ChatSession:
    """
    Maintains conversation state across turns.
    One instance per user session.
    """

    def __init__(self, profile_manager: ProfileManager | None = None):
        self._history: list = []
        self._profile_manager = profile_manager or ProfileManager()
        self._tools = _build_gemini_tools()
        self._model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            tools=self._tools,
        )

    def reset(self):
        self._history = []
        self._profile_manager.reset()

    def chat(self, user_message: str, rag_retrieve_fn=None) -> ChatResponse:
        """
        Process one user turn and return a ChatResponse.

        Parameters
        ----------
        user_message    : Raw text from the user.
        rag_retrieve_fn : Optional callable(query) -> list[chunk_dicts].
                          If None, RAG is skipped.
        """
        # ── 1. Pre-guardrail check ────────────────────────────────────────────
        guard = pre_check(user_message)

        if not guard.allowed and guard.category.value != "sensitive_data":
            return ChatResponse(
                answer=guard.message,
                guardrail_message=guard.message,
                guardrail_category=guard.category.value,
            )

        # Use scrubbed text if sensitive data was found
        effective_message = guard.scrubbed_text or user_message
        sensitive_warning = guard.message if guard.category.value == "sensitive_data" else ""

        # ── 2. RAG retrieve ───────────────────────────────────────────────────
        rag_chunks: list[dict] = []
        sources: list[str] = []
        if rag_retrieve_fn:
            try:
                rag_chunks = rag_retrieve_fn(effective_message)
                sources = list({c["source"] for c in rag_chunks})
            except Exception:
                rag_chunks = []

        # ── 3. Build user content with optional RAG context ───────────────────
        rag_ctx = rag_context_block(rag_chunks)
        if rag_ctx:
            llm_user_text = f"{rag_ctx}\n\n---\n\nUser question: {effective_message}"
        else:
            # Inject profile context if available
            profile_ctx = self._profile_manager.profile.as_context_string()
            if profile_ctx and profile_ctx != "No profile data yet.":
                llm_user_text = f"[Context: {profile_ctx}]\n\n{effective_message}"
            else:
                llm_user_text = effective_message

        # ── 4. LLM + tool-call loop ───────────────────────────────────────────
        messages = list(self._history) + [{"role": "user", "parts": [llm_user_text]}]
        tool_call_records: list[ToolCallRecord] = []
        iterations = 0
        final_text = ""

        while iterations < MAX_TOOL_ITERATIONS:
            iterations += 1
            response = self._model.generate_content(messages)

            # Check if model wants to call tools
            fn_calls = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call.name:
                    fn_calls.append(part.function_call)

            if not fn_calls:
                # No tool calls → extract text answer
                final_text = response.text or ""
                # Append assistant message to history
                messages.append({"role": "model", "parts": [final_text]})
                break

            # Execute each tool call
            tool_response_parts = []
            for fn_call in fn_calls:
                name = fn_call.name
                args = dict(fn_call.args)
                result = _dispatch_tool(name, args, self._profile_manager)

                record = ToolCallRecord(name=name, args=args, result=result)
                tool_call_records.append(record)

                # Format result for Gemini function response
                tool_response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=name,
                            response={"result": json.dumps(result, ensure_ascii=False)},
                        )
                    )
                )

            # Append model's tool-call turn and tool results
            messages.append(response.candidates[0].content)
            messages.append({"role": "user", "parts": tool_response_parts})

        else:
            # Max iterations hit — ask for a simpler follow-up
            final_text = (
                "I've hit the maximum number of calculation steps for this query. "
                "Could you break it into smaller questions?"
            )

        # ── 5. Update history ─────────────────────────────────────────────────
        # Store original user message in history (not augmented with RAG)
        self._history.append({"role": "user", "parts": [effective_message]})
        self._history.append({"role": "model", "parts": [final_text]})
        self._history = _trim_history(self._history, MAX_HISTORY_TURNS)

        # ── 6. Post-guardrail check ───────────────────────────────────────────
        tool_names_used = [r.name for r in tool_call_records]
        post = post_check(final_text, tool_names_used)

        answer = final_text
        if sensitive_warning:
            answer = sensitive_warning + "\n\n" + answer
        if post.flags:
            answer = answer + "\n\n---\n" + "\n".join(post.flags)

        return ChatResponse(
            answer=answer,
            tool_calls=tool_call_records,
            sources=sources,
            flags=post.flags,
            guardrail_message=guard.message,
            guardrail_category=guard.category.value,
        )

