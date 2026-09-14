import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
from uuid import uuid4
import structlog

DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%b %d, %Y"
)


def normalize_date(date: str) -> str | None:
    clean_date = date.strip()

    for format in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(clean_date, format)
            return parsed_date.date().isoformat()
        except ValueError:
            continue
        
    return None


def _is_refund(cleaned_amount: str) -> bool:
    if cleaned_amount[0] == "(" and cleaned_amount[-1] == ")":
        return True
    return False


def normalize_amount(amount: str) -> int | None:
    cleaned_amount = amount.strip()

    if cleaned_amount == "" or cleaned_amount.upper() == "N/A":
        return None

    is_refund = _is_refund(cleaned_amount=cleaned_amount)
    if is_refund:
        cleaned_amount = cleaned_amount[1:-1]
    
    cleaned_amount = (
        cleaned_amount
        .replace("$", "")
        .replace(",", "")
        .replace(" ", "")
        )
    
    try:
        decimal_amount = Decimal(cleaned_amount)
    except InvalidOperation:
        return None

    cents = decimal_amount * 100

    amount_cents = int(cents)

    if is_refund:
        return -abs(amount_cents)
    
    return amount_cents


def normalize_currency(currency: str) -> str | None:
    cleaned_currency = currency.strip()
    if cleaned_currency == "" or cleaned_currency == "$":
        return "USD"
    
    return cleaned_currency.upper()


def normalize_merchant(merchant: str) -> str | None:
    return " ".join(merchant.split())

@dataclass(frozen=True, slots=True)
class CleanRow():
    row_id: str
    date: str
    amount_cents: int | None
    currency:str | None
    merchant: str | None


@dataclass(frozen=True, slots=True)
class ErrorRow:
    row_id: str
    reason: str

@dataclass
class Output:
    clean: list[CleanRow]
    errors: list[ErrorRow]


def normalize_rows(input_path: str, output_path: str) -> Output:
    clean: list[CleanRow] = []
    errors: list[ErrorRow] = []

    with open(input_path, newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file)

        for row in reader:
            row_id = row.get("row_id") or ""
            normalized_date = normalize_date(row.get("date") or "")
            normalized_amount = normalize_amount(row.get("amount") or "")

            if normalized_date is None:
                errors.append(
                    ErrorRow(
                        row_id=row_id,
                        reason="unparseable_date",
                    )
                )
                continue

            if normalized_amount is None:
                errors.append(
                    ErrorRow(
                        row_id=row_id,
                        reason="unparseable_amount",
                    )
                )
                continue

            clean.append(
                CleanRow(
                    row_id=row_id,
                    date=normalized_date,
                    merchant=normalize_merchant(
                        row.get("merchant") or ""
                    ),
                    amount_cents=normalized_amount,
                    currency=normalize_currency(
                        row.get("currency") or ""
                    ),
                )
            )

    output = Output(clean=clean, errors=errors)

    # This must be "w", not "a".
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(asdict(output), output_file, indent=2)
        output_file.write("\n")

    return output



def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("inegration.py, input csv, output json")
    log_path = Path(__file__).parent.parent / "run.log"

    with open(log_path, "w", encoding="utf-8") as log_file:
        structlog.configure(
            processors=[structlog.processors.JSONRenderer(),],
            logger_factory=structlog.PrintLoggerFactory(
                file = log_file
            ),
        )

        log = structlog.get_logger(
        correlation_id = str(uuid4())   
        )

        log.info("run_started")

        output = normalize_rows(
            sys.argv[1],
            sys.argv[2],
        )

        log.info(
            "run completed",
            clean_count = len(output.clean),
            error_count = len(output.errors),
        )

if __name__ == "__main__":
    main()
