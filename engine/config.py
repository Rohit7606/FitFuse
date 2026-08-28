"""FitFuse engine configuration — the single source for all tunable constants.

Every constant has a one-line comment explaining what it means and why it
has that value. No magic numbers in the modules — import from here.

market/ imports from here too. There is exactly one config file (AGENTS.md §7).
"""

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

MOCK_SEED = 42  # Deterministic generation; same seed → byte-identical file

# ---------------------------------------------------------------------------
# Risk model coefficients — transparent scorecard (AGENTS.md §1.5)
# These are hand-set, committed weights. Not learned at runtime.
# ---------------------------------------------------------------------------

# Intercept: baseline logit before any factor contributes
B0 = -4.5

# Buyer credit-grade penalty weight — the primary risk driver (SCHEMA.md §2.6)
B_GRADE = 2.0

# Buyer average payment delay, normalised against DELAY_REF_DAYS
B_DELAY = 1.2

# Buyer payment delay trend (improving or worsening)
B_TREND = 0.8

# Invoice tenor, normalised against TENOR_REF_DAYS
B_TENOR = 0.6

# Invoice size anomaly relative to supplier's typical revenue
B_SIZE = 0.5

# Supplier thin-file penalty (low data completeness → higher risk)
B_THIN = 0.7

# Supplier historical default rate
B_HISTORY = 1.5

# Buyer dispute frequency, normalised against DISPUTE_REF
B_DISPUTE = 0.4

# ---------------------------------------------------------------------------
# Reference denominators for normalisation
# ---------------------------------------------------------------------------

DELAY_REF_DAYS = 30    # A 30-day average delay saturates the delay factor
TREND_REF_DAYS = 10    # A 10-day trend change saturates the trend factor
TENOR_REF_DAYS = 120   # A 120-day tenor saturates the tenor factor
DISPUTE_REF = 3        # 3 disputes/year saturates the dispute factor

# ---------------------------------------------------------------------------
# PD bounds and defaults
# ---------------------------------------------------------------------------

PD_FLOOR = 0.002       # Minimum PD — nothing is risk-free
PD_CEILING = 0.400     # Maximum PD — beyond this, decline

# Used when prior_defaults is null (AGENTS.md §3.6)
NO_HISTORY_PRIOR = 0.02  # Absence of history is not a clean record

# Small constant to prevent division by zero
EPSILON = 1e-9

# ---------------------------------------------------------------------------
# Buyer credit grade penalty lookup
# Produces a 0–1.5 penalty; higher = worse credit
# ---------------------------------------------------------------------------

GRADE_PENALTY = {
    "AAA": 0.00,
    "AA":  0.15,
    "A":   0.35,
    "BBB": 0.60,
    "BB":  0.85,
    "B":   1.10,
    "C":   1.50,
}

# ---------------------------------------------------------------------------
# Uncertainty band parameters
# ---------------------------------------------------------------------------

BASE_UNCERTAINTY = 0.003          # Minimum uncertainty; never claim zero
UNKNOWN_FIELD_PENALTY = 0.002     # Per unknown field
INFERRED_FIELD_PENALTY = 0.001    # Per inferred field
THIN_FILE_PENALTY = 0.006         # Scaled by (1 - data_completeness)
NEW_SUPPLIER_PENALTY = 0.004      # Applied if years_operating < 3

# ---------------------------------------------------------------------------
# Risk band thresholds — banding on pd_upper, not pd (SCHEMA.md §4.8)
# ---------------------------------------------------------------------------

RISK_BAND_THRESHOLDS = {
    "prime":    0.025,   # pd_upper < 0.025
    "standard": 0.060,   # pd_upper 0.025 – 0.060
    "watch":    0.120,   # pd_upper 0.060 – 0.120
    # "decline": pd_upper >= 0.120
}

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

STRUCTURE_MISMATCH = 0.6   # Score when repayment structure doesn't match preference

# Urgency multipliers — applied to weights before combining (PERSON_A §3.4)
URGENCY_SPEED_BOOST = 1.4    # Speed weight boost when supplier.urgent is true
URGENCY_ADVANCE_BOOST = 1.2  # Advance weight boost when supplier.urgent is true

# ---------------------------------------------------------------------------
# Provider agent constants (used by market/ — single config file, AGENTS.md §7)
# ---------------------------------------------------------------------------

RECOVERY_RATE = 0.40           # Expected recovery in default (40%)
CAPITAL_CHARGE_RATE = 0.30     # Capital charge multiplier on pd_upper
# Winner's-curse shading: shade = SHADE_K * uncertainty * log(1 + competitors).
# Uncertainty is a probability (~0.007 on INV001), so K scales a very small
# number up into a rate. At K=8.0 the shade was 776 bp — larger than the entire
# bid — and no provider could reach the DEMO_SCENARIO.md §4 rates. K=0.30 gives
# ~29 bp against three rivals, which is a plausible adverse-selection premium.
SHADE_K = 0.30
EXPLORATION_BONUS = 0.10       # UCB-style exploration bonus for segment learning

# ---------------------------------------------------------------------------
# Clearing constants
# ---------------------------------------------------------------------------

MAX_ROUNDS = 50  # Safety net for deferred acceptance; hitting this is a bug

# ---------------------------------------------------------------------------
# Learning loop constants
# ---------------------------------------------------------------------------

DELAY_LEARNING_RATE = 0.30     # How fast buyer avg delay moves toward observed
SEGMENT_LEARNING_RATE = 0.20   # How fast provider segment estimates move

# ---------------------------------------------------------------------------
# Provider type defaults — used by agents to differentiate non-price terms
# See PERSON_B.md §3.1 for the rationale
# ---------------------------------------------------------------------------

PROVIDER_TYPE_DEFAULTS = {
    "bank": {
        "advance_range": (0.75, 0.82),
        "settlement_range": (2, 4),
        "fee_range": (0.004, 0.006),
        "structures": ["bullet"],
        "rate_posture": "competitive",
    },
    "nbfc": {
        "advance_range": (0.68, 0.75),
        "settlement_range": (1, 2),
        "fee_range": (0.006, 0.010),
        "structures": ["bullet"],
        "rate_posture": "lowest_headline",
    },
    "fund": {
        "advance_range": (0.85, 0.92),
        "settlement_range": (0, 1),
        "fee_range": (0.002, 0.005),
        "structures": ["bullet"],
        "rate_posture": "mid",
    },
    "fintech": {
        "advance_range": (0.72, 0.78),
        "settlement_range": (0, 1),
        "fee_range": (0.001, 0.004),
        "structures": ["instalment"],
        "rate_posture": "highest",
    },
}

# ---------------------------------------------------------------------------
# Weight sum tolerance (SCHEMA.md §3.3)
# ---------------------------------------------------------------------------

WEIGHT_SUM_TOLERANCE = 0.001  # Preference weights must sum to 1.0 ± this
