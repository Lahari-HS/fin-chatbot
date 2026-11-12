"""
tests/test_tools.py — Unit tests for chatbot/tools.py

All expected values are hand-verified in the comments next to each assertion.
Run with:  python -m pytest tests/test_tools.py -v

Tolerance for floating-point comparisons: ±0.5 INR (or ±1% for large values).
"""

from __future__ import annotations

import math
import pytest

from chatbot.tools import (
    loan_emi,
    loan_amortization,
    compound_interest,
    sip_future_value,
    savings_goal_timeline,
    required_monthly_saving,
    budget_split_50_30_20,
    debt_payoff,
    retirement_projection,
    emergency_fund_target,
    inflation_adjusted_value,
)


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def approx(value: float, tolerance_pct: float = 1.0) -> float:
    """Return a pytest.approx for ±tolerance_pct% of value."""
    return pytest.approx(value, rel=tolerance_pct / 100.0)


# ─────────────────────────────────────────────────────────────────────────────
# 1. loan_emi
# ─────────────────────────────────────────────────────────────────────────────

class TestLoanEmi:
    def test_standard_home_loan(self):
        """
        P=4000000, r=8.7%/yr, 20 years.
        Monthly rate = 8.7/12/100 = 0.00725
        n = 240
        EMI = 4000000 * 0.00725 * (1.00725)^240 / ((1.00725)^240 - 1)
        (1.00725)^240 ≈ 5.6107
        EMI ≈ 4000000 * 0.00725 * 5.6107 / 4.6107 ≈ 35,236
        (online calculators confirm ~₹35,236)
        """
        r = loan_emi(4_000_000, 8.7, 20)
        assert r["result"]["emi"] == approx(35_236, 1.0)
        assert r["result"]["total_paid"] == approx(35_236 * 240, 1.0)
        assert r["result"]["total_interest"] > 0
        assert "formula" in r
        assert "inputs_echo" in r

    def test_zero_interest(self):
        """
        P=120000, 0%, 10 years = 120 months.
        EMI = 120000/120 = 1000.
        """
        r = loan_emi(120_000, 0, 10)
        assert r["result"]["emi"] == pytest.approx(1_000, abs=0.01)
        assert r["result"]["total_interest"] == pytest.approx(0, abs=0.01)

    def test_one_month_term(self):
        """P=100000, 12%, 1/12 year (1 month)."""
        r = loan_emi(100_000, 12, 1 / 12)
        # With 1 month: EMI ≈ principal + 1 month interest = 100000 + 1000 = 101000
        assert r["result"]["emi"] == pytest.approx(101_000, rel=0.01)

    def test_very_large_principal(self):
        """10 crore loan, 9%, 30 years — should not overflow."""
        r = loan_emi(10_00_00_000, 9, 30)
        assert r["result"]["emi"] > 0
        assert r["result"]["total_interest"] > 0

    def test_negative_principal_raises(self):
        with pytest.raises(ValueError, match="principal"):
            loan_emi(-100_000, 8, 10)

    def test_negative_rate_raises(self):
        with pytest.raises(ValueError, match="annual_rate_pct"):
            loan_emi(100_000, -1, 10)

    def test_zero_years_raises(self):
        with pytest.raises(ValueError, match="years"):
            loan_emi(100_000, 8, 0)

    def test_return_structure(self):
        r = loan_emi(500_000, 10, 5)
        assert set(r.keys()) == {"result", "formula", "assumptions", "inputs_echo"}
        assert "emi" in r["result"]
        assert "total_paid" in r["result"]
        assert "total_interest" in r["result"]


# ─────────────────────────────────────────────────────────────────────────────
# 2. loan_amortization
# ─────────────────────────────────────────────────────────────────────────────

