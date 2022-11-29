# add here your unittests
import sys
from pathlib import Path

import pytest as pytest
import yaml
from ops.charm import (
    CharmBase,
    ConfigChangedEvent,
    RelationCreatedEvent,
    RelationEvent,
    RelationJoinedEvent,
)
from ops.testing import Harness

lib_root = Path(__file__).parent.parent
sys.path.append(str(lib_root))


from capture_events import capture_events


@pytest.fixture
def harness():
    class Charm(CharmBase):
        pass

    return Harness(Charm,
                   meta=yaml.safe_dump({"requires": {"foo": {"interface": "foo"}}}),
                   config=yaml.safe_dump(
        {'options': {'foo': {'type': 'string'}}}
    ))


@pytest.fixture
def charm(harness):
    harness.begin()
    return harness.charm


def test_capture(charm, harness):
    with capture_events(charm, ConfigChangedEvent, RelationEvent) as captured:
        harness.update_config({'foo': 'bar'})
        harness.add_relation('foo', 'remote')

    assert isinstance(captured[0], ConfigChangedEvent)
    assert isinstance(captured[1], RelationCreatedEvent)

    assert len(captured) == 2
