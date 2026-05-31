from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from mock_salt.config import Settings
from mock_salt.dispatch import dispatch, login_response
from mock_salt.events import EventBus, format_sse
from mock_salt.fleet import build_fleet
from mock_salt.reset import ResetLoop
from mock_salt.simulator import Simulator


class _State:
    """Mutable holder so the reset loop can swap the fleet atomically."""
    def __init__(self, fleet, bus: EventBus) -> None:
        self.fleet = fleet
        self.bus = bus


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    bus = EventBus()
    state = _State(build_fleet(seed=settings.fleet_seed, size=settings.fleet_size), bus)
    sim = Simulator(state.fleet, bus, interval_s=settings.sim_interval_seconds)
    reset = ResetLoop(state, minutes=settings.reset_minutes,
                      seed=settings.fleet_seed, size=settings.fleet_size)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        sim.start()
        reset.start()
        try:
            yield
        finally:
            await sim.stop()
            await reset.stop()

    app = FastAPI(title="mock-salt-api", lifespan=lifespan)

    @app.post("/login")
    async def login(body: dict):
        return login_response(body.get("username") or settings.username)

    @app.post("/")
    async def lowstate(request: Request):
        body = await request.json()
        calls = body if isinstance(body, list) else [body]
        results = []
        for call in calls:
            results.append(await dispatch(state.fleet, state.bus, call))
        merged: list = []
        for r in results:
            merged.extend(r.get("return", []))
        return {"return": merged}

    @app.get("/events")
    async def events(request: Request):
        async def gen():
            with state.bus.subscribe() as q:
                yield ": connected\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        tag, data = await asyncio.wait_for(q.get(), timeout=15.0)
                        yield format_sse(tag, data)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")

    return app
