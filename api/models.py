"""Pydantic request/response models — mirrors the shapes in SCHEMA.md.

Owner: Person B
"""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PreferenceOverrideModel(BaseModel):
    supplier_id: str
    weights: dict[str, float]
    urgent: bool = False


class LiquidityOverrideModel(BaseModel):
    provider_id: str
    available_liquidity_lakh: float


class SettlementEventModel(BaseModel):
    match_id: str
    outcome: str
    days_late: int = 0


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
    days_late: int = 0
    scenario: MarketScenarioModel = MarketScenarioModel()
