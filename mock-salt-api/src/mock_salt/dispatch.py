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


def _resolve_targets(fleet: Fleet, tgt: str, tgt_type: str) -> list[str]:
    """Map a salt target to present accepted minion ids. Good enough for the demo:
    glob '*' = all present; an exact id matches just that minion; 'list' = membership;
    otherwise a glob stem substring match."""
    present = fleet.present_ids()
    if tgt in ("*", ""):
        return present
    if tgt_type == "list":
        wanted = set(tgt.split(",")) if isinstance(tgt, str) else set(tgt)
        return [m for m in present if m in wanted]
    if tgt in present:
        return [tgt]
    stem = tgt.strip("*")
    return [m for m in present if stem and stem in m]


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
        if fun in ("key.accept", "key.reject", "key.delete"):
            return await _key_action(fleet, bus, fun, lowstate.get("match"))
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
        if fun == "saltutil.kill_job":
            job = fleet.jobs.get(lowstate.get("jid") or "")
            if job is not None:
                job.active = False
            return {"return": [{}]}
    elif client == "local":
        if fun == "pkg.list_pkgs":
            return _pkg_list_pkgs(fleet, tgt, tgt_type)
        if fun == "grains.get":
            return _grains_get(fleet, tgt, tgt_type, arg)
        if fun in ("grains.items", "grains.item"):
            return _grains_items(fleet, tgt, tgt_type)
        if fun == "sys.list_functions":
            return _sys_list_functions(fleet, tgt, tgt_type)
    elif client == "local_async":
        return await _local_async(fleet, bus, lowstate)

    return {"return": [{}]}
