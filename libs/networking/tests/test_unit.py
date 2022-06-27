# add here your unittests
import sys
from ipaddress import IPv4Address
from pathlib import Path

import pytest as pytest
from ops.charm import CharmBase, ConfigChangedEvent, RelationEvent
from ops.model import Relation
from ops.testing import Harness

lib_root = Path(__file__).parent.parent
sys.path.append(str(lib_root))

from networking import (
    Network,
    add_network,
    apply_harness_patch,
    networking,
    NetworkingError,
    remove_network,
    retract_harness_patch,
)


def test_notimpl_default():
    class Charm(CharmBase):
        pass

    h: Harness[Charm] = Harness(Charm)
    h.begin()
    c = h.charm
    with pytest.raises(NotImplementedError):
        _ = c.model.get_binding("juju-info").network.bind_address


def test_patch_twice():
    with networking():
        with pytest.raises(NetworkingError):
            apply_harness_patch()


def test_default_juju_info_bind():
    with networking():

        class Charm(CharmBase):
            pass

        h: Harness[Charm] = Harness(Charm)
        h.begin()
        c = h.charm
        assert c.model.get_binding("juju-info").network.bind_address == IPv4Address(
            "1.1.1.1"
        )


def test_add_relation_binding():
    apply_harness_patch()

    class Charm(CharmBase):
        pass

    h: Harness[Charm] = Harness(Charm)
    h.begin()
    c = h.charm
    assert c.model.get_binding("juju-info").network.bind_address == IPv4Address(
        "1.1.1.1"
    )
    retract_harness_patch()


def test_multiple_bindings():
    class Charm(CharmBase):
        pass

    h: Harness[Charm] = Harness(Charm)
    h.begin()
    c = h.charm
    foo = Relation(
        relation_name="foo",
        relation_id=42,
        is_peer=False,
        our_unit=c.unit,
        backend=h._backend,
        cache=h.model._cache,
    )

    with networking(
        networks={foo: Network(private_address="42.42.42.42")}, make_default=True
    ):
        assert c.model.get_binding("juju-info").network.bind_address == IPv4Address(
            "1.1.1.1"
        )
        assert c.model.get_binding(foo).network.bind_address == IPv4Address(
            "42.42.42.42"
        )
        assert c.model.get_binding("foo").network.bind_address == IPv4Address(
            "42.42.42.42"
        )


def test_multiple_bindings_defaults():
    class Charm(CharmBase):
        pass

    h: Harness[Charm] = Harness(Charm)
    h.begin()
    c = h.charm
    foo1 = Relation(
        relation_name="foo",
        relation_id=42,
        is_peer=False,
        our_unit=c.unit,
        backend=h._backend,
        cache=h.model._cache,
    )

    foo2 = Relation(
        relation_name="foo",
        relation_id=43,
        is_peer=False,
        our_unit=c.unit,
        backend=h._backend,
        cache=h.model._cache,
    )

    with networking(
        networks={
            "foo": Network(private_address="42.42.42.42"),
            foo1: Network(private_address="42.42.42.42"),
            foo2: Network(private_address="43.43.43.43"),
        }
    ):
        assert c.model.get_binding("juju-info").network.bind_address == IPv4Address(
            "1.1.1.1"
        )
        assert c.model.get_binding(foo1).network.bind_address == IPv4Address(
            "42.42.42.42"
        )
        # default is foo1's binding
        assert c.model.get_binding("foo").network.bind_address == IPv4Address(
            "42.42.42.42"
        )
        # I can get foo2's binding by specifying the id
        assert c.model.get_binding(foo2).network.bind_address == IPv4Address(
            "43.43.43.43"
        )

        # if I pop foo1, I'm left with no foo1-specific binding
        remove_network("foo", foo1.id)
        del c.model._bindings._data[foo1]  # clear model cache
        # but foo still has sa default binding
        _ = c.model.get_binding("foo").network.bind_address
        # so also for foo1 it will still work
        _ = c.model.get_binding(foo1).network.bind_address

        # foo2 still has its specific override
        assert c.model.get_binding(foo2).network.bind_address == IPv4Address(
            "43.43.43.43"
        )

        # now let's pop the default
        remove_network("foo", None)
        del c.model._bindings._data["foo"]  # clear model cache
        del c.model._bindings._data[foo1]  # clear model cache
        # both foo1 specific and 'foo' will now break:
        with pytest.raises(NetworkingError):
            _ = c.model.get_binding("foo").network.bind_address
        with pytest.raises(NetworkingError):
            _ = c.model.get_binding(foo1).network.bind_address

        # foo2 still works
        assert c.model.get_binding(foo2).network.bind_address == IPv4Address(
            "43.43.43.43"
        )
        # now we pop it
        remove_network("foo", foo2.id)
        del c.model._bindings._data[foo2]  # clear model cache

        # and now it's all gone
        with pytest.raises(NetworkingError):
            _ = c.model.get_binding(foo2).network.bind_address
        with pytest.raises(NetworkingError):
            _ = c.model.get_binding(foo1).network.bind_address
        with pytest.raises(NetworkingError):
            _ = c.model.get_binding("foo").network.bind_address


def test_default_binding():
    class Charm(CharmBase):
        pass

    h: Harness[Charm] = Harness(Charm)
    h.begin()
    c = h.charm

    with networking(networks={"foo": Network(private_address="42.42.42.42")}):
        assert c.model.get_binding("juju-info").network.bind_address == IPv4Address(
            "1.1.1.1"
        )
        assert c.model.get_binding("foo").network.bind_address == IPv4Address(
            "42.42.42.42"
        )


def test_dynamic_add_remove():
    class Charm(CharmBase):
        pass

    h: Harness[Charm] = Harness(Charm)
    h.begin()
    c = h.charm

    with networking():
        with pytest.raises(NetworkingError):
            _ = c.model.get_binding("foo").network
        add_network("foo", None, Network(private_address="42.42.42.42"))

        _ = c.model.get_binding("foo").network

        # model caches stuff..
        del c.model._bindings._data["foo"]

        remove_network("foo", None)
        with pytest.raises(NetworkingError):
            _ = c.model.get_binding("foo").network
