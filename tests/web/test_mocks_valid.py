import json
import os

import jsonschema

WEB_MOCKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "web", "src", "mocks")
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "schema.json")

def load_schema():
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_mock(filename):
    filepath = os.path.join(WEB_MOCKS_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def test_market_mock_validates():
    schema = load_schema()
    mock = load_mock("market.json")
    jsonschema.validate(instance=mock, schema={**schema, "$ref": "#/definitions/MarketInput"})

def test_assess_mock_validates():
    schema = load_schema()
    mock = load_mock("assess.json")
    jsonschema.validate(instance=mock, schema={**schema, "$ref": "#/definitions/Assessment"})

def test_offers_mock_validates():
    schema = load_schema()
    mock = load_mock("offers.json")

    # schema.json defines ScoredOffer and Assessment
    jsonschema.validate(instance=mock.get("assessment"), schema={**schema, "$ref": "#/definitions/Assessment"})
    for offer in mock.get("offers", []):
        jsonschema.validate(instance=offer, schema={**schema, "$ref": "#/definitions/ScoredOffer"})

def test_clear_mock_validates():
    schema = load_schema()
    mock = load_mock("clear.json")
    for match in mock.get("matches", []):
        jsonschema.validate(instance=match, schema={**schema, "$ref": "#/definitions/Match"})

def test_settle_mock_validates():
    schema = load_schema()
    mock = load_mock("settle.json")

    jsonschema.validate(instance=mock.get("before", {}).get("match"), schema={**schema, "$ref": "#/definitions/Match"})
    jsonschema.validate(instance=mock.get("after", {}).get("match"), schema={**schema, "$ref": "#/definitions/Match"})
    jsonschema.validate(instance=mock.get("delta", {}), schema={**schema, "$ref": "#/definitions/LearningDelta"})
