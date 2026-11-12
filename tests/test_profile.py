"""
tests/test_profile.py — Unit tests for chatbot/profile.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from chatbot.profile import ProfileManager, ProfileUpdate, UserProfile


# ─────────────────────────────────────────────────────────────────────────────
# ProfileUpdate validation
# ─────────────────────────────────────────────────────────────────────────────

class TestProfileUpdate:
    def test_valid_income(self):
        p = ProfileUpdate(monthly_income=80_000)
        assert p.monthly_income == 80_000

    def test_valid_all_fields(self):
        p = ProfileUpdate(
            monthly_income=100_000,
            monthly_expenses=60_000,
            age=35,
            risk_tolerance="medium",
            goals=["buy car", "retirement"],
            currency="INR",
        )
        assert p.age == 35
        assert p.risk_tolerance == "medium"

    def test_negative_income_raises(self):
        with pytest.raises(Exception):
            ProfileUpdate(monthly_income=-1000)

    def test_invalid_risk_tolerance_raises(self):
        with pytest.raises(Exception):
            ProfileUpdate(risk_tolerance="extreme")

    def test_age_too_high_raises(self):
        with pytest.raises(Exception):
            ProfileUpdate(age=200)

    def test_empty_goals_string_raises(self):
        with pytest.raises(Exception):
            ProfileUpdate(goals=[""])

    def test_no_fields_raises(self):
        with pytest.raises(Exception):
            ProfileUpdate()


# ─────────────────────────────────────────────────────────────────────────────
# UserProfile dataclass
# ─────────────────────────────────────────────────────────────────────────────

class TestUserProfile:
    def test_default_currency(self):
        p = UserProfile()
        assert p.currency == "INR"

    def test_as_context_no_data(self):
        p = UserProfile()
        assert p.as_context_string() == "No profile data yet."

    def test_as_context_with_data(self):
        p = UserProfile(monthly_income=80_000, age=30, risk_tolerance="medium")
        ctx = p.as_context_string()
        assert "80,000" in ctx
        assert "30" in ctx
        assert "medium" in ctx

    def test_apply_update_returns_changed_fields(self):
        p = UserProfile()
        update = ProfileUpdate(monthly_income=50_000, age=28)
        changed = p.apply_update(update)
        assert "monthly_income" in changed
        assert "age" in changed

    def test_apply_update_no_duplicate_change(self):
        p = UserProfile(monthly_income=50_000)
        update = ProfileUpdate(monthly_income=50_000)
        changed = p.apply_update(update)
        # Same value → not in changed list
        assert "monthly_income" not in changed

    def test_to_dict_round_trip(self):
        p = UserProfile(monthly_income=70_000, age=32, goals=["car", "house"])
        d = p.to_dict()
        p2 = UserProfile.from_dict(d)
        assert p2.monthly_income == 70_000
        assert p2.goals == ["car", "house"]


# ─────────────────────────────────────────────────────────────────────────────
# ProfileManager
# ─────────────────────────────────────────────────────────────────────────────

class TestProfileManager:
    def test_update_valid(self):
        mgr = ProfileManager()
        result = mgr.update({"monthly_income": 80_000, "age": 30})
        assert result["success"] is True
        assert "monthly_income" in result["updated_fields"]
        assert mgr.profile.monthly_income == 80_000

    def test_update_invalid_raises_error_in_result(self):
        mgr = ProfileManager()
        result = mgr.update({"risk_tolerance": "ultra-high"})
        assert result["success"] is False
        assert "error" in result

    def test_update_negative_income_fails(self):
        mgr = ProfileManager()
        result = mgr.update({"monthly_income": -5000})
        assert result["success"] is False

    def test_reset_clears_profile(self):
        mgr = ProfileManager()
        mgr.update({"monthly_income": 80_000})
        mgr.reset()
        assert mgr.profile.monthly_income is None

    def test_persistence_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "profile.json"
            mgr = ProfileManager(persist_path=path)
            mgr.update({"monthly_income": 60_000, "age": 25})

            # Create a new manager from same path
            mgr2 = ProfileManager(persist_path=path)
            assert mgr2.profile.monthly_income == 60_000
            assert mgr2.profile.age == 25

    def test_persistence_corrupt_file_starts_fresh(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "profile.json"
            path.write_text("not valid json", encoding="utf-8")
            mgr = ProfileManager(persist_path=path)
            assert mgr.profile.monthly_income is None

    def test_profile_summary_in_update_result(self):
        mgr = ProfileManager()
        result = mgr.update({"monthly_income": 100_000, "risk_tolerance": "high"})
        assert "profile_summary" in result
        assert "1,00,000" in result["profile_summary"] or "100,000" in result["profile_summary"]

    def test_goals_accumulate(self):
        mgr = ProfileManager()
        mgr.update({"goals": ["buy car"]})
        mgr.update({"goals": ["buy car", "retirement"]})
        assert len(mgr.profile.goals) == 2

