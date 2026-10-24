import { createApp } from "./app.js";
import { loadConfig } from "./config.js";
import { migrate, openDatabase } from "./database.js";

const config = loadConfig();
const db = openDatabase(config.DATABASE_PATH);
migrate(db);
const app = createApp({ db, sessionTtlHours: config.SESSION_TTL_HOURS, secureCookies: config.SECURE_COOKIES });
const server = app.listen(config.PORT, config.HOST, () => {
  process.stdout.write(`${JSON.stringify({ level: "info", event: "server_started", host: config.HOST, port: config.PORT })}\n`);
});

function shutdown(signal: string): void {
  process.stdout.write(`${JSON.stringify({ level: "info", event: "server_shutdown", signal })}\n`);
  server.close(() => { db.close(); process.exit(0); });
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
