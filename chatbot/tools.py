"""
tools.py — Deterministic financial calculators.

Design rules
------------
* Pure functions only: no I/O, no randomness, no side-effects.
* All inputs are validated; negative or nonsensical values raise ValueError
  with a clear, user-readable message.
* Every function returns a dict with four keys:
    result        – the computed value(s) (dict or scalar)
    formula       – human-readable formula string
    assumptions   – list of strings the user should be aware of
    inputs_echo   – dict of validated inputs as received
* Currency values are plain floats (formatting done in formatting.py).
* All rate inputs are percentages (8.5 means 8.5 %, not 0.085).
"""

from __future__ import annotations

import math
from typing import Literal


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require_positive(value: float, name: str) -> None:
    if value < 0:
        raise ValueError(f"'{name}' must be ≥ 0, got {value}.")


def _require_strictly_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"'{name}' must be > 0, got {value}.")


def _pct_to_rate(annual_rate_pct: float) -> float:
    """Convert annual percentage (8.5) to annual decimal (0.085)."""
    return annual_rate_pct / 100.0


# ─────────────────────────────────────────────────────────────────────────────
# 1. loan_emi
# ─────────────────────────────────────────────────────────────────────────────

def loan_emi(
    principal: float,
    annual_rate_pct: float,
    years: float,
) -> dict:
    """
    Calculate the Equated Monthly Instalment (EMI) for a loan.

    Parameters
    ----------
    principal        : Loan amount (₹).
    annual_rate_pct  : Annual interest rate in percent (e.g. 8.5 for 8.5 %).
    years            : Loan tenure in years (e.g. 20).

    Returns
    -------
    dict with result keys:
        emi            – monthly instalment
        total_paid     – total amount paid over loan life
        total_interest – total interest paid
    """
    _require_strictly_positive(principal, "principal")
    _require_positive(annual_rate_pct, "annual_rate_pct")
    if years <= 0:
        raise ValueError(f"'years' must be > 0, got {years}.")

    n = round(years * 12)  # total months

    if annual_rate_pct == 0:
        emi = principal / n
        formula = "EMI = Principal / N  (0% interest, simple division)"
        assumptions = ["Zero-interest loan; each month pays equal principal."]
    else:
        r = _pct_to_rate(annual_rate_pct) / 12  # monthly rate
        emi = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
        formula = "EMI = P × r × (1+r)^N / ((1+r)^N − 1)"
        assumptions = [
            f"Monthly interest rate r = {annual_rate_pct}/12/100 = {r:.6f}",
            f"Total months N = {n}",
            "Interest compounded monthly.",
            "Fixed-rate loan (no floating-rate changes modelled).",
        ]

    total_paid = emi * n
    total_interest = total_paid - principal

    return {
        "result": {
            "emi": round(emi, 2),
            "total_paid": round(total_paid, 2),
            "total_interest": round(total_interest, 2),
        },
        "formula": formula,
        "assumptions": assumptions,
        "inputs_echo": {
            "principal": principal,
            "annual_rate_pct": annual_rate_pct,
            "years": years,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. loan_amortization
# ─────────────────────────────────────────────────────────────────────────────

def loan_amortization(
    principal: float,
    annual_rate_pct: float,
    years: float,
    first_n_months: int = 12,
) -> dict:
    """
    Generate a month-by-month amortization schedule for the first N months.

    Returns each row as {month, payment, principal_paid, interest_paid, balance}.
    """
    _require_strictly_positive(principal, "principal")
    _require_positive(annual_rate_pct, "annual_rate_pct")
    if years <= 0:
        raise ValueError(f"'years' must be > 0, got {years}.")
    total_months = round(years * 12)
    if first_n_months < 1:
        raise ValueError(f"'first_n_months' must be ≥ 1, got {first_n_months}.")
    n_show = min(first_n_months, total_months)

    emi_result = loan_emi(principal, annual_rate_pct, years)
    emi = emi_result["result"]["emi"]

    schedule = []
    balance = principal
    r = _pct_to_rate(annual_rate_pct) / 12

    for month in range(1, n_show + 1):
        interest_paid = round(balance * r, 2) if annual_rate_pct > 0 else 0.0
        principal_paid = round(emi - interest_paid, 2)
        balance = round(balance - principal_paid, 2)
        if balance < 0:
            balance = 0.0
        schedule.append({
            "month": month,
            "payment": round(emi, 2),
            "principal_paid": principal_paid,
            "interest_paid": interest_paid,
            "balance": balance,
        })

    return {
        "result": {"schedule": schedule, "emi": round(emi, 2)},
        "formula": "Interest = Balance × monthly_rate; Principal = EMI − Interest",
        "assumptions": [
            "Same EMI formula as loan_emi.",
            f"Showing first {n_show} of {total_months} months.",
        ],
        "inputs_echo": {
            "principal": principal,
            "annual_rate_pct": annual_rate_pct,
            "years": years,
            "first_n_months": first_n_months,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. compound_interest
# ─────────────────────────────────────────────────────────────────────────────

def compound_interest(
    principal: float,
    annual_rate_pct: float,
    years: float,
    compounds_per_year: int = 1,
) -> dict:
    """
    Calculate future value and interest earned via compound interest.

    Parameters
    ----------
    principal          : Initial investment (₹).
    annual_rate_pct    : Annual interest rate in percent.
    years              : Investment duration.
    compounds_per_year : Compounding frequency per year (1=annual, 12=monthly).
    """
    _require_strictly_positive(principal, "principal")
    _require_positive(annual_rate_pct, "annual_rate_pct")
    if years <= 0:
        raise ValueError(f"'years' must be > 0, got {years}.")
    if compounds_per_year < 1:
        raise ValueError(f"'compounds_per_year' must be ≥ 1, got {compounds_per_year}.")

    r = _pct_to_rate(annual_rate_pct)
    n = compounds_per_year
    t = years

    future_value = principal * (1 + r / n) ** (n * t)
    interest_earned = future_value - principal

    freq_label = {1: "annually", 2: "half-yearly", 4: "quarterly", 12: "monthly"}.get(
        n, f"{n}× per year"
    )

    return {
        "result": {
            "future_value": round(future_value, 2),
            "interest_earned": round(interest_earned, 2),
            "principal": principal,
        },
        "formula": "A = P × (1 + r/n)^(n×t)",
        "assumptions": [
            f"Interest compounded {freq_label} ({n}× per year).",
            "No withdrawals or additional deposits.",
            "Returns not guaranteed; actual returns may differ.",
        ],
        "inputs_echo": {
            "principal": principal,
            "annual_rate_pct": annual_rate_pct,
            "years": years,
            "compounds_per_year": compounds_per_year,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. sip_future_value
# ─────────────────────────────────────────────────────────────────────────────

def sip_future_value(
    monthly_amount: float,
    expected_return_pct: float,
    years: float,
) -> dict:
    """
    Calculate the future value of a Systematic Investment Plan (SIP).

    Uses the standard SIP formula:
        FV = P × [((1+r)^n − 1) / r] × (1+r)

    where r = monthly rate, n = total months.
    """
    _require_strictly_positive(monthly_amount, "monthly_amount")
    _require_positive(expected_return_pct, "expected_return_pct")
    if years <= 0:
        raise ValueError(f"'years' must be > 0, got {years}.")

    n = round(years * 12)
    r = _pct_to_rate(expected_return_pct) / 12

    if r == 0:
        future_value = monthly_amount * n
        formula = "FV = P × N  (0% return)"
    else:
        future_value = monthly_amount * (((1 + r) ** n - 1) / r) * (1 + r)
        formula = "FV = P × [((1+r)^n − 1) / r] × (1+r)"

    total_invested = monthly_amount * n
    gains = future_value - total_invested

    return {
        "result": {
            "future_value": round(future_value, 2),
            "total_invested": round(total_invested, 2),
            "gains": round(gains, 2),
        },
        "formula": formula,
        "assumptions": [
            f"Monthly rate r = {expected_return_pct}/12/100 = {r:.6f}",
            f"Total months n = {n}",
            "Investment made at the START of each month (annuity due).",
            "Expected return is assumed constant; actual mutual fund returns vary.",
            "Returns not guaranteed.",
        ],
        "inputs_echo": {
            "monthly_amount": monthly_amount,
            "expected_return_pct": expected_return_pct,
            "years": years,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. savings_goal_timeline
# ─────────────────────────────────────────────────────────────────────────────

def savings_goal_timeline(
    goal_amount: float,
    current_savings: float,
    monthly_saving: float,
    annual_return_pct: float = 0.0,
) -> dict:
    """
    Calculate how many months are needed to reach a savings goal.

    Parameters
    ----------
    goal_amount      : Target amount (₹).
    current_savings  : Already saved (₹).
    monthly_saving   : Amount saved/invested every month (₹).
    annual_return_pct: Annual return on savings (%), default 0 (no growth).
    """
    _require_strictly_positive(goal_amount, "goal_amount")
    _require_positive(current_savings, "current_savings")
    _require_strictly_positive(monthly_saving, "monthly_saving")
    _require_positive(annual_return_pct, "annual_return_pct")

    if current_savings >= goal_amount:
        return {
            "result": {"months_needed": 0, "already_met": True},
            "formula": "Current savings already meet the goal.",
            "assumptions": [],
            "inputs_echo": {
                "goal_amount": goal_amount,
                "current_savings": current_savings,
                "monthly_saving": monthly_saving,
                "annual_return_pct": annual_return_pct,
            },
        }

    r = _pct_to_rate(annual_return_pct) / 12

    if r == 0:
        # Simple: months = (goal - current) / monthly_saving
        months = math.ceil((goal_amount - current_savings) / monthly_saving)
        formula = "months = (goal − current_savings) / monthly_saving"
        assumptions = ["No return on savings (0% rate)."]
    else:
        # Solve: current*(1+r)^n + monthly * [((1+r)^n - 1)/r] = goal
        # Rearranged via logarithm:
        # (1+r)^n = (goal*r + monthly) / (current*r + monthly)
        ratio = (goal_amount * r + monthly_saving) / (current_savings * r + monthly_saving)
        if ratio <= 1:
            raise ValueError(
                "Goal cannot be reached with these parameters "
                "(monthly saving too low relative to interest on gap)."
            )
        months = math.ceil(math.log(ratio) / math.log(1 + r))
        formula = "(1+r)^n = (goal×r + monthly) / (current×r + monthly); solve for n"
        assumptions = [
            f"Monthly rate r = {annual_return_pct}/12/100 = {r:.6f}",
            "Savings grow at the stated return; actual returns may differ.",
            "Returns not guaranteed.",
        ]

    return {
        "result": {"months_needed": months, "already_met": False},
        "formula": formula,
        "assumptions": assumptions,
        "inputs_echo": {
            "goal_amount": goal_amount,
            "current_savings": current_savings,
            "monthly_saving": monthly_saving,
            "annual_return_pct": annual_return_pct,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. required_monthly_saving
# ─────────────────────────────────────────────────────────────────────────────

def required_monthly_saving(
    goal_amount: float,
    current_savings: float,
    years: float,
    annual_return_pct: float = 0.0,
) -> dict:
    """
    Calculate how much to save every month to reach a goal in a given time.

    Parameters
    ----------
    goal_amount      : Target corpus (₹).
    current_savings  : Already saved (₹).
    years            : Time horizon in years.
    annual_return_pct: Annual return on savings (%).
    """
    _require_strictly_positive(goal_amount, "goal_amount")
    _require_positive(current_savings, "current_savings")
    if years <= 0:
        raise ValueError(f"'years' must be > 0, got {years}.")
    _require_positive(annual_return_pct, "annual_return_pct")

    n = round(years * 12)
    r = _pct_to_rate(annual_return_pct) / 12

    if current_savings >= goal_amount:
        return {
            "result": {"monthly_saving_needed": 0.0, "already_met": True},
            "formula": "Current savings already meet the goal.",
            "assumptions": [],
            "inputs_echo": {
                "goal_amount": goal_amount,
                "current_savings": current_savings,
                "years": years,
                "annual_return_pct": annual_return_pct,
            },
        }

    if r == 0:
        monthly = (goal_amount - current_savings) / n
        formula = "monthly = (goal − current) / n"
        assumptions = ["No return on savings."]
    else:
        future_current = current_savings * (1 + r) ** n
        remaining = goal_amount - future_current
        if remaining <= 0:
            return {
                "result": {"monthly_saving_needed": 0.0, "already_met": True},
                "formula": "Current savings grow to meet the goal without additional deposits.",
                "assumptions": [f"At {annual_return_pct}% p.a., existing ₹{current_savings} grows to cover the goal."],
                "inputs_echo": {
                    "goal_amount": goal_amount,
                    "current_savings": current_savings,
                    "years": years,
                    "annual_return_pct": annual_return_pct,
                },
            }
        monthly = remaining * r / (((1 + r) ** n - 1) * (1 + r))
        formula = "monthly = (goal − current×(1+r)^n) × r / (((1+r)^n − 1) × (1+r))"
        assumptions = [
            f"Monthly rate r = {annual_return_pct}/12/100 = {r:.6f}",
            f"n = {n} months",
            "Returns not guaranteed; actual returns may vary.",
        ]

    return {
        "result": {"monthly_saving_needed": round(monthly, 2)},
        "formula": formula,
        "assumptions": assumptions,
        "inputs_echo": {
            "goal_amount": goal_amount,
            "current_savings": current_savings,
            "years": years,
            "annual_return_pct": annual_return_pct,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. budget_split_50_30_20
# ─────────────────────────────────────────────────────────────────────────────

def budget_split_50_30_20(
    monthly_income: float,
    fixed_expenses: float | None = None,
) -> dict:
    """
    Apply the 50/30/20 budgeting rule.

    50% → Needs (rent, utilities, groceries, EMIs)
    30% → Wants (dining, entertainment, subscriptions)
    20% → Savings / debt repayment

    If fixed_expenses are provided and exceed 50%, the flag
    'fixed_exceed_50_pct' is set True and the user is advised to review.
    """
    _require_strictly_positive(monthly_income, "monthly_income")
    if fixed_expenses is not None:
        _require_positive(fixed_expenses, "fixed_expenses")
        if fixed_expenses > monthly_income:
            raise ValueError(
                f"fixed_expenses ({fixed_expenses}) exceeds monthly_income ({monthly_income})."
            )

    needs = round(monthly_income * 0.50, 2)
    wants = round(monthly_income * 0.30, 2)
    savings = round(monthly_income * 0.20, 2)

    fixed_exceed = False
    if fixed_expenses is not None and fixed_expenses > needs:
        fixed_exceed = True

    result: dict = {
        "needs_budget": needs,
        "wants_budget": wants,
        "savings_budget": savings,
        "fixed_exceed_50_pct": fixed_exceed,
    }
    if fixed_expenses is not None:
        result["fixed_expenses_given"] = fixed_expenses
        result["discretionary_needs_remaining"] = round(needs - fixed_expenses, 2)

    assumptions = [
        "50% → needs (rent, utilities, EMIs, groceries)",
        "30% → wants (dining, travel, subscriptions)",
        "20% → savings and/or debt repayment",
    ]
    if fixed_exceed:
        assumptions.append(
            "⚠️ Your fixed expenses exceed 50% of income. "
            "Consider reviewing discretionary spending or finding ways to increase income."
        )

    return {
        "result": result,
        "formula": "Needs = Income × 0.50; Wants = Income × 0.30; Savings = Income × 0.20",
        "assumptions": assumptions,
        "inputs_echo": {
            "monthly_income": monthly_income,
            "fixed_expenses": fixed_expenses,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. debt_payoff
# ─────────────────────────────────────────────────────────────────────────────

def debt_payoff(
    debts: list[dict],
    extra_payment: float,
    strategy: Literal["avalanche", "snowball"] = "avalanche",
) -> dict:
    """
    Simulate debt payoff using avalanche (highest rate first) or snowball
    (lowest balance first) strategy, and compare both.

    Parameters
    ----------
    debts : list of dicts with keys:
        name        – label (str)
        balance     – outstanding balance (₹, > 0)
        rate_pct    – annual interest rate (%)
        min_payment – minimum monthly payment (₹, > 0)
    extra_payment : Additional monthly payment applied to the target debt.
    strategy      : "avalanche" or "snowball".

    Returns both strategies plus the chosen one's detailed payoff order.
    """
    if not debts:
        raise ValueError("'debts' list must not be empty.")
    _require_positive(extra_payment, "extra_payment")

    for d in debts:
        for key in ("name", "balance", "rate_pct", "min_payment"):
            if key not in d:
                raise ValueError(f"Each debt must have key '{key}'.")
        if d["balance"] <= 0:
            raise ValueError(f"Debt '{d['name']}' has non-positive balance.")
        if d["min_payment"] <= 0:
            raise ValueError(f"Debt '{d['name']}' has non-positive min_payment.")
        _require_positive(d["rate_pct"], "rate_pct")

    def _simulate(debt_list: list[dict], extra: float) -> dict:
        """Core simulation; returns payoff order, months, total interest."""
        import copy
        debts_sim = copy.deepcopy(debt_list)
        months = 0
        total_interest = 0.0
        payoff_order = []
        max_months = 1200  # safety cap (100 years)

        while any(d["balance"] > 0 for d in debts_sim):
            months += 1
            if months > max_months:
                raise ValueError(
                    "Debt cannot be paid off within 100 years with current payments. "
                    "Increase minimum payments."
                )

            # Apply interest
            for d in debts_sim:
                if d["balance"] > 0:
                    monthly_interest = d["balance"] * _pct_to_rate(d["rate_pct"]) / 12
                    total_interest += monthly_interest
                    d["balance"] += monthly_interest

            # Find target debt (first with positive balance in sorted order)
            active = [d for d in debts_sim if d["balance"] > 0]
            if not active:
                break
            target = active[0]

            # Pay minimums on all, extra on target
            for d in debts_sim:
                if d["balance"] > 0 and d is not target:
                    pay = min(d["min_payment"], d["balance"])
                    d["balance"] -= pay
                    d["balance"] = max(0.0, round(d["balance"], 4))

            pay_target = min(target["min_payment"] + extra, target["balance"])
            target["balance"] -= pay_target
            target["balance"] = max(0.0, round(target["balance"], 4))

            if target["balance"] == 0:
                payoff_order.append({
                    "name": target["name"],
                    "paid_off_month": months,
                })
                # freed-up min payment rolls into extra for next debt
                extra += target["min_payment"]

        return {
            "payoff_order": payoff_order,
            "total_months": months,
            "total_interest": round(total_interest, 2),
        }

    # Sort for avalanche (highest rate first) and snowball (lowest balance first)
    avalanche_sorted = sorted(debts, key=lambda d: -d["rate_pct"])
    snowball_sorted = sorted(debts, key=lambda d: d["balance"])

    avalanche_result = _simulate(avalanche_sorted, extra_payment)
    snowball_result = _simulate(snowball_sorted, extra_payment)

    chosen_sorted = avalanche_sorted if strategy == "avalanche" else snowball_sorted
    chosen_result = avalanche_result if strategy == "avalanche" else snowball_result

    comparison = {
        "avalanche": {
            "total_months": avalanche_result["total_months"],
            "total_interest": avalanche_result["total_interest"],
        },
        "snowball": {
            "total_months": snowball_result["total_months"],
            "total_interest": snowball_result["total_interest"],
        },
        "interest_saved_by_avalanche": round(
            snowball_result["total_interest"] - avalanche_result["total_interest"], 2
        ),
    }

    return {
        "result": {
            "strategy_used": strategy,
            "payoff_order": chosen_result["payoff_order"],
            "total_months": chosen_result["total_months"],
            "total_interest": chosen_result["total_interest"],
            "comparison": comparison,
        },
        "formula": (
            "Avalanche: pay minimums on all, extra towards highest-rate debt. "
            "Snowball: pay minimums on all, extra towards lowest-balance debt."
        ),
        "assumptions": [
            "Minimum payments stay constant throughout payoff.",
            "Freed-up minimum of paid-off debt rolls into extra for next target.",
            "Interest accrues monthly on outstanding balance.",
        ],
        "inputs_echo": {
            "debts": debts,
            "extra_payment": extra_payment,
            "strategy": strategy,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 9. retirement_projection
# ─────────────────────────────────────────────────────────────────────────────

def retirement_projection(
    current_age: int,
    retire_age: int,
    monthly_saving: float,
    current_corpus: float,
    return_pct: float,
    inflation_pct: float,
    monthly_expense_today: float,
) -> dict:
    """
    Project retirement corpus and assess rough sufficiency.

    Parameters
    ----------
    current_age          : Age today (years).
    retire_age           : Target retirement age.
    monthly_saving       : Monthly contribution to retirement corpus (₹).
    current_corpus       : Already accumulated (₹).
    return_pct           : Expected annual return on investments (%).
    inflation_pct        : Expected annual inflation rate (%).
    monthly_expense_today: Current monthly living expense (₹).

    Returns projected corpus at retirement, inflation-adjusted monthly expense,
    and a rough years-of-sustenance estimate.
    """
    if current_age < 0:
        raise ValueError(f"'current_age' must be ≥ 0, got {current_age}.")
    if retire_age <= current_age:
        raise ValueError(
            f"'retire_age' ({retire_age}) must be greater than 'current_age' ({current_age})."
        )
    _require_positive(monthly_saving, "monthly_saving")
    _require_positive(current_corpus, "current_corpus")
    _require_positive(return_pct, "return_pct")
    _require_positive(inflation_pct, "inflation_pct")
    _require_strictly_positive(monthly_expense_today, "monthly_expense_today")

    years_to_retire = retire_age - current_age
    n = round(years_to_retire * 12)  # accumulation months
    r = _pct_to_rate(return_pct) / 12

    # Grow existing corpus
    corpus_grown = current_corpus * (1 + r) ** n

    # SIP future value of monthly savings
    if r == 0:
        sip_fv = monthly_saving * n
    else:
        sip_fv = monthly_saving * (((1 + r) ** n - 1) / r) * (1 + r)

    projected_corpus = corpus_grown + sip_fv

    # Inflation-adjusted monthly expense at retirement
    expense_at_retire = monthly_expense_today * (1 + _pct_to_rate(inflation_pct)) ** years_to_retire

    # Post-retirement: assuming corpus earns return_pct and inflation erodes it
    # Real rate = ((1+return)/(1+inflation)) - 1
    real_rate = (1 + _pct_to_rate(return_pct)) / (1 + _pct_to_rate(inflation_pct)) - 1

    if real_rate <= 0:
        # Cannot grow faster than inflation; sustenance = corpus / annual expense (simple)
        years_sustain = projected_corpus / (expense_at_retire * 12)
        sustain_note = "Return ≤ inflation; corpus depletes without growth."
    else:
        # Annual sustenance approximation
        annual_expense_retire = expense_at_retire * 12
        if projected_corpus > 0 and annual_expense_retire > 0:
            years_sustain = projected_corpus / annual_expense_retire
            sustain_note = "Rough estimate based on initial retirement annual expense."
        else:
            years_sustain = 0.0
            sustain_note = "Corpus depleted."

    sufficiency = "✅ Likely sufficient (25+ years)" if years_sustain >= 25 else \
                  "⚠️ May fall short — consider increasing savings"

    return {
        "result": {
            "projected_corpus": round(projected_corpus, 2),
            "expense_at_retire_monthly": round(expense_at_retire, 2),
            "years_sustain_estimate": round(years_sustain, 1),
            "sufficiency_note": sufficiency,
        },
        "formula": (
            "Corpus = current_corpus×(1+r)^n + monthly×[((1+r)^n−1)/r]×(1+r); "
            "Expense at retire = expense_today × (1+inflation)^years"
        ),
        "assumptions": [
            f"Accumulation period: {years_to_retire} years ({n} months).",
            f"Monthly rate r = {return_pct}/12/100.",
            f"Inflation = {inflation_pct}% p.a.",
            "Post-retirement return and inflation assumed constant.",
            "Returns not guaranteed; this is a rough projection only.",
            "Consult a certified financial planner for a detailed retirement plan.",
        ],
        "inputs_echo": {
            "current_age": current_age,
            "retire_age": retire_age,
            "monthly_saving": monthly_saving,
            "current_corpus": current_corpus,
            "return_pct": return_pct,
            "inflation_pct": inflation_pct,
            "monthly_expense_today": monthly_expense_today,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 10. emergency_fund_target
# ─────────────────────────────────────────────────────────────────────────────

def emergency_fund_target(
    monthly_expenses: float,
    months: int = 6,
) -> dict:
    """
    Calculate the recommended emergency fund target.

    Parameters
    ----------
    monthly_expenses : Total monthly essential expenses (₹).
    months           : Number of months to cover (default 6).
    """
    _require_strictly_positive(monthly_expenses, "monthly_expenses")
    if months < 1:
        raise ValueError(f"'months' must be ≥ 1, got {months}.")

    target = monthly_expenses * months

    return {
        "result": {"emergency_fund_target": round(target, 2)},
        "formula": "Target = monthly_expenses × months",
        "assumptions": [
            f"Covers {months} months of essential expenses.",
            "Should be kept in a liquid, low-risk account (savings account or liquid fund).",
            "Essential expenses include rent, food, utilities, EMIs — not discretionary spending.",
        ],
        "inputs_echo": {
            "monthly_expenses": monthly_expenses,
            "months": months,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# 11. inflation_adjusted_value
# ─────────────────────────────────────────────────────────────────────────────

def inflation_adjusted_value(
    amount: float,
    inflation_pct: float,
    years: float,
) -> dict:
    """
    Calculate the future value of an amount after inflation erosion,
    or equivalently, what today's amount will be worth in real terms.

    Returns future_nominal (what it will cost) and real_value_today
    (purchasing power equivalent).
    """
    _require_strictly_positive(amount, "amount")
    _require_positive(inflation_pct, "inflation_pct")
    if years <= 0:
        raise ValueError(f"'years' must be > 0, got {years}.")

    future_nominal = amount * (1 + _pct_to_rate(inflation_pct)) ** years
    # real value: what today's 'amount' buys in 'years' at this inflation
    real_value = amount / (1 + _pct_to_rate(inflation_pct)) ** years

    return {
        "result": {
            "future_nominal": round(future_nominal, 2),
            "real_value_of_todays_amount": round(real_value, 2),
        },
        "formula": "Future = Amount × (1 + inflation)^years",
        "assumptions": [
            f"Inflation = {inflation_pct}% p.a. applied uniformly.",
            "Actual inflation varies by expense category (food, healthcare, education).",
        ],
        "inputs_echo": {
            "amount": amount,
            "inflation_pct": inflation_pct,
            "years": years,
        },
    }

