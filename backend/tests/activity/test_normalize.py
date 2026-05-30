from halite.activity.normalize import normalize_event


def test_job_new():
    ev = normalize_event(
        "salt/job/20260529120000000000/new",
        {"fun": "state.apply", "minions": ["web01", "web02"], "tgt": "*"},
    )
    assert ev is not None
    assert ev["category"] == "job"
    assert ev["event_type"] == "job.new"
    assert ev["jid"] == "20260529120000000000"
    assert ev["fun"] == "state.apply"
    assert ev["minion_id"] is None
    assert "state.apply" in ev["summary"]


def test_job_ret_success():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/web01",
        {"fun": "test.ping", "id": "web01", "retcode": 0, "return": True},
    )
    assert ev["category"] == "job"
    assert ev["event_type"] == "job.ret"
    assert ev["minion_id"] == "web01"
    assert ev["jid"] == "20260529120000000000"
    assert ev["success"] is True


def test_job_ret_failure_via_retcode():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/db07",
        {"fun": "state.apply", "id": "db07", "retcode": 2, "return": {}},
    )
    assert ev["success"] is False


def test_job_ret_highstate_with_changes():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/web01",
        {
            "fun": "state.highstate",
            "id": "web01",
            "retcode": 0,
            "return": {
                "pkg_|-nginx_|-nginx_|-installed": {"changes": {"nginx": "1.2"}},
                "file_|-conf_|-/etc/nginx_|-managed": {"changes": {}},
            },
        },
    )
    assert ev["event_type"] == "job.ret"
    assert ev["success"] is True
    assert ev["changed"] is True


def test_job_ret_highstate_clean():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/web01",
        {
            "fun": "state.highstate",
            "id": "web01",
            "retcode": 0,
            "return": {
                "pkg_|-nginx_|-nginx_|-installed": {"changes": {}},
                "file_|-conf_|-/etc/nginx_|-managed": {"changes": {}},
            },
        },
    )
    assert ev["success"] is True
    assert ev["changed"] is False


def test_job_ret_ping_changed_none():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/web01",
        {"fun": "test.ping", "id": "web01", "retcode": 0, "return": True},
    )
    assert ev["changed"] is None


def test_job_ret_failed_highstate_computes_changed():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/db07",
        {
            "fun": "state.highstate",
            "id": "db07",
            "retcode": 2,
            "return": {
                "pkg_|-x_|-x_|-installed": {"result": False, "changes": {"x": "y"}},
            },
        },
    )
    assert ev["success"] is False
    assert ev["changed"] is True


def test_minion_start():
    ev = normalize_event("salt/minion/web01/start", {"id": "web01"})
    assert ev["category"] == "minion"
    assert ev["event_type"] == "minion.start"
    assert ev["minion_id"] == "web01"


def test_key_accept():
    ev = normalize_event("salt/key", {"id": "db07", "act": "accept"})
    assert ev["category"] == "key"
    assert ev["event_type"] == "key.accept"
    assert ev["minion_id"] == "db07"


def test_auth_pending():
    ev = normalize_event("salt/auth", {"id": "db07", "act": "pend", "result": True})
    assert ev["category"] == "key"
    assert ev["event_type"] == "key.pend"
    assert ev["minion_id"] == "db07"


def test_unknown_tag_dropped():
    assert normalize_event("salt/beacon/web01/diskusage/x", {"id": "web01"}) is None
    assert normalize_event("salt/run/x/new", {}) is None
