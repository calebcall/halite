# Demo Mock salt-api Service — Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Commits:** Do NOT add any `Co-Authored-By` / AI attribution trailer to commit messages (project rule). When dispatching subagents, tell them the same.

**Goal:** Build a standalone service that faithfully mimics the salt-api surface Halite consumes — `POST /login`, the `POST /` lowstate dispatcher, and the `GET /events` SSE bus — backed by a believable, mutable in-memory fleet, with a background simulator that keeps the event stream alive, so Halite can run a fully-interactive demo with no real Salt master.

**Architecture:** A small FastAPI app at `mock-salt-api/`. A `Fleet` in-memory model (deterministic seed) is the single source of truth. A pure `dispatch()` function maps `(client, fun)` lowstate calls to salt-api-shaped responses over the fleet, mutating it and publishing events on actions. An `EventBus` fans normalized Salt events to `/events` SSE subscribers. A `Simulator` emits a lifelike event stream; a reset loop re-seeds periodically. Halite points `SALT_API_URL` at this service unchanged.

**Tech Stack:** Python 3.13, FastAPI, uvicorn, httpx, pytest. No database — pure in-memory.

**Reference:** spec `docs/superpowers/specs/2026-05-31-demo-site-design.md`. The event-shape contract is defined by Halite's `backend/src/halite/activity/normalize.py` (stdlib-only, importable directly). The lowstate field names are defined by `backend/src/halite/jobs/ingest.py`, `jobs/service.py`, `minions/ingest.py`, `inventory/collectors.py`, `fleet/ingest.py`.

