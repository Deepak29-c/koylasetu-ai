// Run with `npm test` (Node 22.18+ strips the types itself; no extra packages).
import assert from "node:assert/strict";
import { test } from "node:test";

import { answerForReport, answerWithReferences, appendText, sourcesList } from "./askReport.ts";

const labels = { page: "p.", sources: "Sources", unverified: "not yet verified" };
const citations = [
  { id: "F1", document: "Coal Directory 2023-24", page: 7, status: "VERIFIED" },
  { id: "C2", document: "Monthly Summary Dec 2024", page: 3, status: null },
  { id: "F3", document: "Coal Directory 2023-24", page: 7, status: "EXTRACTED" },
];

test("markers become readable references and the figures stay as they are", () => {
  assert.equal(
    answerWithReferences("NCL produced 12.70 MT [F1]. Output rose 5.2% [C2].", citations, labels),
    "NCL produced 12.70 MT (Coal Directory 2023-24, p. 7). Output rose 5.2% (Monthly Summary Dec 2024, p. 3).",
  );
});

test("markers side by side make one reference, without repeating a page", () => {
  assert.equal(
    answerWithReferences("Total 773.6 MT [F1][C2] [F3] in all.", citations, labels),
    "Total 773.6 MT (Coal Directory 2023-24, p. 7; Monthly Summary Dec 2024, p. 3) in all.",
  );
});

test("a marker with no citation behind it is dropped", () => {
  assert.equal(answerWithReferences("Nothing found [C9].", citations, labels), "Nothing found.");
});

test("the sources list names each page once and marks unverified figures", () => {
  assert.equal(
    sourcesList(citations, labels),
    "Sources:\n- Coal Directory 2023-24, p. 7\n- Monthly Summary Dec 2024, p. 3\n" +
      "- Coal Directory 2023-24, p. 7 (not yet verified)",
  );
  assert.equal(sourcesList([], labels), "");
});

test("an answer without sources adds only its text", () => {
  assert.equal(answerForReport("No figures here.", [], labels), "No figures here.");
});

test("the addition goes after the report's text with one blank line", () => {
  assert.equal(appendText("Existing text.\n\n\n", "New part."), "Existing text.\n\nNew part.");
  assert.equal(appendText("", "New part."), "New part.");
  assert.equal(appendText(undefined, "New part."), "New part.");
});
