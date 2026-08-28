"""Pydantic request/response models — mirrors the shapes in SCHEMA.md.

The weight dimensions are read out of schema.json rather than retyped here,
so the API and the contract cannot drift apart. That matters: a scenario whose
weights sum to 1.0 over the *wrong* keys passes a sum check and produces a
confidently wrong ranking, which is worse than an error.

Value-level problems (a weight outside [0, 1], a non-finite number, a missing
dimension) are malformed body — 422. Whether the six weights sum to 1.0 is a
400 `invalid_weights`, per SCHEMA.md §5.7.

Owner: Person B
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.json"
with _SCHEMA_PATH.open(encoding="utf-8") as _f:
    _SCHEMA = json.load(_f)

# The six named dimensions, straight from the contract (SCHEMA.md §3.3).
WEIGHT_KEYS: tuple[str, ...] = tuple(
    _SCHEMA["definitions"]["SupplierPreferences"]["properties"]["weights"]["required"]
)

# allow_inf_nan=False is the point of this alias. NaN defeats every comparison
# it touches, so `abs(total - 1.0) > tolerance` is False for a NaN total and a
# NaN weight would sail through the sum check into a meaningless ranking.
Weight = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
Lakh = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PreferenceOverrideModel(BaseModel):
    supplier_id: str
    weights: dict[str, Weight]
    urgent: bool = False

    @field_validator("weights")
    @classmethod
    def _exactly_the_six_dimensions(cls, weights: dict) -> dict:
        missing = [k for k in WEIGHT_KEYS if k not in weights]
        unknown = sorted(set(weights) - set(WEIGHT_KEYS))
        if not missing and not unknown:
            return weights
        problems = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown {', '.join(unknown)}")
        raise ValueError(
            f"weights must name exactly {', '.join(WEIGHT_KEYS)} — "
            + "; ".join(problems)
        )


class LiquidityOverrideModel(BaseModel):
    provider_id: str
    available_liquidity_lakh: Lakh


class SettlementEventModel(BaseModel):
    match_id: str
    outcome: str
    days_late: int = Field(default=0, ge=0)


class MarketScenarioModel(BaseModel):
    preference_overrides: list[PreferenceOverrideModel] = []
    liquidity_overrides: list[LiquidityOverrideModel] = []
    settlement_events: list[SettlementEventModel] = []
    naive_mode: bool = False


class AssessRequest(BaseModel):
    invoice_id: str
    scenario: MarketScenarioModel = MarketScenarioModel()


class OffersRequest(BaseModel):
    invoice_id: str
    scenario: MarketScenarioModel = MarketScenarioModel()


class ClearRequest(BaseModel):
    invoice_ids: list[str]
    scenario: MarketScenarioModel = MarketScenarioModel()


class SettleRequest(BaseModel):
    match_id: str
    outcome: str
    days_late: int = Field(default=0, ge=0)
    scenario: MarketScenarioModel = MarketScenarioModel()
