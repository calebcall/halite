import pytest

from mock_salt.fleet import build_fleet


@pytest.fixture()
def fleet():
    return build_fleet(seed=1337, size=40)
