# What this is

This is a collection of libraries providing useful Harness plugins.
At the moment it contains two extension libraries:

- networking
- capture_events
- harness_ctx

## networking

This is a library providing a utility for mocking networking in Harness.
Good when: 
 - your charm relies on `bind_address`
 - your charm does things with `network-get`

### How to get

`charmcraft fetch-lib charms.harness_extensions.v0.networking`

### How to use

Basic usage:
```python
from charms.harness_extensions.v0 import networking
networking.activate()
```

Advanced use cases:
```python
# let's pretend 'foo' is a relation:
foo = charm.model.get_relation('foo', 1)
with networking(networks={foo: Network(private_address="42.42.42.42")}):
    # the juju-info network is present by default unless you pass None
    assert c.model.get_binding("juju-info").network.bind_address == IPv4Address("1.1.1.1")
    # the custom foo endpoint is mocked:
    assert c.model.get_binding(foo).network.bind_address == IPv4Address("42.42.42.42")
    assert c.model.get_binding('foo').network.bind_address == IPv4Address("42.42.42.42")
```

CAVEAT: The patch is global; that is, if you instantiate two Harnesses (don't do that), 
you won't be able to mock `network-get` calls on a per-harness basis.  

## capture_events

This is a library providing a utility for unittesting events fired on a Harness-ed Charm.
Good when: 
 - you want to verify that a specific event has been fired on the charm as a response to *something*
 - you want to verify that a specific sequence of events have been fired.
 - you want to unittest the interface exposed by some (custom) event.

### How to get

`charmcraft fetch-lib charms.harness_extensions.v0.capture_events`

### How to use

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


## harness_ctx

This is a library providing a utility for testing with Harness in a slightly stricter way.
Good when: 
 - your charm has state-dependent `__init__` logic that is malfunctioning because Harness does not reinitialize the charm
 - your charm (or dependencies) hook onto `framework.on.commit`, which Harness does not fire
 - you want a closer match between production charm behaviour and unittesting charm behaviour

This lib will likely become redundant once https://github.com/canonical/operator/issues/736 is solved; until then, this allows us to experiment with the concept.

### How to get

`charmcraft fetch-lib charms.harness_extensions.v0.harness_ctx`

### How to use

```python
class MyCharm(CharmBase):
    def __init__(self, framework: Framework, key: typing.Optional = None):
        super().__init__(framework, key)
        self.framework.observe(self.on.update_status, self._listen)
        self.framework.observe(self.framework.on.commit, self._listen)

    def _listen(self, e):
        self.event = e

with HarnessCtx(MyCharm, "update-status") as h:
    event = h.emit()  # this will be called automatically on context exit if you didn't call it manually
    assert event.handle.kind == "update_status"

assert h.harness.charm.event.handle.kind == "commit"
```


# How to update

When you contribute to this repo, before your changes get merged to main (but when they are final already), you can run `scripts/update.sh [lib name]`.
This will 
 - Bump the revision
 - Inline the lib
 - Publish the lib

When you bump to a new (major) version, you'll have to manually change the 
value of `$LIB_V` in `scripts/publish.sh`.
