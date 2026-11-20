import { randomUUID } from "node:crypto";
import { hashPassword, verifyPassword, newSession, sessionHash } from "./auth.mjs";

export function postgresConfig(env = process.env) {
  const enabled = env.TREEWISE_STORAGE === "postgres";
  if (enabled && !env.DATABASE_URL) throw new Error("DATABASE_URL required for PostgreSQL storage.");
  return { enabled, url: env.DATABASE_URL || "" };
}

export async function openDatabase(config, importPg = () => import("pg")) {
  if (!config.enabled) return null;
  const { default: pg } = await importPg();
  const pool = new pg.Pool({
    connectionString: config.url,
    max: 5,
    connectionTimeoutMillis: 5000,
    idleTimeoutMillis: 30000
  });
  await pool.query("SELECT 1");
  return pool;
}

export async function createStaff(pool, { username, displayName, password }) {
  const hash = await hashPassword(password);
  const result = await pool.query(
    `INSERT INTO treewise_staff (id, username, display_name, password_hash)
     VALUES ($1,$2,$3,$4) RETURNING id, username, display_name`,
    [randomUUID(), username.toLowerCase(), displayName, hash]
  );
  return result.rows[0];
}
export async function loginStaff(pool, { username, password }) {
  const result = await pool.query(
    "SELECT id, username, display_name, password_hash FROM treewise_staff WHERE username = $1 AND is_active = true",
    [username]
  );
  const staff = result.rows[0];
  // Do equivalent password work even for unknown accounts to reduce timing leakage.
  const fallback = "scrypt:v1:00000000000000000000000000000000:" + "0".repeat(128);
  const matches = await verifyPassword(password, staff?.password_hash || fallback);
  if (!staff || !matches) return null;
  const session = newSession();
  await pool.query(
    "INSERT INTO treewise_sessions(token_hash,staff_id,expires_at) VALUES ($1,$2,$3)",
    [session.tokenHash, staff.id, session.expiresAt]
  );
  return { token: session.token, expiresAt: session.expiresAt, staff: {
    id: staff.id, username: staff.username, displayName: staff.display_name
  }};
}
export async function findSession(pool, token) {
  const hash = sessionHash(token);
  if (!hash) return null;
  const result = await pool.query(
    `SELECT s.staff_id, u.username, u.display_name
       FROM treewise_sessions s JOIN treewise_staff u ON u.id=s.staff_id
      WHERE s.token_hash=$1 AND s.expires_at > NOW() AND u.is_active=true`,
    [hash]
  );
  return result.rows[0] || null;
}
export async function revokeSession(pool, token) {
  const hash = sessionHash(token);
  if (!hash) return;
  await pool.query("DELETE FROM treewise_sessions WHERE token_hash=$1", [hash]);
}
export async function addInquiry(pool, inquiry) {
  const id = randomUUID();
  const result = await pool.query(
    `INSERT INTO treewise_inquiries
       (id,name,email,phone,location,description,urgency,consent_at)
     VALUES ($1,$2,$3,$4,$5,$6,$7,NOW())
     RETURNING id,created_at`,
    [id,inquiry.name,inquiry.email,inquiry.phone,inquiry.location,inquiry.description,inquiry.urgency]
  );
  return { id: result.rows[0].id, createdAt: result.rows[0].created_at };
}
export async function getInquiries(pool, limit = 100) {
  const result = await pool.query(
    `SELECT id,created_at AS "createdAt",name,email,phone,location,description,
            urgency,status
       FROM treewise_inquiries ORDER BY created_at DESC LIMIT $1`, [limit]
  );
  return result.rows;
}
export async function setInquiryStatus(pool, { id, status, note, staffId }) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const record = await client.query(
      "UPDATE treewise_inquiries SET status=$1 WHERE id=$2 RETURNING id", [status,id]);
    if (!record.rowCount) {
      await client.query("ROLLBACK");
      return false;
    }
    await client.query(
      `INSERT INTO treewise_inquiry_events(inquiry_id,staff_id,status,note)
       VALUES ($1,$2,$3,$4)`, [id,staffId,status,note]);
    await client.query("COMMIT");
    return true;
  } catch(error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
