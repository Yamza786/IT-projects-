# IT-projects-

A portfolio repository containing 25 practical, independently runnable applications alongside educational examples and starter templates. The portfolio demonstrates local-first product design, full-stack workflows, data analysis, defensive security, accessibility, integration, and deployment practice.

## The 15-project portfolio

| # | Project | Demonstrates |
|---|---|---|
| 01 | [Polymath OS](polymath-os/README.md) | Personal goals, notes, habits, graph, reminders, export and guarded restore |
| 02 | [Research Assistant](research-assistant/README.md) | Document retrieval, source citations, evaluation, optional grounded generation |
| 03 | [Personal Finance](personal-finance/README.md) | Rand ledger, budgets, debt, net worth, scenarios, exports |
| 04 | [SME Manager](sme-manager/README.md) | Inventory, quotations, invoices, audit trails and reports |
| 05 | [Security Log Analyzer](security-log-analyzer/README.md) | Offline SSH/PAM log parsing, rules, suppressions and incident reports |
| 06 | [Adaptive Learning](adaptive-learning/README.md) | Lessons, quizzes, explainable practice recommendations and review schedule |
| 07 | [South African Open Data](sa-open-data/README.md) | Validated CSV data, interactive reports and source provenance |
| 08 | [Legal Research](legal-research/README.md) | Case/source organization, passage-linked notes, versions and deadlines |
| 09 | [Booking Platform](booking-platform/README.md) | Accounts, timezone-aware availability, overlap checks and payment simulation |
| 10 | [Integration Hub](integration-hub/README.md) | Versioned events, key scopes, idempotency, rate limits and webhooks |
| 11 | [Accessible Services Portal](accessible-portal/README.md) | Multilingual catalogue, official sources and translation review gate |
| 12 | [Developer Toolkit](developer-toolkit/README.md) | CSV utilities, preview-first file operations, verified backups |
| 13 | [DevOps Demonstrator](devops-demo/README.md) | Hardened container, Compose, CI build and smoke deployment |
| 14 | [Contribution Portfolio](contribution-portfolio/README.md) | Evidence-based contribution journal and showcase generation |
| 15 | [Polymath Enterprise](polymath-enterprise/README.md) | Integrated SME workflows, roles, audit, analytics and event export |

The staged implementation record is in [portfolio/ROADMAP.md](portfolio/ROADMAP.md); architecture choices, trade-offs, and system boundaries are in [portfolio/ARCHITECTURE.md](portfolio/ARCHITECTURE.md). All projects are learning-scale examples. Their individual READMEs describe local setup, intended workflows, and limitations.

## IT operations and security projects (16–25)

| # | Project | Demonstrates |
|---|---|---|
| 16 | [Personal Cybersecurity Command Center](personal-cybersecurity-center/README.md) | Local log ingestion, transparent alerts, acknowledgements and incident notes |
| 17 | [Network Diagnostic Toolkit](network-diagnostics/README.md) | Safe DNS, TCP, ICMP and route diagnostics with structured reports |
| 18 | [AI IT Helpdesk Assistant](ai-it-helpdesk/README.md) | Cited local troubleshooting knowledge, ticket tracking and optional LLM adapter |
| 19 | [Password Security Lab](password-security-lab/README.md) | Argon2/bcrypt password hashing, verification and safe password-strength guidance |
| 20 | [PC Health Monitor](pc-health-monitor/README.md) | Cross-platform system metrics, threshold alerts and history |
| 21 | [Mini Cloud Infrastructure Lab](mini-cloud-lab/README.md) | Docker Compose, health checks, CI build and deployment fundamentals |
| 22 | [Vulnerability Management Dashboard](vulnerability-dashboard/README.md) | CVE import, asset/product matching, triage states and remediation tracking |
| 23 | [Automated Software Testing Lab](software-testing-lab/README.md) | A runnable sample service, pytest unit/API tests and CI quality gates |
| 24 | [IT Asset Management System](it-asset-management/README.md) | Asset lifecycle, assignment, inventory search and audit history |
| 25 | [IT/CS Portfolio Command Center](portfolio-command-center/README.md) | Searchable portfolio dashboard and project metadata workflow |

