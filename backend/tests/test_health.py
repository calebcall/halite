import pytest
from httpx import AsyncClient, ASGITransport

from halite.main import create_app


@pytest.mark.asyncio
async def test_healthz_returns_ok():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
