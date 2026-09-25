import assert from "node:assert/strict";
import { test } from "node:test";

import { daysUntil, formatDate, formatDateTime, formatNumber } from "./format.ts";

// A time zone west of UTC, where reading "2026-10-03" as UTC midnight would show 2 October.
// Set before any date is made so Node picks it up.
process.env.TZ = "America/Los_Angeles";

test("the time zone for these tests is really west of UTC", () => {
  assert.equal(new Date("2026-10-03").getDate(), 2);
});

test("a calendar date keeps its day in every time zone", () => {
  assert.equal(formatDate("2026-10-03", "en-IN"), "3 Oct 2026");
  assert.equal(formatDate("2026-01-01", "en-IN"), "1 Jan 2026");
});

test("only the date part of a timestamp is used", () => {
  assert.equal(formatDate("2026-10-03T23:30:00Z", "en-IN"), "3 Oct 2026");
  assert.equal(formatDate("2026-10-03T00:00:00+05:30", "en-IN"), "3 Oct 2026");
});

test("missing and unreadable dates", () => {
  assert.equal(formatDate(null, "en-IN"), "–");
  assert.equal(formatDate(undefined, "en-IN"), "–");
  assert.equal(formatDate("", "en-IN"), "–");
  assert.equal(formatDate("soon", "en-IN"), "soon");
  assert.equal(formatDateTime(null, "en-IN"), "–");
  assert.equal(formatDateTime("not a time", "en-IN"), "not a time");
});

test("Hindi dates keep the same day", () => {
  const hi = formatDate("2026-10-03", "hi-IN");
  assert.match(hi, /3/);
  assert.match(hi, /2026/);
  assert.doesNotMatch(hi, /2 /);
});

function isoDaysFromToday(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

test("days until a calendar date counts whole local days", () => {
  assert.equal(daysUntil(isoDaysFromToday(0)), 0);
  assert.equal(daysUntil(isoDaysFromToday(1)), 1);
  assert.equal(daysUntil(isoDaysFromToday(-3)), -3);
  assert.equal(daysUntil(isoDaysFromToday(30)), 30);
  assert.equal(daysUntil(`${isoDaysFromToday(2)}T23:59:00Z`), 2);
});

test("days until has no answer without a date", () => {
  assert.equal(daysUntil(null), null);
  assert.equal(daysUntil(""), null);
  assert.equal(daysUntil("next week"), null);
});

test("numbers", () => {
  assert.equal(formatNumber(null, "en-IN"), "–");
  assert.equal(formatNumber(1234567, "en-IN"), "12,34,567");
  assert.equal(formatNumber(2.345, "en-IN", 1), "2.3");
});
