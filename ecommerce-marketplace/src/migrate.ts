import { loadConfig } from "./config.js";
import { migrate, openDatabase } from "./database.js";

const db = openDatabase(loadConfig().DATABASE_PATH);
try {
  migrate(db);
  const version = db.prepare("PRAGMA user_version").get() as { user_version: number };
  process.stdout.write(`${JSON.stringify({ level: "info", event: "migrations_applied", version: version.user_version })}\n`);
} finally {
  db.close();
}