class TestLoanAmortization:
    def test_schedule_month_1(self):
        """
        P=1000000, 12%, 10 years.
        Monthly rate = 1% = 0.01
        Month-1 interest = 10000, principal = EMI - 10000
        EMI at 1%/m, 120m: = 1000000*0.01*(1.01)^120/((1.01)^120-1)
        (1.01)^120 ≈ 3.3004
        EMI ≈ 1000000*0.01*3.3004/2.3004 ≈ 14,347
        Month-1 interest = 10,000; principal_paid ≈ 4,347
        """
        r = loan_amortization(1_000_000, 12, 10, first_n_months=1)
        m1 = r["result"]["schedule"][0]
        assert m1["month"] == 1
        assert m1["interest_paid"] == pytest.approx(10_000, abs=1)
        assert m1["balance"] < 1_000_000

    def test_schedule_length(self):
        r = loan_amortization(500_000, 8, 5, first_n_months=6)
        assert len(r["result"]["schedule"]) == 6

    def test_capped_at_total_months(self):
        """Asking for 24 months from a 1-year loan should give 12."""
        r = loan_amortization(100_000, 10, 1, first_n_months=24)
        assert len(r["result"]["schedule"]) == 12

    def test_balance_decreasing(self):
        r = loan_amortization(1_000_000, 10, 10, first_n_months=12)
        balances = [m["balance"] for m in r["result"]["schedule"]]
        assert all(balances[i] > balances[i + 1] for i in range(len(balances) - 1))

    def test_negative_principal_raises(self):
        with pytest.raises(ValueError):
            loan_amortization(-100_000, 8, 5)


# ─────────────────────────────────────────────────────────────────────────────
# 3. compound_interest
# ─────────────────────────────────────────────────────────────────────────────

class TestCompoundInterest:
    def test_annual_compounding(self):
        """
        P=100000, r=10%, 5 years, annually.
        FV = 100000 * (1.10)^5 = 100000 * 1.61051 = 161051
        """
        r = compound_interest(100_000, 10, 5, compounds_per_year=1)
        assert r["result"]["future_value"] == approx(161_051, 0.01)
        assert r["result"]["interest_earned"] == approx(61_051, 0.1)

    def test_monthly_compounding(self):
        """
        P=100000, r=12%, 1 year, monthly.
        FV = 100000 * (1 + 0.12/12)^12 = 100000 * (1.01)^12 = 100000 * 1.12683 = 112683
        """
        r = compound_interest(100_000, 12, 1, compounds_per_year=12)
        assert r["result"]["future_value"] == approx(112_683, 0.1)

    def test_zero_rate(self):
        """P=50000, 0%, 5 years → FV = 50000."""
        r = compound_interest(50_000, 0, 5)
        # 0% rate: (1 + 0/1)^5 = 1; FV = 50000
        assert r["result"]["future_value"] == pytest.approx(50_000, abs=0.1)
        assert r["result"]["interest_earned"] == pytest.approx(0, abs=0.1)

    def test_negative_principal_raises(self):
        with pytest.raises(ValueError):
            compound_interest(-1000, 10, 5)

    def test_zero_compounds_raises(self):
        with pytest.raises(ValueError):
            compound_interest(100_000, 10, 5, compounds_per_year=0)

    def test_return_structure(self):
        r = compound_interest(100_000, 8, 10)
        assert "future_value" in r["result"]
        assert "interest_earned" in r["result"]


# ─────────────────────────────────────────────────────────────────────────────
# 4. sip_future_value
# ─────────────────────────────────────────────────────────────────────────────

class TestSipFutureValue:
    def test_standard_sip(self):
        """
        P=5000/month, 12% annual, 10 years.
        r = 1% = 0.01, n = 120
        FV = 5000 * [((1.01)^120 - 1)/0.01] * (1.01)
        (1.01)^120 ≈ 3.30039
        FV ≈ 5000 * [2.30039/0.01] * 1.01 ≈ 5000 * 230.039 * 1.01 ≈ 11,61,695
        Online SIP calculators confirm ~₹11.62 lakh
        """
        r = sip_future_value(5_000, 12, 10)
        assert r["result"]["future_value"] == approx(11_61_695, 1.0)
        assert r["result"]["total_invested"] == pytest.approx(5_000 * 120, abs=1)
        assert r["result"]["gains"] > 0

    def test_zero_return(self):
        """P=1000/month, 0%, 5 years → FV = 1000*60 = 60000."""
        r = sip_future_value(1_000, 0, 5)
        assert r["result"]["future_value"] == pytest.approx(60_000, abs=1)
        assert r["result"]["gains"] == pytest.approx(0, abs=1)

    def test_one_month(self):
        """P=10000, 12%, 1/12 year (1 month)."""
        r = sip_future_value(10_000, 12, 1 / 12)
        # 1 payment at start of month, grows for 1 month at 1%
        # FV ≈ 10000 * 1.01 ≈ 10100
        assert r["result"]["future_value"] == pytest.approx(10_100, rel=0.01)

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError):
            sip_future_value(-1000, 12, 10)

    def test_zero_years_raises(self):
        with pytest.raises(ValueError):
            sip_future_value(1000, 12, 0)


