import { parse } from "csv-parse/sync";
import { randomUUID } from "node:crypto";
import { closeSync, openSync, readFileSync, writeFileSync, writeSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const DATE_FORMATS = ["iso", "us-slash", "month-name"] as const;

const MONTH_ABBREVIATIONS: Record<string, number> = {
  jan: 1,
  feb: 2,
  mar: 3,
  apr: 4,
  may: 5,
  jun: 6,
  jul: 7,
  aug: 8,
  sep: 9,
  oct: 10,
  nov: 11,
  dec: 12,
};

interface DateParts {
  year: number;
  month: number;
  day: number;
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function isValidDate(year: number, month: number, day: number): boolean {
  if (month < 1 || month > 12) return false;
  if (day < 1) return false;
  return day <= daysInMonth(year, month);
}

function toIso(parts: DateParts): string {
  const y = String(parts.year).padStart(4, "0");
  const m = String(parts.month).padStart(2, "0");
  const d = String(parts.day).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function parseIsoDate(value: string): DateParts | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!isValidDate(year, month, day)) return null;
  return { year, month, day };
}

function parseUsSlashDate(value: string): DateParts | null {
  const match = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value);
  if (!match) return null;
  const month = Number(match[1]);
  const day = Number(match[2]);
  const year = Number(match[3]);
  if (!isValidDate(year, month, day)) return null;
  return { year, month, day };
}

function parseMonthNameDate(value: string): DateParts | null {
  const match = /^([A-Za-z]{3}) (\d{1,2}), (\d{4})$/.exec(value);
  if (!match) return null;
  const month = MONTH_ABBREVIATIONS[match[1]!.toLowerCase()];
  if (month === undefined) return null;
  const day = Number(match[2]);
  const year = Number(match[3]);
  if (!isValidDate(year, month, day)) return null;
  return { year, month, day };
}

function parseByFormat(format: (typeof DATE_FORMATS)[number], value: string): DateParts | null {
  switch (format) {
    case "iso":
      return parseIsoDate(value);
    case "us-slash":
      return parseUsSlashDate(value);
    case "month-name":
      return parseMonthNameDate(value);
  }
}

export function normalize_date(date: string): string | null {
  const cleanDate = date.trim();

  for (const format of DATE_FORMATS) {
    const parts = parseByFormat(format, cleanDate);
    if (parts !== null) {
      return toIso(parts);
    }
  }

  return null;
}

function _is_refund(cleanedAmount: string): boolean {
  return cleanedAmount.startsWith("(") && cleanedAmount.endsWith(")");
}

export function normalize_amount(amount: string): number | null {
  let cleanedAmount = amount.trim();

  if (cleanedAmount === "" || cleanedAmount.toUpperCase() === "N/A") {
    return null;
  }

  const isRefund = _is_refund(cleanedAmount);
  if (isRefund) {
    cleanedAmount = cleanedAmount.slice(1, -1);
  }

  cleanedAmount = cleanedAmount.replaceAll("$", "").replaceAll(",", "").replaceAll(" ", "");

  if (cleanedAmount === "") {
    return null;
  }

  const value = Number(cleanedAmount);
  if (!Number.isFinite(value)) {
    return null;
  }

  // Number(x)*100 can land a hair off an integer (binary float rounding),
  // e.g. 44999.999999999996 instead of 45000 — Math.round absorbs that.
  const amountCents = Math.round(value * 100);

  if (isRefund) {
    return -Math.abs(amountCents);
  }

  return amountCents;
}

export function normalize_currency(currency: string): string | null {
  const cleanedCurrency = currency.trim();
  if (cleanedCurrency === "" || cleanedCurrency === "$") {
    return "USD";
  }

  return cleanedCurrency.toUpperCase();
}

export function normalize_merchant(merchant: string): string | null {
  return merchant.trim().split(/\s+/).join(" ");
}

export interface CleanRow {
  row_id: string;
  date: string;
  amount_cents: number | null;
  currency: string | null;
  merchant: string | null;
}

export interface ErrorRow {
  row_id: string;
  reason: string;
}

export interface Output {
  clean: CleanRow[];
  errors: ErrorRow[];
}

export function normalize_rows(inputPath: string, outputPath: string): Output {
  const clean: CleanRow[] = [];
  const errors: ErrorRow[] = [];

  const inputContent = readFileSync(inputPath, "utf-8");
  const rows: Record<string, string>[] = parse(inputContent, {
    columns: true,
  });

  for (const row of rows) {
    const rowId = row.row_id ?? "";
    const normalizedDate = normalize_date(row.date ?? "");
    const normalizedAmount = normalize_amount(row.amount ?? "");

    if (normalizedDate === null) {
      errors.push({
        row_id: rowId,
        reason: "unparseable_date",
      });
      continue;
    }

    if (normalizedAmount === null) {
      errors.push({
        row_id: rowId,
        reason: "unparseable_amount",
      });
      continue;
    }

    clean.push({
      row_id: rowId,
      date: normalizedDate,
      amount_cents: normalizedAmount,
      currency: normalize_currency(row.currency ?? ""),
      merchant: normalize_merchant(row.merchant ?? ""),
    });
  }

  const output: Output = { clean, errors };

  // This must truncate, not append.
  writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`, "utf-8");

  return output;
}

export function placeholder(): boolean {
  return true;
}

function main(): void {
  if (process.argv.length !== 4) {
    console.error("integration.ts, input csv, output json");
    process.exit(1);
  }

  const [, , inputPath, outputPath] = process.argv;
  const scriptDir = dirname(fileURLToPath(import.meta.url));
  const logPath = join(scriptDir, "..", "run.log");
  const correlationId = randomUUID();

  const logFd = openSync(logPath, "w");
  const log = (event: string, fields: Record<string, unknown> = {}): void => {
    const line = JSON.stringify({ correlation_id: correlationId, ...fields, event });
    writeSync(logFd, `${line}\n`);
  };

  log("run_started");

  const output = normalize_rows(inputPath as string, outputPath as string);

  log("run completed", {
    clean_count: output.clean.length,
    error_count: output.errors.length,
  });

  closeSync(logFd);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
