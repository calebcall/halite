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
    returns: dict[str, dict] = field(default_factory=dict)
    active: bool = False


@dataclass
class Fleet:
    minions: dict[str, Minion]
    jobs: dict[str, Job]
    packages: dict[str, dict]

    def accepted_ids(self) -> list[str]:
        return [m.id for m in self.minions.values() if m.key_state == "accepted"]

    def present_ids(self) -> list[str]:
        return [m.id for m in self.minions.values()
                if m.key_state == "accepted" and m.online]

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

    specials = {0: "pending", 1: "pending", 2: "pending", 3: "rejected", 4: "denied"}
    for i in range(size):
        os_name, family, release = _OS[i % len(_OS)]
        role = _ROLES[i % len(_ROLES)]
        mid = f"{role}{i:02d}.demo.halite"
        key_state = specials.get(i, "accepted")
        online = key_state == "accepted" and i not in (7, 12, 19)
        last_seen = datetime.now(tz=UTC) - (
            timedelta(days=3) if i == 7 else timedelta(minutes=rng.randint(0, 30))
        )
        minions[mid] = Minion(
            id=mid, grains=_grains(rng, mid, os_name, family, release),
            key_state=key_state, online=online, last_seen=last_seen,
        )
        base = dict(_PKGS_WIN if os_name == "Windows" else _PKGS_LINUX)
        if rng.random() < 0.4 and "nginx" in base:
            base["nginx"] = "1.22.1"
        packages[mid] = base

    jobs: dict[str, Job] = {}
    accepted = [m.id for m in minions.values() if m.key_state == "accepted"]
    funs = ["test.ping", "state.apply", "pkg.install", "cmd.run", "service.restart"]
    for n in range(220):
        fun = rng.choice(funs)
        offset = rng.uniform(0, 48 * 3600)
        jid = now_jid(offset)
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
