"""FitFuse valuation engine.

Owns: invoice verification, risk scoring, eligibility filtering,
whole-offer value scoring, and reason generation.

Owner: Person A
Reviewer: Person B

Public surface:
    assess.assess()       — verify, score risk, determine eligibility
    assess.score_offers() — score and rank competing offers
"""
