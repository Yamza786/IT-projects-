import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, isAbsolute, relative, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';

const cases = [];

export function test(name, callback) {
  if (typeof name !== 'string' || name.trim() === '' || typeof callback !== 'function') {
    throw new TypeError('test requires a non-empty name and callback');
  }
  cases.push({ name: name.trim(), callback });
}

export const check = Object.freeze({
  equal: assert.equal,
  deepEqual: assert.deepEqual,
  ok: assert.ok,
  match: assert.match,
  throws: assert.throws,
  rejects: assert.rejects,
});

export async function temporaryDirectory(context, prefix = 'testkit-') {
  const directory = await mkdtemp(resolve(tmpdir(), prefix));
  context.cleanup(() => rm(directory, { recursive: true, force: true }));
  return Object.freeze({
    path: directory,
    async write(name, contents) {
      const target = resolve(directory, name);
      const rel = relative(directory, target);
      if (rel === '' || rel === '..' || rel.startsWith(`..${sep}`) || isAbsolute(rel)) {
        throw new Error('fixture path must stay inside its temporary directory');
      }
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, contents, { flag: 'wx' });
      return target;
    },
    read: (name) => readFile(resolve(directory, name), 'utf8'),
  });
}

export async function httpFixture(context, handler) {
  if (typeof handler !== 'function') throw new TypeError('HTTP fixture requires a handler');
  const server = createServer(handler);
  await new Promise((resolveListen, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolveListen);
  });
  const address = server.address();
  if (address === null || typeof address === 'string') throw new Error('HTTP fixture did not bind a TCP port');
  context.cleanup(() => new Promise((resolveClose, reject) => {
    server.close((error) => error ? reject(error) : resolveClose());
    server.closeAllConnections();
  }));
  return Object.freeze({ server, url: `http://127.0.0.1:${address.port}` });
}

export async function runSuite({ files = [], reporter = 'tap', filter = '' } = {}) {
  cases.length = 0;
  for (const file of files) await import(pathToFileURL(resolve(file)).href);
  const selected = cases.filter(({ name }) => name.includes(filter));
  const results = [];
  for (const item of selected) {
    const cleanups = [];
    const context = Object.freeze({ cleanup(callback) {
      if (typeof callback !== 'function') throw new TypeError('cleanup requires a function');
      cleanups.push(callback);
    } });
    const startedAt = performance.now();
    let error;
    try { await item.callback(context); } catch (caught) { error = caught; }
    for (const cleanup of cleanups.reverse()) {
      try { await cleanup(); } catch (caught) { error ??= caught; }
    }
    results.push({ name: item.name, ok: error === undefined, durationMs: Number((performance.now() - startedAt).toFixed(2)), ...(error === undefined ? {} : { error: String(error?.stack ?? error) }) });
  }
  if (selected.length === 0) results.push({ name: 'No matching tests were registered', ok: false, durationMs: 0 });
  report(results, reporter);
  return results;
}

function report(results, reporter) {
  const failed = results.filter((result) => !result.ok).length;
  if (reporter === 'json') {
    process.stdout.write(`${JSON.stringify({ total: results.length, passed: results.length - failed, failed, tests: results }, null, 2)}\n`);
    return;
  }
  if (reporter !== 'tap') throw new TypeError(`unknown reporter: ${reporter}`);
  process.stdout.write(`TAP version 13\n1..${results.length}\n`);
  results.forEach((result, index) => {
    process.stdout.write(`${result.ok ? 'ok' : 'not ok'} ${index + 1} - ${result.name} # time=${result.durationMs}ms\n`);
    if (result.error) process.stdout.write(`  ---\n  message: ${JSON.stringify(result.error)}\n  ...\n`);
  });
  process.stdout.write(`# tests ${results.length}\n# pass ${results.length - failed}\n# fail ${failed}\n`);
}