The first runnable release details are in [portfolio/ROADMAP.md](portfolio/ROADMAP.md). Security and network tools are designed for systems and networks you own or are authorized to assess; they do not perform exploitation or broad network scanning.

## 30-project IT and Computer Science portfolio program

The staged implementation plan, build order, requirements, dependencies, milestones and verification strategy for a new 30-project portfolio program are tracked in [PORTFOLIO_ROADMAP.md](PORTFOLIO_ROADMAP.md). Its project [index](portfolio/INDEX.md) and [skills matrix](portfolio/SKILLS_MATRIX.md) track progress separately from the existing applications above. Projects 1–22 have implementation work, including the [Enterprise SaaS Management Platform](enterprise-saas-management/README.md), [Pocket Ledger Android app](personal-finance-android/README.md), [Network Monitoring Suite](network-monitoring-suite/README.md), [Signal Desk Mini SIEM](mini-siem-platform/README.md), [Relay Arena multiplayer game](multiplayer-3d-game/README.md), [Schema Guard migration toolkit](database-migration-toolkit/README.md), [Hearthline smart home system](smart-home-iot/README.md), [Pipeline Forge CI/CD runner](cicd-automation-platform/README.md), [Market Square marketplace](ecommerce-marketplace/README.md), [SysCare Linux administration toolkit](linux-system-admin-toolkit/README.md), [Vaultsmith password manager](encrypted-password-manager/README.md), [iOS Study Planner](ios-study-planner/README.md), [InfraGuard infrastructure provisioning](cloud-infrastructure-provisioning/README.md), [Phoenix Collaboration Platform](realtime-collaboration-platform/README.md), [BI Workbench](business-intelligence-analytics-engine/README.md), [Browser-Based IDE and Code Runner](browser-ide-code-runner/README.md), [Digital Forensics Toolkit](digital-forensics-toolkit/README.md), the [Blockchain Voting and Audit Prototype](blockchain-voting-audit-prototype/README.md), the [API Gateway and Rate-Limiting Service](api-gateway-rate-limiter/README.md), the [Computer Vision Application](computer-vision-application/README.md), [TinyLang](custom-programming-language/README.md), and the [Process and Memory Visualizer](process-memory-visualizer/README.md). Project-specific verification and environment constraints are tracked in the roadmap. New work in this program excludes Python; existing repository projects are preserved as-is.

Project 23, the [Desktop Knowledge Manager](desktop-knowledge-manager/README.md), is now in implementation with local SQLite notes, search, an encrypted backup flow, and Flutter desktop CI.

Project 24, the [Enterprise HR and Payroll Prototype](enterprise-hr-payroll/README.md), adds role-separated employee management, fixed-cents calculations, audit events, and CSV reports.

Project 25, [Portfolio Testkit](automated-testing-framework/README.md), provides reusable Node.js test cases, fixtures, assertions, and machine-readable reports.

Project 26, [Cloud File Storage and Synchronization](cloud-file-sync/README.md), implements authenticated resumable chunks, integrity checks, and optimistic file versions.

## Verify the portfolio workflows

Use Python 3.12 or newer and install dependencies with `python -m pip install -r requirements-termux.txt`. Run the same suite as CI:

```sh
python -m pytest tests -q
```

The GitHub Actions workflow also runs Chromium accessibility/keyboard checks for the adaptive-learning app and portfolio dashboard, builds and runs the mini-cloud lab container with health and persistence checks, validates the hardened Compose configuration, and builds the enterprise container. These checks cover documented demo workflows; manual screen-reader, device zoom, production security, and host-specific recovery reviews remain necessary before a public service launch.

## Other repository projects

- [algorithms-python](algorithms-python/README.md) — educational algorithms and tests
- [fastapi-template](fastapi-template/README.md) — minimal application scaffold
- [sys-admin-scripts](sys-admin-scripts/README.md) — systems administration utilities
- [vuln-web-lab](vuln-web-lab/README.md) — intentionally vulnerable local security lab
- [ml-from-scratch](ml-from-scratch/README.md) — introductory machine-learning implementations

Do not deploy the vulnerable lab publicly. Keep credentials, private data, databases, and backups out of Git.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes to the portfolio suite should include focused workflow tests and documentation updates.
