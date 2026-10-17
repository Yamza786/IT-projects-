# Polymath portfolio roadmap

The portfolio is developed in small, demonstrable releases. A project is called complete only when its documented core workflow is implemented and usable; entries below are proposed scope, not claims of completion.

## Stage 1 — foundations

- **01 Polymath OS — usable first release:** personal goals, projects, notes, habit check-ins/streaks, search, relationship graph, reminders, analytics, JSON export/import, editing endpoints, and local SQLite storage. Restore is restricted to a fresh workspace.
- **12 Developer and Office Automation Toolkit — usable first release:** CSV audit, grouped Markdown reports, preview-first file sorting, ZIP backup with checksum manifest, and a documented recovery drill. Structured operational logs remain a follow-up.

## Stage 2 — practical applications

- **03 Personal Finance and Wealth Analytics — usable first release:** local rand-based ledger, budgets, savings goals, debt balances/payments, monthly cash-flow/savings-rate summary, net-worth snapshots, assumption-based scenarios, transaction editing, and CSV export.
- **04 SME Business Management System — usable first release:** local products, customers, editable draft quotes, atomic stock-check and invoice issue, paid-status transitions, role keys, audit events, stock adjustment ledger, CSV exports, and low-stock/revenue report.
- **09 E-commerce and Booking Platform — usable first release:** service catalogue, timezone-aware availability slots, scrypt-backed accounts, expiring/revocable sessions, own-booking view/cancellation, admin-key protected management, overlap prevention, configurable weekday calendars, and in-memory request throttles. Email verification and a provider-backed payment sandbox remain follow-ups.

## Stage 3 — specialisation

- **02 AI Research and Knowledge Assistant — usable retrieval release:** local text/Markdown imports, source metadata, lexical ranking, extractive summaries, deletion, unanswered-question tracking, an offline labeled retrieval evaluator, and optional explicitly configured grounded generation. Answer-quality still requires human review; generated output stays distinct from cited source passages.
- **05 Cybersecurity Monitoring and Log Analyzer — usable CLI release:** SSH/PAM log parsing, configurable threshold/suppression rule packs, repeated-failure and success-after-failure alerts, source timeline, input hash, reviewed suppressions, response notes, and synthetic sample. Detection is heuristic and remains limited to authentication events.
- **06 Adaptive Learning and Tutoring Platform — usable first release:** instructor-authored lessons with HTTPS source attribution and verification dates, quizzes, stored attempts, accessible UI, tag-based suggestions, and spaced review dates. A broader accessibility review remains a follow-up.
- **08 Legal Research and Case Management Toolkit — usable first release:** matters, source records, passage-linked notes, searchable case/source/document/deadline records, versioned document metadata, and closable deadlines.

## Stage 4 — professional engineering

- **10 API and Integration Hub — usable first release:** versioned event ingestion, scoped comma-rotatable keys, persistent per-key rate buckets, validation, idempotency, and local event storage. Outbound adapters remain a follow-up.
- **13 Cloud Deployment and DevOps Demonstrator — container and CI ready:** non-root Polymath Enterprise image, hardened loopback Compose service, persistent data volume, health check, GitHub Actions build/config/smoke workflow, administrator-only backup export, backup script, and deployment runbook. A monitored live deployment requires selecting a host and configuring its secrets and persistent storage.
- **14 Open-Source Contribution Portfolio — usable CLI release:** local contribution journal, validated issue/PR URLs, Markdown showcase, review-state and verification fields.

## Stage 5 — analysis, access, and integration

- **07 South African Open-Data Intelligence Platform — usable local report generator:** validates tidy CSVs and creates a standalone interactive area/year report. Sample values are synthetic; real datasets must document provenance, definitions, and limitations.
- **11 Accessible Multilingual Services Portal — usable content catalogue:** ten South African language codes, HTTPS source records, verification dates, keyboard-accessible responsive browsing, and translation review guidance. No unverified service claims are seeded.
- **15 Polymath Enterprise — usable capstone:** browser administration, customers, products, stock ledger, atomic sales, expenses, role-checked keys, audit records, monthly analytics, explainable expense anomaly candidates, security report import from project 05, source evidence from project 02, idempotent event feed for project 10, and administrator-only JSON backup. Production monitoring and a provider-specific restore procedure remain deployment work.

## Delivery standard

Each substantial project should include a problem statement, intended users, setup and usage instructions, screenshots or a demo, meaningful verification, architecture and decision notes, security and accessibility considerations, known limitations, and attribution for dependencies or borrowed material. Use synthetic data by default; never commit credentials or private data.