**Run commands (from `mock-salt-api/`):**
```bash
python3.13 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
pytest -q                                   # unit tests
uvicorn mock_salt.app:create_app --factory --reload --port 8000   # run the service
```
On this machine `python3.13` is at `~/.cache/halite-docs-node/python/bin` (prepend to PATH if `python3.13` isn't found).

---

## File structure

```
mock-salt-api/
├── pyproject.toml                 # package + deps + pytest/ruff config
├── Dockerfile                     # runtime image
├── README.md                      # how to run
├── src/mock_salt/
│   ├── __init__.py
│   ├── config.py                  # env-driven settings
│   ├── fleet.py                   # Minion/Job dataclasses + Fleet + build_fleet(seed)
│   ├── dispatch.py                # login_response() + dispatch(fleet, bus, lowstate)
│   ├── events.py                  # EventBus (pub/sub) + SSE framing
│   ├── simulator.py               # background liveness loop
│   ├── reset.py                   # periodic re-seed loop
│   └── app.py                     # FastAPI: /login, POST /, GET /events, lifespan
└── tests/
    ├── conftest.py                # fleet fixture, TestClient
    ├── test_fleet.py
    ├── test_dispatch_reads.py
    ├── test_dispatch_actions.py
    ├── test_events.py
    ├── test_simulator.py
    ├── test_app.py
    └── test_normalize_contract.py # imports halite.activity.normalize — the guard
```

---

## Task 1: Scaffold the package

**Files:**
- Create: `mock-salt-api/pyproject.toml`
- Create: `mock-salt-api/src/mock_salt/__init__.py`
- Create: `mock-salt-api/src/mock_salt/config.py`
- Create: `mock-salt-api/tests/test_config.py`

- [ ] **Step 1: Write `mock-salt-api/pyproject.toml`**

```toml
[project]
name = "mock-salt-api"
version = "0.1.0"
description = "Mock salt-api server for the Halite demo"
requires-python = ">=3.13,<3.14"
dependencies = [
    "fastapi==0.115.*",
    "uvicorn[standard]==0.32.*",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.*",
    "httpx==0.27.*",
    "ruff==0.6.*",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mock_salt"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
line-length = 100
target-version = "py313"
```

- [ ] **Step 2: Create the package init**

`mock-salt-api/src/mock_salt/__init__.py`:
```python
"""Mock salt-api server for the Halite demo."""
```

- [ ] **Step 3: Write the failing test for config**

`mock-salt-api/tests/test_config.py`:
```python
from mock_salt.config import Settings


def test_defaults():
    s = Settings()
    assert s.username == "halite-demo"
    assert s.reset_minutes == 30
    assert s.fleet_size == 40
    assert s.fleet_seed == 1337


def test_env_override(monkeypatch):
    monkeypatch.setenv("MOCK_SALT_USERNAME", "svc")
    monkeypatch.setenv("MOCK_RESET_MINUTES", "5")
    s = Settings()
    assert s.username == "svc"
    assert s.reset_minutes == 5
```

- [ ] **Step 4: Run it to verify it fails**

```bash
cd mock-salt-api && python3.13 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
pytest tests/test_config.py -q
```
Expected: FAIL (`ModuleNotFoundError: No module named 'mock_salt.config'`).

- [ ] **Step 5: Write `mock-salt-api/src/mock_salt/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    username: str = os.getenv("MOCK_SALT_USERNAME", "halite-demo")
    password: str = os.getenv("MOCK_SALT_PASSWORD", "demo")
    eauth: str = os.getenv("MOCK_SALT_EAUTH", "pam")
    reset_minutes: int = int(os.getenv("MOCK_RESET_MINUTES", "30"))
    fleet_size: int = int(os.getenv("MOCK_FLEET_SIZE", "40"))
    fleet_seed: int = int(os.getenv("MOCK_FLEET_SEED", "1337"))
    sim_interval_seconds: float = float(os.getenv("MOCK_SIM_INTERVAL_S", "6"))
```

- [ ] **Step 6: Run to verify pass**

```bash
pytest tests/test_config.py -q
```
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add mock-salt-api/
git commit -m "feat(mock): scaffold mock-salt-api package + config"
```

---

## Task 2: Fleet model + deterministic seed

**Files:**
- Create: `mock-salt-api/src/mock_salt/fleet.py`
- Create: `mock-salt-api/tests/test_fleet.py`
- Create: `mock-salt-api/tests/conftest.py`

- [ ] **Step 1: Write `mock-salt-api/tests/conftest.py`**

```python
import pytest

from mock_salt.fleet import build_fleet


@pytest.fixture()
def fleet():
    return build_fleet(seed=1337, size=40)
```

- [ ] **Step 2: Write the failing test**

`mock-salt-api/tests/test_fleet.py`:
```python
from mock_salt.fleet import build_fleet


def test_seed_is_deterministic():
    a = build_fleet(seed=1337, size=40)
    b = build_fleet(seed=1337, size=40)
    assert list(a.minions) == list(b.minions)


def test_minion_counts_and_key_states(fleet):
    assert len(fleet.minions) == 40
    states = {}
    for m in fleet.minions.values():
        states[m.key_state] = states.get(m.key_state, 0) + 1
    # 3 pending, 1 rejected, 1 denied; the rest accepted
    assert states.get("pending") == 3
    assert states.get("rejected") == 1
    assert states.get("denied") == 1
    assert states.get("accepted") == 40 - 5


def test_grains_shape(fleet):
    accepted = [m for m in fleet.minions.values() if m.key_state == "accepted"]
    g = accepted[0].grains
    for key in ("id", "os", "os_family", "osrelease", "fqdn", "ip4_interfaces"):
        assert key in g


def test_seeded_jobs_include_state_runs(fleet):
    funs = {j.fun for j in fleet.jobs.values()}
    assert "state.apply" in funs           # drives Fleet Health
    assert "test.ping" in funs
    assert len(fleet.jobs) >= 100


def test_some_minions_offline_or_stale(fleet):
    assert any(not m.online for m in fleet.minions.values())


def test_packages_present(fleet):
    accepted = next(m for m in fleet.minions.values() if m.key_state == "accepted")
    assert fleet.packages[accepted.id]            # non-empty pkg map
```

- [ ] **Step 3: Run to verify it fails**

```bash
pytest tests/test_fleet.py -q
```
Expected: FAIL (`No module named 'mock_salt.fleet'`).

- [ ] **Step 4: Write `mock-salt-api/src/mock_salt/fleet.py`**

```python
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

# Salt job ids are 20-digit timestamps: YYYYMMDDHHMMSSffffff
_JID_FMT = "%Y%m%d%H%M%S%f"


def now_jid(offset_seconds: float = 0.0) -> str:
    return (datetime.now(tz=UTC) - timedelta(seconds=offset_seconds)).strftime(_JID_FMT)


def salt_time(dt: datetime) -> str:
    # Matches salt's StartTime format, e.g. "2026, May 31 14:03:01.123456"
    return dt.strftime("%Y, %b %d %H:%M:%S.%f")


_OS = [
    ("Ubuntu", "Debian", "24.04"), ("Ubuntu", "Debian", "22.04"),
    ("Debian", "Debian", "12"), ("Rocky", "RedHat", "9.3"),
    ("AlmaLinux", "RedHat", "9.3"), ("Alpine", "Alpine", "3.20"),
    ("Windows", "Windows", "2022"),
]
_ROLES = ["web", "db", "cache", "edge"]
_PKGS_LINUX = {"openssl": "3.0.13", "bash": "5.2.21", "curl": "8.5.0",
               "nginx": "1.24.0", "python3": "3.12.3", "systemd": "255.4"}
_PKGS_WIN = {"PowerShell": "7.4.1", "salt-minion": "3007.1"}


@dataclass
class Minion:
    id: str
    grains: dict
    key_state: str           # accepted | pending | rejected | denied
    online: bool
    last_seen: datetime


@dataclass
class Job:
    jid: str
    fun: str
    tgt: str
    tgt_type: str
    user: str
    arg: list
    start_time: datetime
    minions: list[str]
    # per-minion return: {minion_id: {"return": <obj>, "retcode": int, "success": bool}}
    returns: dict[str, dict] = field(default_factory=dict)
    active: bool = False


@dataclass
class Fleet:
    minions: dict[str, Minion]
    jobs: dict[str, Job]
    packages: dict[str, dict]   # minion_id -> {pkg_name: version}

    def accepted_ids(self) -> list[str]:
        return [m.id for m in self.minions.values() if m.key_state == "accepted"]

    def present_ids(self) -> list[str]:
        return [m.id for m in self.minions.values()
                if m.key_state == "accepted" and m.online]


def _grains(rng: random.Random, mid: str, os_name: str, family: str, release: str) -> dict:
    ip = f"10.0.{rng.randint(0, 9)}.{rng.randint(2, 250)}"
    return {
        "id": mid, "os": os_name, "os_family": family, "osrelease": release,
        "kernel": "Windows" if os_name == "Windows" else "Linux",
        "fqdn": f"{mid}.demo.halite",
        "fqdn_ip4": [ip], "ip4_gw": "10.0.0.1",
        "ip4_interfaces": {"eth0": [ip]},
        "cpuarch": "x86_64", "num_cpus": rng.choice([2, 4, 8]),
        "mem_total": rng.choice([2048, 4096, 8192, 16384]),
    }


def _state_return(rng: random.Random, changed: bool, failed: bool) -> dict:
    """A salt state.apply-style return: {state_id: {result, changes, duration, comment}}."""
    states = {}
    for i in range(rng.randint(2, 5)):
        ok = not (failed and i == 0)
        states[f"file_|-cfg{i}_|-/etc/app/{i}.conf_|-managed"] = {
            "result": ok,
            "changes": {"diff": "updated"} if (changed and ok and i == 0) else {},
            "duration": round(rng.uniform(2.0, 120.0), 3),
            "comment": "OK" if ok else "failed to apply",
        }
    return states


def build_fleet(seed: int = 1337, size: int = 40) -> Fleet:
    rng = random.Random(seed)
    minions: dict[str, Minion] = {}
    packages: dict[str, dict] = {}

    # key-state assignment: 3 pending, 1 rejected, 1 denied, rest accepted
    specials = {0: "pending", 1: "pending", 2: "pending", 3: "rejected", 4: "denied"}
    for i in range(size):
        os_name, family, release = _OS[i % len(_OS)]
        role = _ROLES[i % len(_ROLES)]
        mid = f"{role}{i:02d}.demo.halite"
        key_state = specials.get(i, "accepted")
        # a few accepted minions are offline; one stale
        online = key_state == "accepted" and not (i in (7, 12, 19))
        last_seen = datetime.now(tz=UTC) - (
            timedelta(days=3) if i == 7 else timedelta(minutes=rng.randint(0, 30))
        )
        minions[mid] = Minion(
            id=mid, grains=_grains(rng, mid, os_name, family, release),
            key_state=key_state, online=online, last_seen=last_seen,
        )
        base = dict(_PKGS_WIN if os_name == "Windows" else _PKGS_LINUX)
        # introduce version variance so inventory drill-down is interesting
        if rng.random() < 0.4 and "nginx" in base:
            base["nginx"] = "1.22.1"
        packages[mid] = base

    jobs: dict[str, Job] = {}
    accepted = [m.id for m in minions.values() if m.key_state == "accepted"]
    funs = ["test.ping", "state.apply", "pkg.install", "cmd.run", "service.restart"]
    for n in range(220):
        fun = rng.choice(funs)
        offset = rng.uniform(0, 48 * 3600)            # within last 48h
        jid = now_jid(offset)
        # avoid jid collisions
        while jid in jobs:
            offset += 0.001
            jid = now_jid(offset)
        targets = rng.sample(accepted, k=rng.randint(1, min(8, len(accepted))))
        start = datetime.now(tz=UTC) - timedelta(seconds=offset)
        job = Job(jid=jid, fun=fun, tgt="*", tgt_type="glob", user="demo",
                  arg=[], start_time=start, minions=list(targets))
        for mid in targets:
            failed = rng.random() < 0.12
            changed = fun == "state.apply" and rng.random() < 0.5
            if fun == "state.apply":
                ret = _state_return(rng, changed=changed, failed=failed)
            elif fun == "test.ping":
                ret = True
            else:
                ret = "" if not failed else "command not found"
            job.returns[mid] = {
                "return": ret, "retcode": 1 if failed else 0, "success": not failed,
            }
        jobs[jid] = job

    return Fleet(minions=minions, jobs=jobs, packages=packages)
```

- [ ] **Step 5: Run to verify pass**

```bash
pytest tests/test_fleet.py -q
```
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add mock-salt-api/src/mock_salt/fleet.py mock-salt-api/tests/test_fleet.py mock-salt-api/tests/conftest.py
git commit -m "feat(mock): in-memory Fleet model + deterministic seed"
```

---

## Task 3: Event bus + SSE framing

**Files:**
- Create: `mock-salt-api/src/mock_salt/events.py`
- Create: `mock-salt-api/tests/test_events.py`

- [ ] **Step 1: Write the failing test**

`mock-salt-api/tests/test_events.py`:
```python
import asyncio

import pytest

from mock_salt.events import EventBus, format_sse


def test_format_sse_frame():
    frame = format_sse("salt/job/123/new", {"fun": "test.ping"})
    assert frame.startswith("tag: salt/job/123/new\n")
    assert 'data: {"tag": "salt/job/123/new"' in frame
    assert frame.endswith("\n\n")


@pytest.mark.asyncio
async def test_pub_sub_delivers_to_subscriber():
    bus = EventBus()
    with bus.subscribe() as q:
        await bus.publish("salt/key", {"id": "web01.demo.halite", "act": "accept"})
        tag, data = await asyncio.wait_for(q.get(), timeout=1.0)
    assert tag == "salt/key"
    assert data["act"] == "accept"


@pytest.mark.asyncio
async def test_unsubscribe_on_context_exit():
    bus = EventBus()
    with bus.subscribe():
        pass
    assert bus.subscriber_count == 0
```

Add to `pyproject.toml` `[tool.pytest.ini_options]`: `asyncio_mode = "auto"` and add `pytest-asyncio==0.24.*` to dev deps.

- [ ] **Step 2: Update pyproject dev deps + asyncio mode**

In `mock-salt-api/pyproject.toml`, add `"pytest-asyncio==0.24.*"` to `[project.optional-dependencies].dev`, and under `[tool.pytest.ini_options]` add:
```toml
asyncio_mode = "auto"
```
Then `pip install -e '.[dev]'` again.

- [ ] **Step 3: Run to verify it fails**

```bash
pytest tests/test_events.py -q
```
Expected: FAIL (`No module named 'mock_salt.events'`).

- [ ] **Step 4: Write `mock-salt-api/src/mock_salt/events.py`**

```python
from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from typing import Any


def format_sse(tag: str, data: dict[str, Any]) -> str:
    """Render one Salt SSE frame. Halite reads the tag from the JSON `data:`
    line; we also send a `tag:` line for fidelity with real salt-api."""
    payload = json.dumps({"tag": tag, "data": data})
    return f"tag: {tag}\ndata: {payload}\n\n"


class EventBus:
    """In-process async pub/sub. Publishers call publish(); each subscriber
    gets its own unbounded asyncio.Queue of (tag, data) tuples."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @contextmanager
    def subscribe(self):
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        try:
            yield q
        finally:
            self._subscribers.discard(q)

    async def publish(self, tag: str, data: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            q.put_nowait((tag, data))
```

- [ ] **Step 5: Run to verify pass**

```bash
pytest tests/test_events.py -q
```
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add mock-salt-api/src/mock_salt/events.py mock-salt-api/tests/test_events.py mock-salt-api/pyproject.toml
git commit -m "feat(mock): async EventBus + salt-api SSE framing"
```

---

## Task 4: Lowstate dispatcher — reads

**Files:**
- Create: `mock-salt-api/src/mock_salt/dispatch.py`
- Create: `mock-salt-api/tests/test_dispatch_reads.py`

- [ ] **Step 1: Write the failing test**

`mock-salt-api/tests/test_dispatch_reads.py`:
```python
import pytest

from mock_salt.dispatch import dispatch, login_response


def test_login_response_shape():
    body = login_response("halite-demo")
    rec = body["return"][0]
    assert rec["token"] and rec["user"] == "halite-demo"
    assert "expire" in rec


@pytest.mark.asyncio
async def test_key_list_all_buckets(fleet):
    body = await dispatch(fleet, None, {"client": "wheel", "fun": "key.list_all"})
    data = body["return"][0]["data"]["return"]
    assert len(data["minions"]) == fleet.minions.__len__() - 5
    assert len(data["minions_pre"]) == 3
    assert len(data["minions_rejected"]) == 1
    assert len(data["minions_denied"]) == 1


@pytest.mark.asyncio
async def test_manage_present_show_ip(fleet):
    body = await dispatch(fleet, None, {"client": "runner", "fun": "manage.present",
                                        "show_ip": True})
    pairs = body["return"][0]
    assert all(isinstance(p, list) and len(p) == 2 for p in pairs)
    assert {p[0] for p in pairs} == set(fleet.present_ids())


@pytest.mark.asyncio
async def test_manage_present_plain(fleet):
    body = await dispatch(fleet, None, {"client": "runner", "fun": "manage.present"})
    ids = body["return"][0]
    assert set(ids) == set(fleet.present_ids())


@pytest.mark.asyncio
async def test_jobs_list_jobs_metadata(fleet):
    body = await dispatch(fleet, None, {"client": "runner", "fun": "jobs.list_jobs"})
    table = body["return"][0]
    jid, meta = next(iter(table.items()))
    assert "Function" in meta and "StartTime" in meta and "Target" in meta


@pytest.mark.asyncio
async def test_jobs_list_job_detail(fleet):
    jid = next(iter(fleet.jobs))
    body = await dispatch(fleet, None, {"client": "runner", "fun": "jobs.list_job",
                                        "jid": jid})
    detail = body["return"][0]
    assert detail["Function"] == fleet.jobs[jid].fun
    assert isinstance(detail["Result"], dict)


@pytest.mark.asyncio
async def test_pkg_list_pkgs(fleet):
    body = await dispatch(fleet, None, {"client": "local", "fun": "pkg.list_pkgs",
                                        "tgt": "*", "tgt_type": "glob"})
    result = body["return"][0]
    mid = fleet.accepted_ids()[0]
    assert mid in result and isinstance(result[mid], dict)


@pytest.mark.asyncio
async def test_sys_list_functions(fleet):
    body = await dispatch(fleet, None, {"client": "local", "fun": "sys.list_functions",
                                        "tgt": "*", "tgt_type": "glob"})
    result = body["return"][0]
    mid = fleet.accepted_ids()[0]
    assert "test.ping" in result[mid]


@pytest.mark.asyncio
async def test_unknown_call_is_safe(fleet):
    body = await dispatch(fleet, None, {"client": "runner", "fun": "does.not_exist"})
    assert body == {"return": [{}]}
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_dispatch_reads.py -q
```
Expected: FAIL (`No module named 'mock_salt.dispatch'`).

- [ ] **Step 3: Write `mock-salt-api/src/mock_salt/dispatch.py` (reads only — actions added in Task 5)**

```python
from __future__ import annotations

import secrets
import time
from typing import Any

from mock_salt.fleet import Fleet, salt_time

_KEY_BUCKETS = {
    "accepted": "minions", "pending": "minions_pre",
    "rejected": "minions_rejected", "denied": "minions_denied",
}


def login_response(username: str) -> dict[str, Any]:
    return {"return": [{
        "token": secrets.token_hex(20),
        "expire": time.time() + 12 * 3600,
        "start": time.time(),
        "user": username,
        "eauth": "pam",
        "perms": [".*", "@wheel", "@runner", "@jobs"],
    }]}


def _key_list_all(fleet: Fleet) -> dict[str, Any]:
    out: dict[str, list[str]] = {v: [] for v in _KEY_BUCKETS.values()}
    out["local"] = ["master.pem", "master.pub"]
    for m in fleet.minions.values():
        bucket = _KEY_BUCKETS.get(m.key_state)
        if bucket:
            out[bucket].append(m.id)
    for v in out.values():
        v.sort()
    return {"return": [{"data": {"return": out}}]}


def _manage_present(fleet: Fleet, show_ip: bool) -> dict[str, Any]:
    present = sorted(fleet.present_ids())
    if show_ip:
        pairs = [[mid, fleet.minions[mid].grains["fqdn_ip4"][0]] for mid in present]
        return {"return": [pairs]}
    return {"return": [present]}


def _cache_grains(fleet: Fleet, tgt: str | None, tgt_type: str | None) -> dict[str, Any]:
    ids = _resolve_targets(fleet, tgt or "*", tgt_type or "glob")
    return {"return": [{mid: fleet.minions[mid].grains for mid in ids}]}


def _jobs_list_jobs(fleet: Fleet) -> dict[str, Any]:
    table = {}
    for jid, job in fleet.jobs.items():
        table[jid] = {
            "Function": job.fun, "Target": job.tgt, "Target-type": job.tgt_type,
            "User": job.user, "StartTime": salt_time(job.start_time),
            "Arguments": job.arg,
        }
    return {"return": [table]}


def _jobs_list_job(fleet: Fleet, jid: str | None) -> dict[str, Any]:
    job = fleet.jobs.get(jid or "")
    if job is None:
        return {"return": [{}]}
    return {"return": [{
        "jid": job.jid, "Function": job.fun, "Target": job.tgt,
        "Target-type": job.tgt_type, "User": job.user,
        "StartTime": salt_time(job.start_time),
        "Arguments": job.arg,
        "Minions": list(job.minions),
        "Result": {
            mid: {"return": r["return"], "retcode": r["retcode"], "success": r["success"]}
            for mid, r in job.returns.items()
        },
    }]}


def _jobs_active(fleet: Fleet) -> dict[str, Any]:
    active = {}
    for jid, job in fleet.jobs.items():
        if job.active:
            active[jid] = {"Function": job.fun, "Target": job.tgt,
                           "Running": [{mid: 0} for mid in job.minions]}
    return {"return": [active]}


def _pkg_list_pkgs(fleet: Fleet, tgt: str | None, tgt_type: str | None) -> dict[str, Any]:
    ids = _resolve_targets(fleet, tgt or "*", tgt_type or "glob")
    # attr=version,arch shape: {name: [{"version": v, "arch": "x86_64"}]}
    out = {}
    for mid in ids:
        out[mid] = {name: [{"version": ver, "arch": "x86_64"}]
                    for name, ver in fleet.packages.get(mid, {}).items()}
    return {"return": [out]}


def _grains_get(fleet: Fleet, tgt: str | None, tgt_type: str | None,
                arg: list | None) -> dict[str, Any]:
    key = (arg or ["os_family"])[0]
    ids = _resolve_targets(fleet, tgt or "*", tgt_type or "glob")
    return {"return": [{mid: fleet.minions[mid].grains.get(key, "") for mid in ids}]}


def _grains_items(fleet: Fleet, tgt: str | None, tgt_type: str | None) -> dict[str, Any]:
    ids = _resolve_targets(fleet, tgt or "*", tgt_type or "glob")
    return {"return": [{mid: fleet.minions[mid].grains for mid in ids}]}


_FUNCTION_CATALOG = sorted([
    "test.ping", "test.version", "state.apply", "state.highstate", "state.sls",
    "pkg.install", "pkg.remove", "pkg.list_pkgs", "pkg.version",
    "cmd.run", "service.restart", "service.status", "grains.items", "grains.get",
    "sys.list_functions", "disk.usage", "network.interfaces", "user.list_users",
])


def _sys_list_functions(fleet: Fleet, tgt: str | None, tgt_type: str | None) -> dict[str, Any]:
    ids = _resolve_targets(fleet, tgt or "*", tgt_type or "glob")
    return {"return": [{mid: list(_FUNCTION_CATALOG) for mid in ids}]}


def _resolve_targets(fleet: Fleet, tgt: str, tgt_type: str) -> list[str]:
    """Map a salt target to present accepted minion ids. Good enough for the demo:
    glob '*' = all present; 'list' = comma/list match; otherwise substring match."""
    present = fleet.present_ids()
    if tgt in ("*", ""):
        return present
    if tgt_type == "list":
        wanted = set(tgt.split(",")) if isinstance(tgt, str) else set(tgt)
        return [m for m in present if m in wanted]
    return [m for m in present if tgt.strip("*") in m]


async def dispatch(fleet: Fleet, bus, lowstate: dict[str, Any]) -> dict[str, Any]:
    """Map a single lowstate dict to a salt-api-shaped response over the fleet.
    `bus` (EventBus | None) is used by action calls in Task 5. Read calls ignore it.
    Unknown (client, fun) returns a valid empty shape — never raises."""
    client = lowstate.get("client")
    fun = lowstate.get("fun")
    tgt = lowstate.get("tgt")
    tgt_type = lowstate.get("tgt_type")
    arg = lowstate.get("arg")

    if client == "wheel":
        if fun == "key.list_all":
            return _key_list_all(fleet)
    elif client == "runner":
        if fun == "manage.present":
            return _manage_present(fleet, bool(lowstate.get("show_ip")))
        if fun == "cache.grains":
            return _cache_grains(fleet, tgt, tgt_type)
        if fun == "jobs.list_jobs":
            return _jobs_list_jobs(fleet)
        if fun == "jobs.list_job":
            return _jobs_list_job(fleet, lowstate.get("jid"))
        if fun == "jobs.active":
            return _jobs_active(fleet)
    elif client == "local":
        if fun == "pkg.list_pkgs":
            return _pkg_list_pkgs(fleet, tgt, tgt_type)
        if fun == "grains.get":
            return _grains_get(fleet, tgt, tgt_type, arg)
        if fun in ("grains.items", "grains.item"):
            return _grains_items(fleet, tgt, tgt_type)
        if fun == "sys.list_functions":
            return _sys_list_functions(fleet, tgt, tgt_type)

    return {"return": [{}]}
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_dispatch_reads.py -q
```
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add mock-salt-api/src/mock_salt/dispatch.py mock-salt-api/tests/test_dispatch_reads.py
git commit -m "feat(mock): lowstate dispatcher read calls (keys/present/grains/jobs/pkg/sys)"
```

---

## Task 5: Dispatcher actions — mutate fleet + emit events

**Files:**
- Modify: `mock-salt-api/src/mock_salt/fleet.py` (add mutation methods)
- Modify: `mock-salt-api/src/mock_salt/dispatch.py` (wheel key.* actions, saltutil.kill_job, local_async)
- Create: `mock-salt-api/tests/test_dispatch_actions.py`

- [ ] **Step 1: Write the failing test**

`mock-salt-api/tests/test_dispatch_actions.py`:
```python
import pytest

from mock_salt.dispatch import dispatch
from mock_salt.events import EventBus


@pytest.mark.asyncio
async def test_accept_key_mutates_and_emits(fleet):
    pending = next(m for m in fleet.minions.values() if m.key_state == "pending")
    bus = EventBus()
    with bus.subscribe() as q:
        await dispatch(fleet, bus, {"client": "wheel", "fun": "key.accept",
                                    "match": pending.id})
        tag, data = await q.get()
    assert fleet.minions[pending.id].key_state == "accepted"
    assert tag == "salt/key" and data == {"id": pending.id, "act": "accept"}


@pytest.mark.asyncio
async def test_delete_key_removes_minion_and_emits(fleet):
    target = fleet.accepted_ids()[0]
    bus = EventBus()
    with bus.subscribe() as q:
        await dispatch(fleet, bus, {"client": "wheel", "fun": "key.delete",
                                    "match": target})
        tag, data = await q.get()
    assert target not in fleet.minions
    assert tag == "salt/key" and data["act"] == "delete"


@pytest.mark.asyncio
async def test_local_async_run_returns_jid_and_emits_new_then_ret(fleet):
    bus = EventBus()
    events = []
    with bus.subscribe() as q:
        body = await dispatch(fleet, bus, {
            "client": "local_async", "fun": "test.ping", "tgt": "*",
            "tgt_type": "glob", "arg": [], "kwarg": {}})
        ret = body["return"][0]
        assert ret["jid"] and isinstance(ret["minions"], list) and ret["minions"]
        # job/new first, then one job/ret per targeted minion
        for _ in range(1 + len(ret["minions"])):
            events.append(await q.get())
    tags = [t for t, _ in events]
    assert tags[0] == f"salt/job/{ret['jid']}/new"
    assert all(t == f"salt/job/{ret['jid']}/ret/" + m
               for (t, _), m in zip(events[1:], ret["minions"]))
    assert ret["jid"] in fleet.jobs


@pytest.mark.asyncio
async def test_kill_job_marks_inactive(fleet):
    # make a job active first
    jid = next(iter(fleet.jobs))
    fleet.jobs[jid].active = True
    await dispatch(fleet, None, {"client": "runner", "fun": "saltutil.kill_job",
                                 "jid": jid})
    assert fleet.jobs[jid].active is False
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_dispatch_actions.py -q
```
Expected: FAIL (key.accept falls through to the empty shape; no mutation/event).

- [ ] **Step 3: Add mutation methods to `fleet.py`**

Append to the `Fleet` class in `mock-salt-api/src/mock_salt/fleet.py`:
```python
    def set_key_state(self, minion_id: str, state: str) -> bool:
        m = self.minions.get(minion_id)
        if m is None:
            return False
        m.key_state = state
        if state == "accepted":
            m.online = True
        return True

    def delete_minion(self, minion_id: str) -> bool:
        self.packages.pop(minion_id, None)
        return self.minions.pop(minion_id, None) is not None

    def dispatch_job(self, fun: str, tgt: str, tgt_type: str, user: str,
                     arg: list, target_ids: list[str]) -> "Job":
        jid = now_jid()
        while jid in self.jobs:
            jid = now_jid(-0.001)
        job = Job(jid=jid, fun=fun, tgt=tgt, tgt_type=tgt_type, user=user,
                  arg=list(arg or []), start_time=datetime.now(tz=UTC),
                  minions=list(target_ids), active=True)
        self.jobs[jid] = job
        return job

    def complete_job_for(self, jid: str, minion_id: str) -> dict:
        job = self.jobs[jid]
        if job.fun == "test.ping":
            ret = {"return": True, "retcode": 0, "success": True}
        elif job.fun.startswith("state."):
            ret = {"return": {"file_|-demo_|-/etc/demo_|-managed":
                              {"result": True, "changes": {}, "duration": 12.5,
                               "comment": "OK"}},
                   "retcode": 0, "success": True}
        else:
            ret = {"return": "", "retcode": 0, "success": True}
        job.returns[minion_id] = ret
        return ret
```

- [ ] **Step 4: Add action handling to `dispatch.py`**

In `mock-salt-api/src/mock_salt/dispatch.py`, add these helpers above `dispatch()`:
```python
_KEY_ACTS = {"key.accept": ("accepted", "accept"), "key.reject": ("rejected", "reject")}


async def _key_action(fleet: Fleet, bus, fun: str, match: str | None) -> dict[str, Any]:
    if not match:
        return {"return": [{"data": {"success": True, "return": {}}}]}
    if fun == "key.delete":
        fleet.delete_minion(match)
        act = "delete"
    else:
        state, act = _KEY_ACTS[fun]
        fleet.set_key_state(match, state)
    if bus is not None:
        await bus.publish("salt/key", {"id": match, "act": act})
        if act == "accept":
            await bus.publish(f"salt/minion/{match}/start", {"id": match})
    return {"return": [{"data": {"success": True, "return": {match: act}}}]}


async def _local_async(fleet: Fleet, bus, lowstate: dict[str, Any]) -> dict[str, Any]:
    fun = lowstate.get("fun") or "test.ping"
    tgt = lowstate.get("tgt") or "*"
    tgt_type = lowstate.get("tgt_type") or "glob"
    arg = lowstate.get("arg") or []
    targets = _resolve_targets(fleet, tgt, tgt_type)
    job = fleet.dispatch_job(fun, tgt, tgt_type, "demo", arg, targets)
    if bus is not None:
        await bus.publish(f"salt/job/{job.jid}/new",
                          {"fun": fun, "minions": list(targets), "user": "demo", "tgt": tgt})
        for mid in targets:
            ret = fleet.complete_job_for(job.jid, mid)
            await bus.publish(
                f"salt/job/{job.jid}/ret/{mid}",
                {"id": mid, "fun": fun, "retcode": ret["retcode"],
                 "return": ret["return"], "user": "demo", "tgt": tgt},
            )
    job.active = False
    return {"return": [{"jid": job.jid, "minions": list(targets)}]}
```

Then extend the `dispatch()` branches: in the `wheel` block add after `key.list_all`:
```python
        if fun in ("key.accept", "key.reject", "key.delete"):
            return await _key_action(fleet, bus, fun, lowstate.get("match"))
```
in the `runner` block add after `jobs.active`:
```python
        if fun == "saltutil.kill_job":
            job = fleet.jobs.get(lowstate.get("jid") or "")
            if job is not None:
                job.active = False
            return {"return": [{}]}
```
and add a new top-level branch:
```python
    elif client == "local_async":
        return await _local_async(fleet, bus, lowstate)
```

- [ ] **Step 5: Run to verify pass**

```bash
pytest tests/test_dispatch_actions.py tests/test_dispatch_reads.py -q
```
Expected: PASS (all). Re-run full suite: `pytest -q`.

- [ ] **Step 6: Commit**

```bash
git add mock-salt-api/src/mock_salt/fleet.py mock-salt-api/src/mock_salt/dispatch.py mock-salt-api/tests/test_dispatch_actions.py
git commit -m "feat(mock): key/run/kill actions mutate fleet and emit events"
```

---

## Task 6: Event-shape contract test (the guard)

**Files:**
- Create: `mock-salt-api/tests/test_normalize_contract.py`

This test imports Halite's real normalizer (stdlib-only) and asserts every event the mock emits normalizes to the intended typed row — so the mock can never drift from what Halite consumes.

- [ ] **Step 1: Write the test**

`mock-salt-api/tests/test_normalize_contract.py`:
```python
import sys
from pathlib import Path

import pytest

# Import Halite's normalizer directly from the sibling backend (stdlib-only module).
_BACKEND_SRC = Path(__file__).resolve().parents[2] / "backend" / "src"
sys.path.insert(0, str(_BACKEND_SRC))
from halite.activity.normalize import normalize_event  # noqa: E402

from mock_salt.dispatch import dispatch  # noqa: E402
from mock_salt.events import EventBus  # noqa: E402


async def _collect(fleet, lowstate, n):
    bus = EventBus()
    out = []
    with bus.subscribe() as q:
        await dispatch(fleet, bus, lowstate)
        for _ in range(n):
            out.append(await q.get())
    return out


@pytest.mark.asyncio
async def test_run_events_normalize(fleet):
    body_targets = fleet.present_ids()
    events = await _collect(fleet, {"client": "local_async", "fun": "state.apply",
                                    "tgt": "*", "tgt_type": "glob"},
                            1 + len(body_targets))
    rows = [normalize_event(tag, data) for tag, data in events]
    assert rows[0] is not None and rows[0]["event_type"] == "job.new"
    assert all(r is not None and r["event_type"] == "job.ret" for r in rows[1:])
    assert rows[1]["category"] == "job"


@pytest.mark.asyncio
async def test_key_accept_events_normalize(fleet):
    pending = next(m for m in fleet.minions.values() if m.key_state == "pending")
    events = await _collect(fleet, {"client": "wheel", "fun": "key.accept",
                                    "match": pending.id}, 2)
    by_type = {}
    for tag, data in events:
        r = normalize_event(tag, data)
        assert r is not None
        by_type[r["event_type"]] = r
    assert "key.accept" in by_type
    assert "minion.start" in by_type
    assert by_type["key.accept"]["minion_id"] == pending.id


@pytest.mark.asyncio
async def test_delete_key_normalizes(fleet):
    target = fleet.accepted_ids()[0]
    events = await _collect(fleet, {"client": "wheel", "fun": "key.delete",
                                    "match": target}, 1)
    r = normalize_event(*events[0])
    assert r is not None and r["event_type"] == "key.delete"
```

- [ ] **Step 2: Run to verify pass**

```bash
pytest tests/test_normalize_contract.py -q
```
Expected: PASS (3 passed). If a row is `None` or the wrong type, the mock's emitted `(tag, data)` doesn't match `normalize.py` — fix the event payload in `dispatch.py` until it passes.

- [ ] **Step 3: Commit**

```bash
git add mock-salt-api/tests/test_normalize_contract.py
git commit -m "test(mock): assert emitted events match Halite's normalize contract"
```

---

## Task 7: Background simulator + reset loop

**Files:**
- Create: `mock-salt-api/src/mock_salt/simulator.py`
- Create: `mock-salt-api/src/mock_salt/reset.py`
- Create: `mock-salt-api/tests/test_simulator.py`

- [ ] **Step 1: Write the failing test**

`mock-salt-api/tests/test_simulator.py`:
```python
import pytest

from mock_salt.events import EventBus
from mock_salt.fleet import build_fleet
from mock_salt.simulator import Simulator


@pytest.mark.asyncio
async def test_tick_emits_a_job_lifecycle():
    fleet = build_fleet(seed=1, size=10)
    bus = EventBus()
    sim = Simulator(fleet, bus, rng_seed=1)
    collected = []
    with bus.subscribe() as q:
        await sim.tick()
        while not q.empty():
            collected.append(await q.get())
    tags = [t for t, _ in collected]
    assert any(t.endswith("/new") for t in tags)
    assert any("/ret/" in t for t in tags)


@pytest.mark.asyncio
async def test_tick_adds_a_job_to_fleet():
    fleet = build_fleet(seed=1, size=10)
    before = len(fleet.jobs)
    sim = Simulator(fleet, EventBus(), rng_seed=1)
    await sim.tick()
    assert len(fleet.jobs) == before + 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_simulator.py -q
```
Expected: FAIL (`No module named 'mock_salt.simulator'`).

- [ ] **Step 3: Write `mock-salt-api/src/mock_salt/simulator.py`**

```python
from __future__ import annotations

import asyncio
import random

from mock_salt.dispatch import _local_async
from mock_salt.events import EventBus
from mock_salt.fleet import Fleet

_SIM_FUNS = ["test.ping", "state.apply", "cmd.run", "service.status"]


class Simulator:
    """Periodically dispatches a synthetic job (and occasionally a key-pending
    event) so the live feed moves without any visitor input."""

    def __init__(self, fleet: Fleet, bus: EventBus, *, interval_s: float = 6.0,
                 rng_seed: int | None = None) -> None:
        self._fleet = fleet
        self._bus = bus
        self._interval = interval_s
        self._rng = random.Random(rng_seed)
        self._task: asyncio.Task | None = None

    async def tick(self) -> None:
        fun = self._rng.choice(_SIM_FUNS)
        present = self._fleet.present_ids()
        if not present:
            return
        tgt = self._rng.choice(present)
        await _local_async(self._fleet, self._bus,
                           {"client": "local_async", "fun": fun, "tgt": tgt,
                            "tgt_type": "glob", "arg": []})
        if self._rng.random() < 0.1:
            mid = f"new-minion-{self._rng.randint(100, 999)}.demo.halite"
            await self._bus.publish("salt/key", {"id": mid, "act": "pend"})

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.tick()
            except Exception:  # never let the sim loop die
                pass

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
```

- [ ] **Step 4: Write `mock-salt-api/src/mock_salt/reset.py`**

```python
from __future__ import annotations

import asyncio

from mock_salt.fleet import build_fleet


class ResetLoop:
    """Periodically re-seeds the fleet to baseline so the shared demo stays clean.
    Mutates the passed-in state holder's `.fleet` attribute in place."""

    def __init__(self, holder, *, minutes: int, seed: int, size: int) -> None:
        self._holder = holder
        self._interval = minutes * 60
        self._seed = seed
        self._size = size
        self._task: asyncio.Task | None = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            self._holder.fleet = build_fleet(seed=self._seed, size=self._size)

    def start(self) -> None:
        if self._interval > 0 and self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
```

- [ ] **Step 5: Run to verify pass**

```bash
pytest tests/test_simulator.py -q
```
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add mock-salt-api/src/mock_salt/simulator.py mock-salt-api/src/mock_salt/reset.py mock-salt-api/tests/test_simulator.py
git commit -m "feat(mock): background simulator + periodic fleet reset"
```

---

## Task 8: FastAPI app + Dockerfile + smoke test

**Files:**
- Create: `mock-salt-api/src/mock_salt/app.py`
- Create: `mock-salt-api/tests/test_app.py`
- Create: `mock-salt-api/Dockerfile`
- Create: `mock-salt-api/README.md`

- [ ] **Step 1: Write the failing test**

`mock-salt-api/tests/test_app.py`:
```python
import json

from fastapi.testclient import TestClient

from mock_salt.app import create_app


def _client():
    return TestClient(create_app())


def test_login_then_lowstate():
    c = _client()
    r = c.post("/login", json={"username": "halite-demo", "password": "demo",
                               "eauth": "pam"})
    assert r.status_code == 200
    token = r.json()["return"][0]["token"]
    r2 = c.post("/", json=[{"client": "wheel", "fun": "key.list_all"}],
                headers={"X-Auth-Token": token})
    assert r2.status_code == 200
    assert "minions_pre" in r2.json()["return"][0]["data"]["return"]


def test_lowstate_accepts_single_object_or_list():
    c = _client()
    r = c.post("/", json={"client": "runner", "fun": "manage.present"},
               headers={"X-Auth-Token": "x"})
    assert r.status_code == 200
    assert isinstance(r.json()["return"][0], list)


def test_events_stream_emits_frames():
    c = _client()
    # the simulator is disabled under TestClient; publish via an action instead
    with c.stream("GET", "/events", params={"token": "x"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        # trigger an event from a second request while streaming
        c.post("/", json=[{"client": "local_async", "fun": "test.ping", "tgt": "*"}],
               headers={"X-Auth-Token": "x"})
        chunk = next(resp.iter_lines())
        # first non-empty line should be a tag: or data: line eventually
        assert chunk is not None
```

> Note: if the streaming assertion proves flaky under `TestClient`, keep the status/content-type checks and assert frame *formatting* via a direct `format_sse` unit test instead (already covered in Task 3). Do not loop forever waiting on the stream.

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_app.py -q
```
Expected: FAIL (`No module named 'mock_salt.app'`).

- [ ] **Step 3: Write `mock-salt-api/src/mock_salt/app.py`**

```python
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
    async def lowstate(body, request: Request):
        calls = body if isinstance(body, list) else [body]
        results = []
        for call in calls:
            results.append(await dispatch(state.fleet, state.bus, call))
        # salt-api merges the per-call "return" lists into one envelope
        merged: list = []
        for r in results:
            merged.extend(r.get("return", []))
        return {"return": merged}

    @app.get("/events")
    async def events(request: Request):
        async def gen():
            with state.bus.subscribe() as q:
                # keepalive comment on connect
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
```

> Note: the `POST /` handler takes `body` untyped so it accepts both a single lowstate object and salt-api's list form. The merge mirrors salt-api returning one `return` array per envelope.

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_app.py -q && pytest -q
```
Expected: app tests PASS; full suite green.

- [ ] **Step 5: Write `mock-salt-api/Dockerfile`**

```dockerfile
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "mock_salt.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 6: Write `mock-salt-api/README.md`**

````markdown
# mock-salt-api

A standalone server that mimics the salt-api surface Halite consumes
(`POST /login`, `POST /` lowstate dispatch, `GET /events` SSE), backed by a
seeded in-memory fleet with a background simulator. Used for the Halite demo —
see `docs/superpowers/specs/2026-05-31-demo-site-design.md`.

```bash
python3.13 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
pytest -q
uvicorn mock_salt.app:create_app --factory --reload --port 8000
```

Point Halite at it with `SALT_API_URL=http://localhost:8000`, service user
`halite-demo` / `demo` (override via `MOCK_SALT_USERNAME`/`MOCK_SALT_PASSWORD`),
and enable the event stream in Settings.
````

- [ ] **Step 7: Manual integration check (point Halite at the mock)**

Run the mock (`uvicorn ... --port 8000`). In a separate Halite backend dev instance, set `AppSettings` salt connection to `http://localhost:8000` / `halite-demo` / `demo`, enable the event stream, and confirm: Minions/Keys/Jobs/Inventory/Fleet pages populate, the Activity feed streams live events, and a Run dispatches and returns. (This is the Phase-1 acceptance gate; Phase 2 automates the wiring.)

- [ ] **Step 8: Commit**

```bash
git add mock-salt-api/src/mock_salt/app.py mock-salt-api/tests/test_app.py mock-salt-api/Dockerfile mock-salt-api/README.md
git commit -m "feat(mock): FastAPI app (login/lowstate/events) + Dockerfile + README"
```

---

## Self-review notes

- **Spec coverage:** login + lowstate dispatch (Tasks 3–5) covers every `(client, fun)` in the spec's contract table incl. inventory (`pkg.list_pkgs`, `grains.get`) and fleet (`jobs.list_job` with state-style returns); `/events` SSE + framing (Tasks 3, 8); event-shape contract guard (Task 6); simulator + reset (Task 7); seeded fleet with key states / offline+stale / state runs / inventory variance (Task 2); Dockerfile (Task 8). Demo-mode + compose are intentionally **Phase 2** (separate plan).
- **Type consistency:** `Fleet`/`Minion`/`Job` fields, `dispatch(fleet, bus, lowstate)`, `EventBus.subscribe()/publish()`, `format_sse(tag, data)`, `_local_async`/`_key_action`, `Simulator(fleet, bus)`, `ResetLoop(holder, ...)` are used consistently across tasks.
- **Events match `normalize.py`:** Task 6 imports the real normalizer and is the regression guard against drift.
- **No DB / no Halite changes** in Phase 1 — the mock is fully standalone; the only cross-import is the test-only `sys.path` import of the stdlib-only `normalize.py`.
