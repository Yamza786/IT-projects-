# Portfolio Testkit

A dependency-free JavaScript test runner for small Node.js projects. It provides registered async tests, strict assertions, cleanup hooks, temporary-directory and loopback HTTP fixtures, name filtering, TAP 13 and JSON reports, and a correct failing exit status.

## Use

```js
import { check, test, temporaryDirectory } from './src/testkit.mjs';

test('writes a test fixture', async (context) => {
  const fixture = await temporaryDirectory(context);
  await fixture.write('input.txt', 'hello');
  check.equal(await fixture.read('input.txt'), 'hello');
});
```

Run project self-tests and the example HTTP/file suite:

```sh
npm test
npm run demo
node bin/run-tests.mjs --reporter=json --filter='HTTP' examples/calculator.test.mjs
```

Use the exported `check` methods for equality, deep equality, truth, matching, synchronous exceptions and rejected promises. Fixture cleanup runs in reverse registration order even if a test fails. Fixture paths cannot escape the generated temporary directory. HTTP fixtures bind only to loopback and are closed after each test.

## Limits

This teaching framework intentionally remains small: no parallel workers, browser driver, coverage instrumentation or snapshot store. Tests within one runner process run sequentially so their fixtures remain deterministic. Node's built-in test runner and assertion package verify the framework itself; no third-party runtime or development dependencies are needed.
