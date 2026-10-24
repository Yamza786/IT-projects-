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
  const sqlFiles = readdirSync(directory).filter((file) => file.endsWith(".sql")).sort();
  const files = sqlFiles.filter((file) => /^\d{3}_[a-z0-9_]+\.sql$/.test(file));
  if (files.length !== sqlFiles.length) throw new Error("Migration SQL filename must use NNN_lowercase_name.sql");
  const versions = files.map((file) => Number(file.slice(0, 3)));
  if (files.length === 0 || versions.some((version, index) => version !== index + 1)) {
    throw new Error("Migration files must start at 001 and be contiguous");
  }
  for (const file of files) {
    const version = Number(file.slice(0, 3));
    const current = db.prepare("PRAGMA user_version").get() as { user_version: number };
    if (version <= current.user_version) continue;
    const sql = readFileSync(resolve(directory, file), "utf8");
    db.exec("BEGIN IMMEDIATE");
    try {
      db.exec(sql);
      const applied = db.prepare("PRAGMA user_version").get() as { user_version: number };
      if (applied.user_version !== version) throw new Error(`Migration ${file} must set PRAGMA user_version = ${version}`);
      db.exec("COMMIT");
    } catch (error) {
      db.exec("ROLLBACK");
      throw error;
    }
  }
}
