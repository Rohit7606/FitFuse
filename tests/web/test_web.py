"""Tests for the frontend — Person C's test suite.

Test list from PERSON_C.md §7:
    test_mocks_valid          — every file in src/mocks/ validates against schema.json
    test_renders_offers       — offer cards render from mock data without errors
    test_weights_sum          — slider interaction always produces weights summing to 1.0
    test_reorder              — changing preferences reorders the cards
    test_reasons_untruncated  — reason_text and exclusion_reason render in full
    test_infeasible_shown     — offer with feasible:false renders greyed, with reason
    test_naive_toggle         — toggle switches ranking without a network call
    test_no_browser_storage   — grep bundle for localStorage / sessionStorage

Owner: Person C
"""

# Person C: implement these as the frontend is built.
# test_mocks_valid can be implemented early (Python + jsonschema).
