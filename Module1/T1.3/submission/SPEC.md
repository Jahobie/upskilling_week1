# Build the Ingestion Service (self-contained)

You're doing week-1 of a customer engagement (think John Deere or BBVA): stand up
the customer-side ingestion service. A synthetic feed is provided — no external data.

- `feed.jsonl` — records `{event_id, entity_id, seq, ts, payload}`.
- `replay.jsonl` — the same feed with a block of records duplicated (for the
  idempotency test).

## Exact rules (so output is well-defined)

Process records **in file order**. Maintain a canonical **store**: per `entity_id`,
keep the payload of the **highest `seq`** seen. Reject a record (with `event_id`
and a `reason`) for any of these **5 failure modes**:

| reason | condition |
|---|---|
| `duplicate` | `event_id` already processed (idempotency — process once) |
| `missing_field` | `entity_id` or `seq` absent |
| `bad_type` | `seq` is not an integer |
| `oversized_payload` | `payload` longer than 200 characters |
| `out_of_order` | `seq` ≤ the entity's already-seen max seq |

Replaying records (running on `replay.jsonl`) must produce the **same store** as
`feed.jsonl` — that's idempotency.

## Contract

```bash
bash submission/run.sh <input_jsonl> <output_json>
```

Output: `{ "store": { "<entity_id>": {"seq": N, "payload": "..."}, ... },
"rejects": [ {"event_id": "...", "reason": "..."}, ... ] }`.

Also ship: negative tests for all 5 failure modes, and a **1-page on-call runbook**.

## Grading

An automated grader checks the store matches the expected output, is stable under replay (idempotency),
and that your rejects match the expected list with all 5 reasons applied — all deterministic. The
runbook and customer-context fit are judged separately.
