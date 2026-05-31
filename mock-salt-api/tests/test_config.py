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