# ─────────────────────────────────────────────────────────────────────────────
# 5. savings_goal_timeline
# ─────────────────────────────────────────────────────────────────────────────

class TestSavingsGoalTimeline:
    def test_simple_no_return(self):
        """
        Goal=1000000, current=0, monthly=20000, 0% return.
        months = 1000000/20000 = 50.
        """
        r = savings_goal_timeline(1_000_000, 0, 20_000, 0)
        assert r["result"]["months_needed"] == 50

    def test_already_met(self):
        r = savings_goal_timeline(50_000, 100_000, 5_000, 0)
        assert r["result"]["already_met"] is True
        assert r["result"]["months_needed"] == 0

    def test_with_return(self):
        """
        Goal=500000, current=0, monthly=10000, 6% annual.
        Without return: 50 months.
        With 6% return should be fewer months.
        """
        r_no_return = savings_goal_timeline(500_000, 0, 10_000, 0)
        r_with_return = savings_goal_timeline(500_000, 0, 10_000, 6)
        assert r_with_return["result"]["months_needed"] < r_no_return["result"]["months_needed"]

    def test_negative_goal_raises(self):
        with pytest.raises(ValueError):
            savings_goal_timeline(-1000, 0, 500, 0)

    def test_zero_monthly_raises(self):
        with pytest.raises(ValueError):
            savings_goal_timeline(100_000, 0, 0, 0)

    def test_negative_return_raises(self):
        with pytest.raises(ValueError):
            savings_goal_timeline(100_000, 0, 5_000, -1)


# ─────────────────────────────────────────────────────────────────────────────
# 6. required_monthly_saving
# ─────────────────────────────────────────────────────────────────────────────

class TestRequiredMonthlySaving:
    def test_simple_no_return(self):
        """
        Goal=600000, current=0, 5 years (60 months), 0%.
        monthly = 600000/60 = 10000.
        """
        r = required_monthly_saving(600_000, 0, 5, 0)
        assert r["result"]["monthly_saving_needed"] == pytest.approx(10_000, abs=1)

    def test_already_met(self):
        r = required_monthly_saving(100_000, 200_000, 5, 0)
        assert r["result"]["already_met"] is True

    def test_with_return_less_than_zero_rate(self):
        """With a positive return, monthly saving should be < zero-return case."""
        r_no_return = required_monthly_saving(1_000_000, 0, 10, 0)
        r_with_return = required_monthly_saving(1_000_000, 0, 10, 10)
        assert r_with_return["result"]["monthly_saving_needed"] < r_no_return["result"]["monthly_saving_needed"]

    def test_zero_years_raises(self):
        with pytest.raises(ValueError):
            required_monthly_saving(100_000, 0, 0, 0)


# ─────────────────────────────────────────────────────────────────────────────
# 7. budget_split_50_30_20
# ─────────────────────────────────────────────────────────────────────────────

class TestBudgetSplit:
    def test_standard_split(self):
        """
        Income=100000.
        Needs=50000, Wants=30000, Savings=20000.
        """
        r = budget_split_50_30_20(100_000)
        assert r["result"]["needs_budget"] == 50_000
        assert r["result"]["wants_budget"] == 30_000
        assert r["result"]["savings_budget"] == 20_000
        assert r["result"]["fixed_exceed_50_pct"] is False

    def test_fixed_exceeds_50(self):
        """Income=80000, fixed=45000. 50% = 40000 < 45000 → flag."""
        r = budget_split_50_30_20(80_000, fixed_expenses=45_000)
        assert r["result"]["fixed_exceed_50_pct"] is True

    def test_fixed_within_50(self):
        r = budget_split_50_30_20(80_000, fixed_expenses=30_000)
        assert r["result"]["fixed_exceed_50_pct"] is False
        assert r["result"]["discretionary_needs_remaining"] == pytest.approx(10_000, abs=1)

    def test_zero_income_raises(self):
        with pytest.raises(ValueError):
            budget_split_50_30_20(0)

    def test_negative_income_raises(self):
        with pytest.raises(ValueError):
            budget_split_50_30_20(-50_000)

    def test_fixed_exceeds_income_raises(self):
        with pytest.raises(ValueError):
            budget_split_50_30_20(50_000, fixed_expenses=60_000)

    def test_messy_input_80k_income(self):
        """Demo conversation 1: 80k income, 25k rent."""
        r = budget_split_50_30_20(80_000, fixed_expenses=25_000)
        assert r["result"]["needs_budget"] == 40_000
        assert r["result"]["wants_budget"] == 24_000
        assert r["result"]["savings_budget"] == 16_000
        assert r["result"]["fixed_exceed_50_pct"] is False  # 25k < 40k


