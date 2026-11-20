import test from "node:test";
import assert from "node:assert/strict";
import {
  hashPassword, verifyPassword, newSession, sessionHash,
  bearerToken, validateCredentials
} from "../auth.mjs";
import { postgresConfig, loginStaff, findSession, addInquiry } from "../postgres.mjs";

test("password hashes are salted and can be verified", async () => {
  const first = await hashPassword("a-strong-test-passphrase");
  const second = await hashPassword("a-strong-test-passphrase");
  assert.notEqual(first, second);
  assert.equal(await verifyPassword("a-strong-test-passphrase", first), true);
  assert.equal(await verifyPassword("incorrect-password", first), false);
  assert.equal(await verifyPassword("incorrect-password", "garbage"), false);
});

test("credential validation normalizes username", () => {
  assert.deepEqual(validateCredentials({ username: "TREE.Team", password: "test-password-123" }),
    { username: "tree.team", password: "test-password-123" });
  assert.equal(validateCredentials({ username: "bad space", password: "test-password-123" }), null);
  assert.equal(validateCredentials({ username: "goodname", password: "short" }), null);
});

test("session token has 256 bits entropy and hashes before persistence", () => {
  const session = newSession();
  assert.match(session.token, /^[a-f0-9]{64}$/);
  assert.equal(session.tokenHash, sessionHash(session.token));
  assert.notEqual(session.tokenHash, session.token);
  assert.equal(bearerToken("Bearer " + session.token), session.token);
  assert.equal(bearerToken("Basic " + session.token), null);
  assert.equal(sessionHash("invalid"), null);
});

test("missing pg driver gives a clear startup error", async () => {
  const { openDatabase } = await import("../postgres.mjs");
  await assert.rejects(
    openDatabase({ enabled: true, url: "postgres://example.invalid/db" },
      () => Promise.reject(new Error("Cannot find package 'pg'"))),
    /needs the pg package/
  );
});

test("PostgreSQL mode requires explicit URL", () => {
  assert.equal(postgresConfig({}).enabled, false);
  assert.throws(() => postgresConfig({ TREEWISE_STORAGE: "postgres" }), /DATABASE_URL/);
});

test("successful login uses a parameterized user lookup and persists only a token digest", async () => {
  const password = "long-test-password-for-staff";
  const stored = await hashPassword(password);
  const calls = [];
  const pool = { async query(sql, args) {
    calls.push({ sql, args });
    if (sql.startsWith("SELECT id, username")) {
      return { rows: [{ id: "staff-id", username: "arborist", display_name: "Staff User", password_hash: stored }] };
    }
    return { rows: [] };
  }};
  const result = await loginStaff(pool, { username: "arborist", password });
  assert.equal(result.staff.displayName, "Staff User");
  assert.equal(calls.length, 3);
  assert.match(calls[0].sql, /username = \$1/);
  assert.match(calls[1].sql, /^DELETE FROM treewise_sessions WHERE expires_at <= NOW\(\)$/);
  assert.equal(calls[2].args[0], sessionHash(result.token));
  assert.notEqual(calls[2].args[0], result.token);
});

test("login removes expired sessions before issuing a new one", async () => {
  const password = "long-test-password-for-staff";
  const stored = await hashPassword(password);
  const sqlSeen = [];
  const pool = { async query(sql) {
    sqlSeen.push(sql);
    if (sql.startsWith("SELECT id, username")) {
      return { rows: [{ id: "staff-id", username: "arborist", display_name: "Staff User", password_hash: stored }] };
    }
    return { rows: [] };
  }};
  await loginStaff(pool, { username: "arborist", password });
  const purgeAt = sqlSeen.findIndex(sql => sql.startsWith("DELETE FROM treewise_sessions"));
  const insertAt = sqlSeen.findIndex(sql => sql.startsWith("INSERT INTO treewise_sessions"));
  assert.ok(purgeAt > 0 && purgeAt < insertAt, "expired sessions purged before insert");
});

test("session lookup rejects unknown or expired sessions in SQL", async () => {
  let sql = "";
  const pool = { async query(statement) { sql = statement; return { rows: [] }; } };
  assert.equal(await findSession(pool, "not-a-token"), null);
  assert.equal(sql, "");
  assert.equal(await findSession(pool, newSession().token), null);
  assert.match(sql, /expires_at > NOW\(\)/);
});

test("inquiry insertion parameterizes customer supplied values", async () => {
  let statement, params;
  const pool = { async query(sql, values) {
    statement = sql; params = values;
    return { rows: [{ id: "fake-id", created_at: "2026-11-20" }] };
  }};
  await addInquiry(pool, {
    name: "Example", email: "a@example.com", phone: "",
    location: "Boulder", description: "A long concern about a leaning tree.",
    urgency: "soon"
  });
  assert.match(statement, /VALUES \(\$1,\$2,\$3,\$4,\$5,\$6,\$7,NOW\(\)\)/);
  assert.equal(params[1], "Example");
});
