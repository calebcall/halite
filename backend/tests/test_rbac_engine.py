from halite.rbac.engine import check, matches_glob


def test_matches_glob_star_at_end():
    assert matches_glob("state.*", "state.apply") is True
    assert matches_glob("state.*", "test.ping") is False


def test_matches_glob_full_wildcard():
    assert matches_glob("*", "anything") is True


def test_matches_glob_prefix_with_colon():
    assert matches_glob("key:web-*", "key:web-01") is True
    assert matches_glob("key:web-*", "key:db-01") is False


def test_matches_glob_exact():
    assert matches_glob("test.ping", "test.ping") is True
    assert matches_glob("test.ping", "test.ping2") is False


class _FakeUser:
    def __init__(self, perms: list[tuple[str, str]]):
        self.permissions_cache = perms
        self.is_active = True


def test_check_allows_when_perm_matches():
    user = _FakeUser([("run", "state.*")])
    assert check(user, "run", "state.apply") is True


def test_check_denies_when_no_perm_matches():
    user = _FakeUser([("view", "minion:*")])
    assert check(user, "run", "state.apply") is False


def test_check_denies_inactive_user():
    user = _FakeUser([("*", "*")])
    user.is_active = False
    assert check(user, "run", "anything") is False


def test_check_wildcard_verb():
    user = _FakeUser([("*", "*")])
    assert check(user, "run", "state.apply") is True
    assert check(user, "view", "audit") is True
