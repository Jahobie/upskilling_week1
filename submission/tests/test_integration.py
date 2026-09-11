import pytest
from typing import cast
from pathlib import Path
import json

from src.integration import (
    normalize_amount,
    normalize_currency,
    normalize_date,
    normalize_merchant,
    normalize_rows,
)


def test_normalize_date_valid_formats() -> None:
    assert normalize_date("2025-03-28") == "2025-03-28"
    assert normalize_date("Dec 18, 1969") == "1969-12-18"
    assert normalize_date("06/13/1959") == "1959-06-13"

def test_normalize_date_invalid() -> None:
    assert normalize_date(" ") is None
    assert normalize_date("not-a-date") is None
    assert normalize_date("2025/03/14") is None
    assert normalize_date("02/30/2025") is None

def test_normalize_amount_valid() -> None:
    assert normalize_amount("12.50") == 1250
    assert normalize_amount("(10.14)") == -1014
    assert normalize_amount("$451.50,") == 45150

def test_normalize_amount_invalid() -> None:
    assert normalize_amount("") is None
    assert normalize_amount("n/a") is None
    assert normalize_amount("N/A") is None

def test_normalize_currency() -> None:
    assert normalize_currency("") == "USD"
    assert normalize_currency("usd") == "USD"
    assert normalize_currency("USD") == "USD"

def test_normalize_merchant() -> None:
    assert normalize_merchant(" Acme  Corp") == "Acme Corp"
    assert normalize_merchant("Umbrella  Corp") == "Umbrella Corp"


def test_normalize_rows(tmp_path: Path) -> None:
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.json"

    input_path.write_text(
        "row_id,date,merchant,amount,currency\n"
        "R001,2025-03-14,  Acme   Co  ,12.34,usd\n"
        "R002,bad-date,Store,10.00,USD\n"
        "R003,03/15/2025,Store,N/A,$\n",
        encoding="utf-8",
    )

    result = normalize_rows(
        str(input_path),
        str(output_path),
    )

    assert len(result.clean) == 1
    assert len(result.errors) == 2

    data = cast(
        dict[str, object],
        json.loads(output_path.read_text(encoding="utf-8")),
    )

    assert data["clean"] == [
        {
            "row_id": "R001",
            "date": "2025-03-14",
            "merchant": "Acme Co",
            "amount_cents": 1234,
            "currency": "USD",
        }
    ]

    assert data["errors"] == [
        {
            "row_id": "R002",
            "reason": "unparseable_date",
        },
        {
            "row_id": "R003",
            "reason": "unparseable_amount",
        },
    ]
