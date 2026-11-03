import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

test("Room 1-to-2 migration preserves legacy budgets and creates recurring tables", () => {
  const sourceUrl = new URL("../app/src/main/java/dev/portfolio/pocketledger/Ledger.kt", import.meta.url);
  const source = readFileSync(sourceUrl, "utf8");
  const start = source.indexOf("val MIGRATION_1_2 = object");
  const end = source.indexOf("\nclass LedgerRepository", start);
  assert.notEqual(start, -1, "migration declaration exists");
  assert.notEqual(end, -1, "migration ends before repository declaration");
  const migrationSource = source.slice(start, end);
  const statements = [...migrationSource.matchAll(/database\.execSQL\("((?:\\.|[^"\\])*)"\)/g)]
    .map((match) => JSON.parse(`"${match[1]}"`));
  assert.equal(statements.length, 7, "all production migration SQL statements were extracted");

  const db = new DatabaseSync(":memory:");
  try {
    db.exec("PRAGMA foreign_keys=ON");
    db.exec("CREATE TABLE budgets (month TEXT NOT NULL, category TEXT NOT NULL, limitMinor INTEGER NOT NULL, currency TEXT NOT NULL, PRIMARY KEY(month,category))");
    db.exec("INSERT INTO budgets VALUES ('2026-10','Food',50000,'USD')");
    db.exec("BEGIN IMMEDIATE");
    for (const sql of statements) db.exec(sql);
    db.exec("COMMIT");

    const budget = Object.fromEntries(Object.entries(db.prepare("SELECT month,category,limitMinor,currency FROM budgets").get()));
    assert.deepEqual(budget, { month: "2026-10", category: "Food", limitMinor: 50000, currency: "USD" });
    const primaryKeys = db.prepare("PRAGMA table_info(budgets)").all()
      .filter((column) => column.pk > 0)
      .sort((left, right) => left.pk - right.pk)
      .map((column) => column.name);
    assert.deepEqual(primaryKeys, ["month", "category", "currency"]);

    const foreignKey = db.prepare("PRAGMA foreign_key_list(recurrence_receipts)").get();
    assert.equal(foreignKey.table, "recurring_rules");
    db.exec("INSERT INTO recurring_rules(amountMinor,currency,kind,category,memo,frequency,anchorDay,nextRunOn,active) VALUES (2500,'USD','EXPENSE','Transport','pass','MONTHLY',31,'2026-10-24',1)");
    db.exec("INSERT INTO recurrence_receipts VALUES (1,'2026-10-24',7)");
    assert.equal(db.prepare("SELECT COUNT(*) AS count FROM recurrence_receipts").get().count, 1);
  } finally {
    db.close();
  }
});
