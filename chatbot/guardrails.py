"""
guardrails.py — Rule-based pre- and post-check filters.

Pre-check: Runs BEFORE the user message reaches the LLM.
Post-check: Runs on the LLM's answer AFTER generation.

Both return a GuardrailResult dataclass.
No I/O, fully typed, no LLM calls (rule-based only for speed and reliability).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from config import CRISIS_HELPLINE, FLAGGED_RESPONSE_PHRASES


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

class Category(str, Enum):
    ALLOWED = "allowed"
    STOCK_PICK = "stock_pick"
    GUARANTEED_RETURNS = "guaranteed_returns"
    SENSITIVE_DATA = "sensitive_data"
    OUT_OF_SCOPE = "out_of_scope"
    CRISIS = "crisis"
    FLAGGED_RESPONSE = "flagged_response"


@dataclass
class GuardrailResult:
    allowed: bool
    category: Category
    message: str                      # human-readable explanation / redirect
    scrubbed_text: str = ""           # text with sensitive data removed (pre-check)
    flags: list[str] = field(default_factory=list)  # post-check flags


# ─────────────────────────────────────────────────────────────────────────────
# Regex patterns
# ─────────────────────────────────────────────────────────────────────────────

# Sensitive data patterns
_CARD_PATTERN = re.compile(
    r"\b(?:\d[ -]?){13,16}\b",  # 13–16 digit card numbers
)
_AADHAAR_PATTERN = re.compile(
    r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b",  # 12-digit Aadhaar
)
_PAN_PATTERN = re.compile(
    r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",  # PAN format: ABCDE1234F
)
_OTP_PATTERN = re.compile(
    r"\b(?:otp|one[- ]time[- ]password|verification[- ]code)[:\s]*\d{4,8}\b",
    re.IGNORECASE,
)
_PASSWORD_PATTERN = re.compile(
    r"\b(?:password|passwd|pin)[:\s=]+\S+",
    re.IGNORECASE,
)
_CVV_PATTERN = re.compile(
    r"\b(?:cvv|cvc|security[- ]code)[:\s]*\d{3,4}\b",
    re.IGNORECASE,
)

# Stock / crypto pick patterns
_STOCK_PICK_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bwhich\s+(?:stock|share|equity|crypto|coin|token)s?\s+(?:should|to|must|can)\s+(?:i\s+)?buy\b",
        r"\bbuy\s+(?:this\s+)?(?:stock|share|equity|crypto|coin|nifty|sensex)\b",
        r"\bshould\s+i\s+(?:buy|sell|invest\s+in)\s+(?:.*?\s+)?(?:stock|share|equity|crypto|coin|bitcoin|ethereum|solana|doge|btc|eth)\b",
        r"\bwhich\s+(?:mutual\s+fund|mf|etf)\s+(?:should|to|must)\s+(?:i\s+)?(?:buy|invest)\b",
        r"\bgive\s+me\s+(?:a\s+)?(?:hot\s+)?(?:insider\s+)?stock\s+tip\b",
        r"\b(?:insider|hot)\s+tips?\b",
        r"\bwhich\s+(?:crypto|bitcoin|ethereum|altcoin)\s+(?:to\s+buy|should\s+i\s+buy)\b",
        r"\bshould\s+i\s+invest\s+in\s+(?:this|that)\s+(?:stock|ipo)\b",
    ]
]

# Guaranteed returns patterns
_GUARANTEED_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bguaranteed\s+(?:\d+%\s+)?(?:returns?|profit|income|gains?)\b",
        r"\brisk[- ]free\s+(?:returns?|investment|profit)\b",
        r"\b(?:no|zero)\s+risk\s+investment\b",
        r"\bassured\s+returns?\b",
        r"\b100\s*%\s+(?:safe|secure)\s+investment\b",
        r"\binsider\s+(?:tips?|info|information|knowledge)\b",
    ]
]

# Out-of-scope patterns (topics unrelated to personal finance)
_OOS_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(?:cricket|football|ipl|sports?\s+bet)\b",
        r"\b(?:recipe|cooking|food\s+prep)\b",
        r"\b(?:political\s+party|election|vote)\b",
        r"\b(?:write\s+(?:me\s+)?(?:a\s+)?(?:poem|story|essay|code(?!\s+for)))\b",
        r"\b(?:movie|movies|netflix|web\s+series)\b",
        r"\bhow\s+(?:to\s+)?(?:cook|bake|make\s+(?:food|recipe))\b",
    ]
]

# Financial crisis / self-harm indicators
_CRISIS_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(?:end\s+(?:it\s+)?all|no\s+reason\s+to\s+live|want\s+to\s+die)\b",
        r"\b(?:suicide|suicidal|kill\s+myself)\b",
        r"\b(?:completely\s+)?ruined[\.,!]?\s*(?:financially|my\s+life)",
        r"\bcan[' ]?t\s+(?:go\s+on|continue)\b",
        r"\b(?:lost\s+everything|destroyed\s+my\s+(?:life|family))\b",
        r"\b(?:no\s+way\s+out|no\s+hope)\b",
    ]
]

# Post-check: currency amounts without tool backing
_CURRENCY_AMOUNT_PATTERN = re.compile(
    r"(?:₹|INR|Rs\.?)\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|thousand|k|L|Cr))?",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Pre-check
# ─────────────────────────────────────────────────────────────────────────────

def pre_check(user_text: str) -> GuardrailResult:
    """
    Validate user input before forwarding to the LLM.

    Returns a GuardrailResult. If allowed=False, the caller should return
    GuardrailResult.message directly to the user WITHOUT calling the LLM.
    If sensitive data is found, scrubbed_text replaces the original.
    """
    # 1. Crisis check (highest priority)
    for pattern in _CRISIS_PATTERNS:
        if pattern.search(user_text):
            return GuardrailResult(
                allowed=False,
                category=Category.CRISIS,
                message=(
                    "I can hear that you're going through something really hard right now. "
                    "Your situation is not hopeless — financial problems, however severe, "
                    "can be worked through one step at a time.\n\n"
                    "Please reach out for support:\n"
                    f"📞 **{CRISIS_HELPLINE}**\n\n"
                    "I'm here to help you work through the financial side whenever you're ready."
                ),
            )

    # 2. Sensitive data check
    scrubbed = user_text
    sensitive_found = []

    if _CARD_PATTERN.search(user_text):
        scrubbed = _CARD_PATTERN.sub("[CARD-NUMBER-REMOVED]", scrubbed)
        sensitive_found.append("card number")
    if _AADHAAR_PATTERN.search(user_text):
        scrubbed = _AADHAAR_PATTERN.sub("[AADHAAR-REMOVED]", scrubbed)
        sensitive_found.append("Aadhaar number")
    if _PAN_PATTERN.search(user_text):
        scrubbed = _PAN_PATTERN.sub("[PAN-REMOVED]", scrubbed)
        sensitive_found.append("PAN")
    if _OTP_PATTERN.search(user_text):
        scrubbed = _OTP_PATTERN.sub("[OTP-REMOVED]", scrubbed)
        sensitive_found.append("OTP")
    if _PASSWORD_PATTERN.search(user_text):
        scrubbed = _PASSWORD_PATTERN.sub("[PASSWORD-REMOVED]", scrubbed)
        sensitive_found.append("password")
    if _CVV_PATTERN.search(user_text):
        scrubbed = _CVV_PATTERN.sub("[CVV-REMOVED]", scrubbed)
        sensitive_found.append("CVV")

    if sensitive_found:
        joined = ", ".join(sensitive_found)
        return GuardrailResult(
            allowed=True,   # Allow to proceed but with scrubbed text
            category=Category.SENSITIVE_DATA,
            message=(
                f"🚨 **Heads up:** I've detected what looks like sensitive data "
                f"({joined}) in your message. Please **never share** card numbers, "
                f"Aadhaar, PAN, OTPs, or passwords here. I've removed that detail "
                f"and will answer your question without it."
            ),
            scrubbed_text=scrubbed,
        )

    # 3. Stock / crypto pick check
    for pattern in _STOCK_PICK_PATTERNS:
        if pattern.search(user_text):
            return GuardrailResult(
                allowed=False,
                category=Category.STOCK_PICK,
                message=(
                    "I'm not able to recommend specific stocks, funds, or cryptocurrencies to buy "
                    "or sell — that would be personalised investment advice, which requires a "
                    "SEBI-registered advisor.\n\n"
                    "What I *can* help you with:\n"
                    "- 📊 Understand how equity, mutual funds, or SIPs work\n"
                    "- ⚖️ Compare asset classes (stocks vs FD vs debt funds)\n"
                    "- 🎯 Figure out how much to invest to reach your goals\n"
                    "- 💡 Learn how to evaluate a fund's risk profile\n\n"
                    "Would any of those help?"
                ),
            )

    # 4. Guaranteed returns check
    for pattern in _GUARANTEED_PATTERNS:
        if pattern.search(user_text):
            return GuardrailResult(
                allowed=False,
                category=Category.GUARANTEED_RETURNS,
                message=(
                    "No legitimate investment offers guaranteed returns (except government-backed "
                    "instruments like PPF, Sukanya Samriddhi, or fixed bank deposits up to DICGC limits). "
                    "Claims of 'guaranteed high returns' or 'risk-free profits' are hallmarks of fraud.\n\n"
                    "I can help you understand:\n"
                    "- 🏦 Safe instruments: PPF, FDs, government bonds\n"
                    "- 📈 Risk-return trade-offs for different asset classes\n"
                    "- 🛡️ How to diversify to manage risk\n\n"
                    "What would you like to explore?"
                ),
            )

    # 5. Out-of-scope check
    for pattern in _OOS_PATTERNS:
        if pattern.search(user_text):
            return GuardrailResult(
                allowed=False,
                category=Category.OUT_OF_SCOPE,
                message=(
                    "I'm focused on personal finance topics — budgeting, savings, loans, "
                    "investments, and planning. I'm not the right tool for that one!\n\n"
                    "Is there anything financial I can help you with today?"
                ),
            )

    # All checks passed
    return GuardrailResult(
        allowed=True,
        category=Category.ALLOWED,
        message="",
        scrubbed_text=user_text,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Post-check
# ─────────────────────────────────────────────────────────────────────────────

def post_check(answer: str, tool_calls_made: list[str]) -> GuardrailResult:
    """
    Validate the LLM's answer after generation.

    Flags:
    - Currency amounts present but no tool was called in this turn
    - Flagged phrases ("guaranteed", "risk-free", etc.)

    Returns GuardrailResult. If flags exist, the caller should append a note.
    """
    flags = []

    # Flag: currency amount without tool backing
    if _CURRENCY_AMOUNT_PATTERN.search(answer) and not tool_calls_made:
        flags.append(
            "⚠️ This answer contains currency amounts but no calculation tool was called. "
            "Numbers may be approximations — please treat them as illustrative only."
        )

    # Flag: guaranteed/risk-free language
    answer_lower = answer.lower()
    for phrase in FLAGGED_RESPONSE_PHRASES:
        if phrase.lower() in answer_lower:
            flags.append(
                f"⚠️ This response contains the phrase '{phrase}' — please note that "
                "no investment is truly guaranteed or risk-free."
            )
            break  # one flag is enough

    allowed = len(flags) == 0
    return GuardrailResult(
        allowed=allowed,
        category=Category.FLAGGED_RESPONSE if flags else Category.ALLOWED,
        message="\n".join(flags),
        flags=flags,
    )

