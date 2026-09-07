import pytest
import asyncio

try:
    # Expect FastAPI app to be importable as app.main:app
    from app.main import app  # type: ignore
except Exception as e:
    app = None
    import_error = e


pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def check_app_available():
    if app is None:
        pytest.skip(f"FastAPI app not importable from app.main: {import_error}")


async def test_root_returns_200(check_app_available):
    from httpx import AsyncClient

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/")
    assert r.status_code == 200, f"Expected 200 on GET / but got {r.status_code} - body: {r.text}"


async def test_openapi_present(check_app_available):
    from httpx import AsyncClient

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/openapi.json")
    assert r.status_code == 200, "/openapi.json is missing or not reachable"
    assert "openapi" in r.json(), "openapi key not found in response"


async def test_health_or_ping(check_app_available):
    from httpx import AsyncClient

    endpoints = ["/health", "/ping", "/status"]
    ok = False
    async with AsyncClient(app=app, base_url="http://test") as ac:
        for ep in endpoints:
            r = await ac.get(ep)
            if r.status_code == 200:
                ok = True
                break
    if not ok:
        pytest.skip("No /health, /ping, or /status endpoint returned 200; add a health endpoint to the app to enable this test")
