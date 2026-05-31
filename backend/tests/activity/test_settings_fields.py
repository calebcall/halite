from halite.settings.schemas import PollerSettingsIn


def test_event_stream_fields_accepted():
    p = PollerSettingsIn(event_stream_enabled=True, event_stream_retention_days=14)
    assert p.event_stream_enabled is True
    assert p.event_stream_retention_days == 14
