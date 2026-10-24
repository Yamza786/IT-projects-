import { DatabaseSync } from "node:sqlite";
import { mkdirSync, readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

export type Database = DatabaseSync;

export function openDatabase(path: string): Database {
  if (path !== ":memory:") mkdirSync(dirname(resolve(path)), { recursive: true, mode: 0o700 });
  const db = new DatabaseSync(path);
  db.exec("PRAGMA foreign_keys = ON; PRAGMA busy_timeout = 5000; PRAGMA journal_mode = WAL;");
  return db;
}

export function migrate(db: Database): void {
  const directory = resolve(process.cwd(), "migrations");
  const migrationFiles = readdirSync(directory).filter((file) => file.endsWith(".sql")).sort();
  for (const file of migrationFiles) {
    const match = /^([0-9]+)_/.exec(file);
    if (!match) throw new Error(`Invalid migration filename: ${file}`);
    const version = Number(match[1]);
    const current = db.prepare("PRAGMA user_version").get() as { user_version: number };
    if (version <= current.user_version) continue;
    const sql = readFileSync(resolve(directory, file), "utf8");
    db.exec("BEGIN");
    try {
      db.exec(sql);
      db.exec("COMMIT");
    } catch (error) {
      db.exec("ROLLBACK");
      throw error;
    }
  }
}
