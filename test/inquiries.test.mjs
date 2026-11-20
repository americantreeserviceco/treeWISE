import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, chmod, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { intakeConfig, validateInquiry, saveInquiry, makeRateLimiter } from "../inquiries.mjs";

const valid = () => ({
  name: "Example Customer",
  email: "test@example.com",
  phone: "",
  location: "Boulder County",
  description: "My mature tree has several broken branches.",
  urgency: "soon",
  consent: true
});

test("rejects missing consent", () => {
  assert.equal(validateInquiry({ ...valid(), consent: false }).ok, false);
});

test("requires contact method and meaningful description", () => {
  assert.equal(validateInquiry({ ...valid(), email: "" }).ok, false);
  assert.equal(validateInquiry({ ...valid(), description: "help" }).ok, false);
});

test("rejects unsupported photo payload and fields", () => {
  assert.equal(validateInquiry({ ...valid(), image: "data:image/png;base64,AA==" }).ok, false);
  assert.equal(validateInquiry({ ...valid(), urgency: "emergency-dispatched" }).ok, false);
});

test("honeypot rejects automated submissions", () => {
  assert.equal(validateInquiry({ ...valid(), website: "spam.test" }).spam, true);
});

test("accepts valid phone-only submission", () => {
  assert.equal(validateInquiry({ ...valid(), email: "", phone: "303-555-0199" }).ok, true);
});

test("queue is opt-in and needs absolute location", () => {
  assert.deepEqual(intakeConfig({}), { enabled: false, file: "" });
  assert.throws(() => intakeConfig({ ENABLE_INQUIRY_INTAKE: "true", INQUIRY_QUEUE_FILE: "./leads.jsonl" }), /absolute/);
});

test("writes one private JSONL record and returns reference", async () => {
  const root = await mkdtemp(join(tmpdir(), "treewise-inquiry-"));
  await chmod(root, 0o700);
  const file = join(root, "inquiries.jsonl");
  const saved = await saveInquiry(valid(), { enabled: true, file });
  assert.match(saved.id, /^[a-f0-9-]{36}$/);
  const records = (await readFile(file, "utf8")).trim().split("\n").map(line => JSON.parse(line));
  assert.equal(records.length, 1);
  assert.equal(records[0].id, saved.id);
  assert.equal(records[0].status, "pending");
  assert.deepEqual(records[0].consent, { given: true, at: records[0].createdAt, notice: "local-queue-v1" });
});

test("rejects queue file symlink", async () => {
  const root = await mkdtemp(join(tmpdir(), "treewise-link-"));
  await chmod(root, 0o700);
  const source = join(root, "source.jsonl");
  const target = join(root, "target.jsonl");
  await symlink(source, target);
  await assert.rejects(saveInquiry(valid(), { enabled: true, file: target }));
});

test("rate limit resets with time", () => {
  let time = 100;
  const allow = makeRateLimiter({ limit: 2, windowMs: 1000, now: () => time });
  assert.equal(allow("local"), true);
  assert.equal(allow("local"), true);
  assert.equal(allow("local"), false);
  time = 1100;
  assert.equal(allow("local"), true);
});
