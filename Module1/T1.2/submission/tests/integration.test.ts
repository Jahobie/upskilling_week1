import { describe, it, expect, test } from "vitest";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  placeholder,
  normalize_date,
  normalize_amount,
  normalize_currency,
  normalize_merchant,
  normalize_rows,
} from "../src/integration.js";

describe("environment smoke test", () => {
  it("wires up vitest, tsx, and module resolution", () => {
    expect(placeholder()).toBe(true);
  });
});


test("normalize_date function test", () =>{
    expect(normalize_date("2025-03-28")).toBe("2025-03-28") 
    expect(normalize_date("Dec 18, 1969")).toBe("1969-12-18") 
    expect(normalize_date(" ")).toBe(null)
    expect(normalize_date("not-a-date")).toBe(null)
    expect(normalize_date("2025/03/14")).toBe(null)
    expect(normalize_date("02/30/2025")).toBe(null)
})


describe("normalize_amount", () => {
  it("valid amounts", () => {
    expect(normalize_amount("12.50")).toBe(1250);
    expect(normalize_amount("(10.14)")).toBe(-1014);
    expect(normalize_amount("$451.50,")).toBe(45150);
  });

  it("invalid amounts", () => {
    expect(normalize_amount("")).toBe(null);
    expect(normalize_amount("n/a")).toBe(null);
    expect(normalize_amount("N/A")).toBe(null);
  });
});


test("normalize_currency function test", () => {
  expect(normalize_currency("")).toBe("USD");
  expect(normalize_currency("usd")).toBe("USD");
  expect(normalize_currency("USD")).toBe("USD");
});


test("normalize_merchant function test", () => {
  expect(normalize_merchant(" Acme  Corp")).toBe("Acme Corp");
  expect(normalize_merchant("Umbrella  Corp")).toBe("Umbrella Corp");
});


describe("normalize_rows", () => {
  it("splits clean rows from error rows and writes matching output.json", () => {
    const dir = mkdtempSync(join(tmpdir(), "integration-test-"));
    const inputPath = join(dir, "input.csv");
    const outputPath = join(dir, "output.json");

    try {
      writeFileSync(
        inputPath,
        "row_id,date,merchant,amount,currency\n" +
          "R001,2025-03-14,  Acme   Co  ,12.34,usd\n" +
          "R002,bad-date,Store,10.00,USD\n" +
          "R003,03/15/2025,Store,N/A,$\n",
        "utf-8",
      );

      const result = normalize_rows(inputPath, outputPath);

      expect(result.clean.length).toBe(1);
      expect(result.errors.length).toBe(2);

      const data = JSON.parse(readFileSync(outputPath, "utf-8"));

      expect(data.clean).toEqual([
        {
          row_id: "R001",
          date: "2025-03-14",
          merchant: "Acme Co",
          amount_cents: 1234,
          currency: "USD",
        },
      ]);

      expect(data.errors).toEqual([
        {
          row_id: "R002",
          reason: "unparseable_date",
        },
        {
          row_id: "R003",
          reason: "unparseable_amount",
        },
      ]);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
