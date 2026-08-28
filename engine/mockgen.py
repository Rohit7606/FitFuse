"""Synthetic market generator — everyone's day-one dependency.

Generates mock data conforming to SCHEMA.md, with DEMO_SCENARIO.md entities
placed explicitly first, then filler generated deterministically.

Usage:
    python -m engine.mockgen --seed 42 --out data/mock/market.json

Requirements:
    - ~60 suppliers, ~12 buyers, ~180 invoices, exactly 6 providers
    - DEMO_SCENARIO.md §2 entities placed first with specified terms
    - Deterministic: same seed → byte-identical file
    - Seed a local random.Random(seed), never the global module
    - Output validates against MarketInput before writing
    - Randomness permitted here and NOWHERE ELSE

Owner: Person A
"""

from __future__ import annotations


def generate_market(seed: int = 42) -> dict:
    """Generate a complete MarketInput dict.

    The DEMO_SCENARIO.md entities (SUP001, BUY001, INV001, INV002, INV014,
    PRV001-PRV006) are placed explicitly first with their specified terms.
    Filler entities are generated deterministically from the seed.

    Returns:
        MarketInput dict, validated against schema.json before return.
    """
    raise NotImplementedError("Person A: implement generate_market()")


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Generate FitFuse mock market data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--out", type=str, default="data/mock/market.json",
                        help="Output path (default: data/mock/market.json)")
    args = parser.parse_args()

    market = generate_market(seed=args.seed)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(market, f, indent=2, ensure_ascii=False)
    print(f"Generated market with seed {args.seed} → {args.out}")
