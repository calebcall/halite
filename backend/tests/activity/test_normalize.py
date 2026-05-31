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


def test_job_new_initiator_target_from_user_tgt():
    ev = normalize_event(
        "salt/job/20260529120000000000/new",
        {"fun": "state.apply", "minions": ["web01"], "tgt": "web*", "user": "alice"},
    )
    assert ev["initiator"] == "alice"
    assert ev["target"] == "web*"
    assert ev["duration_ms"] is None


def test_job_ret_state_durations_summed():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/web01",
        {
            "fun": "state.highstate",
            "id": "web01",
            "retcode": 0,
            "return": {
                "pkg_|-nginx_|-nginx_|-installed": {"changes": {}, "duration": 12.5},
                "file_|-conf_|-/etc/nginx_|-managed": {"changes": {}, "duration": 7.4},
                "cmd_|-noop_|-true_|-run": {"changes": {}},  # no duration key
            },
        },
    )
    assert ev["duration_ms"] == 20  # round(12.5 + 7.4) == 20


def test_job_ret_ping_duration_none():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/web01",
        {"fun": "test.ping", "id": "web01", "retcode": 0, "return": True},
    )
    assert ev["duration_ms"] is None


def test_job_ret_initiator_target_none_when_absent():
    ev = normalize_event(
        "salt/job/20260529120000000000/ret/web01",
        {"fun": "test.ping", "id": "web01", "retcode": 0, "return": True},
    )
    assert ev["initiator"] is None
    assert ev["target"] is None


def test_job_new_list_tgt_coerced_to_string():
    """salt -L targeting sends tgt as a list; _opt_str must coerce it to a string."""
    ev = normalize_event(
        "salt/job/20260529120000000000/new",
        {"fun": "test.ping", "minions": ["web01", "web02"], "tgt": ["web01", "web02"], "user": "alice"},
    )
    assert ev is not None
    assert ev["target"] == "['web01', 'web02']"
    assert ev["initiator"] == "alice"


def test_job_new_string_tgt_passes_through():
    """Plain glob/string tgt must pass through unchanged."""
    ev = normalize_event(
        "salt/job/20260529120000000000/new",
        {"fun": "test.ping", "minions": ["web01"], "tgt": "web*", "user": "bob"},
    )
    assert ev is not None
    assert ev["target"] == "web*"
    assert ev["initiator"] == "bob"


def test_unknown_tag_dropped():
    assert normalize_event("salt/beacon/web01/diskusage/x", {"id": "web01"}) is None
    assert normalize_event("salt/run/x/new", {}) is None
