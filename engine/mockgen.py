import json
import random
import os
import argparse
from datetime import datetime
import jsonschema

from engine.config import MOCK_SEED

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
            "min_advance_rate": None,
            "max_days_to_cash": None,
            "preferred_structure": None,
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
        "issue_date": "2023-10-01",
        "due_date": "2023-11-30",
        "tenor_days": 60,
        "irn": "valid_irn_001",
        "document_hash": "hash_001",
        "goods_description": "Auto components",
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
        "issue_date": "2023-10-01",
        "due_date": "2023-11-30",
        "tenor_days": 60,
        "irn": "valid_irn_002",
        "document_hash": "hash_001",  # Same as INV001
        "goods_description": "Auto components",
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
        "issue_date": "2023-11-01",
        "due_date": "2023-12-01",
        "tenor_days": 30,
        "irn": "valid_irn_014",
        "document_hash": "hash_014",
        "goods_description": "Auto components",
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
        "sector_limits": {},
        "buyer_limit": 100.00,
        "current_exposure": {},
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
        "sector_limits": {},
        "buyer_limit": 50.00,
        "current_exposure": {},
        "speed_capability_days": 2,
        "preferred_structures": ["bullet"],
        "data_source": "synthetic"
    }

    # Kestrel: 500 total, 20% limit = 100, 94 exposure => 6 available.
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
        "sector_limits": {"auto_components": 0.20},
        "buyer_limit": 50.00,
        "current_exposure": {"auto_components": 94.00},
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
        "sector_limits": {},
        "buyer_limit": 30.00,
        "current_exposure": {},
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
        "sector_limits": {},
        "buyer_limit": 10.00,
        "current_exposure": {},
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
        "sector_limits": {},
        "buyer_limit": 200.00,
        "current_exposure": {},
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
    names_prefix = ["Apex", "Zenith", "Prime", "Global", "Indian", "Sunrise", "National", "Star", "Royal", "Balaji"]
    names_suffix = ["Industries", "Enterprises", "Traders", "Solutions", "Manufacturing", "Synthetics", "Corp"]

    for i in range(2, 61): # SUP002 to SUP060
        sid = f"SUP{i:03d}"
        if i == 2:
            # SUP002 already referenced in INV002
            sup = {
                "supplier_id": sid,
                "name": "Ramesh Enterprises",
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
                "name": f"{rng.choice(names_prefix)} {rng.choice(names_suffix)} Pvt Ltd",
                "sector": rng.choice(sectors),
                "city": rng.choice(cities),
                "years_operating": rng.randint(1, 25),
                "annual_revenue_lakh": round(rng.lognormvariate(4.5, 1.2), 2),
                "gstin": f"27{rng.choice(['AAD', 'BBE', 'CCF'])}{rng.randint(1000, 9999)}A1Z{rng.randint(1,9)}",
                "prior_financings": rng.randint(0, 50),
                "prior_defaults": rng.choice([0, 0, 0, 0, 0, 1, 2]),
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
    b_names = ["Mega", "Titan", "Pinnacle", "Vertex", "Quantum", "Nexus", "Stellar", "Horizon", "Orbit", "Nova", "Galaxy"]
    b_types = ["Retail", "Motors", "Electronics", "Foods", "Pharma"]
    grades = ["AAA", "AA", "A", "BBB", "BB"]
    for i in range(2, 13):
        bid = f"BUY{i:03d}"
        grade = rng.choice(["AAA", "AA", "AA", "A", "A", "A", "BBB", "BB"]) # skewed towards A/AA
        buy = {
            "buyer_id": bid,
            "name": f"{rng.choice(b_names)} {rng.choice(b_types)} Ltd",
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
    for i in range(3, 181):
        if i == 14: continue # INV014 already done
        iid = f"INV{i:03d}"
        amount = round(rng.lognormvariate(1.5, 1.2), 2)
        if amount < 0.5: amount = 0.5
        if amount > 80.0: amount = 80.0
        amount = round(amount + rng.random(), 2) # non-round
        
        sup_id = rng.choice(suppliers)["supplier_id"]
        buy_id = rng.choice(buyers)["buyer_id"]
        tenor = rng.choice([30, 45, 60, 90])
        
        inv = {
            "invoice_id": iid,
            "supplier_id": sup_id,
            "buyer_id": buy_id,
            "amount_lakh": amount,
            "issue_date": "2023-10-15",
            "due_date": "2023-11-15",
            "tenor_days": tenor,
            "irn": f"valid_irn_{i:03d}",
            "document_hash": f"hash_{i:03d}",
            "goods_description": "Various goods",
            "delivery_confirmed": rng.choice([True, False, None]),
            "status": "open",
            "data_source": "synthetic",
            "field_confidence": {}
        }
        invoices.append(inv)
        
    # Set another provider close to a limit (PRV001)
    prv001["sector_limits"] = {"textiles": 0.15}
    prv001["current_exposure"] = {"textiles": 1450.00} # 15% of 10000 = 1500 limit. 1450 exposure => 50 max fundable

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
            "generated_at": datetime.utcnow().isoformat() + "Z",
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
    with open(schema_path, "r") as f:
        schema = json.load(f)
    jsonschema.validate(instance=market, schema=schema)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=MOCK_SEED)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()
    
    market = generate_market(args.seed)
    
    # Check fixed constraints
    assert market["suppliers"][0]["supplier_id"] == "SUP001"
    assert market["buyers"][0]["buyer_id"] == "BUY001"
    
    # We must reset meta timestamps to be deterministic
    market["meta"]["generated_at"] = "2024-01-01T00:00:00Z"
    
    # Validate against schema
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.json")
    validate_market(market, schema_path)
    
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(market, f, indent=2)
    print(f"Market generated successfully at {args.out}")
