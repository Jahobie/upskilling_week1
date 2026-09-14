"""Tests for the ingestion service."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from src.service import ingest

REPO_ROOT = Path(__file__).parent.parent


def run_ingestion(feed: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Helper: run ingestion on feed, return (store, rejects)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.jsonl"

        with open(input_file, "w") as f:
            for record in feed:
                f.write(json.dumps(record) + "\n")

        result = ingest(str(input_file))
        return result["store"], result["rejects"]


class TestDuplicate:
    """Test: duplicate - event_id already processed (idempotency)."""

    def test_duplicate_rejection(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 1, "ts": "2025-01-01T00:00:00Z", "payload": "first"},
            {"event_id": "E1", "entity_id": "A", "seq": 2, "ts": "2025-01-01T00:01:00Z", "payload": "second"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": 1, "payload": "first"}}
        assert rejects == [{"event_id": "E1", "reason": "duplicate"}]

    def test_duplicate_check_is_entity_agnostic(self) -> None:
        """event_id is the dedup key regardless of which entity_id it's attached to."""
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 1, "payload": "first"},
            {"event_id": "E1", "entity_id": "B", "seq": 1, "payload": "second"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": 1, "payload": "first"}}
        assert rejects == [{"event_id": "E1", "reason": "duplicate"}]


class TestMissingField:
    """Test: missing_field - entity_id or seq absent."""

    def test_missing_entity_id(self) -> None:
        feed = [
            {"event_id": "E1", "seq": 1, "ts": "2025-01-01T00:00:00Z", "payload": "test"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {}
        assert rejects == [{"event_id": "E1", "reason": "missing_field"}]

    def test_missing_seq(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": "A", "ts": "2025-01-01T00:00:00Z", "payload": "test"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {}
        assert rejects == [{"event_id": "E1", "reason": "missing_field"}]

    def test_both_entity_id_and_seq_missing(self) -> None:
        feed = [{"event_id": "E1", "payload": "test"}]
        store, rejects = run_ingestion(feed)

        assert store == {}
        assert rejects == [{"event_id": "E1", "reason": "missing_field"}]


class TestBadType:
    """Test: bad_type - seq is not an integer."""

    @pytest.mark.parametrize("seq", ["one", 1.5, True, False, None, [1], {"a": 1}])
    def test_non_integer_seq_rejected(self, seq: object) -> None:
        feed = [{"event_id": "E1", "entity_id": "A", "seq": seq, "payload": "test"}]
        store, rejects = run_ingestion(feed)

        assert store == {}
        assert rejects == [{"event_id": "E1", "reason": "bad_type"}]

    def test_seq_zero_is_a_valid_first_value(self) -> None:
        feed = [{"event_id": "E1", "entity_id": "A", "seq": 0, "payload": "test"}]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": 0, "payload": "test"}}
        assert rejects == []

    def test_negative_seq_is_a_valid_first_value(self) -> None:
        feed = [{"event_id": "E1", "entity_id": "A", "seq": -5, "payload": "test"}]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": -5, "payload": "test"}}
        assert rejects == []

    def test_very_large_seq_is_accepted(self) -> None:
        big = 10**30
        feed = [{"event_id": "E1", "entity_id": "A", "seq": big, "payload": "test"}]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": big, "payload": "test"}}
        assert rejects == []


class TestOversizedPayload:
    """Test: oversized_payload - payload longer than 200 characters."""

    def test_payload_exceeds_200_chars(self) -> None:
        oversized = "X" * 201
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 1, "ts": "2025-01-01T00:00:00Z", "payload": oversized},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {}
        assert rejects == [{"event_id": "E1", "reason": "oversized_payload"}]

    def test_payload_exactly_200_chars(self) -> None:
        exact = "X" * 200
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 1, "ts": "2025-01-01T00:00:00Z", "payload": exact},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": 1, "payload": exact}}
        assert rejects == []

    @pytest.mark.parametrize("payload", [None, 123, [1, 2, 3], {"a": 1}, True])
    def test_non_string_payload_is_rejected_not_crashed(self, payload: object) -> None:
        """No dedicated reason exists for a wrong-type payload, so it's bucketed
        under oversized_payload rather than raising TypeError from len()."""
        feed = [{"event_id": "E1", "entity_id": "A", "seq": 1, "payload": payload}]
        store, rejects = run_ingestion(feed)

        assert store == {}
        assert rejects == [{"event_id": "E1", "reason": "oversized_payload"}]

    def test_missing_payload_key_defaults_to_empty_string(self) -> None:
        feed = [{"event_id": "E1", "entity_id": "A", "seq": 1}]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": 1, "payload": ""}}
        assert rejects == []


class TestOutOfOrder:
    """Test: out_of_order - seq <= the entity's already-seen max seq."""

    def test_seq_lower_than_max(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 3, "ts": "2025-01-01T00:00:00Z", "payload": "third"},
            {"event_id": "E2", "entity_id": "A", "seq": 1, "ts": "2025-01-01T00:01:00Z", "payload": "first"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": 3, "payload": "third"}}
        assert rejects == [{"event_id": "E2", "reason": "out_of_order"}]

    def test_seq_equal_to_max(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 2, "ts": "2025-01-01T00:00:00Z", "payload": "first"},
            {"event_id": "E2", "entity_id": "A", "seq": 2, "ts": "2025-01-01T00:01:00Z", "payload": "second"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": 2, "payload": "first"}}
        assert rejects == [{"event_id": "E2", "reason": "out_of_order"}]

    def test_rejected_record_does_not_advance_the_max_seq(self) -> None:
        """A record rejected for another reason (here: oversized) must not raise
        the entity's watermark, or a legitimately later record would be
        wrongly rejected as out_of_order."""
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 1, "payload": "ok"},
            {"event_id": "E2", "entity_id": "A", "seq": 9, "payload": "X" * 201},
            {"event_id": "E3", "entity_id": "A", "seq": 2, "payload": "ok2"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": 2, "payload": "ok2"}}
        assert [r["reason"] for r in rejects] == ["oversized_payload"]

    def test_rejects_preserve_file_order_across_interleaved_entities(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 5, "payload": "a5"},
            {"event_id": "E2", "entity_id": "B", "seq": 5, "payload": "b5"},
            {"event_id": "E3", "entity_id": "A", "seq": 1, "payload": "a1-late"},
            {"event_id": "E4", "entity_id": "B", "seq": 1, "payload": "b1-late"},
        ]
        store, rejects = run_ingestion(feed)

        assert [r["event_id"] for r in rejects] == ["E3", "E4"]


class TestPrecedence:
    """The spec lists 5 reasons as if independent, but a record can match more
    than one at once. Pin the check order so it can't silently drift."""

    def test_duplicate_beats_out_of_order(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 5, "payload": "first"},
            {"event_id": "E1", "entity_id": "A", "seq": 5, "payload": "first"},
        ]
        _, rejects = run_ingestion(feed)

        assert rejects == [{"event_id": "E1", "reason": "duplicate"}]

    def test_missing_field_beats_bad_type(self) -> None:
        # entity_id absent AND payload oversized would also fail other checks;
        # missing_field (checked first) must win.
        feed = [{"event_id": "E1", "seq": "not-an-int", "payload": "test"}]
        _, rejects = run_ingestion(feed)

        assert rejects == [{"event_id": "E1", "reason": "missing_field"}]

    def test_missing_field_beats_oversized_payload(self) -> None:
        feed = [{"event_id": "E1", "payload": "X" * 201}]
        _, rejects = run_ingestion(feed)

        assert rejects == [{"event_id": "E1", "reason": "missing_field"}]

    def test_bad_type_beats_oversized_payload(self) -> None:
        feed = [{"event_id": "E1", "entity_id": "A", "seq": "bad", "payload": "X" * 201}]
        _, rejects = run_ingestion(feed)

        assert rejects == [{"event_id": "E1", "reason": "bad_type"}]

    def test_oversized_payload_beats_out_of_order(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 5, "payload": "first"},
            {"event_id": "E2", "entity_id": "A", "seq": 1, "payload": "X" * 201},
        ]
        _, rejects = run_ingestion(feed)

        assert rejects[-1] == {"event_id": "E2", "reason": "oversized_payload"}


class TestEntityIdKeyCollision:
    """The store's output contract is JSON, whose object keys are always
    strings. If entity_id "1" (str) and entity_id 1 (int) were tracked as
    distinct Python dict keys, json.dump would silently emit two literal
    "1" keys in the output file and a standard JSON parser (including
    json.loads itself) would keep only the last one — an entity vanishing
    from disk with no reject and no error. entity_id must therefore be
    normalized to its string form for every store read and write."""

    def test_numeric_and_string_entity_id_are_the_same_entity(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": 1, "seq": 1, "payload": "from-int-key"},
            {"event_id": "E2", "entity_id": "1", "seq": 2, "payload": "from-str-key"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {"1": {"seq": 2, "payload": "from-str-key"}}
        assert rejects == []

    def test_out_of_order_check_sees_across_entity_id_types(self) -> None:
        """A later record with the string form of an entity_id already
        stored under its int form must still be checked against that max
        seq, not treated as a fresh, never-seen entity."""
        feed = [
            {"event_id": "E1", "entity_id": 1, "seq": 5, "payload": "int-first"},
            {"event_id": "E2", "entity_id": "1", "seq": 3, "payload": "str-stale"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {"1": {"seq": 5, "payload": "int-first"}}
        assert rejects == [{"event_id": "E2", "reason": "out_of_order"}]

    def test_store_round_trips_through_json_without_losing_entities(self, tmp_path: Path) -> None:
        """End-to-end: write output.json and re-parse it. Confirms the fix
        addresses the actual on-disk contract, not just the in-memory dict."""
        input_file = tmp_path / "input.jsonl"
        input_file.write_text(
            json.dumps({"event_id": "E1", "entity_id": 7, "seq": 1, "payload": "a"}) + "\n"
            + json.dumps({"event_id": "E2", "entity_id": "7", "seq": 1, "payload": "b"}) + "\n"
            + json.dumps({"event_id": "E3", "entity_id": "other", "seq": 1, "payload": "c"}) + "\n"
        )
        output_file = tmp_path / "output.json"

        result = ingest(str(input_file))
        with open(output_file, "w") as f:
            json.dump(result, f)

        reparsed = json.loads(output_file.read_text())
        assert set(reparsed["store"].keys()) == {"7", "other"}

    def test_null_entity_id_does_not_collide_with_literal_string_none(self) -> None:
        """Regression: a naive str(entity_id) coercion would turn None into
        the Python spelling "None", colliding with a genuine entity literally
        named "None" — reintroducing the exact silent-collision bug the
        entity_id key fix exists to prevent. The store key for null must
        match JSON's own convention ("null"), not Python's."""
        feed = [
            {"event_id": "E1", "entity_id": None, "seq": 1, "payload": "from-null"},
            {"event_id": "E2", "entity_id": "None", "seq": 1, "payload": "from-literal-string"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {
            "null": {"seq": 1, "payload": "from-null"},
            "None": {"seq": 1, "payload": "from-literal-string"},
        }
        assert rejects == []

    def test_bool_entity_id_does_not_collide_with_literal_string_true(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": True, "seq": 1, "payload": "from-bool"},
            {"event_id": "E2", "entity_id": "True", "seq": 1, "payload": "from-literal-string"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {
            "true": {"seq": 1, "payload": "from-bool"},
            "True": {"seq": 1, "payload": "from-literal-string"},
        }
        assert rejects == []


class TestEventIdEdgeCases:
    """A missing/null event_id must never act as a shared sentinel that makes
    unrelated records look like duplicates of each other."""

    def test_two_records_missing_event_id_are_both_accepted(self) -> None:
        feed = [
            {"entity_id": "A", "seq": 1, "payload": "first"},
            {"entity_id": "B", "seq": 1, "payload": "second-unrelated"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {
            "A": {"seq": 1, "payload": "first"},
            "B": {"seq": 1, "payload": "second-unrelated"},
        }
        assert rejects == []

    def test_two_records_with_null_event_id_are_both_accepted(self) -> None:
        feed = [
            {"event_id": None, "entity_id": "A", "seq": 1, "payload": "first"},
            {"event_id": None, "entity_id": "B", "seq": 1, "payload": "second"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {
            "A": {"seq": 1, "payload": "first"},
            "B": {"seq": 1, "payload": "second"},
        }
        assert rejects == []


class TestMalformedInputDoesNotCrash:
    """Regression tests for crashes found in adversarial review: a single bad
    line must never abort the run or lose the rest of the batch."""

    def test_unhashable_entity_id_is_skipped(self) -> None:
        feed = [{"event_id": "E1", "entity_id": [1, 2], "seq": 1, "payload": "x"}]
        store, rejects = run_ingestion(feed)

        assert store == {}
        assert rejects == []

    def test_unhashable_event_id_is_skipped(self) -> None:
        feed = [{"event_id": [1, 2], "entity_id": "A", "seq": 1, "payload": "x"}]
        store, rejects = run_ingestion(feed)

        assert store == {}
        assert rejects == []

    def test_non_object_json_lines_are_skipped(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.jsonl"
        input_file.write_text('[1, 2, 3]\n"just a string"\n42\nnull\n')

        result = ingest(str(input_file))

        assert result == {"store": {}, "rejects": []}

    def test_blank_and_whitespace_only_lines_are_skipped(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.jsonl"
        input_file.write_text(
            '\n   \n{"event_id": "E1", "entity_id": "A", "seq": 1, "payload": "x"}\n\n'
        )

        result = ingest(str(input_file))

        assert result["store"] == {"A": {"seq": 1, "payload": "x"}}
        assert result["rejects"] == []

    def test_invalid_json_line_is_skipped_and_later_lines_still_process(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.jsonl"
        input_file.write_text(
            '{not valid json\n{"event_id": "E1", "entity_id": "A", "seq": 1, "payload": "x"}\n'
        )

        result = ingest(str(input_file))

        assert result["store"] == {"A": {"seq": 1, "payload": "x"}}
        assert result["rejects"] == []

    def test_utf8_bom_prefixed_file_does_not_lose_the_first_record(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.jsonl"
        content = '{"event_id": "E1", "entity_id": "A", "seq": 1, "payload": "x"}\n'
        input_file.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

        result = ingest(str(input_file))

        assert result["store"] == {"A": {"seq": 1, "payload": "x"}}
        assert result["rejects"] == []

    def test_crlf_line_endings_are_handled(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.jsonl"
        input_file.write_bytes(
            b'{"event_id": "E1", "entity_id": "A", "seq": 1, "payload": "x"}\r\n'
        )

        result = ingest(str(input_file))

        assert result["store"] == {"A": {"seq": 1, "payload": "x"}}
        assert result["rejects"] == []


class TestHappyPath:
    """Test: valid records are stored correctly."""

    def test_single_entity_ascending_seq(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 1, "ts": "2025-01-01T00:00:00Z", "payload": "first"},
            {"event_id": "E2", "entity_id": "A", "seq": 2, "ts": "2025-01-01T00:01:00Z", "payload": "second"},
            {"event_id": "E3", "entity_id": "A", "seq": 3, "ts": "2025-01-01T00:02:00Z", "payload": "third"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {"A": {"seq": 3, "payload": "third"}}
        assert rejects == []

    def test_multiple_entities(self) -> None:
        feed = [
            {"event_id": "E1", "entity_id": "A", "seq": 1, "ts": "2025-01-01T00:00:00Z", "payload": "A1"},
            {"event_id": "E2", "entity_id": "B", "seq": 1, "ts": "2025-01-01T00:01:00Z", "payload": "B1"},
            {"event_id": "E3", "entity_id": "A", "seq": 2, "ts": "2025-01-01T00:02:00Z", "payload": "A2"},
            {"event_id": "E4", "entity_id": "B", "seq": 2, "ts": "2025-01-01T00:03:00Z", "payload": "B2"},
        ]
        store, rejects = run_ingestion(feed)

        assert store == {
            "A": {"seq": 2, "payload": "A2"},
            "B": {"seq": 2, "payload": "B2"},
        }
        assert rejects == []


class TestIdempotency:
    """Test: replaying feed produces same result."""

    def test_idempotency_with_duplicated_records(self) -> None:
        original = [
            {"event_id": "E1", "entity_id": "A", "seq": 1, "ts": "2025-01-01T00:00:00Z", "payload": "first"},
            {"event_id": "E2", "entity_id": "B", "seq": 1, "ts": "2025-01-01T00:01:00Z", "payload": "second"},
        ]

        replayed = original + original

        store1, rejects1 = run_ingestion(original)
        store2, rejects2 = run_ingestion(replayed)

        assert store1 == store2
        assert len(rejects2) == len(original)


class TestRealFeedFiles:
    """Pin the actual grading fixtures (feed.jsonl / replay.jsonl) so a
    regression in the store or reject logic is caught, not just toy cases."""

    EXPECTED_STORE = {
        "asset-1": {"seq": 2, "payload": "state-1-2"},
        "asset-2": {"seq": 3, "payload": "state-2-3"},
        "asset-3": {"seq": 2, "payload": "state-3-2"},
        "asset-4": {"seq": 2, "payload": "state-4-2"},
        "asset-5": {"seq": 1, "payload": "state-5-1"},
        "asset-6": {"seq": 1, "payload": "state-6-1"},
        "asset-7": {"seq": 3, "payload": "state-7-3"},
        "asset-8": {"seq": 1, "payload": "state-8-1"},
    }

    EXPECTED_FEED_REJECTS = [
        {"event_id": "E1003", "reason": "out_of_order"},
        {"event_id": "E1012", "reason": "out_of_order"},
        {"event_id": "E1016", "reason": "missing_field"},
        {"event_id": "E1003", "reason": "duplicate"},
        {"event_id": "E1017", "reason": "bad_type"},
        {"event_id": "E1000", "reason": "out_of_order"},
        {"event_id": "E1011", "reason": "out_of_order"},
        {"event_id": "E1018", "reason": "oversized_payload"},
        {"event_id": "E1002", "reason": "out_of_order"},
        {"event_id": "E1015", "reason": "out_of_order"},
    ]

    @staticmethod
    def _sorted(rejects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rejects, key=lambda r: (r["event_id"], r["reason"]))

    def test_feed_jsonl_produces_expected_store_and_rejects(self) -> None:
        result = ingest(str(REPO_ROOT / "feed.jsonl"))

        assert result["store"] == self.EXPECTED_STORE
        assert self._sorted(result["rejects"]) == self._sorted(self.EXPECTED_FEED_REJECTS)

    def test_replay_jsonl_is_idempotent_with_feed_jsonl(self) -> None:
        feed_result = ingest(str(REPO_ROOT / "feed.jsonl"))
        replay_result = ingest(str(REPO_ROOT / "replay.jsonl"))

        assert replay_result["store"] == feed_result["store"] == self.EXPECTED_STORE

        # replay.jsonl repeats the feed's first 6 records verbatim; each repeat's
        # event_id was already processed, so each becomes an extra "duplicate".
        repeated_event_ids = ["E1004", "E1013", "E1003", "E1012", "E1005", "E1016"]
        extra_duplicates = [{"event_id": eid, "reason": "duplicate"} for eid in repeated_event_ids]

        assert len(replay_result["rejects"]) == len(feed_result["rejects"]) + len(extra_duplicates)
        assert self._sorted(replay_result["rejects"]) == self._sorted(
            self.EXPECTED_FEED_REJECTS + extra_duplicates
        )


class TestRunShContract:
    """Exercise the actual deliverable contract: `bash run.sh <input> <output>`.
    A broken run.sh must fail these even if ingest() itself is correct."""

    def test_run_sh_on_feed_jsonl_writes_expected_output(self, tmp_path: Path) -> None:
        output_file = tmp_path / "output.json"

        result = subprocess.run(
            ["bash", str(REPO_ROOT / "run.sh"), str(REPO_ROOT / "feed.jsonl"), str(output_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)

        assert set(data.keys()) == {"store", "rejects"}
        assert data["store"] == TestRealFeedFiles.EXPECTED_STORE

    def test_run_sh_fails_cleanly_with_wrong_arg_count(self) -> None:
        result = subprocess.run(
            ["bash", str(REPO_ROOT / "run.sh")],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
