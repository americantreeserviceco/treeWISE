import "dotenv/config";
import { createStaff, openDatabase, postgresConfig } from "../postgres.mjs";
import { validateCredentials } from "../auth.mjs";

const username = process.env.TREEWISE_STAFF_USERNAME;
const displayName = process.env.TREEWISE_STAFF_DISPLAY_NAME;
const password = process.env.TREEWISE_STAFF_PASSWORD;

if (!username || !displayName || !password ||
    !validateCredentials({ username, password }) ||
    displayName.length > 120 || displayName.length < 2) {
  console.error("Set TREEWISE_STAFF_USERNAME, TREEWISE_STAFF_DISPLAY_NAME and a 12+ character TREEWISE_STAFF_PASSWORD.");
  process.exitCode = 1;
} else {
  let pool;
  try {
    pool = await openDatabase(postgresConfig({ ...process.env, TREEWISE_STORAGE: "postgres" }));
    const created = await createStaff(pool, { username, displayName, password });
    console.log(`Created staff account: ${created.username} (${created.id})`);
  } catch(error) {
    console.error("Staff creation failed:", error.message);
    process.exitCode = 1;
  } finally {
    await pool?.end();
  }
}
