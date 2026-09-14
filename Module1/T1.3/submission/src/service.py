#!/usr/bin/env python3
"""Event ingestion service with idempotency and validation."""

import sys
import json
from typing import Any


class StoreManager:
    def __init__(self) -> None:
        self.canonical_store: dict[str, dict[str, Any]] = {}
        self.reject_store: list[dict[str, Any]] = []
        self.seen_event_ids: set[str] = set()

    def process_record(self, raw: dict[str, Any]) -> None:
        event_id = raw.get("event_id", "")
        trackable = self._is_trackable_id(event_id)

        reason = self._validate(raw, event_id, trackable)

        if reason:
            self.reject_store.append({"event_id": event_id, "reason": reason})
        else:
            entity_id = raw["entity_id"]
            seq = raw["seq"]
            payload = raw.get("payload", "")
            self.canonical_store[self._store_key(entity_id)] = {"seq": seq, "payload": payload}

        if trackable:
            self.seen_event_ids.add(event_id)

    @staticmethod
    def _store_key(entity_id: Any) -> str:
        # The output contract's store is keyed by JSON object keys, which are
        # always strings. Coerce every entity_id to its string form *before*
        # using it as a dict key so e.g. entity_id 1 (int) and "1" (str) are
        # treated as the same entity everywhere. Without this, they'd be
        # tracked as two distinct Python dict keys in memory but collapse to
        # one identical "1" key on json.dump — silently dropping whichever
        # entity was written first, with no error or reject to show for it.
        #
        # None/bool get their own branches rather than falling through to
        # plain str() because Python's str(None) == "None" and str(True) ==
        # "True", while json.dump's own key coercion uses "null"/"true" —
        # lowercase, matching the JSON literals. Using bare str() here would
        # silently reintroduce the exact same collision this method exists to
        # prevent: entity_id None and entity_id "None" (a literal string)
        # would land on the same "None" key under str(), whereas mirroring
        # json's own coercion keeps them apart ("null" vs "None").
        if entity_id is None:
            return "null"
        if isinstance(entity_id, bool):
            return "true" if entity_id else "false"
        return str(entity_id)

    @staticmethod
    def _is_trackable_id(value: Any) -> bool:
        # Only a real, non-empty string event_id can be tracked for dedup.
        # Missing/null event_ids must never share a sentinel, or unrelated
        # records collide as false "duplicate"s.
        return isinstance(value, str) and value != ""

    def _validate(
        self, record: dict[str, Any], event_id: Any, trackable: bool
    ) -> str | None:
        if trackable and event_id in self.seen_event_ids:
            return "duplicate"

        if self._missing_field(record):
            return "missing_field"

        if self._bad_type(record):
            return "bad_type"

        if self._oversized_payload(record):
            return "oversized_payload"

        if self._out_of_order(record):
            return "out_of_order"

        return None

    def _missing_field(self, record: dict[str, Any]) -> bool:
        return "entity_id" not in record or "seq" not in record

    def _bad_type(self, record: dict[str, Any]) -> bool:
        seq = record.get("seq")
        return not isinstance(seq, int) or isinstance(seq, bool)

    def _oversized_payload(self, record: dict[str, Any]) -> bool:
        payload = record.get("payload", "")
        if not isinstance(payload, str):
            return True
        return len(payload) > 200

    def _out_of_order(self, record: dict[str, Any]) -> bool:
        key = self._store_key(record.get("entity_id"))
        seq = record.get("seq")

        if key not in self.canonical_store:
            return False

        stored_seq = self.canonical_store[key]["seq"]
        return bool(seq <= stored_seq)

    def get_result(self) -> dict[str, Any]:
        return {
            "store": self.canonical_store,
            "rejects": self.reject_store,
        }


def _is_hashable(value: Any) -> bool:
    try:
        hash(value)
        return True
    except TypeError:
        return False


def ingest(input_file: str) -> dict[str, Any]:
    """Process JSONL feed and return store with rejects."""
    manager = StoreManager()

    with open(input_file, "r", encoding="utf-8-sig") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(f"line {line_number}: invalid JSON, skipping", file=sys.stderr)
                continue

            if not isinstance(record, dict):
                print(f"line {line_number}: not a JSON object, skipping", file=sys.stderr)
                continue

            entity_id = record.get("entity_id")
            event_id = record.get("event_id")
            if not _is_hashable(entity_id) or not _is_hashable(event_id):
                print(
                    f"line {line_number}: entity_id/event_id not hashable, skipping",
                    file=sys.stderr,
                )
                continue

            manager.process_record(record)

    return manager.get_result()


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: service.py <input_jsonl> <output_json>", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    result = ingest(input_file)

    with open(output_file, "w") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()
