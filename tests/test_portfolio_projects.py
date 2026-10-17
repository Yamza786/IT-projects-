"""Smoke and workflow coverage for the portfolio applications."""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def load_module(project: str, module_name: str):
    path = ROOT / project / "app" / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def open_app(tmp_path: Path, project: str, module_name: str):
    module = load_module(project, module_name)
    module.DB_PATH = tmp_path / f"{module_name}.db"
    with TestClient(module.app) as client:
        yield client, module


def test_polymath_goal_note_graph_and_export(tmp_path):
    with open_app(tmp_path, "polymath-os", "test_polymath") as (client, _):
        assert client.get("/").status_code == 200
        goal = client.post("/api/goals", json={"title": "Learn SQL"}).json()
        note = client.post("/api/notes", json={"title": "Joins", "body": "A join combines related rows."}).json()
        link = client.post("/api/links", json={"source_type": "goal", "source_id": goal["id"],
                                                "target_type": "note", "target_id": note["id"]})
        assert link.status_code == 201
        graph = client.get("/api/graph").json()
        assert len(graph["nodes"]) == 2 and len(graph["edges"]) == 1
        assert client.get("/api/export").json()["format"] == "polymath-os-json-v1"


def test_research_assistant_returns_cited_evidence(tmp_path):
    with open_app(tmp_path, "research-assistant", "test_research") as (client, module):
        module.LLM_URL = ""
        assert client.get("/").status_code == 200
        created = client.post("/api/documents", json={"title": "Evidence notes", "source_uri": "archive:demo",
            "text": "A traceable source and publication date make a claim easier to verify. Correlation alone does not establish causation."})
        assert created.status_code == 201
        answer = client.post("/api/ask", json={"question": "What makes a claim easier to verify?"}).json()
        assert answer["answer_mode"] == "retrieval-only"
        assert answer["results"][0]["source_uri"] == "archive:demo"
        assert "traceable source" in answer["results"][0]["excerpt"]


def test_finance_cashflow_and_debt_payment(tmp_path):
    with open_app(tmp_path, "personal-finance", "test_finance") as (client, _):
        assert client.get("/").status_code == 200
        month = date.today().strftime("%Y-%m")
        client.post("/api/transactions", json={"kind": "income", "category": "Salary", "amount_cents": 200000})
        debt = client.post("/api/debts", json={"name": "Study loan", "balance_cents": 50000}).json()
        paid = client.post(f"/api/debts/{debt['id']}/payments", json={"amount_cents": 10000})
        assert paid.status_code == 201
        summary = client.get("/api/summary", params={"month": month}).json()
        assert summary["income_cents"] == 200000
        assert summary["expense_cents"] == 10000
        assert client.get("/api/debts").json()[0]["balance_cents"] == 40000


def test_sme_quote_issue_deducts_stock_atomically(tmp_path):
    with open_app(tmp_path, "sme-manager", "test_sme") as (client, _):
        assert client.get("/").status_code == 200
        product = client.post("/api/products", json={"sku": "A-1", "name": "Notebook", "unit_price_cents": 2500, "stock": 3}).json()
        customer = client.post("/api/customers", json={"name": "Demo buyer"}).json()
        invoice = client.post("/api/invoices", json={"customer_id": customer["id"], "items":[{"product_id":product["id"],"quantity":2}]}).json()
        issued = client.post(f"/api/invoices/{invoice['id']}/issue")
        assert issued.status_code == 200 and issued.json()["status"] == "issued"
        assert client.get("/api/products").json()[0]["stock"] == 1
        assert client.get("/api/stock-ledger").json()[0]["delta"] == -2
        another = client.post("/api/invoices", json={"customer_id":customer["id"],"items":[{"product_id":product["id"],"quantity":2}]}).json()
        assert client.post(f"/api/invoices/{another['id']}/issue").status_code == 409
        assert client.get("/api/products").json()[0]["stock"] == 1


def test_sme_role_keys_enforce_reader_manager_admin(tmp_path):
    with open_app(tmp_path, "sme-manager", "test_sme_roles") as (client,module):
        module.ROLE_KEYS={"reader":"sme-reader","manager":"sme-manager","admin":"sme-admin"}
        assert client.get("/api/products").status_code==401
        assert client.post("/api/customers",json={"name":"No access"},headers={"X-API-Key":"sme-reader"}).status_code==403
        assert client.post("/api/customers",json={"name":"Allowed"},headers={"X-API-Key":"sme-manager"}).status_code==201
        assert client.get("/api/audit",headers={"X-API-Key":"sme-manager"}).status_code==403
        assert client.get("/api/audit",headers={"X-API-Key":"sme-admin"}).status_code==200


