export type VoteEvent = {
  blockNumber: number;
  transactionIndex: number;
  logIndex: number;
  voter: string;
  candidateId: number;
};

export type AuditSummary = {
  counts: number[];
  totalVotes: number;
  voterCount: number;
};

export function replayVotes(events: VoteEvent[], candidateCount: number): AuditSummary {
  if (!Number.isInteger(candidateCount) || candidateCount < 2 || candidateCount > 16) {
    throw new Error("candidate count must be between 2 and 16");
  }
  const ordered = [...events].sort((a, b) => a.blockNumber - b.blockNumber ||
    a.transactionIndex - b.transactionIndex || a.logIndex - b.logIndex);
  const counts = Array.from({ length: candidateCount }, () => 0);
  const voters = new Set<string>();
  for (const event of ordered) {
    if (!Number.isInteger(event.candidateId) || event.candidateId < 0 || event.candidateId >= candidateCount) {
      throw new Error("vote event references an unknown candidate");
    }
    if (!/^0x[0-9a-fA-F]{40}$/.test(event.voter)) throw new Error("vote event has an invalid voter address");
    const voter = event.voter.toLowerCase();
    if (voters.has(voter)) throw new Error("duplicate voter event detected");
    voters.add(voter);
    counts[event.candidateId] += 1;
  }
  return { counts, totalVotes: ordered.length, voterCount: voters.size };
}
