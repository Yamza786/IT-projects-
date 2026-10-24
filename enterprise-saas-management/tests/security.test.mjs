import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { loadConfig } from '../dist/config.js';
import { digestToken, hashPassword, newSessionToken, verifyPassword } from '../dist/security.js';

describe('security primitives', () => {
  it('creates salted password hashes and verifies without storing plaintext', async () => {
    const first = await hashPassword('a-long-test-password');
    const second = await hashPassword('a-long-test-password');
    assert.notEqual(first, second);
    assert.ok(!first.includes('a-long-test-password'));
    assert.equal(await verifyPassword('a-long-test-password', first), true);
    assert.equal(await verifyPassword('incorrect-password', first), false);
  });

  it('generates high-entropy session tokens and stable SHA-256 digests', () => {
    const token = newSessionToken();
    assert.equal(token.length, 43);
    assert.equal(digestToken(token), digestToken(token));
    assert.notEqual(digestToken(token), token);
  });

  it('validates configuration and requires bootstrap credentials as a pair', () => {
    assert.equal(loadConfig({ DATABASE_PATH: ':memory:', BOOTSTRAP_EMAIL: 'owner@example.test', BOOTSTRAP_PASSWORD: 'long-enough-password' }).PORT, 3000);
    assert.throws(() => loadConfig({ DATABASE_PATH: ':memory:', BOOTSTRAP_EMAIL: 'owner@example.test' }));
  });
});
