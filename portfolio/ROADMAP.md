# Polymath portfolio roadmap

The portfolio is developed in small, demonstrable releases. A project is called complete only when its documented core workflow is implemented and usable; entries below are proposed scope, not claims of completion.

## Stage 1 — foundations

- **01 Polymath OS — usable first release:** personal goals, projects, notes, habit check-ins/streaks, search, relationship graph, reminders, analytics, JSON export, and local SQLite storage. Next: editing flows and import.
- **12 Developer and Office Automation Toolkit — usable first release:** CSV audit, grouped Markdown reports, preview-first file sorting, and ZIP backup with checksum manifest. Next: structured operational logs and recovery guides.

## Stage 2 — practical applications

- **03 Personal Finance and Wealth Analytics — usable first release:** local rand-based ledger, budgets, savings goals, debt balances/payments, monthly cash-flow/savings-rate summary, net-worth snapshots, and explicitly assumption-based scenarios. Next: transaction edits and exports.
- **04 SME Business Management System — usable first release:** local products, customers, draft quotes, atomic stock-check and invoice issue, paid-status transitions, audit events, stock adjustment ledger, and low-stock/revenue report. Next: role permissions, quotation editing, and exports.
- **09 E-commerce and Booking Platform — usable first release:** service catalogue, timezone-aware availability slots, scrypt-backed accounts, expiring/revocable sessions, own-booking view/cancellation, admin-key protected management, overlap prevention, and in-memory request throttles. Next: account verification, configurable calendars, and payment sandbox.

## Stage 3 — specialisation

- **02 AI Research and Knowledge Assistant — usable retrieval release:** local document capture, source-passage citations, lexical ranking, extractive summaries, deletion, and unanswered-question tracking. Next: supported document imports, privacy controls, and retrieval evaluation; no generated answers are presented as evidence.
- **05 Cybersecurity Monitoring and Log Analyzer — usable CLI release:** SSH log parsing, repeated-failure and success-after-failure alerts, source timeline, input hash, reviewed suppressions, response notes, and synthetic sample. Next: configurable rule packs and broader log formats.
- **06 Adaptive Learning and Tutoring Platform — usable first release:** reviewed sample lesson, instructor-authored quizzes, stored attempts, accessible UI, tag-based suggestions, and spaced review dates. Next: lesson-source citations and richer accessibility review.
- **08 Legal Research and Case Management Toolkit — usable first release:** matters, source records, passage-linked notes, versioned document metadata, and closable deadlines. Next: search and deeper document workflows.

## Stage 4 — professional engineering

- **10 API and Integration Hub — usable first release:** versioned event ingestion, scoped keys, rate limits, validation, idempotency, and local event storage. Next: persistent gateway-level rate limits, credential rotation, and outbound adapters.
- **13 Cloud Deployment and DevOps Demonstrator — container and CI ready:** non-root Polymath Enterprise image, persistent data volume, health check, GitHub Actions build and smoke workflow, and deployment runbook. Next: a monitored deployment to a chosen host.
- **14 Open-Source Contribution Portfolio — usable CLI release:** local contribution journal, validated issue/PR URLs, and Markdown showcase. Next: richer review and verification fields.

## Stage 5 — analysis, access, and integration

- **07 South African Open-Data Intelligence Platform — usable local report generator:** validates tidy CSVs and creates a standalone interactive area/year report. Sample values are synthetic; real datasets must document provenance, definitions, and limitations.
- **11 Accessible Multilingual Services Portal — usable content catalogue:** ten South African language codes, HTTPS source records, verification dates, keyboard-accessible responsive browsing, and translation review guidance. No unverified service claims are seeded.
- **15 Polymath Enterprise — usable capstone:** browser administration, customers, products, stock ledger, atomic sales, expenses, role-checked keys, audit records, monthly analytics, robust expense anomaly candidates with explanations, security report import from project 05, and idempotent event feed for project 10. Next: evidence links to project 02, export/backup, and production hardening.

## Delivery standard

Each substantial project should include a problem statement, intended users, setup and usage instructions, screenshots or a demo, meaningful verification, architecture and decision notes, security and accessibility considerations, known limitations, and attribution for dependencies or borrowed material. Use synthetic data by default; never commit credentials or private data.
