#!/usr/bin/env node
import { runSuite } from '../src/testkit.mjs';

const args = process.argv.slice(2);
let reporter = 'tap';
let filter = '';
const files = [];
for (const arg of args) {
  if (arg.startsWith('--reporter=')) reporter = arg.slice('--reporter='.length);
  else if (arg.startsWith('--filter=')) filter = arg.slice('--filter='.length);
  else if (arg.startsWith('--')) {
    process.stderr.write(`Unknown option: ${arg}\n`);
    process.exit(2);
  } else files.push(arg);
}
try {
  const results = await runSuite({ files, reporter, filter });
  if (results.some((result) => !result.ok)) process.exitCode = 1;
} catch (error) {
  process.stderr.write(`testkit: ${error?.stack ?? error}\n`);
  process.exitCode = 2;
}
