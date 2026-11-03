import test from "node:test";
import assert from "node:assert/strict";
import { replayVotes } from "../dist/audit.js";

test("replays votes in chain order and counts candidates", () => {
  const result = replayVotes([
    { blockNumber: 2, transactionIndex: 0, logIndex: 0, voter: "0x0000000000000000000000000000000000000002", candidateId: 1 },
    { blockNumber: 1, transactionIndex: 0, logIndex: 0, voter: "0x0000000000000000000000000000000000000001", candidateId: 0 },
  ], 2);
  assert.deepEqual(result, { counts: [1, 1], totalVotes: 2, voterCount: 2 });
});

test("rejects duplicate voters and out-of-range candidates", () => {
  const voter = "0x0000000000000000000000000000000000000001";
  assert.throws(() => replayVotes([
    { blockNumber: 1, transactionIndex: 0, logIndex: 0, voter, candidateId: 0 },
    { blockNumber: 2, transactionIndex: 0, logIndex: 0, voter: voter.toUpperCase().replace("0X", "0x"), candidateId: 1 },
  ], 2), /duplicate voter/);
  assert.throws(() => replayVotes([
    { blockNumber: 1, transactionIndex: 0, logIndex: 0, voter, candidateId: 2 },
  ], 2), /unknown candidate/);
});
