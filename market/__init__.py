"""FitFuse market simulator.

Owns: provider agents, clearing (deferred acceptance), settlement state machine,
and the learning loop.

Owner: Person B
Reviewer: Person A

Public surface:
    simulate.generate_offers() — provider agents bid on an invoice
    simulate.clear()           — deferred-acceptance matching
    simulate.settle()          — settlement and learning
"""
