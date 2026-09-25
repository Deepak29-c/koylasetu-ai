import assert from "node:assert/strict";
import { test } from "node:test";

import { safeInternalPath, sourceHref } from "./sources.ts";

const query = (href: string) => new URL(href, "http://site.test").searchParams;

test("a source link carries the page and, when given, where to go back to", () => {
  const href = sourceHref({ document_id: "doc-1", page: 4 }, "/reports/7?tab=content");
  assert.ok(href.startsWith("/documents/doc-1?"));
  const q = query(href);
  assert.equal(q.get("page"), "4");
  assert.equal(q.get("from"), "/reports/7?tab=content");
  assert.equal(q.get("chunk"), null);
  assert.equal(q.get("box"), null);
});

test("without a back path there is no from parameter", () => {
  assert.equal(query(sourceHref({ document_id: "d", page: 1 })).has("from"), false);
});

test("a table cell box wins over a text block", () => {
  const q = query(sourceHref({ document_id: "d", page: 2, chunk_id: "c9", bbox: [10, 20.5, 30, 40] }));
  assert.equal(q.get("box"), "10,20.5,30,40");
  assert.equal(q.get("chunk"), null);
});

test("a text block is used when there is no complete box", () => {
  assert.equal(query(sourceHref({ document_id: "d", page: 2, chunk_id: "c9", bbox: [1, 2, 3] })).get("chunk"), "c9");
  assert.equal(query(sourceHref({ document_id: "d", page: 2, chunk_id: "c9", bbox: null })).get("chunk"), "c9");
});

test("the back path is encoded so its own query does not leak into the link", () => {
  const href = sourceHref({ document_id: "d", page: 1 }, "/ask?qa=5&x=1");
  const q = query(href);
  assert.equal(q.get("from"), "/ask?qa=5&x=1");
  assert.equal(q.has("x"), false);
  assert.equal(q.has("qa"), false);
});

test("paths on this site pass through unchanged", () => {
  assert.equal(safeInternalPath("/"), "/");
  assert.equal(safeInternalPath("/reports/1?x=y"), "/reports/1?x=y");
  assert.equal(safeInternalPath("/documents/d?page=2#top"), "/documents/d?page=2#top");
});

test("links that could leave the site are refused", () => {
  for (const bad of [
    null,
    undefined,
    "",
    "reports",
    "//evil.example/x",
    "/\\evil.example",
    "/\\/evil.example",
    "/\tevil",
    "/\n/evil.example",
    "/\r/evil.example",
    "https://evil.example/",
    "http://internal.invalid/x",
    "javascript:alert(1)",
    " /reports",
  ]) {
    assert.equal(safeInternalPath(bad), null, JSON.stringify(bad));
  }
});
