import { spawnSync } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test as nodeTest } from 'node:test';
import { check, runSuite } from '../src/testkit.mjs';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));

nodeTest('suite runner accepts filters and rejects empty matches', async () => {
  const results = await runSuite({ files: [], filter: 'never registered' });
  check.equal(results.length, 1);
  check.equal(results[0].ok, false);
});

nodeTest('CLI runs example tests and emits valid JSON results', () => {
  const result = spawnSync(process.execPath, ['bin/run-tests.mjs', '--reporter=json', 'examples/calculator.test.mjs'], { cwd: root, encoding: 'utf8' });
  check.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  check.equal(report.total, 3);
  check.equal(report.failed, 0);
});

nodeTest('CLI exits nonzero when a user test fails', async () => {
  const directory = await mkdtemp(resolve(tmpdir(), 'testkit-failure-'));
  try {
    const file = resolve(directory, 'broken.test.mjs');
    await writeFile(file, "import { test, check } from '" + resolve(root, 'src/testkit.mjs') + "'; test('known failure', () => check.equal(1, 2));\n");
    const result = spawnSync(process.execPath, ['bin/run-tests.mjs', '--reporter=json', file], { cwd: root, encoding: 'utf8' });
    check.equal(result.status, 1);
    check.equal(JSON.parse(result.stdout).failed, 1);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
