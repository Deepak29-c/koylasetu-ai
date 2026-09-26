import assert from "node:assert/strict";
import { test } from "node:test";

import { activeHref, NAV_GROUPS, visibleNav } from "./nav.ts";

// Each role's permissions, as backend/app/core/rbac.py grants them.
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: [
    "manage_admin",
    "upload_documents",
    "view_processing",
    "review_facts",
    "ask_questions",
    "export_reports",
    "view_topics",
    "view_audit",
    "view_metrics",
  ],
  operator: ["upload_documents", "view_processing", "ask_questions", "view_topics"],
  reviewer: ["upload_documents", "view_processing", "review_facts", "ask_questions", "view_topics"],
  analyst: ["view_processing", "ask_questions", "edit_reports", "export_reports", "view_topics"],
  approver: [
    "ask_questions",
    "edit_reports",
    "approve_reports",
    "export_reports",
    "view_topics",
    "view_audit",
    "view_metrics",
  ],
  viewer: ["ask_questions", "export_reports", "view_topics"],
};

const NEW_REPORTS = ["/pq-replies/new", "/monthly-reports/new", "/briefing-notes/new"];

const EXPECTED: Record<string, string[]> = {
  admin: [
    "/", "/ask", "/reports", "/upload", "/documents", "/review", "/map", "/topics", "/metrics",
    "/admin/users", "/admin/templates", "/admin/rules", "/audit",
  ],
  operator: ["/", "/ask", "/upload", "/documents", "/map", "/topics"],
  reviewer: ["/", "/ask", "/upload", "/documents", "/review", "/map", "/topics"],
  analyst: ["/", "/ask", "/reports", ...NEW_REPORTS, "/documents", "/map", "/topics"],
  approver: ["/", "/ask", "/reports", "/approvals", ...NEW_REPORTS, "/map", "/topics", "/metrics", "/audit"],
  viewer: ["/", "/ask", "/reports", "/map", "/topics"],
};

const hrefs = (permissions: string[]) => visibleNav(permissions).flatMap((g) => g.items.map((i) => i.href));

for (const [role, expected] of Object.entries(EXPECTED)) {
  test(`the ${role} sees exactly their menu entries`, () => {
    assert.deepEqual(hrefs(ROLE_PERMISSIONS[role]), expected);
  });
}

test("a user with several roles sees what any of them allows", () => {
  const both = [...new Set([...ROLE_PERMISSIONS.operator, ...ROLE_PERMISSIONS.viewer])];
  assert.deepEqual(hrefs(both), ["/", "/ask", "/reports", "/upload", "/documents", "/map", "/topics"]);
});

test("no permissions leaves only Home, and empty groups are dropped", () => {
  const groups = visibleNav([]);
  assert.equal(groups.length, 1);
  assert.deepEqual(groups[0].items.map((i) => i.href), ["/"]);
});

test("the admin group appears only for someone who may open one of its pages", () => {
  const labels = (role: string) => visibleNav(ROLE_PERMISSIONS[role]).map((g) => g.label ?? null);
  assert.ok(labels("admin").includes("nav.admin"));
  assert.ok(labels("approver").includes("nav.admin"));
  assert.ok(!labels("analyst").includes("nav.admin"));
  assert.ok(!labels("viewer").includes("nav.admin"));
});

test("an unknown permission shows nothing extra", () => {
  assert.deepEqual(hrefs(["delete_everything"]), ["/"]);
});

test("every menu entry is a site path and appears once", () => {
  const all = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.href));
  assert.equal(new Set(all).size, all.length);
  for (const h of all) assert.match(h, /^\/(?!\/)/);
});

test("the active entry is the longest matching prefix", () => {
  assert.equal(activeHref("/"), "/");
  assert.equal(activeHref("/reports"), "/reports");
  assert.equal(activeHref("/reports/abc-123"), "/reports");
  assert.equal(activeHref("/admin/users"), "/admin/users");
  assert.equal(activeHref("/profile"), "/profile");
  assert.equal(activeHref("/reportsx"), null);
  assert.equal(activeHref("/nowhere"), null);
});