def test_security_analyzer_flags_and_suppresses_documentation_ip():
    spec = importlib.util.spec_from_file_location("test_security_cli", ROOT / "security-log-analyzer" / "analyze.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = ROOT / "security-log-analyzer" / "sample-auth.log"
    report = module.analyze(path, 5)
    assert any(alert["rule"] == "success_after_failures" for alert in report["alerts"])
    quiet = module.analyze(path, 5, {"192.0.2.44"})
    assert not quiet["alerts"]
    assert quiet["timeline"] and quiet["suppressed_sources"] == ["192.0.2.44"]


def test_learning_answer_schedules_next_review(tmp_path):
    with open_app(tmp_path, "adaptive-learning", "test_learning") as (client, _):
        assert client.get("/").status_code == 200
        lesson = client.get("/api/lessons").json()[0]
        question = client.get(f"/api/lessons/{lesson['id']}/quiz").json()[0]
        response = client.post(f"/api/questions/{question['id']}/answer", json={"selected_index": 0})
        assert response.status_code == 200
        assert response.json()["next_review_on"]


def test_legal_research_preserves_source_link_and_document_versions(tmp_path):
    with open_app(tmp_path, "legal-research", "test_legal") as (client, _):
        assert client.get("/").status_code == 200
        case = client.post("/api/cases", json={"title":"Synthetic matter"}).json()
        source = client.post("/api/sources", json={"case_id":case["id"],"title":"Sample statute",
            "issuer":"Synthetic source","locator":"archive:law-1"}).json()
        note = client.post("/api/notes", json={"case_id":case["id"],"source_id":source["id"],
            "claim":"Check this element","passage":"A short synthetic passage."})
        assert note.status_code == 201
        doc = client.post("/api/documents", json={"case_id":case["id"],"title":"Brief.pdf","version":1})
        assert doc.status_code == 201
        assert client.post(f"/api/documents", json={"case_id":case["id"],"title":"Brief.pdf","version":1}).status_code == 409


def test_booking_requires_account_and_rejects_overlap(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKING_ADMIN_KEY", "unused-admin-key")
    with open_app(tmp_path, "booking-platform", "test_booking") as (client, module):
        assert client.get("/").status_code == 200
        account = client.post("/api/accounts", json={"name":"Demo user","email":"demo@example.test","password":"long-demo-password"})
        assert account.status_code == 201
        login = client.post("/api/login", json={"email":"demo@example.test","password":"long-demo-password"}).json()
        headers = {"Authorization":"Bearer "+login["access_token"]}
        start = (datetime.now(timezone.utc)+timedelta(days=3)).replace(hour=10,minute=0,second=0,microsecond=0)
        body = {"service_id":1,"starts_at":start.isoformat()}
        assert client.post("/api/bookings", json=body, headers=headers).status_code == 201
        assert client.post("/api/bookings", json=body, headers=headers).status_code == 409
        assert len(client.get("/api/my-bookings", headers=headers).json()) == 1


def test_integration_hub_idempotency(tmp_path):
    with open_app(tmp_path, "integration-hub", "test_hub") as (client, module):
        module.WRITE_KEY="write-test-key"
        module.READ_KEY="read-test-key"
        headers={"X-API-Key":"write-test-key","Idempotency-Key":"billing-17"}
        event={"external_id":"17","kind":"invoice.paid","occurred_at":"2026-10-17T12:00:00Z","payload":{"total_cents":1200}}
        first=client.post("/api/v1/integrations/billing/events",json=event,headers=headers)
        replay=client.post("/api/v1/integrations/billing/events",json=event,headers=headers)
        assert first.status_code==201 and replay.json()["replayed"] is True
        assert len(client.get("/api/v1/events",headers={"X-API-Key":"read-test-key"}).json())==1


def test_portal_requires_https_source_and_serves_language_filter(tmp_path):
    with open_app(tmp_path, "accessible-portal", "test_portal") as (client, _):
        assert client.get("/").status_code == 200
        payload={"slug":"demo-resource","language":"en","title":"Demo information","summary":"Synthetic text for accessibility review.",
                 "topic":"demo","source_title":"Synthetic publisher","source_url":"https://example.org/resource","verified_on":"2026-10-17"}
        assert client.post("/api/resources",json=payload).status_code==201
        assert len(client.get("/api/resources",params={"language":"en"}).json())==1
        payload["slug"]="bad-link";payload["source_url"]="http://example.org/resource"
        assert client.post("/api/resources",json=payload).status_code==422


def test_enterprise_roles_atomic_sale_and_security_import(tmp_path):
    with open_app(tmp_path, "polymath-enterprise", "test_enterprise") as (client,module):
        assert client.get("/").status_code == 200
        module.KEYS={"reader":"reader-key","manager":"manager-key","admin":"admin-key"}
        reader={"X-API-Key":"reader-key"};manager={"X-API-Key":"manager-key"};admin={"X-API-Key":"admin-key"}
        assert client.post("/api/customers",json={"name":"Demo"},headers=reader).status_code==403
        customer=client.post("/api/customers",json={"name":"Demo"},headers=manager).json()
        product=client.post("/api/products",json={"sku":"D-1","name":"Demo item","price_cents":500,"opening_stock":2},headers=manager).json()
        sale=client.post("/api/sales",json={"customer_id":customer["id"],"items":[{"product_id":product["id"],"quantity":1}]},headers=manager)
        assert sale.status_code==201 and sale.json()["total_cents"]==500
        report={"input_sha256":"a"*64,"events_parsed":3,"alerts":[{"rule":"repeated_failures","severity":"medium","source":"192.0.2.1","failure_count":5,"success_count":0,"evidence_lines":[1,2,3]}]}
        assert client.post("/api/security-reports",json=report,headers=admin).status_code==201
        assert client.get("/api/security-reports",headers=reader).json()[0]["alerts"][0]["source"]=="192.0.2.1"


def test_csv_and_open_data_tools_validate_synthetic_inputs(tmp_path):
    spec=importlib.util.spec_from_file_location("test_open_data",ROOT/"sa-open-data"/"dashboard.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=module.read_data(ROOT/"sa-open-data"/"sample.csv")
    assert len(data)==6 and "Example" in module.build(data,"Demo","Synthetic sample")
    audit_spec=importlib.util.spec_from_file_location("test_csv_audit",ROOT/"developer-toolkit"/"csv_audit.py")
    audit=importlib.util.module_from_spec(audit_spec);audit_spec.loader.exec_module(audit)
    path=tmp_path/"data.csv";path.write_text("name,email\nAda,ada@example.test\n",encoding="utf-8")
    count,issues=audit.audit(path,["name","email"],20)
    assert count==1 and not issues


def test_automation_preview_grouped_report_and_backup(tmp_path,monkeypatch):
    source=tmp_path/"source";source.mkdir();(source/"notes.TXT").write_text("private demo",encoding="utf-8")
    organizer_spec=importlib.util.spec_from_file_location("test_organizer",ROOT/"developer-toolkit"/"organize_files.py")
    organizer=importlib.util.module_from_spec(organizer_spec);organizer_spec.loader.exec_module(organizer)
    planned=organizer.plan(source)
    assert planned[0][1].parent.name=="txt" and (source/"notes.TXT").exists()
    monkeypatch.setattr(sys,"argv",["organize_files.py",str(source)])
    assert organizer.main()==0 and (source/"notes.TXT").exists()

    report_spec=importlib.util.spec_from_file_location("test_csv_report",ROOT/"developer-toolkit"/"csv_report.py")
    report_module=importlib.util.module_from_spec(report_spec);report_spec.loader.exec_module(report_module)
    csv_path=tmp_path/"hours.csv";csv_path.write_text("team,hours\nA,2.5\nA,1.5\nB,4\n",encoding="utf-8")
    _,groups=report_module.summarize(csv_path,"team","hours")
    assert groups[0]["sum"]==4 and groups[1]["mean"]==4

    backup_spec=importlib.util.spec_from_file_location("test_backup",ROOT/"developer-toolkit"/"backup.py")
    backup=importlib.util.module_from_spec(backup_spec);backup_spec.loader.exec_module(backup)
    destination=tmp_path/"backups"
    monkeypatch.setattr(sys,"argv",["backup.py",str(source),str(destination)])
    assert backup.main()==0
    archive=next(destination.glob("*.zip"))
    with zipfile.ZipFile(archive) as zipped:
        assert "notes.TXT" in zipped.namelist()
    assert archive.with_suffix(".manifest.json").is_file()


def test_contribution_showcase_and_finance_scenario(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location("test_contributions",ROOT/"contribution-portfolio"/"contributions.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    markdown=module.markdown([{"project":"demo","date":"2026-10-17","summary":"Fixed a parser edge case","lesson":"Reproduced before editing","issue_url":"https://github.com/a/b/issues/1","pr_url":""}])
    assert "Fixed a parser edge case" in markdown and "issues/1" in markdown
    module.DATA_PATH=tmp_path/"contributions.json"
    monkeypatch.setattr(sys,"argv",["contributions.py","add","--project","demo","--issue-url","https://github.com/a/b/issues/2","--summary","Reproduced a bug","--lesson","Read the existing flow"])
    assert module.main()==0 and json.loads(module.DATA_PATH.read_text())[0]["project"]=="demo"
    with open_app(tmp_path,"personal-finance","test_scenario") as (client,_):
        scenario=client.post("/api/scenarios",json={"initial_cents":0,"monthly_cents":10000,"annual_return_percent":0,"months":12}).json()
        assert scenario["projected_cents"]==120000
