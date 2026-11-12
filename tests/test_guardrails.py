"""
tests/test_guardrails.py — Unit tests for chatbot/guardrails.py

Tests are split into:
  - Should BLOCK (not allowed / sensitive)
  - Should ALLOW (normal finance questions)
  - Sensitive data detection
  - Post-check flags
"""

from __future__ import annotations

import pytest
from chatbot.guardrails import Category, pre_check, post_check


# ─────────────────────────────────────────────────────────────────────────────
# PRE-CHECK — Should BLOCK
# ─────────────────────────────────────────────────────────────────────────────

class TestShouldBlock:
    """These inputs must NOT be forwarded to the LLM."""

    # ── Stock picks ────────────────────────────────────────────────────────────
    def test_which_stock_to_buy(self):
        r = pre_check("Which stock should I buy this week?")
        assert not r.allowed
        assert r.category == Category.STOCK_PICK

    def test_buy_crypto(self):
        r = pre_check("Should I buy Bitcoin right now?")
        assert not r.allowed
        assert r.category == Category.STOCK_PICK

    def test_hot_stock_tip(self):
        r = pre_check("Give me a hot stock tip for tomorrow")
        assert not r.allowed
        assert r.category == Category.STOCK_PICK

    def test_which_mf_to_buy(self):
        r = pre_check("Which mutual fund should I invest in?")
        assert not r.allowed
        assert r.category == Category.STOCK_PICK

    def test_insider_tip(self):
        r = pre_check("Do you have any insider tips on the market?")
        assert not r.allowed
        assert r.category == Category.STOCK_PICK

    # ── Guaranteed returns ─────────────────────────────────────────────────────
    def test_guaranteed_returns(self):
        r = pre_check("I want guaranteed returns on my investment")
        assert not r.allowed
        assert r.category == Category.GUARANTEED_RETURNS

    def test_risk_free_investment(self):
        r = pre_check("Tell me about risk-free investment options with high returns")
        assert not r.allowed
        assert r.category == Category.GUARANTEED_RETURNS

    def test_assured_returns(self):
        r = pre_check("I need assured returns of 20% per year")
        assert not r.allowed
        assert r.category == Category.GUARANTEED_RETURNS

    def test_zero_risk_investment(self):
        r = pre_check("Is there a zero risk investment that gives 15% annual return?")
        assert not r.allowed
        assert r.category == Category.GUARANTEED_RETURNS

    # ── Out of scope ───────────────────────────────────────────────────────────
    def test_cricket_bet(self):
        r = pre_check("Should I bet on cricket today?")
        assert not r.allowed
        assert r.category == Category.OUT_OF_SCOPE

    def test_recipe(self):
        r = pre_check("Give me a recipe for dal makhani")
        assert not r.allowed
        assert r.category == Category.OUT_OF_SCOPE

    def test_movie_recommendations(self):
        r = pre_check("What movies should I watch on Netflix this weekend?")
        assert not r.allowed
        assert r.category == Category.OUT_OF_SCOPE

    # ── Crisis ────────────────────────────────────────────────────────────────
    def test_self_harm_language(self):
        r = pre_check("I lost everything in the market and want to end it all")
        assert not r.allowed
        assert r.category == Category.CRISIS
        assert "iCall" in r.message or "Vandrevala" in r.message

    def test_financial_ruin_despair(self):
        r = pre_check("I'm completely ruined financially and there's no way out")
        assert not r.allowed
        assert r.category == Category.CRISIS


# ─────────────────────────────────────────────────────────────────────────────
# PRE-CHECK — Should ALLOW
# ─────────────────────────────────────────────────────────────────────────────

