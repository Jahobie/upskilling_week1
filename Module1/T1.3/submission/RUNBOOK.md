

# Contract: 
`bash run.sh <input.jsonl> <output.json>`
Runs `src/service.py` with the standard library only — no venv, no network,
no third-party install step.

# Output shape: 
`{"store": {entity_id: {seq, payload}}, "rejects": [{event_id, reason}]}`

## How the logic works (src/service.py)
- Reads the input file line by line (`utf-8-sig`, so a BOM-prefixed export
  won't corrupt the first line).
- Each line is validated in this exact order — first match wins:
  1. `duplicate` — event_id already processed
  2. `missing_field` — `entity_id` or `seq` key absent
  3. `bad_type` — `seq` is not an int (bools are explicitly excluded)
  4. `oversized_payload` — payload is not a string, or is longer than 200 chars
  5. `out_of_order` — seq <= the entity's current max seq
- A record that fails none of these is written into `store[entity_id]`,
  replacing whatever was there. A rejected record never advances that
  entity's max seq.
- Lines that aren't valid JSON, aren't a JSON *object*, or have an
  unhashable `entity_id`/`event_id` (e.g. a list) are **skipped entirely** —
  not counted as a reject, since none of the 5 spec reasons cover
  "not a record at all." Each skip prints one line to **stderr**:
  `line N: invalid JSON, skipping` / `line N: not a JSON object, skipping` /
  `line N: entity_id/event_id not hashable, skipping`. This output only
  exists for the duration of the run — capture stderr if you need to keep it.

## If a run fails or looks wrong

### 1. Check the exit code and stderr first
```bash
bash run.sh feed.jsonl output.json
echo "exit code: $?"
```
- **Non-zero exit, no output.json written**: either the wrong number of
  arguments was passed (prints `Usage: ...` to stderr), or an *uncaught*
  error occurred — the only two known uncaught cases are the input file not
  existing (`FileNotFoundError`) and the output path not being writable
  (`OSError`). Neither is currently caught, so you'll see a raw Python
  traceback. Check the paths passed to `run.sh`.
- **Exit 0 but stderr has `line N: ... skipping` messages**: some input
  lines were silently dropped. This is by design for structurally broken
  lines, but if the *count* of skipped lines is high, the upstream feed
  generator is likely producing malformed output — that's a data problem,
  not a bug here.

### 2. Inspect the output
```bash
python3 -m json.tool output.json | head -30      # pretty-print (output is one line)
python3 -c "import json; d=json.load(open('output.json')); print(len(d['store']), 'entities,', len(d['rejects']), 'rejects')"
```

### 3. Break down rejects by reason
```bash
python3 -c "
import json, collections
d = json.load(open('output.json'))
print(collections.Counter(r['reason'] for r in d['rejects']))
"
```
| Dominant reason | What it usually means |
|---|---|
| `out_of_order` | Feed genuinely contains stale/replayed updates for an entity, or the upstream source is sending records out of sequence. Expected in small numbers (see feed.jsonl); a spike means check the upstream ordering. |
| `duplicate` | The same `event_id` appeared more than once — normal for replay/idempotency testing (see replay.jsonl), abnormal if it's the first run of a fresh feed. |
| `missing_field` | Upstream is dropping `entity_id` or `seq` on some records — check the producer, not this service. |
| `bad_type` | `seq` is arriving as a string/float/bool instead of an int — likely a serialization bug upstream. |
| `oversized_payload` | Payload is either non-string or over 200 chars — check whether the 200-char limit is still the right contract, or whether upstream payloads have grown. |

### 4. Confirm idempotency if you suspect a logic regression
```bash
bash run.sh feed.jsonl out1.json
bash run.sh feed.jsonl out2.json
diff out1.json out2.json && echo "stable"
```
Running the same file twice must always produce an identical `store`. If it
differs, this is a correctness bug in `service.py`, not a data problem —
stop and escalate.

### 5. Run the test suite
```bash
python3 -m pytest tests/ -v        # if uv isn't available on this box
uv run pytest tests/ -v            # if it is
uv run mypy --strict src/
```
`tests/test_ingestion.py` covers all 5 reject reasons, their precedence
when more than one applies, the "rejected record doesn't advance max seq"
invariant, the malformed-input cases above, and runs the actual
`run.sh` contract against the real `feed.jsonl`/`replay.jsonl` fixtures
with a pinned expected store — if these fail, something in `service.py`
or `run.sh` itself regressed.

## Known, intentional behavior (not bugs)
- `seq: 0` and negative `seq` values are valid — the spec only rejects
  non-integers, not particular integer values.
- A record whose `payload` is present but not a string (e.g. `null`, a
  number, a list) is rejected as `oversized_payload`, not a separate
  reason — the spec defines exactly 5 reasons and this doesn't fit any of
  the other 4.
- Two records that are both missing `event_id` (or both have
  `event_id: null`) are **not** treated as duplicates of each other; only
  a real, non-empty string `event_id` is used for dedup.

## What is *not* handled
- The output write is not atomic — a crash mid-`json.dump` would leave a
  truncated `output.json`. Not currently a problem at this data size, but
  worth knowing if input files get large enough for this to matter.
- Missing input file / unwritable output path produce a raw traceback
  instead of a clean error message.

## Escalation
Placeholder for this exercise — in a real deployment, list the on-call
channel for the pipeline that invokes this CLI and the upstream data
producer's contact here.