# ─────────────────────────────────────────────────────────────────────────────
# 8. debt_payoff
# ─────────────────────────────────────────────────────────────────────────────

class TestDebtPayoff:
    def _two_debts(self):
        return [
            {"name": "Credit Card", "balance": 50_000, "rate_pct": 36, "min_payment": 2_000},
            {"name": "Personal Loan", "balance": 200_000, "rate_pct": 14, "min_payment": 5_000},
        ]

    def test_avalanche_saves_more_interest(self):
        """Avalanche should always save ≥ interest vs snowball."""
        r = debt_payoff(self._two_debts(), extra_payment=3_000, strategy="avalanche")
        comparison = r["result"]["comparison"]
        assert comparison["interest_saved_by_avalanche"] >= 0

    def test_snowball_strategy(self):
        r = debt_payoff(self._two_debts(), extra_payment=3_000, strategy="snowball")
        # Snowball pays lowest balance first = Credit Card (50k) first
        assert r["result"]["payoff_order"][0]["name"] == "Credit Card"

    def test_avalanche_strategy_order(self):
        """Avalanche: highest rate = Credit Card (36%) paid first."""
        r = debt_payoff(self._two_debts(), extra_payment=3_000, strategy="avalanche")
        assert r["result"]["payoff_order"][0]["name"] == "Credit Card"

    def test_zero_extra_payment(self):
        """Should still work with zero extra payment."""
        r = debt_payoff(self._two_debts(), extra_payment=0, strategy="avalanche")
        assert r["result"]["total_months"] > 0
        assert r["result"]["total_interest"] > 0

    def test_empty_debts_raises(self):
        with pytest.raises(ValueError, match="empty"):
            debt_payoff([], extra_payment=1_000)

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="name"):
            debt_payoff([{"balance": 1000, "rate_pct": 10, "min_payment": 100}], extra_payment=0)

    def test_negative_balance_raises(self):
        with pytest.raises(ValueError):
            debt_payoff([{"name": "Card", "balance": -1000, "rate_pct": 20, "min_payment": 100}], extra_payment=0)

    def test_return_structure(self):
        r = debt_payoff(self._two_debts(), extra_payment=1_000)
        assert "payoff_order" in r["result"]
        assert "total_months" in r["result"]
        assert "total_interest" in r["result"]
        assert "comparison" in r["result"]

    def test_demo_credit_vs_personal_loan(self):
        """Demo conversation 6: CC @36%, personal loan @14%."""
        r = debt_payoff(
            [
                {"name": "Credit Card", "balance": 50_000, "rate_pct": 36, "min_payment": 2_500},
                {"name": "Personal Loan", "balance": 2_00_000, "rate_pct": 14, "min_payment": 5_000},
            ],
            extra_payment=2_000,
            strategy="avalanche",
        )
        # CC should be paid first under avalanche (36% > 14%)
        assert r["result"]["payoff_order"][0]["name"] == "Credit Card"
        # Interest saved vs snowball should be positive
        assert r["result"]["comparison"]["interest_saved_by_avalanche"] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 9. retirement_projection
# ─────────────────────────────────────────────────────────────────────────────

class TestRetirementProjection:
    def test_basic_projection(self):
        """
        Age 30, retire 60 (30 years), save 10k/month, 0 existing corpus,
        10% return, 6% inflation, 50k/month expenses.
        30 years = 360 months, r_monthly ≈ 0.833%
        SIP FV ≈ 10000 * [((1.00833)^360 - 1)/0.00833] * 1.00833
        (1.00833)^360 ≈ 19.837
        FV ≈ 10000 * [18.837/0.00833] * 1.00833 ≈ 10000 * 2262 * 1.00833 ≈ 2.28 crore
        """
        r = retirement_projection(
            current_age=30,
            retire_age=60,
            monthly_saving=10_000,
            current_corpus=0,
            return_pct=10,
            inflation_pct=6,
            monthly_expense_today=50_000,
        )
        assert r["result"]["projected_corpus"] > 1_00_00_000  # > 1 crore
        assert r["result"]["expense_at_retire_monthly"] > 50_000  # inflation pushes it up
        assert "sufficiency_note" in r["result"]

    def test_retire_before_current_age_raises(self):
        with pytest.raises(ValueError):
            retirement_projection(60, 55, 10_000, 0, 10, 6, 50_000)

    def test_zero_expense_raises(self):
        with pytest.raises(ValueError):
            retirement_projection(30, 60, 10_000, 0, 10, 6, 0)

    def test_negative_corpus_raises(self):
        with pytest.raises(ValueError):
            retirement_projection(30, 60, 10_000, -1, 10, 6, 50_000)


