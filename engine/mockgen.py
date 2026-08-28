import argparse
import hashlib
import json
import os
import random
from datetime import date, timedelta

import jsonschema

from engine.config import MOCK_SEED

# Fixed build-time stamp. A wall-clock call here would make the same seed
# produce a different file on every run, breaking AGENTS.md §3.1.
GENERATED_AT = "2026-08-28T00:00:00Z"

# Every invoice is issued relative to this date, so tenor_days always equals
# due_date - issue_date (SCHEMA.md §3.5) without depending on today's date.
BASE_ISSUE_DATE = date(2026, 8, 20)


def _irn(invoice_id):
    """A GST IRN is a 64-character hex string — see PERSON_A.md §3.1."""
    return hashlib.sha256(f"irn:{invoice_id}".encode()).hexdigest()


def _doc_hash(token):
    """Document fingerprint. Two invoices sharing one are a duplicate-financing attempt."""
    return "sha256:" + hashlib.sha256(f"doc:{token}".encode()).hexdigest()


def generate_market(seed=MOCK_SEED):
    rng = random.Random(seed)

    # 1. FIXED ENTITIES

    # SUP001
    sup001 = {
        "supplier_id": "SUP001",
        "name": "Sharda Auto Components Pvt Ltd",
        "sector": "auto_components",
        "city": "Pune",
        "years_operating": 7,
        "annual_revenue_lakh": 480.00,
        "gstin": "27AADCS1234E1Z1",
        "prior_financings": 12,
        "prior_defaults": 0,
        "data_completeness": 0.95,
        "preferences": {
            "preset": "cash_fastest",
            "weights": {
                "cost": 0.15,
                "advance": 0.30,
                "speed": 0.35,
                "tenor": 0.10,
                "fees": 0.05,
                "structure": 0.05
            },
            # Payroll on Friday: at least 70% advance, cash within 5 days.
            # Hard constraints, not preferences — see PERSON_A.md §3.4 step 1.
            "min_advance_rate": 0.70,
            "max_days_to_cash": 5,
            "preferred_structure": "bullet",
            "urgent": True
        },
        "data_source": "synthetic",
        "field_confidence": {}
    }

    # BUY001
    buy001 = {
        "buyer_id": "BUY001",
        "name": "Vireon Motors India Ltd",
        "sector": "auto_components",
        "credit_grade": "AA",
        "avg_payment_delay_days": 4,
        "payment_delay_trend": 0.0,
        "disputes_last_year": 1,
        "annual_procurement_lakh": 50000.00,
        "data_source": "synthetic",
        "field_confidence": {}
    }

    # INV001
    inv001 = {
        "invoice_id": "INV001",
        "supplier_id": "SUP001",
        "buyer_id": "BUY001",
        "amount_lakh": 10.00,
        "issue_date": BASE_ISSUE_DATE.isoformat(),
        "due_date": (BASE_ISSUE_DATE + timedelta(days=60)).isoformat(),
        "tenor_days": 60,
        "irn": _irn("INV001"),
        "document_hash": _doc_hash("INV001"),
        "goods_description": "hydraulic_seal_kits",
        "delivery_confirmed": None,
        "status": "open",
        "data_source": "synthetic",
        "field_confidence": {"delivery_confirmed": "unknown"}
    }

    # INV002 (duplicate)
    inv002 = {
        "invoice_id": "INV002",
        "supplier_id": "SUP002",
        "buyer_id": "BUY001",
        "amount_lakh": 10.00,
        "issue_date": BASE_ISSUE_DATE.isoformat(),
        "due_date": (BASE_ISSUE_DATE + timedelta(days=60)).isoformat(),
        "tenor_days": 60,
        "irn": _irn("INV002"),
        "document_hash": _doc_hash("INV001"),  # Same fingerprint as INV001 — the planted duplicate
        "goods_description": "hydraulic_seal_kits",
        "delivery_confirmed": None,
        "status": "open",
        "data_source": "synthetic",
        "field_confidence": {}
    }

    # INV014
    inv014 = {
        "invoice_id": "INV014",
        "supplier_id": "SUP001",
        "buyer_id": "BUY001",
        "amount_lakh": 5.00,
        "issue_date": (BASE_ISSUE_DATE + timedelta(days=7)).isoformat(),
        "due_date": (BASE_ISSUE_DATE + timedelta(days=37)).isoformat(),
        "tenor_days": 30,
        "irn": _irn("INV014"),
        "document_hash": _doc_hash("INV014"),
        "goods_description": "brake_line_assemblies",
        "delivery_confirmed": True,
        "status": "open",
        "data_source": "synthetic",
        "field_confidence": {}
    }

    # Providers
    prv001 = {
        "provider_id": "PRV001",
        "name": "Meridian Bank",
        "type": "bank",
        "available_liquidity_lakh": 2000.00,
        "total_portfolio_lakh": 10000.00,
        "risk_appetite": 0.10,
        "min_ticket_lakh": 1.00,
        "max_ticket_lakh": 500.00,
        "cost_of_funds": 0.05,
        "target_return": 0.08,
        "sector_limits": {"auto_components": 0.25, "textiles": 0.15},
        "buyer_limit": 0.15,
        "current_exposure": {
            "by_sector": {"auto_components": 1180.00, "textiles": 1450.00},
            "by_buyer": {"BUY001": 210.00},
        },
        "speed_capability_days": 3,
        "preferred_structures": ["bullet"],
        "data_source": "synthetic"
    }

    prv002 = {
        "provider_id": "PRV002",
        "name": "Arcline Capital",
        "type": "nbfc",
        "available_liquidity_lakh": 1000.00,
        "total_portfolio_lakh": 5000.00,
        "risk_appetite": 0.15,
        "min_ticket_lakh": 0.50,
        "max_ticket_lakh": 200.00,
        "cost_of_funds": 0.08,
        "target_return": 0.12,
        "sector_limits": {"auto_components": 0.30, "textiles": 0.25},
        "buyer_limit": 0.20,
        "current_exposure": {
            "by_sector": {"auto_components": 640.00},
            "by_buyer": {"BUY001": 145.00},
        },
        "speed_capability_days": 2,
        "preferred_structures": ["bullet"],
        "data_source": "synthetic"
    }

    # Kestrel is the demo's syndication beat: auto-components sits at 94% of a 20%
    # cap on a 500 portfolio, so sector headroom is exactly 6.00 lakh. The buyer
    # limit is deliberately slack (0.15 x 500 - 20 = 55) so the SECTOR is what binds.
    prv003 = {
        "provider_id": "PRV003",
        "name": "Kestrel Credit Fund",
        "type": "fund",
        "available_liquidity_lakh": 500.00,
        "total_portfolio_lakh": 500.00,
        "risk_appetite": 0.20,
        "min_ticket_lakh": 1.00,
        "max_ticket_lakh": 200.00,
        "cost_of_funds": 0.06,
        "target_return": 0.15,
        "sector_limits": {"auto_components": 0.20, "electronics": 0.30},
        "buyer_limit": 0.15,
        "current_exposure": {
            "by_sector": {"auto_components": 94.00, "electronics": 61.50},
            "by_buyer": {"BUY001": 20.00},
        },
        "speed_capability_days": 0,
        "preferred_structures": ["bullet"],
        "data_source": "synthetic"
    }

    prv004 = {
        "provider_id": "PRV004",
        "name": "Nimbus Finserv",
        "type": "fintech",
        "available_liquidity_lakh": 800.00,
        "total_portfolio_lakh": 2000.00,
        "risk_appetite": 0.25,
        "min_ticket_lakh": 0.10,
        "max_ticket_lakh": 100.00,
        "cost_of_funds": 0.07,
        "target_return": 0.14,
        "sector_limits": {"auto_components": 0.35, "fmcg": 0.30},
        "buyer_limit": 0.25,
        "current_exposure": {
            "by_sector": {"auto_components": 402.00},
            "by_buyer": {"BUY001": 88.00},
        },
        "speed_capability_days": 1,
        "preferred_structures": ["instalment"],
        "data_source": "synthetic"
    }

    prv005 = {
        "provider_id": "PRV005",
        "name": "Coastal Cooperative Bank",
        "type": "bank",
        "available_liquidity_lakh": 300.00,
        "total_portfolio_lakh": 800.00,
        "risk_appetite": 0.08,
        "min_ticket_lakh": 0.50,
        "max_ticket_lakh": 8.00,  # Limits this from INV001 (10.00)
        "cost_of_funds": 0.05,
        "target_return": 0.07,
        "sector_limits": {"auto_components": 0.20, "agriculture": 0.35},
        "buyer_limit": 0.12,
        "current_exposure": {
            "by_sector": {"auto_components": 96.00},
            "by_buyer": {"BUY001": 14.00},
        },
        "speed_capability_days": 4,
        "preferred_structures": ["bullet", "instalment"],
        "data_source": "synthetic"
    }

    prv006 = {
        "provider_id": "PRV006",
        "name": "Sentinel Asset Managers",
        "type": "fund",
        "available_liquidity_lakh": 1500.00,
        "total_portfolio_lakh": 8000.00,
        "risk_appetite": 0.015,  # Too low for INV001 pd_upper
        "min_ticket_lakh": 5.00,
        "max_ticket_lakh": 300.00,
        "cost_of_funds": 0.04,
        "target_return": 0.10,
        "sector_limits": {"auto_components": 0.25, "pharmaceuticals": 0.30},
        "buyer_limit": 0.18,
        "current_exposure": {
            "by_sector": {"auto_components": 1240.00},
            "by_buyer": {"BUY001": 300.00},
        },
        "speed_capability_days": 1,
        "preferred_structures": ["bullet"],
        "data_source": "synthetic"
    }

    suppliers = [sup001]
    buyers = [buy001]
    invoices = [inv001, inv002, inv014]
    providers = [prv001, prv002, prv003, prv004, prv005, prv006]
    history = []

    # 2. FILLER GENERATION

    # Generate Suppliers (up to ~60)
    sectors = ["auto_components", "textiles", "fmcg", "electronics", "pharmaceuticals", "agriculture"]
    cities = ["Pune", "Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Ahmedabad"]
    names_prefix = [
        "Apex", "Zenith", "Prime", "Global", "Indian", "Sunrise", "National", "Star", "Royal", "Balaji",
        "Krishna", "Vindhya", "Deccan", "Oriental", "Pioneer", "Sterling", "Bharat", "Aarav", "Paramount",
        "Supreme", "Dynamic", "Precision", "Modern", "Classic", "Universal", "Maruthi", "Swastik"
    ]
    names_suffix = [
        "Industries", "Enterprises", "Traders", "Solutions", "Manufacturing", "Synthetics", "Corp",
        "Logistics", "Ventures", "Plastics", "Steel", "Textiles", "Exports", "Engineering", "Motors",
        "Electronics", "Auto", "Packaging", "Chemicals", "Agrotech"
    ]

    used_names = set()
    used_names.add(sup001["name"])
    used_names.add(buy001["name"])
    # We will also add the hardcoded providers to avoid any extremely unlikely overlaps, though they have different shapes.
    for p in providers:
        used_names.add(p["name"])

    for i in range(2, 61): # SUP002 to SUP060
        sid = f"SUP{i:03d}"
        
        while True:
            if i == 2:
                name_candidate = "Ramesh Enterprises"
            else:
                name_candidate = f"{rng.choice(names_prefix)} {rng.choice(names_suffix)} Pvt Ltd"
            
            if name_candidate not in used_names:
                used_names.add(name_candidate)
                break
            else:
                # If collision, try again. If we somehow exhaust combinations (impossible with this pool size), it loops.
                # To be completely safe, we can just let it loop since the pool has 27 * 20 = 540 combinations for 59 slots.
                pass

        if i == 2:
            # SUP002 already referenced in INV002
            sup = {
                "supplier_id": sid,
                "name": name_candidate,
                "sector": "textiles",
                "city": "Mumbai",
                "years_operating": rng.randint(1, 20),
                "annual_revenue_lakh": round(rng.lognormvariate(4.0, 1.0), 2),
                "gstin": f"27AABCU{rng.randint(1000, 9999)}A1Z5",
                "prior_financings": rng.randint(0, 15),
                "prior_defaults": rng.choice([0, 0, 0, 1]),
                "data_completeness": round(rng.uniform(0.5, 1.0), 2),
                "preferences": {
                    "preset": "cheapest",
                    "weights": {
                        "cost": 0.55, "advance": 0.10, "speed": 0.05,
                        "tenor": 0.10, "fees": 0.15, "structure": 0.05
                    },
                    "min_advance_rate": None,
                    "max_days_to_cash": None,
                    "preferred_structure": None,
                    "urgent": False
                },
                "data_source": "synthetic",
                "field_confidence": {}
            }
        else:
            sup = {
                "supplier_id": sid,
                "name": name_candidate,
                "sector": rng.choice(sectors),
                "city": rng.choice(cities),
                "years_operating": rng.randint(1, 25),
                "annual_revenue_lakh": round(rng.lognormvariate(4.5, 1.2), 2),
                "gstin": f"27{rng.choice(['AAD', 'BBE', 'CCF'])}{rng.randint(1000, 9999)}A1Z{rng.randint(1,9)}",
                "prior_financings": rng.randint(0, 50),
                # None is not the same as 0 — a declared clean record should help,
                # silence should not. See AGENTS.md §3.6.
                "prior_defaults": rng.choice([0, 0, 0, 0, 0, 1, 2, None, None]),
                "data_completeness": round(rng.uniform(0.4, 0.99), 2),
                "preferences": {
                    "preset": "cheapest",
                    "weights": {
                        "cost": 0.55, "advance": 0.10, "speed": 0.05,
                        "tenor": 0.10, "fees": 0.15, "structure": 0.05
                    },
                    "min_advance_rate": None,
                    "max_days_to_cash": None,
                    "preferred_structure": None,
                    "urgent": rng.choice([True, False, False])
                },
                "data_source": "synthetic",
                "field_confidence": {}
            }
        suppliers.append(sup)

    # Generate Buyers (up to ~12)
    b_names = [
        "Mega", "Titan", "Pinnacle", "Vertex", "Quantum", "Nexus", "Stellar", "Horizon", "Orbit", "Nova", "Galaxy",
        "Atlas", "Omega", "Cosmos", "Jupiter", "Apollo", "Meridian", "Vanguard", "Eon"
    ]
    b_types = [
        "Retail", "Motors", "Electronics", "Foods", "Pharma", "FMCG", "Apparel",
        "Logistics", "Engineering", "Infotech", "Healthcare", "Energy"
    ]
    for i in range(2, 13):
        bid = f"BUY{i:03d}"
        
        while True:
            name_candidate = f"{rng.choice(b_names)} {rng.choice(b_types)} Ltd"
            if name_candidate not in used_names:
                used_names.add(name_candidate)
                break
                
        grade = rng.choice(["AAA", "AA", "AA", "A", "A", "A", "BBB", "BB"]) # skewed towards A/AA
        buy = {
            "buyer_id": bid,
            "name": name_candidate,
            "sector": rng.choice(sectors),
            "credit_grade": grade,
            "avg_payment_delay_days": rng.randint(0, 15),
            "payment_delay_trend": round(rng.uniform(-2.0, 2.0), 2),
            "disputes_last_year": rng.randint(0, 5),
            "annual_procurement_lakh": round(rng.uniform(1000.0, 100000.0), 2),
            "data_source": "synthetic",
            "field_confidence": {}
        }
        buyers.append(buy)

    # Generate Invoices (up to ~180)
    goods = [
        "hydraulic_seal_kits", "cotton_yarn_bales", "injection_moulded_housings",
        "packaged_snack_cartons", "pcb_assemblies", "steel_fasteners",
        "api_drug_intermediates", "corrugated_packaging", "wiring_harnesses",
        "industrial_lubricants", "cold_rolled_coils", "agro_seed_consignment",
    ]
    for i in range(3, 181):
        if i == 14: continue # INV014 already done
        iid = f"INV{i:03d}"
        # Jitter first, then clamp — clamping first lets the jitter push it back out of range.
        amount = round(rng.lognormvariate(1.5, 1.2) + rng.random(), 2)
        amount = round(min(max(amount, 0.5), 80.0), 2)

        sup_id = rng.choice(suppliers)["supplier_id"]
        buy_id = rng.choice(buyers)["buyer_id"]
        tenor = rng.choice([30, 45, 60, 90])

        # due_date is derived from the tenor so the two always agree (SCHEMA.md §3.5).
        issued = BASE_ISSUE_DATE - timedelta(days=rng.randint(0, 45))

        inv = {
            "invoice_id": iid,
            "supplier_id": sup_id,
            "buyer_id": buy_id,
            "amount_lakh": amount,
            "issue_date": issued.isoformat(),
            "due_date": (issued + timedelta(days=tenor)).isoformat(),
            "tenor_days": tenor,
            "irn": _irn(iid),
            "document_hash": _doc_hash(iid),
            "goods_description": rng.choice(goods),
            "delivery_confirmed": rng.choice([True, False, None]),
            "status": "open",
            "data_source": "synthetic",
            "field_confidence": {}
        }
        invoices.append(inv)
        
    # Generate Financing History (~50 entries)
    for i in range(1, 51):
        hist_iid = f"HINV{i:03d}"
        provider_id = rng.choice(providers)["provider_id"]
        buyer_id = rng.choice(buyers)["buyer_id"]
        
        outcome_roll = rng.random()
        if outcome_roll < 0.80:
            outcome = "settled"
            days_late = 0
        elif outcome_roll < 0.95:
            outcome = "late"
            days_late = rng.randint(1, 20)
        else:
            outcome = "defaulted"
            days_late = 90
            
        hist = {
            "invoice_id": hist_iid,
            "provider_id": provider_id,
            "buyer_id": buyer_id,
            "sector": rng.choice(sectors),
            "amount_lakh": round(rng.uniform(1.0, 20.0), 2),
            "outcome": outcome,
            "days_late": days_late
        }
        history.append(hist)

    market = {
        "meta": {
            "schema_version": "1.0",
            "generated_at": GENERATED_AT,
            "generator": "mockgen",
            "seed": seed,
            "currency_unit": "INR_lakh"
        },
        "suppliers": sorted(suppliers, key=lambda x: x["supplier_id"]),
        "buyers": sorted(buyers, key=lambda x: x["buyer_id"]),
        "invoices": sorted(invoices, key=lambda x: x["invoice_id"]),
        "providers": sorted(providers, key=lambda x: x["provider_id"]),
        "financing_history": history
    }
    
    return market

def validate_market(market, schema_path):
    """Validate against MarketInput specifically.

    schema.json is a definitions-only document with no top-level constraints, so
    validating against its root accepts literally any instance. The $ref is what
    makes this a real check rather than a no-op.
    """
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(
        instance=market,
        schema={**schema, "$ref": "#/definitions/MarketInput"},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=MOCK_SEED)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()

    market = generate_market(args.seed)

    # Check fixed constraints
    assert market["suppliers"][0]["supplier_id"] == "SUP001"
    assert market["buyers"][0]["buyer_id"] == "BUY001"

    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.json")
    validate_market(market, schema_path)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(market, f, indent=2, ensure_ascii=False)
    print(f"Market generated successfully at {args.out}")
