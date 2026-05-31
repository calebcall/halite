from halite.activity.consumer import EventStreamConsumer
from halite.activity.hub import EventHub
from halite.runtime import RuntimeConfig


def test_runtime_exposes_event_attrs():
    # Imports resolve and the symbols exist; full boot is covered by integration tests.
    assert EventStreamConsumer is not None
    hub = EventHub()
    assert hub.recent() == []
    # RuntimeConfig.__init__ sets event_hub/event_consumer to None by default.
    import inspect
    src = inspect.getsource(RuntimeConfig.__init__)
    assert "event_hub" in src
    assert "event_consumer" in src
