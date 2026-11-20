import { randomUUID } from "node:crypto";
import { mkdir, open, realpath, stat } from "node:fs/promises";
import { constants } from "node:fs";
import { dirname, resolve, isAbsolute } from "node:path";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE = /^[+()\d\s.-]{7,24}$/;
const text = (value) => typeof value === "string" ? value.trim() : "";
const controlChars = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/;
const allowedUrgency = new Set(["routine", "soon", "urgent"]);

export function validateInquiry(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { ok: false, error: "Invalid form data." };
  }
  // Honeypot. Behave like success to avoid advertising filtering decisions.
  if (text(body.website)) return { ok: false, spam: true, error: "Request not accepted." };
  if (body.consent !== true) return { ok: false, error: "Consent is required." };
  const name = text(body.name);
  const email = text(body.email);
  const phone = text(body.phone);
  const location = text(body.location);
  const description = text(body.description);
  const urgency = text(body.urgency) || "routine";
  const values = [name, email, phone, location, description];
  if (values.some(value => controlChars.test(value))) {
    return { ok: false, error: "Form fields contain unsupported characters." };
  }
  if (name.length < 2 || name.length > 120) return { ok: false, error: "Enter your name (2–120 characters)." };
  if (email.length > 254 || (email && !EMAIL.test(email))) return { ok: false, error: "Enter a valid email address." };
  if (phone && !PHONE.test(phone)) return { ok: false, error: "Enter a valid phone number." };
  if (!email && !phone) return { ok: false, error: "Provide an email address or phone number." };
  if (location.length > 250) return { ok: false, error: "Location is too long." };
  if (description.length < 20 || description.length > 3000) return { ok: false, error: "Describe the issue in 20–3000 characters." };
  if (!allowedUrgency.has(urgency)) return { ok: false, error: "Select a valid priority." };
  if (body.image != null) return { ok: false, error: "Photo submission is not yet available. Please submit text only." };
  return { ok: true, value: { name, email, phone, location, description, urgency } };
}

export function intakeConfig(env = process.env) {
  const enabled = env.ENABLE_INQUIRY_INTAKE === "true";
  const file = text(env.INQUIRY_QUEUE_FILE);
  if (enabled && env.TREEWISE_STORAGE !== "postgres" && (!file || !isAbsolute(file))) {
    throw new Error("INQUIRY_QUEUE_FILE must be an absolute private path when intake is enabled.");
  }
  return { enabled, file };
}

export async function saveInquiry(record, config) {
  if (!config.enabled) throw new Error("Inquiry intake is disabled.");
  const file = resolve(config.file);
  const parent = dirname(file);
  await mkdir(parent, { recursive: true, mode: 0o700 });
  // Require private existing directory; do not follow symlinks for the file.
  const actualParent = await realpath(parent);
  if (actualParent !== parent) throw new Error("Queue parent must not be a symlink.");
  const directory = await stat(parent);
  if ((directory.mode & 0o077) !== 0) throw new Error("Queue directory must be private (0700).");
  const handle = await open(file, constants.O_APPEND | constants.O_CREAT | constants.O_WRONLY | constants.O_NOFOLLOW, 0o600);
  try {
    const stat = await handle.stat();
    if (!stat.isFile() || (stat.mode & 0o077) !== 0) {
      throw new Error("Queue file must be private (0600).");
    }
    const id = randomUUID();
    const createdAt = new Date().toISOString();
    await handle.writeFile(JSON.stringify({ id, createdAt, status: "pending", ...record }) + "\n");
    await handle.sync();
    return { id, createdAt };
  } finally {
    await handle.close();
  }
}

// In-memory limiter intentionally applies per server process, not across replicas.
// This application is localhost-only and not designed for public traffic.
export function makeRateLimiter({ limit = 3, windowMs = 60_000, now = Date.now } = {}) {
  const hits = new Map();
  return function allow(key) {
    const timestamp = now();
    for (const [k, entry] of hits) if (entry.expires <= timestamp) hits.delete(k);
    const entry = hits.get(key) ?? { count: 0, expires: timestamp + windowMs };
    if (entry.count >= limit) return false;
    entry.count += 1;
    hits.set(key, entry);
    return true;
  };
}
