from __future__ import annotations

from halite.fleet.parser import HighstateCounts, summarize_lowstate


def test_summarize_lowstate_returns_none_when_not_a_dict():
    assert summarize_lowstate(None) is None
    assert summarize_lowstate([]) is None
    assert summarize_lowstate("nope") is None


def test_summarize_lowstate_returns_none_when_keys_dont_match_pattern():
    assert summarize_lowstate({"not_a_valid_key": {}}) is None


def test_summarize_lowstate_counts_pass_fail_change():
    raw = {
        "pkg_|-redis_install_|-redis_|-installed": {
            "result": True, "comment": "", "changes": {},
            "duration": 100.0, "__run_num__": 1,
        },
        "service_|-redis_running_|-redis_|-running": {
            "result": True, "comment": "", "changes": {"pid": 1234},
            "duration": 200.0, "__run_num__": 2,
        },
        "cmd_|-broken_|-fail.sh_|-run": {
            "result": False, "comment": "boom", "changes": {},
            "duration": 50.0, "__run_num__": 3,
        },
        "file_|-noop_|-/tmp/x_|-managed": {
            "result": None, "comment": "test mode", "changes": {},
            "duration": 10.0, "__run_num__": 4,
        },
    }
    counts = summarize_lowstate(raw)
    assert counts == HighstateCounts(
        total=4, passed=2, failed=1, changed=1, duration_ms=360
    )


def test_summarize_lowstate_handles_multiline_state_names():
    raw = {
        "cmd_|-teleport_install_|-#!/bin/bash\necho hi\nexit 0_|-run": {
            "result": True, "comment": "", "changes": {},
            "duration": 500.0, "__run_num__": 1,
        },
    }
    counts = summarize_lowstate(raw)
    assert counts is not None
    assert counts.total == 1
    assert counts.passed == 1