class TestShouldAllow:
    """These inputs should pass through to the LLM."""

    def test_emi_question(self):
        r = pre_check("What is the EMI on a 30 lakh home loan at 8.5% for 15 years?")
        assert r.allowed
        assert r.category in (Category.ALLOWED, Category.SENSITIVE_DATA)

    def test_sip_question(self):
        r = pre_check("How much can I accumulate with a ₹5000 monthly SIP for 10 years?")
        assert r.allowed

    def test_budget_question(self):
        r = pre_check("I earn 80000 a month. How should I budget using the 50/30/20 rule?")
        assert r.allowed

    def test_emergency_fund(self):
        r = pre_check("How much should I keep in an emergency fund?")
        assert r.allowed

    def test_debt_payoff(self):
        r = pre_check("I have a credit card debt and personal loan. Which should I pay first?")
        assert r.allowed

    def test_sip_vs_lumpsum(self):
        r = pre_check("What is the difference between SIP and lump sum investment?")
        assert r.allowed

    def test_ppf_question(self):
        r = pre_check("What is PPF and should I invest in it?")
        assert r.allowed

    def test_credit_score(self):
        r = pre_check("How can I improve my CIBIL credit score?")
        assert r.allowed

    def test_term_insurance(self):
        r = pre_check("What is term insurance and do I need it?")
        assert r.allowed

    def test_fd_vs_mf(self):
        r = pre_check("Is a fixed deposit better than a mutual fund?")
        assert r.allowed

    def test_retirement_planning(self):
        r = pre_check("How much do I need to save for retirement at 60?")
        assert r.allowed

    def test_inflation_question(self):
        r = pre_check("How does inflation affect my savings?")
        assert r.allowed

    def test_savings_goal(self):
        r = pre_check("How long will it take me to save 10 lakh?")
        assert r.allowed

    def test_income_tax_question(self):
        r = pre_check("What are the tax benefits of investing in ELSS?")
        assert r.allowed

    def test_diversification(self):
        r = pre_check("What does diversification mean in investing?")
        assert r.allowed


# ─────────────────────────────────────────────────────────────────────────────
# PRE-CHECK — Sensitive data detection
# ─────────────────────────────────────────────────────────────────────────────

class TestSensitiveData:
    """Sensitive data should be scrubbed; message should still be allowed (with warning)."""

    def test_card_number_scrubbed(self):
        r = pre_check("My card number is 4111111111111111 and I want to know my limit")
        assert r.allowed  # allowed=True (scrubbed)
        assert r.category == Category.SENSITIVE_DATA
        assert "4111111111111111" not in r.scrubbed_text
        assert "card number" in r.message

    def test_aadhaar_scrubbed(self):
        r = pre_check("My Aadhaar is 1234 5678 9012 and I need help")
        assert r.allowed
        assert r.category == Category.SENSITIVE_DATA
        assert "1234 5678 9012" not in r.scrubbed_text

    def test_pan_scrubbed(self):
        r = pre_check("My PAN is ABCDE1234F and I need tax advice")
        assert r.allowed
        assert r.category == Category.SENSITIVE_DATA
        assert "ABCDE1234F" not in r.scrubbed_text

    def test_password_scrubbed(self):
        r = pre_check("My password: secret123 — can you help me?")
        assert r.allowed
        assert r.category == Category.SENSITIVE_DATA

    def test_otp_scrubbed(self):
        r = pre_check("OTP: 456789 — please help me verify")
        assert r.allowed
        assert r.category == Category.SENSITIVE_DATA


# ─────────────────────────────────────────────────────────────────────────────
# POST-CHECK
# ─────────────────────────────────────────────────────────────────────────────

class TestPostCheck:
    def test_flagged_guaranteed_in_answer(self):
        answer = "This FD offers guaranteed returns of 7% per annum."
        r = post_check(answer, tool_calls_made=[])
        assert len(r.flags) > 0
        assert any("guaranteed" in f.lower() for f in r.flags)

    def test_flagged_risk_free_in_answer(self):
        answer = "This is a risk-free investment option."
        r = post_check(answer, tool_calls_made=[])
        assert len(r.flags) > 0

    def test_currency_without_tool_flagged(self):
        answer = "You should invest ₹50,000 in this fund."
        r = post_check(answer, tool_calls_made=[])
        # Has currency but no tool → flagged
        assert len(r.flags) > 0

    def test_currency_with_tool_not_flagged(self):
        answer = "Based on the calculation, your EMI will be ₹35,236."
        r = post_check(answer, tool_calls_made=["loan_emi"])
        # Has currency AND has tool call → should NOT flag currency issue
        currency_flags = [f for f in r.flags if "currency" in f.lower() or "tool" in f.lower()]
        assert len(currency_flags) == 0

    def test_clean_answer_passes(self):
        answer = "SIP stands for Systematic Investment Plan. It allows you to invest regularly."
        r = post_check(answer, tool_calls_made=[])
        # No currency amounts, no flagged phrases → allowed
        assert r.allowed

    def test_flags_are_list(self):
        r = post_check("hello world", [])
        assert isinstance(r.flags, list)

