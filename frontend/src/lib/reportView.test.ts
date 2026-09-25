// Run with `npm test` (Node 22.18+ strips the types itself; no extra packages).
import assert from "node:assert/strict";
import { test } from "node:test";

import { contentMode, versionLine } from "./reportView.ts";

test("someone who cannot edit reports sees read-only content at every status (#64)", () => {
  for (const status of ["DRAFT", "IN_REVIEW", "RETURNED", "APPROVED", "EXPORTED"] as const) {
    assert.equal(contentMode(false, status), "read_only");
  }
});

test("an editor is blocked by status only outside Draft and Returned", () => {
  assert.equal(contentMode(true, "DRAFT"), "edit");
  assert.equal(contentMode(true, "RETURNED"), "edit");
  assert.equal(contentMode(true, "IN_REVIEW"), "status_blocked");
  assert.equal(contentMode(true, "APPROVED"), "status_blocked");
  assert.equal(contentMode(true, "EXPORTED"), "status_blocked");
});

test("a known code is worded by the page and the comment is passed through untouched (#71)", () => {
  const words = "  कृपया p. 4 का आँकड़ा जाँचें ";
  assert.deepEqual(versionLine({ change_kind: "returned", change_comment: words, change_note: null }), {
    kind: "returned",
    comment: words,
    fallback: null,
  });
  assert.deepEqual(versionLine({ change_kind: "approved", change_comment: null, change_note: "Approved" }), {
    kind: "approved",
    comment: null,
    fallback: null,
  });
});

test("an unknown code falls back to the stored sentence instead of an empty line", () => {
  assert.deepEqual(versionLine({ change_kind: "merged", change_comment: null, change_note: "Merged by admin" }), {
    kind: null,
    comment: null,
    fallback: "Merged by admin",
  });
  assert.deepEqual(versionLine({ change_kind: null, change_comment: null, change_note: null }), {
    kind: null,
    comment: null,
    fallback: null,
  });
});
