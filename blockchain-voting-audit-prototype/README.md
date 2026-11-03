# Transparent Ballot Audit Prototype

A local-development Solidity ballot and a TypeScript event-log replay helper. The contract supports owner-managed voter eligibility, a fixed voting window, one vote per registered address, candidate totals, and on-chain audit events.

## Build and test

Requirements: Foundry (Forge/Anvil), Node.js 24, and npm.

```sh
forge fmt --check
forge test -vvv
npm ci
npm run build
npm test
```

Foundry tests run contract scenarios in a local EVM. `forge test` uses no public chain, RPC endpoint, wallet, or deployed contract. The TypeScript `replayVotes` helper checks decoded `VoteCast` logs for candidate bounds, address format, duplicate addresses, and deterministic chain ordering.

## Contract behavior

The owner creates a ballot with 2–16 unique candidate labels and future open/close times, then registers eligible addresses before voting opens. Eligible addresses can cast one vote during the half-open interval `[opensAt, closesAt)`. Anyone can inspect public totals; the owner can finalize after the deadline. Contract events record registration, voter/candidate choice, and closure.

## Prototype limits

This is not suitable for public elections. Candidate choices and voter addresses are public on-chain; there is no ballot secrecy, identity proof, coercion resistance, sybil resistance, accessibility audit, legal certification, or production key management. One address can vote once, but an administrator can register multiple addresses for one person. Use only synthetic test ballots on a local chain. Do not connect real voter data, production wallets, or public-election processes.

## Contribution and license

Use the repository's [contribution guidance](../CONTRIBUTING.md). This project is distributed under the repository's [license](../LICENSE).
