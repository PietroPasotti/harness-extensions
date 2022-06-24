# What this is

This is a library providing a utility for unittesting events fired on a Harness-ed Charm.
Good when: 
 - you want to verify that a specific event has been fired on the charm as a response to <something>
 - you want to verify that a specific sequence of events have been fired.
 - you want to unittest the interface exposed by some (custom) event.

# How to get

`charmcraft fetch-lib charms.harness_extensions.v0.capture_events`

# How to use

```python
from charms.harness_extensions.v0.capture_events import capture, capture_events
from charm import MyCustomEvent, OtherCustomEvent
from ops.charm import RelationEvent, ConfigChangedEvent
from ops.testing import Harness


def test_relation_event_emitted(harness: Harness):
    with capture(harness.charm, RelationEvent) as captured:
        harness.add_relation('foo', 'remote')
    assert captured.event.unit.name == 'remote'

    
def test_many_events_emitted(harness: Harness):
    id = harness.add_relation('foo', 'remote')

    with capture_events(harness.charm, RelationEvent, MyCustomEvent, OtherCustomEvent, ConfigChangedEvent) as captured:
        harness.remove_relation(id)
        
    assert len(captured) == 5
    broken, departed, custom1, custom2, config = captured
    assert broken.relation.name == 'foo'
    assert departed.relation.name == 'foo'
    assert custom1.foo == 'bar'
    assert isinstance(config, ConfigChangedEvent)
```

# How to update

All subsequent times, if you want to publish a new revision, you can run `scripts/update.sh`.
This will 
 - Bump the revision
 - Inline the lib
 - Publish the lib

When you bump to a new (major) version, you'll have to manually change the 
value of `$LIB_V` in `scripts/publish.sh`.
