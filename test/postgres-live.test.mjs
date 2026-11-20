// Live PostgreSQL tests. They run only when TREEWISE_TEST_DATABASE_URL points
// at a dedicated, disposable test database. Never point this at real data.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { openDatabase, createStaff, loginStaff, findSession, revokeSession,
  addInquiry, getInquiries, setInquiryStatus } from "../postgres.mjs";

const url = process.env.TREEWISE_TEST_DATABASE_URL || "";

test("live: migration, login, status audit and logout", { skip: !url && "set TREEWISE_TEST_DATABASE_URL to run" }, async () => {
  const pool = await openDatabase({ enabled: true, url });
  try {
    await pool.query(await readFile(new URL("../db/001_init.sql", import.meta.url), "utf8"));
    const username = `test.${randomUUID().slice(0, 8)}`;
    const password = "live-test-passphrase-123";
    const staff = await createStaff(pool, { username, displayName: "Live Test", password });

    const login = await loginStaff(pool, { username, password });
    assert.ok(login, "login succeeds with the right password");
    assert.equal(await loginStaff(pool, { username, password: "wrong-passphrase-123" }), null);
    assert.equal((await findSession(pool, login.token)).username, username);

    const inquiry = await addInquiry(pool, {
      name: "Synthetic Customer", email: "synthetic@example.com", phone: "",
      location: "Test", description: "Synthetic test inquiry for the live check.", urgency: "routine"
    });
    assert.equal(await setInquiryStatus(pool, { id: inquiry.id, status: "reviewing", note: "live test", staffId: staff.id }), true);
    const { rows } = await pool.query("SELECT COUNT(*)::int AS n FROM treewise_inquiry_events WHERE inquiry_id = $1", [inquiry.id]);
    assert.equal(rows[0].n, 1, "status change wrote one audit event");
    assert.equal((await getInquiries(pool)).some(item => item.id === inquiry.id), true);

    await revokeSession(pool, login.token);
    assert.equal(await findSession(pool, login.token), null, "logout revokes the session");

    await pool.query("DELETE FROM treewise_inquiries WHERE id = $1", [inquiry.id]);
    await pool.query("DELETE FROM treewise_staff WHERE id = $1", [staff.id]);
  } finally {
    await pool.end();
  }
});
