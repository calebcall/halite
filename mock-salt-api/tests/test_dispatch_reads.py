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


@pytest.mark.asyncio
async def test_jobs_active_shape(fleet):
    jid = next(iter(fleet.jobs))
    fleet.jobs[jid].active = True
    body = await dispatch(fleet, None, {"client": "runner", "fun": "jobs.active"})
    active = body["return"][0]
    assert jid in active and "Function" in active[jid]


@pytest.mark.asyncio
async def test_cache_grains_shape(fleet):
    body = await dispatch(fleet, None, {"client": "runner", "fun": "cache.grains",
                                        "tgt": "*", "tgt_type": "glob"})
    result = body["return"][0]
    mid = fleet.accepted_ids()[0]
    assert result[mid]["os_family"]


@pytest.mark.asyncio
async def test_grains_get_os_family(fleet):
    body = await dispatch(fleet, None, {"client": "local", "fun": "grains.get",
                                        "tgt": "*", "tgt_type": "glob",
                                        "arg": ["os_family"]})
    result = body["return"][0]
    mid = fleet.accepted_ids()[0]
    assert result[mid] in ("Debian", "RedHat", "Alpine", "Windows")


@pytest.mark.asyncio
async def test_grains_items_shape(fleet):
    body = await dispatch(fleet, None, {"client": "local", "fun": "grains.items",
                                        "tgt": "*", "tgt_type": "glob"})
    result = body["return"][0]
    mid = fleet.accepted_ids()[0]
    assert result[mid]["id"] == mid
