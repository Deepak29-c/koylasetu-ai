// Run with `npm test` (Node 22.18+ strips the types itself; no extra packages).
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  depthLabel,
  periodLabel,
  project,
  radius,
  segmentWidths,
  shadeBreaks,
  shadeIndex,
  stateKey,
} from "./mapView.ts";

test("shades follow the values' spread, not equal steps", () => {
  // State resources: a few huge, many small
  const values = [91811, 99203, 78000, 30000, 12000, 5000, 1600, 900, 110, 14];
  const breaks = shadeBreaks(values);
  assert.equal(breaks.length, 5);
  assert.equal(shadeIndex(14, breaks), 0);
  assert.equal(shadeIndex(99203, breaks), 4);
  // Each shade gets about the same number of states
  const counts = [0, 0, 0, 0, 0];
  for (const v of values) counts[shadeIndex(v, breaks)]++;
  assert.deepEqual(counts, [2, 2, 2, 2, 2]);
});

test("few values give few shades, none give none", () => {
  assert.deepEqual(shadeBreaks([]), []);
  assert.deepEqual(shadeBreaks([7, 7]), [7]);
  assert.equal(shadeIndex(7, [7]), 0);
});

test("state names from the extractor match the boundary file", () => {
  assert.equal(stateKey("Jammu & Kashmir"), stateKey("Jammu and Kashmir"));
  assert.equal(stateKey("Andaman & Nicobar"), stateKey("ANDAMAN AND NICOBAR"));
  assert.notEqual(stateKey("Odisha"), stateKey("Assam"));
});

test("projection puts the north-west corner at the origin", () => {
  const p = { west: 68, north: 37, scale: 10, kx: 1 };
  assert.deepEqual(project(68, 37, p), [0, 0]);
  assert.deepEqual(project(78, 27, p), [100, 100]);
});

test("circle area grows with the value", () => {
  assert.equal(radius(100, 100), 34);
  assert.equal(radius(25, 100), 17);
  assert.equal(radius(0, 100), 5);
  assert.equal(radius(0.001, 100), 5);
});

test("resource months read 'as on', production months don't", () => {
  assert.equal(periodLabel("2024-04", "coal_resource", "as on"), "as on Apr 2024");
  assert.equal(periodLabel("2024-12", "coal_production", "as on"), "Dec 2024");
  assert.equal(periodLabel("FY 2023-24", "coal_offtake", "as on"), "FY 2023-24");
  assert.equal(periodLabel(null, "coal_offtake", "as on"), "–");
});

test("depth labels and bar widths", () => {
  assert.equal(depthLabel("0-300"), "0–300 m");
  assert.equal(depthLabel("600-1200"), "600–1200 m");
  const w = segmentWidths([
    { measured: 50, indicated: 30, inferred: 20, total: 100 },
    { measured: 10, indicated: 10, inferred: 5, total: 25 },
  ]);
  assert.deepEqual(w, [
    { measured: 50, indicated: 30, inferred: 20 },
    { measured: 10, indicated: 10, inferred: 5 },
  ]);
  assert.deepEqual(segmentWidths([{ measured: 0, indicated: 0, inferred: 0, total: 0 }]), [
    { measured: 0, indicated: 0, inferred: 0 },
  ]);
});
