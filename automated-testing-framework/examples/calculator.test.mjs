import { add } from './calculator.mjs';
import { check, httpFixture, test, temporaryDirectory } from '../src/testkit.mjs';

test('adds integer values and rejects unsafe output', () => {
  check.equal(add(20, 22), 42);
  check.throws(() => add(Number.MAX_SAFE_INTEGER, 2), RangeError);
});

test('provides an isolated temporary file fixture', async (context) => {
  const fixture = await temporaryDirectory(context, 'calculator-fixture-');
  await fixture.write('input/case.txt', 'fixture value');
  check.equal(await fixture.read('input/case.txt'), 'fixture value');
  await check.rejects(fixture.write('../outside.txt', 'blocked'), /inside its temporary directory/);
});

test('starts and closes a loopback HTTP fixture', async (context) => {
  const fixture = await httpFixture(context, (request, response) => {
    response.writeHead(request.url === '/health' ? 200 : 404, { 'content-type': 'text/plain' });
    response.end(request.url === '/health' ? 'ready' : 'missing');
  });
  const response = await fetch(`${fixture.url}/health`);
  check.equal(response.status, 200);
  check.equal(await response.text(), 'ready');
});
