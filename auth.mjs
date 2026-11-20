import { randomBytes, scrypt as scryptCallback, timingSafeEqual, createHash } from "node:crypto";
import { promisify } from "node:util";
const scrypt = promisify(scryptCallback);
const normalizedUsername = input => typeof input === "string" && /^[a-z][a-z0-9._-]{2,79}$/i.test(input) ? input.toLowerCase() : null;
const digest = token => createHash("sha256").update(token).digest("hex");

export function validateCredentials(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const username = normalizedUsername(input.username);
  if (!username || typeof input.password !== "string" ||
      input.password.length < 12 || input.password.length > 1024) return null;
  return { username, password: input.password };
}
export async function hashPassword(password) {
  if (typeof password !== "string" || password.length < 12 || password.length > 1024) {
    throw new Error("Password length must be 12–1024 characters.");
  }
  const salt = randomBytes(16).toString("hex");
  const derived = await scrypt(password, Buffer.from(salt, "hex"), 64);
  return `scrypt:v1:${salt}:${derived.toString("hex")}`;
}
export async function verifyPassword(password, stored) {
  if (typeof password !== "string" || typeof stored !== "string") return false;
  const fields = stored.split(":");
  if (fields.length !== 4 || fields[0] !== "scrypt" || fields[1] !== "v1" ||
      !/^[0-9a-f]{32}$/.test(fields[2]) || !/^[0-9a-f]{128}$/.test(fields[3])) return false;
  const expected = Buffer.from(fields[3], "hex");
  const actual = await scrypt(password, Buffer.from(fields[2], "hex"), expected.length);
  return timingSafeEqual(actual, expected);
}
export function newSession(durationHours = 8) {
  const token = randomBytes(32).toString("hex");
  return {
    token,
    tokenHash: digest(token),
    expiresAt: new Date(Date.now() + durationHours * 3600_000)
  };
}
export function sessionHash(token) {
  if (typeof token !== "string" || !/^[0-9a-f]{64}$/.test(token)) return null;
  return digest(token);
}
export function bearerToken(header) {
  if (typeof header !== "string") return null;
  const match = /^Bearer ([a-f0-9]{64})$/.exec(header);
  return match ? match[1] : null;
}
