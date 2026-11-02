import json
from pathlib import Path

import pytest

from app.sources.ember import EmberError, rows_from_monthly_payload

FIXTURES = Path(__file__).parent / "fixtures"


def test_ember_filters_entity_code():
    rows = rows_from_monthly_payload(json.loads((FIXTURES / "ember_monthly.json").read_text()), "USA")
    assert [r["value"] for r in rows] == [330.5, 310.1]
    assert rows[0]["ts_utc"].month == 1 and rows[0]["ts_utc"].day == 1


def test_ember_rejects_unexpected_shape():
    with pytest.raises(EmberError):
        rows_from_monthly_payload({"detail": "unauthorized"}, "USA")
