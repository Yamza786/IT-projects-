import assert from 'node:assert/strict';
import { afterEach, beforeEach, describe, it } from 'node:test';
import { createServer } from 'node:http';
import { DatabaseSync } from 'node:sqlite';
import { createApp } from '../dist/app.js';
import { migrate } from '../dist/database.js';

describe('SaaS management API', () => {
  let db;
  let server;
  let baseUrl;
  let adminCookie;
  let tenantId;

  async function call(path, { method = 'GET', cookie, body } = {}) {
    const headers = {};
    if (cookie) headers.cookie = cookie;
    if (body !== undefined) headers['content-type'] = 'application/json';
    const response = await fetch(`${baseUrl}${path}`, {
      method,
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const text = await response.text();
    return { status: response.status, headers: response.headers, body: text ? JSON.parse(text) : undefined };
  }

  beforeEach(async () => {
    db = new DatabaseSync(':memory:');
    db.exec('PRAGMA foreign_keys = ON');
    migrate(db);
    const app = await createApp({
      db,
      sessionTtlHours: 12,
      secureCookies: false,
      bootstrapEmail: 'admin@example.test',
      bootstrapPassword: 'correct-horse-battery-1',
    });
    server = createServer(app);
    await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
    const address = server.address();
    baseUrl = `http://127.0.0.1:${address.port}`;

    const login = await call('/auth/login', {
      method: 'POST',
      body: { email: 'ADMIN@example.test', password: 'correct-horse-battery-1' },
    });
    assert.equal(login.status, 200);
    adminCookie = login.headers.get('set-cookie').split(';')[0];
    const tenant = await call('/tenants', {
      method: 'POST', cookie: adminCookie,
      body: { name: 'Acme Group', slug: 'acme-group' },
    });
    tenantId = tenant.body.tenant.id;
    const user = await call('/users', {
      method: 'POST', cookie: adminCookie,
      body: { email: 'member@example.test', password: 'member-password-1' },
    });
    assert.equal(user.status, 201);
  });

  afterEach(async () => {
    server.closeAllConnections();
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    db.close();
  });

  it('requires authentication and rejects invalid credentials', async () => {
    assert.equal((await call('/tenants')).status, 401);
    assert.equal((await call('/auth/login', {
      method: 'POST', body: { email: 'admin@example.test', password: 'wrong' },
    })).status, 401);
    assert.equal((await call('/auth/login', {
      method: 'POST', body: { email: 'not-an-email', password: 'x' },
    })).status, 400);
  });

  it('creates tenant, owner membership, starter subscription and audit record', async () => {
    const tenants = await call('/tenants', { cookie: adminCookie });
    assert.equal(tenants.status, 200);
    assert.equal(tenants.body.tenants.length, 1);
    const members = await call(`/tenants/${tenantId}/members`, { cookie: adminCookie });
    assert.ok(members.body.members.some((member) => member.role === 'OWNER' && member.email === 'admin@example.test'));
    const subscription = await call(`/tenants/${tenantId}/subscription`, { cookie: adminCookie });
    assert.deepEqual(subscription.body.subscription, { plan: 'FREE', status: 'TRIAL', seats: 3, updatedAt: subscription.body.subscription.updatedAt });
    const audit = await call(`/tenants/${tenantId}/audit`, { cookie: adminCookie });
    assert.ok(audit.body.events.some((event) => event.action === 'tenant.created'));
  });

  it('enforces tenant roles on membership and billing operations', async () => {
    assert.equal((await call(`/tenants/${tenantId}/members`, {
      method: 'POST', cookie: adminCookie,
      body: { email: 'member@example.test', role: 'VIEWER' },
    })).status, 201);
    const login = await call('/auth/login', {
      method: 'POST', body: { email: 'member@example.test', password: 'member-password-1' },
    });
    const cookie = login.headers.get('set-cookie').split(';')[0];
    assert.equal((await call(`/tenants/${tenantId}`, { cookie })).status, 200);
    assert.equal((await call(`/tenants/${tenantId}/subscription`, { cookie })).status, 200);
    assert.equal((await call(`/tenants/${tenantId}/subscription`, {
      method: 'PUT', cookie,
      body: { plan: 'GROWTH', status: 'ACTIVE', seats: 20 },
    })).status, 403);
    assert.equal((await call(`/tenants/${tenantId}/audit`, { cookie })).status, 403);
    assert.equal((await call('/tenants', { cookie })).body.tenants.length, 1);
  });

  it('allows billing members to update a validated subscription', async () => {
    await call(`/tenants/${tenantId}/members`, {
      method: 'POST', cookie: adminCookie,
      body: { email: 'member@example.test', role: 'BILLING' },
    });
    const login = await call('/auth/login', {
      method: 'POST', body: { email: 'member@example.test', password: 'member-password-1' },
    });
    const cookie = login.headers.get('set-cookie').split(';')[0];
    const update = await call(`/tenants/${tenantId}/subscription`, {
      method: 'PUT', cookie, body: { plan: 'GROWTH', status: 'ACTIVE', seats: 20 },
    });
    assert.equal(update.status, 200);
    assert.equal(update.body.subscription.plan, 'GROWTH');
    assert.equal((await call(`/tenants/${tenantId}/subscription`, {
      method: 'PUT', cookie, body: { plan: 'GROWTH', status: 'ACTIVE', seats: 0 },
    })).status, 400);
  });

  it('hashes stored session tokens and revokes logout sessions', async () => {
    const login = await call('/auth/login', {
      method: 'POST', body: { email: 'admin@example.test', password: 'correct-horse-battery-1' },
    });
    const cookie = login.headers.get('set-cookie').split(';')[0];
    const rawToken = cookie.slice('saas_session='.length);
    const storedTokens = db.prepare('SELECT token_hash FROM sessions').all();
    assert.ok(storedTokens.every(({ token_hash }) => token_hash !== rawToken));
    assert.equal((await call('/auth/logout', { method: 'POST', cookie })).status, 204);
    assert.equal((await call('/auth/me', { cookie })).status, 401);
  });
});
