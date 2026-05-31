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
    assert "state.apply" in funs
    assert "test.ping" in funs
    assert len(fleet.jobs) >= 100


def test_some_minions_offline_or_stale(fleet):
    assert any(not m.online for m in fleet.minions.values())


def test_packages_present(fleet):
    accepted = next(m for m in fleet.minions.values() if m.key_state == "accepted")
    assert fleet.packages[accepted.id]
