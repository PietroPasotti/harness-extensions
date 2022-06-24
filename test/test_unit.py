# add here your unittests
import pytest as pytest
from ops.charm import CharmBase, ConfigChangedEvent, RelationEvent
from ops.testing import Harness

from capture_events import capture_events


@pytest.fixture
def harness():
    class Charm(CharmBase):
        pass

    return Harness(Charm)


@pytest.fixture
def charm(harness):
    return harness.charm


def test_capture(charm, harness):
    with capture_events(charm, ConfigChangedEvent, RelationEvent) as captured:
        harness.update_config({'foo', 'bar'})
        harness.add_relation('...')

    assert isinstance(captured[0], ConfigChangedEvent)

