import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, chmod, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { staffConfig, authorizeStaff, validateStatusChange, listStaffInquiries, appendStatus, mergeStatus } from "../staff.mjs";

const id = "a3b83b9c-574b-4cfb-a2f5-78b123456789";
const token = "secure-test-token-at-least-thirty-two-chars";

test("staff review defaults off", () => {
  assert.equal(staffConfig({}).enabled, false);
});
test("staff review requires intake, strong token and private path", () => {
  assert.throws(() => staffConfig({ ENABLE_STAFF_REVIEW: "true" }), /ENABLE_INQUIRY_INTAKE/);
  assert.throws(() => staffConfig({ ENABLE_STAFF_REVIEW: "true", ENABLE_INQUIRY_INTAKE: "true", STAFF_REVIEW_TOKEN: "short", INQUIRY_QUEUE_FILE: "/tmp/x" }), /32/);
  assert.equal(staffConfig({ ENABLE_STAFF_REVIEW: "true", ENABLE_INQUIRY_INTAKE: "true", STAFF_REVIEW_TOKEN: token, INQUIRY_QUEUE_FILE: "/tmp/private/x" }).enabled, true);
});
test("token authentication checks bearer header and enabled state", () => {
  const config = { enabled: true, token };
  assert.equal(authorizeStaff("Bearer " + token, config), true);
  assert.equal(authorizeStaff("Bearer incorrect-test-token-000000000000000", config), false);
  assert.equal(authorizeStaff("Basic " + token, config), false);
  assert.equal(authorizeStaff("Bearer " + token, { ...config, enabled: false }), false);
});
test("status edits reject unknown ids, states and control characters", () => {
  assert.equal(validateStatusChange("bad", { status: "contacted" }).ok, false);
  assert.equal(validateStatusChange(id, { status: "deleted" }).ok, false);
  assert.equal(validateStatusChange(id, { status: "reviewing", note: "line\nbreak" }).ok, false);
  assert.equal(validateStatusChange(id, { status: "contacted", note: "called customer" }).ok, true);
});
test("status events merge without overwriting original inquiry", () => {
  const records = [{ id, name: "Test", status: "pending", createdAt: "2026-11-20T10:00:00Z" }];
  const items = mergeStatus(records, [{ id, status: "contacted", note: "called", createdAt: "2026-11-20T11:00:00Z" }]);
  assert.equal(items[0].status, "contacted");
  assert.equal(items[0].latestNote, "called");
  assert.equal(records[0].status, "pending");
});
test("staff queue reads and records status updates", async () => {
  const dir = await mkdtemp(join(tmpdir(), "treewise-staff-"));
  await chmod(dir, 0o700);
  const file = join(dir, "queue.jsonl");
  await writeFile(file, JSON.stringify({ id, name: "Example", status: "pending", createdAt: "2026-11-20T10:00:00Z" }) + "\n", { mode: 0o600 });
  const event = await appendStatus(file, { id, status: "reviewing", note: "staff reviewing" });
  assert.equal(event.id, id);
  const records = await listStaffInquiries(file);
  assert.equal(records.length, 1);
  assert.equal(records[0].status, "reviewing");
});
