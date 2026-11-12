"""
tool_schemas.py — JSON schemas for Gemini function-calling.

Each entry follows the Gemini `Tool` / `FunctionDeclaration` schema.
Units are stated explicitly in every description so the LLM never guesses.

Usage::

    from chatbot.tool_schemas import TOOL_DECLARATIONS
    # Pass TOOL_DECLARATIONS to the Gemini SDK's Tool constructor.
"""

from __future__ import annotations

# Type alias for clarity
_Schema = dict

TOOL_DECLARATIONS: list[_Schema] = [
    # ── 1. loan_emi ───────────────────────────────────────────────────────────
    {
        "name": "loan_emi",
        "description": (
            "Calculate the Equated Monthly Instalment (EMI) for a loan. "
            "Also returns total amount paid and total interest paid over the life of the loan. "
            "Use for home loans, car loans, personal loans, education loans, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "principal": {
                    "type": "number",
                    "description": "Loan amount in INR (e.g. 4000000 for ₹40 lakh). Must be > 0.",
                },
                "annual_rate_pct": {
                    "type": "number",
                    "description": (
                        "Annual interest rate as a percentage. "
                        "8.5 means 8.5% per annum. Use 0 for interest-free loans. Must be ≥ 0."
                    ),
                },
                "years": {
                    "type": "number",
                    "description": "Loan tenure in years (e.g. 20 for a 20-year home loan). Must be > 0.",
                },
            },
            "required": ["principal", "annual_rate_pct", "years"],
        },
    },

    # ── 2. loan_amortization ──────────────────────────────────────────────────
    {
        "name": "loan_amortization",
        "description": (
            "Generate a month-by-month amortization schedule for the first N months of a loan. "
            "Shows how much of each EMI goes to principal vs interest, and the remaining balance. "
            "Useful for prepayment analysis."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "principal": {
                    "type": "number",
                    "description": "Loan amount in INR. Must be > 0.",
                },
                "annual_rate_pct": {
                    "type": "number",
                    "description": "Annual interest rate as a percentage (e.g. 8.5 for 8.5%). Must be ≥ 0.",
                },
                "years": {
                    "type": "number",
                    "description": "Loan tenure in years. Must be > 0.",
                },
                "first_n_months": {
                    "type": "integer",
                    "description": (
                        "Number of months to show in the schedule. Default 12. "
                        "Capped at total loan tenure in months."
                    ),
                },
            },
            "required": ["principal", "annual_rate_pct", "years"],
        },
    },

    # ── 3. compound_interest ──────────────────────────────────────────────────
    {
        "name": "compound_interest",
        "description": (
            "Calculate the future value of a lump-sum investment via compound interest. "
            "Also returns interest earned. Useful for FDs, PPF, bonds, lump-sum investments."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "principal": {
                    "type": "number",
                    "description": "Initial investment amount in INR. Must be > 0.",
                },
                "annual_rate_pct": {
                    "type": "number",
                    "description": "Annual interest/return rate as a percentage (e.g. 7.1 for 7.1%). Must be ≥ 0.",
                },
                "years": {
                    "type": "number",
                    "description": "Investment duration in years. Must be > 0.",
                },
                "compounds_per_year": {
                    "type": "integer",
                    "description": (
                        "How many times interest is compounded per year. "
                        "1 = annually, 2 = half-yearly, 4 = quarterly, 12 = monthly. "
                        "Default 1."
                    ),
                },
            },
            "required": ["principal", "annual_rate_pct", "years"],
        },
    },

    # ── 4. sip_future_value ───────────────────────────────────────────────────
    {
        "name": "sip_future_value",
        "description": (
            "Calculate the future value of a Systematic Investment Plan (SIP) in mutual funds. "
            "Returns corpus at maturity, total amount invested, and total gains. "
            "Assumes equal monthly investments at the START of each month."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "monthly_amount": {
                    "type": "number",
                    "description": "Amount invested every month in INR (e.g. 5000). Must be > 0.",
                },
                "expected_return_pct": {
                    "type": "number",
                    "description": (
                        "Expected annual return rate as a percentage (e.g. 12 for 12% p.a.). "
                        "Must be ≥ 0. Note: mutual fund returns are not guaranteed."
                    ),
                },
                "years": {
                    "type": "number",
                    "description": "SIP duration in years. Must be > 0.",
                },
            },
            "required": ["monthly_amount", "expected_return_pct", "years"],
        },
    },

    # ── 5. savings_goal_timeline ──────────────────────────────────────────────
    {
        "name": "savings_goal_timeline",
        "description": (
            "Calculate how many months it will take to reach a savings goal "
            "given current savings and a fixed monthly saving amount. "
            "Optionally accounts for returns on savings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal_amount": {
                    "type": "number",
                    "description": "Target amount to save in INR (e.g. 1000000 for ₹10 lakh). Must be > 0.",
                },
                "current_savings": {
                    "type": "number",
                    "description": "Amount already saved in INR. Must be ≥ 0.",
                },
                "monthly_saving": {
                    "type": "number",
                    "description": "Amount saved/invested every month in INR. Must be > 0.",
                },
                "annual_return_pct": {
                    "type": "number",
                    "description": (
                        "Annual return on savings as a percentage (e.g. 6.5). "
                        "Use 0 for a plain savings account with no growth. Default 0."
                    ),
                },
            },
            "required": ["goal_amount", "current_savings", "monthly_saving"],
        },
    },

    # ── 6. required_monthly_saving ────────────────────────────────────────────
    {
        "name": "required_monthly_saving",
        "description": (
            "Calculate how much to save every month to reach a financial goal "
            "in a given number of years. Optionally accounts for returns on savings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal_amount": {
                    "type": "number",
                    "description": "Target corpus in INR. Must be > 0.",
                },
                "current_savings": {
                    "type": "number",
                    "description": "Amount already saved in INR. Must be ≥ 0.",
                },
                "years": {
                    "type": "number",
                    "description": "Time horizon in years. Must be > 0.",
                },
                "annual_return_pct": {
                    "type": "number",
                    "description": (
                        "Annual return on savings/investments as a percentage. Default 0 (no growth). "
                        "Returns not guaranteed."
                    ),
                },
            },
            "required": ["goal_amount", "current_savings", "years"],
        },
    },

    # ── 7. budget_split_50_30_20 ──────────────────────────────────────────────
    {
        "name": "budget_split_50_30_20",
        "description": (
            "Apply the 50/30/20 budgeting rule to a monthly income. "
            "Returns recommended budget for Needs (50%), Wants (30%), and Savings (20%). "
            "If fixed expenses are provided, flags if they exceed 50% of income."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "monthly_income": {
                    "type": "number",
                    "description": "Take-home (post-tax) monthly income in INR. Must be > 0.",
                },
                "fixed_expenses": {
                    "type": "number",
                    "description": (
                        "Total known fixed monthly expenses (rent, EMIs, subscriptions) in INR. "
                        "Optional. If provided, flags if this exceeds 50% of income."
                    ),
                },
            },
            "required": ["monthly_income"],
        },
    },

    # ── 8. debt_payoff ────────────────────────────────────────────────────────
    {
        "name": "debt_payoff",
        "description": (
            "Simulate paying off multiple debts using either the avalanche strategy "
            "(highest interest rate first — minimises total interest) or the snowball strategy "
            "(lowest balance first — motivates with quick wins). "
            "Compares both strategies and shows payoff order, months, and total interest."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "debts": {
                    "type": "array",
                    "description": "List of debts to pay off.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name/label for the debt (e.g. 'Credit Card', 'Personal Loan').",
                            },
                            "balance": {
                                "type": "number",
                                "description": "Outstanding balance in INR. Must be > 0.",
                            },
                            "rate_pct": {
                                "type": "number",
                                "description": "Annual interest rate as a percentage (e.g. 36 for 36% p.a.).",
                            },
                            "min_payment": {
                                "type": "number",
                                "description": "Minimum monthly payment in INR. Must be > 0.",
                            },
                        },
                        "required": ["name", "balance", "rate_pct", "min_payment"],
                    },
                },
                "extra_payment": {
                    "type": "number",
                    "description": (
                        "Extra monthly amount applied to the target debt, above all minimums. "
                        "Use 0 if no extra payment available. Must be ≥ 0."
                    ),
                },
                "strategy": {
                    "type": "string",
                    "enum": ["avalanche", "snowball"],
                    "description": (
                        "'avalanche' targets highest interest rate first (saves most money). "
                        "'snowball' targets lowest balance first (psychological motivation). "
                        "Default: 'avalanche'."
                    ),
                },
            },
            "required": ["debts", "extra_payment"],
        },
    },

    # ── 9. retirement_projection ──────────────────────────────────────────────
    {
        "name": "retirement_projection",
        "description": (
            "Project the retirement corpus at a target age, estimate inflation-adjusted "
            "monthly expenses at retirement, and assess rough corpus sufficiency. "
            "This is a rough estimate — not a certified financial plan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "current_age": {
                    "type": "integer",
                    "description": "User's current age in years. Must be ≥ 0.",
                },
                "retire_age": {
                    "type": "integer",
                    "description": "Target retirement age in years. Must be > current_age.",
                },
                "monthly_saving": {
                    "type": "number",
                    "description": "Monthly amount being saved/invested for retirement in INR. Must be ≥ 0.",
                },
                "current_corpus": {
                    "type": "number",
                    "description": "Retirement corpus already accumulated in INR (PF, NPS, MFs, etc.). Must be ≥ 0.",
                },
                "return_pct": {
                    "type": "number",
                    "description": "Expected annual return on retirement investments as a percentage (e.g. 10). Must be ≥ 0. Returns not guaranteed.",
                },
                "inflation_pct": {
                    "type": "number",
                    "description": "Expected annual inflation rate as a percentage (e.g. 6). Must be ≥ 0.",
                },
                "monthly_expense_today": {
                    "type": "number",
                    "description": "Current monthly living expenses in INR (used to project future expense). Must be > 0.",
                },
            },
            "required": [
                "current_age", "retire_age", "monthly_saving",
                "current_corpus", "return_pct", "inflation_pct",
                "monthly_expense_today",
            ],
        },
    },

    # ── 10. emergency_fund_target ─────────────────────────────────────────────
    {
        "name": "emergency_fund_target",
        "description": (
            "Calculate the recommended emergency fund target. "
            "Standard advice is 3–6 months of essential expenses in a liquid account."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "monthly_expenses": {
                    "type": "number",
                    "description": "Total essential monthly expenses in INR (rent, food, utilities, EMIs). Must be > 0.",
                },
                "months": {
                    "type": "integer",
                    "description": (
                        "Number of months of expenses to cover. "
                        "3 for minimal, 6 for standard, 12 for high-risk jobs/self-employed. Default 6."
                    ),
                },
            },
            "required": ["monthly_expenses"],
        },
    },

    # ── 11. inflation_adjusted_value ──────────────────────────────────────────
    {
        "name": "inflation_adjusted_value",
        "description": (
            "Show the impact of inflation on a sum of money over time. "
            "Returns (a) what that amount will cost in the future (future nominal value), "
            "and (b) what today's amount is worth in real purchasing-power terms after N years."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "The amount in INR to evaluate. Must be > 0.",
                },
                "inflation_pct": {
                    "type": "number",
                    "description": "Annual inflation rate as a percentage (e.g. 6 for 6% p.a.). Must be ≥ 0.",
                },
                "years": {
                    "type": "number",
                    "description": "Number of years into the future. Must be > 0.",
                },
            },
            "required": ["amount", "inflation_pct", "years"],
        },
    },

    # ── 12. update_profile (profile tool) ────────────────────────────────────
    {
        "name": "update_profile",
        "description": (
            "Update the user's financial profile with information they share in conversation. "
            "Only update fields the user has explicitly stated. Never ask for sensitive data. "
            "Profile values are used as defaults for calculations but are always confirmed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "monthly_income": {
                    "type": "number",
                    "description": "User's monthly take-home income in INR.",
                },
                "monthly_expenses": {
                    "type": "number",
                    "description": "User's total monthly expenses in INR.",
                },
                "age": {
                    "type": "integer",
                    "description": "User's current age in years.",
                },
                "risk_tolerance": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "User's investment risk tolerance.",
                },
                "goals": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of financial goals (e.g. ['buy a car', 'retirement', 'child education']).",
                },
                "currency": {
                    "type": "string",
                    "description": "Preferred currency code (default 'INR').",
                },
            },
            "required": [],
        },
    },
]

