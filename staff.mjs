import { createHash, timingSafeEqual } from "node:crypto";
import { readFile, open, stat, realpath } from "node:fs/promises";
import { constants } from "node:fs";
import { dirname, resolve } from "node:path";

const STATES = new Set(["pending", "reviewing", "contacted", "resolved", "closed"]);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const hash = (value) => createHash("sha256").update(value).digest();

export function staffConfig(env = process.env) {
  const enabled = env.ENABLE_STAFF_REVIEW === "true";
  const token = env.STAFF_REVIEW_TOKEN || "";
  const file = env.INQUIRY_QUEUE_FILE || "";
  if (enabled && (!env.ENABLE_INQUIRY_INTAKE || env.ENABLE_INQUIRY_INTAKE !== "true")) {
    throw new Error("Staff review requires ENABLE_INQUIRY_INTAKE=true.");
  }
  if (enabled && (token.length < 32 || !file.startsWith("/"))) {
    throw new Error("Staff review requires a 32+ character token and absolute queue path.");
  }
  return { enabled, token, file };
}

export function authorizeStaff(authorization, config) {
  if (!config.enabled || typeof authorization !== "string" ||
      !authorization.startsWith("Bearer ")) return false;
  const supplied = authorization.slice(7);
  if (supplied.length < 32 || supplied.length > 512) return false;
  return timingSafeEqual(hash(supplied), hash(config.token));
}

export function validateStatusChange(id, body) {
  if (!UUID.test(id)) return { ok: false, error: "Invalid inquiry reference." };
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { ok: false, error: "Invalid update." };
  }
  const status = body.status;
  const note = body.note ?? "";
  if (!STATES.has(status) || typeof note !== "string" ||
      note.length > 500 || /[\u0000-\u001f\u007f]/.test(note)) {
    return { ok: false, error: "Invalid status or note." };
  }
  return { ok: true, value: { id, status, note: note.trim() } };
}

export async function readQueue(file) {
  let raw;
  try { raw = await readFile(file, "utf8"); }
  catch (error) { if (error.code === "ENOENT") return []; throw error; }
  if (Buffer.byteLength(raw) > 5_000_000) throw new Error("Queue exceeds supported size.");
  // One damaged line must not take the whole review queue offline. Skip lines
  // that are not JSON objects with a string id and createdAt, and say so.
  const records = [];
  let skipped = 0;
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    let entry;
    try { entry = JSON.parse(line); } catch { skipped += 1; continue; }
    if (entry && typeof entry === "object" && !Array.isArray(entry) &&
        typeof entry.id === "string" && typeof entry.createdAt === "string") {
      records.push(entry);
    } else {
      skipped += 1;
    }
  }
  if (skipped > 0) console.warn(`Skipped ${skipped} malformed line(s) in ${file}.`);
  return records;
}

export function mergeStatus(records, events) {
  const current = new Map(records.map(item => [item.id, { ...item }]));
  for (const event of events) {
    const item = current.get(event.id);
    if (item && STATES.has(event.status)) {
      item.status = event.status;
      item.updatedAt = event.createdAt;
      item.latestNote = event.note;
    }
  }
  return Array.from(current.values()).sort((a,b) => b.createdAt.localeCompare(a.createdAt));
}

export async function listStaffInquiries(file) {
  const [records, events] = await Promise.all([readQueue(file), readQueue(file + ".events")]);
  return mergeStatus(records, events);
}

export async function appendStatus(file, change) {
  const path = resolve(file + ".events");
  const parent = dirname(path);
  if (await realpath(parent) !== parent) throw new Error("Unsafe queue directory.");
  const dir = await stat(parent);
  if ((dir.mode & 0o077) !== 0) throw new Error("Queue directory must be private.");
  const handle = await open(path, constants.O_WRONLY | constants.O_APPEND | constants.O_CREAT | constants.O_NOFOLLOW, 0o600);
  try {
    const info = await handle.stat();
    if (!info.isFile() || (info.mode & 0o077) !== 0) throw new Error("Status file must be private.");
    const event = { ...change, createdAt: new Date().toISOString() };
    await handle.writeFile(JSON.stringify(event) + "\n");
    await handle.sync();
    return event;
  } finally {
    await handle.close();
  }
}
