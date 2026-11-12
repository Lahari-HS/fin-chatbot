"""
profile.py — User financial profile store.

The profile is built up over the conversation as the user shares details.
It is used as default input for tools (always confirmed before use).
No sensitive identifiers (PAN, Aadhaar, card numbers) are stored.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic validation model (used by update_profile tool)
# ─────────────────────────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    """Validated input for the update_profile tool call."""

    monthly_income: float | None = Field(None, ge=0, description="Monthly take-home income in INR")
    monthly_expenses: float | None = Field(None, ge=0, description="Total monthly expenses in INR")
    age: int | None = Field(None, ge=0, le=120, description="Age in years")
    risk_tolerance: Literal["low", "medium", "high"] | None = Field(
        None, description="Investment risk tolerance"
    )
    goals: list[str] | None = Field(None, description="List of financial goals")
    currency: str | None = Field(None, min_length=1, max_length=10, description="Currency code")
    existing_debts: list[dict] | None = Field(None, description="List of existing debts")

    @field_validator("monthly_income", "monthly_expenses", mode="before")
    @classmethod
    def _non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value must be non-negative")
        return v

    @field_validator("goals", mode="before")
    @classmethod
    def _goals_non_empty_strings(cls, v):
        if v is not None:
            for item in v:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError("Each goal must be a non-empty string")
        return v

    @model_validator(mode="after")
    def _at_least_one_field(self):
        values = {k: v for k, v in self.model_dump().items() if v is not None}
        if not values:
            raise ValueError("At least one profile field must be provided")
        return self


# ─────────────────────────────────────────────────────────────────────────────
# Profile dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    monthly_income: float | None = None
    monthly_expenses: float | None = None
    age: int | None = None
    risk_tolerance: Literal["low", "medium", "high"] | None = None
    goals: list[str] = field(default_factory=list)
    existing_debts: list[dict] = field(default_factory=list)
    currency: str = "INR"

    # ── update from validated dict ────────────────────────────────────────────
    def apply_update(self, update: ProfileUpdate) -> list[str]:
        """
        Apply a validated ProfileUpdate, return list of changed field names.
        """
        changed = []
        for field_name, value in update.model_dump(exclude_none=True).items():
            if getattr(self, field_name) != value:
                setattr(self, field_name, value)
                changed.append(field_name)
        return changed

    # ── summary for LLM context ───────────────────────────────────────────────
    def as_context_string(self) -> str:
        """Return a compact summary the LLM can use as context."""
        parts = []
        if self.monthly_income is not None:
            parts.append(f"Monthly income: ₹{self.monthly_income:,.0f}")
        if self.monthly_expenses is not None:
            parts.append(f"Monthly expenses: ₹{self.monthly_expenses:,.0f}")
        if self.age is not None:
            parts.append(f"Age: {self.age}")
        if self.risk_tolerance:
            parts.append(f"Risk tolerance: {self.risk_tolerance}")
        if self.goals:
            parts.append(f"Goals: {', '.join(self.goals)}")
        if self.existing_debts:
            parts.append(f"Debts: {len(self.existing_debts)} recorded")
        if not parts:
            return "No profile data yet."
        return "User profile — " + " | ".join(parts)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "UserProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─────────────────────────────────────────────────────────────────────────────
# Profile session manager
# ─────────────────────────────────────────────────────────────────────────────

class ProfileManager:
    """
    Manages a UserProfile for one session.
    Optionally persists to a local JSON file (no sensitive data stored).
    """

    def __init__(self, persist_path: Path | None = None):
        self._profile = UserProfile()
        self._persist_path = persist_path
        if persist_path and persist_path.exists():
            try:
                with open(persist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._profile = UserProfile.from_dict(data)
            except Exception:
                self._profile = UserProfile()  # start fresh on corrupt file

    @property
    def profile(self) -> UserProfile:
        return self._profile

    def update(self, raw_args: dict) -> dict:
        """
        Called by the LLM tool handler with raw args from the tool call.
        Validates via Pydantic, applies changes, persists.
        Returns a summary dict for the LLM.
        """
        try:
            update = ProfileUpdate(**raw_args)
        except Exception as e:
            return {"success": False, "error": str(e)}

        changed = self._profile.apply_update(update)
        self._save()
        return {
            "success": True,
            "updated_fields": changed,
            "profile_summary": self._profile.as_context_string(),
        }

    def _save(self):
        if self._persist_path:
            try:
                self._persist_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._persist_path, "w", encoding="utf-8") as f:
                    json.dump(self._profile.to_dict(), f, indent=2, ensure_ascii=False)
            except Exception:
                pass  # persistence failure is non-fatal

    def reset(self):
        self._profile = UserProfile()
        self._save()

