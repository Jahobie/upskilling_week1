# TypeScript port — trade-offs

This is a TypeScript port of the Python integration in `submission/`. Same
input CSV, same normalization rules, same output JSON and log format
(verified against the Python version row-for-row). Two trade-offs stood out
while porting.

## 1. TypeScript did worse: no built-in decimal type

Python's standard library ships `decimal.Decimal`, an exact, arbitrary-precision
decimal type. Converting a dollar amount to cents is a one-liner with no
precision risk:

```python
decimal_amount = Decimal(cleaned_amount)
cents = decimal_amount * 100
amount_cents = int(cents)
```

JavaScript/TypeScript has no equivalent — every number is an IEEE-754 double,
so money math is float math unless you pull in a third-party decimal library.
Without `Decimal`, parsing `amount` in `src/integration.ts` needed two things
Python gets for free:

```ts
const value = Number(cleanedAmount);
if (!Number.isFinite(value)) {
  return null;
}

// Number(x)*100 can land a hair off an integer (binary float rounding),
// e.g. 44999.999999999996 instead of 45000 — Math.round absorbs that.
const amountCents = Math.round(value * 100);
```

`Math.round` isn't decoration — `parseFloat("450.00") * 100` can come out as
`44999.999999999996` due to binary floating-point representation, and a naive
truncation instead of a round would have quietly produced the wrong number of
cents. I also had to add an explicit empty-string guard (`cleanedAmount === ""`)
after stripping `()`/`$`/commas, because `Number("")` evaluates to `0` — a
valid, non-error value — where Python's `Decimal("")` raises `InvalidOperation`
and correctly flags the row as `unparseable_amount`. Every one of these is a
case Python's `Decimal` type + exception handling covers structurally, that
TypeScript's number type just doesn't protect you from — you have to know to
add the guard yourself.

## 2. TypeScript did better: interfaces serialize to JSON for free

Python's dataclasses aren't JSON-serializable on their own. `normalize_rows`
has to convert the whole `Output` object graph into plain dicts with `asdict()`
before `json.dump` can touch it:

```python
@dataclass
class Output:
    clean: list[CleanRow]
    errors: list[ErrorRow]

...

json.dump(asdict(output), output_file, indent=2)
```

Skip `asdict()` and `json.dump(output, ...)` raises
`TypeError: Object of type Output is not JSON serializable` — dataclasses need
an explicit conversion step every time you cross that boundary.

TypeScript `interface`s are compile-time-only — they're erased entirely by the
time the code runs, so an object built to satisfy `CleanRow`/`ErrorRow`/`Output`
is already a plain JavaScript object at runtime. There's no conversion step:

```ts
export interface Output {
  clean: CleanRow[];
  errors: ErrorRow[];
}

const output: Output = { clean, errors };
writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf-8");
```

`JSON.stringify(output, null, 2)` works immediately, while the `Output` type
still gives full compile-time checking on every `clean.push({...})` call in
`normalize_rows` — the type safety and the free serialization aren't in
tension the way they are in Python, where you get one or the other depending
on whether you remember to call `asdict()`.
