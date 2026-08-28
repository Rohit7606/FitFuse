"""Tests for the API — Person B's API test suite.

Test list from PERSON_B.md §7:
    test_market_shape       — /api/market validates against MarketResponse
    test_assess_shape       — /api/assess validates against Assessment
    test_offers_shape       — /api/offers validates, naive_ranking present
    test_clear_shape        — /api/clear validates against ClearingResponse
    test_settle_shape       — /api/settle validates against SettleResponse
    test_unknown_id_400     — bad ID returns 400, not 500, names the ID
    test_bad_weights_400    — weights summing to 0.87 return 400
    test_malformed_422      — garbage body returns 422
    test_stateless          — two identical requests → identical responses
    test_fit_beats_rate     — /api/offers on INV001 returns fit_beats_rate: true

Owner: Person B
"""

import pytest


class TestEndpointShapes:
    """All five endpoints return contract-valid shapes."""

    @pytest.mark.skip(reason="Person B: implement after endpoints")
    def test_market_shape(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after endpoints")
    def test_assess_shape(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after endpoints")
    def test_offers_shape(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after endpoints")
    def test_clear_shape(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after endpoints")
    def test_settle_shape(self):
        pass


class TestErrorHandling:
    """Error responses follow SCHEMA.md §5.7."""

    @pytest.mark.skip(reason="Person B: implement after error handlers")
    def test_unknown_id_400(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after error handlers")
    def test_bad_weights_400(self):
        pass

    @pytest.mark.skip(reason="Person B: implement after error handlers")
    def test_malformed_422(self):
        pass


class TestStateless:
    """No server-side state."""

    @pytest.mark.skip(reason="Person B: implement after endpoints")
    def test_stateless(self):
        pass


class TestProductThesis:
    """The one assertion that the product still makes its point."""

    @pytest.mark.skip(reason="Person B: implement after full pipeline")
    def test_fit_beats_rate(self):
        pass
