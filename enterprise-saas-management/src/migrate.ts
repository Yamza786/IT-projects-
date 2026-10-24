import { loadConfig } from "./config.js";
import { migrate, openDatabase } from "./database.js";

const config = loadConfig();
const db = openDatabase(config.DATABASE_PATH);
try {
  migrate(db);
  const version = (db.prepare("PRAGMA user_version").get() as { user_version: number }).user_version;
  process.stdout.write(`Database migrations applied (schema version ${version}).\n`);
} finally {
  db.close();
}
