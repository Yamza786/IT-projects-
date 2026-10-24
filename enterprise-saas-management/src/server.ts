import { createApp } from "./app.js";
import { loadConfig } from "./config.js";
import { migrate, openDatabase } from "./database.js";

async function main(): Promise<void> {
  const config = loadConfig();
  const db = openDatabase(config.DATABASE_PATH);
  migrate(db);
  const app = await createApp({
    db,
    sessionTtlHours: config.SESSION_TTL_HOURS,
    secureCookies: config.COOKIE_SECURE,
    bootstrapEmail: config.BOOTSTRAP_EMAIL,
    bootstrapPassword: config.BOOTSTRAP_PASSWORD,
  });
  const server = app.listen(config.PORT, "127.0.0.1", () => {
    process.stdout.write(`${JSON.stringify({ level: "info", event: "server_started", host: "127.0.0.1", port: config.PORT })}\n`);
  });
  const shutdown = (): void => { server.close(() => { db.close(); process.exit(0); }); };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((error: unknown) => {
  process.stderr.write(`${JSON.stringify({ level: "error", event: "startup_failed", message: error instanceof Error ? error.message : "Unknown error" })}\n`);
  process.exitCode = 1;
});
