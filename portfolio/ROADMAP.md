# Polymath portfolio roadmap

The portfolio is developed in small, demonstrable releases. A project is called complete only when its documented core workflow is implemented and usable; entries below are proposed scope, not claims of completion.

## Stage 1 — foundations

- **01 Polymath OS — usable first release:** personal goals, projects, notes, habit check-ins/streaks, search, relationship graph, reminders, analytics, JSON export/import, editing endpoints, and local SQLite storage. Restore is restricted to a fresh workspace.
- **12 Developer and Office Automation Toolkit — usable first release:** CSV audit, grouped Markdown reports, preview-first file sorting, ZIP backup with checksum manifest (without following symlinks or exposing absolute source paths), structured JSONL operation logs for sorting/backups, a streaming archive/path verifier, and a documented recovery drill.

## Stage 2 — practical applications

- **03 Personal Finance and Wealth Analytics — usable first release:** local rand-based ledger, budgets, savings goals, debt balances/payments, monthly cash-flow/savings-rate summary, net-worth snapshots, assumption-based scenarios, transaction editing, and CSV export.
- **04 SME Business Management System — usable first release:** local products, customers, editable draft quotes, atomic stock-check and invoice issue, paid-status transitions, role keys, audit events, stock adjustment ledger, CSV exports, and low-stock/revenue report.
- **09 E-commerce and Booking Platform — usable first release:** service catalogue, timezone-aware availability slots, scrypt-backed accounts, optional one-time email verification with SMTP delivery, expiring/revocable sessions, own-booking view/cancellation, admin-key protected management, overlap prevention, configurable weekday calendars, idempotent success/decline payment simulation, and persistent per-client request limits. The simulator is not a processor sandbox; real provider integration requires choosing a processor.

## Stage 3 — specialisation

- **02 AI Research and Knowledge Assistant — usable retrieval release:** bounded local text/Markdown imports (100 KB), source metadata, lexical ranking, extractive summaries, deletion, unanswered-question tracking, an offline labeled retrieval evaluator that validates document labels, and optional explicitly configured grounded generation. Answer-quality still requires human review; generated output stays distinct from cited source passages.
- **05 Cybersecurity Monitoring and Log Analyzer — usable CLI release:** SSH/PAM log parsing, configurable threshold/suppression rule packs, repeated-failure and success-after-failure alerts, source timeline, input hash, reviewed suppressions, response notes, and synthetic sample. Detection is heuristic and remains limited to authentication events.
- **06 Adaptive Learning and Tutoring Platform — usable first release:** instructor-authored lessons with HTTPS source attribution and verification dates, quizzes, stored attempts, keyboard-accessible UI, measured WCAG AA text contrast, tag-based suggestions, and spaced review dates. CI now runs axe-core and a keyboard quiz/reflow browser check in Chromium; manual TalkBack and true 200% zoom testing remains a release check.
- **08 Legal Research and Case Management Toolkit — usable first release:** matters, source records, passage-linked notes, searchable case/source/document/deadline records, versioned document metadata, and closable deadlines.

## Stage 4 — professional engineering

- **10 API and Integration Hub — usable first release:** versioned event ingestion, scoped comma-rotatable keys, persistent per-key rate buckets, validation, idempotency, local event storage, and an opt-in resumable HTTPS webhook dispatcher.
- **13 Cloud Deployment and DevOps Demonstrator — container and CI ready:** non-root Polymath Enterprise image, hardened loopback Compose service, persistent data volume, health check, GitHub Actions build/config/smoke workflow, administrator-only backup export, backup script, and deployment runbook. A Render Blueprint now configures the service, health check, generated role secrets, and persistent disk; provisioning it requires a connected Render account and approval of the paid service cost.
- **14 Open-Source Contribution Portfolio — usable CLI release:** local contribution journal, validated issue/PR URLs, Markdown showcase, review-state and verification fields.

## Stage 5 — analysis, access, and integration

- **07 South African Open-Data Intelligence Platform — usable local report generator:** validates tidy CSVs and creates a standalone interactive area/year report. Real-data reports require and display HTTPS source URL, access date, units, indicator definitions, coverage, and missing-data handling; sample values are synthetic.
- **11 Accessible Multilingual Services Portal — usable content catalogue:** ten South African language codes, HTTPS source records, verification dates, keyboard-accessible responsive browsing, a fluent-review queue that withholds non-English entries until approved, and an optional idempotent English seed pack of official employment/education links checked 2026-10-17. The seed intentionally makes no translations; those require fluent-speaker review.
- **15 Polymath Enterprise — usable capstone:** browser administration, customers, products, stock ledger, atomic sales, expenses, role-checked keys, audit records, monthly analytics, explainable expense anomaly candidates, security report import from project 05, source evidence from project 02, idempotent event feed for project 10, administrator-only JSON backup, database readiness check, and admin-protected Prometheus metrics. A host-specific restore procedure remains deployment work.

## Delivery standard

Each substantial project should include a problem statement, intended users, setup and usage instructions, screenshots or a demo, meaningful verification, architecture and decision notes, security and accessibility considerations, known limitations, and attribution for dependencies or borrowed material. Use synthetic data by default; never commit credentials or private data.

## Stage 6 — IT operations, security, and portfolio (projects 16–25)

- **16 Personal Cybersecurity Command Center — local first release:** import offline SSH/PAM analyzer findings into SQLite, deduplicate source files by SHA-256, review/close alerts with notes; does not retain raw logs or run continuously.
- **17 Network Diagnostic Toolkit — bounded CLI release:** resolve one hostname, optionally test one TCP port and a capped ICMP count, show route when available, export JSON; no network/port scanning.
- **18 AI IT Helpdesk Assistant — cited support API:** offline keyword retrieval over a small approved article set, source IDs, fallback to human support, SQLite tickets, optional explicitly configured OpenAI-compatible endpoint; no autonomous commands.
- **19 Password Security Lab — CLI learning release:** hidden password prompt, Argon2id and bcrypt support when installed, standard-library scrypt fallback, verification and transparent composition hints; hashes and credentials are never stored.
- **20 PC Health Monitor — local sampler:** optional psutil CPU/memory/disk metrics, thresholds and SQLite history; no telemetry or fleet collection.
- **21 Mini Cloud Infrastructure Lab — container/CI release:** non-root standard-library HTTP service, read-only container, health endpoint, persistent SQLite volume, loopback-only Compose port.
- **22 Vulnerability Management Dashboard — offline tracker:** import local CVE JSON, validate IDs, track triage states and notes; does not fetch feeds or determine exploitability.
- **23 Automated Software Testing Lab — test practice release:** pure sample ticket service, boundary/parameterized pytest examples, dedicated CI job.
- **24 IT Asset Management System — local API release:** FastAPI/SQLite asset create/search/update and audit history; no identity provider or internet exposure.
- **25 IT/CS Portfolio Command Center — static showcase:** searchable project catalogue, category filters, responsive accessible UI; links to project docs without implying live deployment.

Projects 16–25 are independent educational demos. The security and networking projects are for authorized defensive administration only. Optional dependencies and operational boundaries are documented in each project README.
