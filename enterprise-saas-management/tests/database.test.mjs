import assert from 'node:assert/strict';
import { after, describe, it } from 'node:test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { migrate, openDatabase } from '../dist/database.js';

describe('SQLite migrations', () => {
  const directory = mkdtempSync(join(tmpdir(), 'saas-migration-test-'));
  const db = openDatabase(join(directory, 'test.sqlite'));

  after(() => {
    db.close();
    rmSync(directory, { recursive: true, force: true });
  });

  it('applies the initial schema to a file database and safely reruns', () => {
    migrate(db);
    migrate(db);
    const version = db.prepare('PRAGMA user_version').get().user_version;
    const tables = db.prepare("SELECT name FROM sqlite_master WHERE type = 'table'").all().map((row) => row.name);
    assert.equal(version, 1);
    assert.ok(tables.includes('tenants'));
    assert.ok(tables.includes('memberships'));
    assert.ok(tables.includes('audit_events'));
  });
});