# ─────────────────────────────────────────────────────────────────────────────
# 10. emergency_fund_target
# ─────────────────────────────────────────────────────────────────────────────

class TestEmergencyFundTarget:
    def test_standard_6_months(self):
        """monthly=40000, 6 months → 240000."""
        r = emergency_fund_target(40_000, 6)
        assert r["result"]["emergency_fund_target"] == pytest.approx(2_40_000, abs=1)

    def test_default_months(self):
        """Default is 6 months."""
        r = emergency_fund_target(30_000)
        assert r["result"]["emergency_fund_target"] == pytest.approx(1_80_000, abs=1)

    def test_3_months(self):
        r = emergency_fund_target(50_000, 3)
        assert r["result"]["emergency_fund_target"] == pytest.approx(1_50_000, abs=1)

    def test_zero_expense_raises(self):
        with pytest.raises(ValueError):
            emergency_fund_target(0)

    def test_negative_months_raises(self):
        with pytest.raises(ValueError):
            emergency_fund_target(30_000, 0)


# ─────────────────────────────────────────────────────────────────────────────
# 11. inflation_adjusted_value
# ─────────────────────────────────────────────────────────────────────────────

class TestInflationAdjustedValue:
    def test_future_nominal(self):
        """
        Amount=100000, inflation=6%, 10 years.
        Future = 100000 * (1.06)^10 = 100000 * 1.79085 = 179085.
        """
        r = inflation_adjusted_value(100_000, 6, 10)
        assert r["result"]["future_nominal"] == approx(179_085, 0.1)

    def test_real_value_less_than_nominal(self):
        """Real value should be less than original amount with positive inflation."""
        r = inflation_adjusted_value(100_000, 6, 10)
        assert r["result"]["real_value_of_todays_amount"] < 100_000

    def test_zero_inflation(self):
        """0% inflation → future_nominal = amount."""
        r = inflation_adjusted_value(50_000, 0, 5)
        assert r["result"]["future_nominal"] == pytest.approx(50_000, abs=1)
        assert r["result"]["real_value_of_todays_amount"] == pytest.approx(50_000, abs=1)

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError):
            inflation_adjusted_value(-1000, 6, 5)

    def test_zero_years_raises(self):
        with pytest.raises(ValueError):
            inflation_adjusted_value(100_000, 6, 0)

    def test_negative_inflation_raises(self):
        with pytest.raises(ValueError):
            inflation_adjusted_value(100_000, -1, 5)


# ─────────────────────────────────────────────────────────────────────────────
# Edge / stress tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_loan_emi_very_short_tenure(self):
        """1-month loan."""
        r = loan_emi(10_000, 24, 1 / 12)
        assert r["result"]["emi"] > 10_000  # must include interest

    def test_sip_tiny_amount(self):
        """₹1/month SIP for 1 year."""
        r = sip_future_value(1, 12, 1)
        assert r["result"]["future_value"] > 1

    def test_budget_very_low_income(self):
        """₹1 income — edge but valid."""
        r = budget_split_50_30_20(1)
        assert r["result"]["needs_budget"] == pytest.approx(0.50, abs=0.01)

    def test_savings_goal_same_as_current(self):
        """Goal equals current savings → 0 months."""
        r = savings_goal_timeline(100_000, 100_000, 5_000, 0)
        assert r["result"]["already_met"] is True

    def test_emergency_fund_12_months_selfemployed(self):
        """Self-employed: 12-month buffer."""
        r = emergency_fund_target(60_000, 12)
        assert r["result"]["emergency_fund_target"] == pytest.approx(7_20_000, abs=1)

    def test_inflation_1_year(self):
        """Amount=100, 10% inflation, 1 year → 110."""
        r = inflation_adjusted_value(100, 10, 1)
        assert r["result"]["future_nominal"] == pytest.approx(110, abs=0.01)

    def test_debt_payoff_single_debt(self):
        """Single debt payoff."""
        r = debt_payoff(
            [{"name": "Card", "balance": 50_000, "rate_pct": 24, "min_payment": 3_000}],
            extra_payment=2_000,
        )
        assert r["result"]["total_months"] > 0
        assert len(r["result"]["payoff_order"]) == 1

