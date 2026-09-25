// Run with `npm test` (Node 22.18+ strips the types itself; no extra packages).
import assert from "node:assert/strict";
import { test } from "node:test";

import { pqQuestionText } from "./similar.ts";

test("the similar-questions search uses the subject and every part of the question", () => {
  const report = {
    title: "Lok Sabha Unstarred Q. No. 12: Coal import",
    content_json: {
      header: { subject: "Coal import" },
      blocks: [
        { question: "the import of coal during 2023-24;" },
        { question: " the steps  taken to reduce it" },
      ],
    },
  } as unknown as Parameters<typeof pqQuestionText>[0];
  assert.equal(pqQuestionText(report), "Coal import the import of coal during 2023-24; the steps taken to reduce it");
});

test("a reply saved as plain text is searched by its title", () => {
  assert.equal(pqQuestionText({ title: "RS Q 7: कोयला आयात", content_json: { text: "..." } }), "RS Q 7: कोयला आयात");
});
