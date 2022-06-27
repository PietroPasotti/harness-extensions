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
        with pytest.raises(RuntimeError):
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

    with networking(networks={foo: Network(private_address="42.42.42.42")}):
        assert c.model.get_binding("juju-info").network.bind_address == IPv4Address(
            "1.1.1.1"
        )
        assert c.model.get_binding(foo).network.bind_address == IPv4Address(
            "42.42.42.42"
        )


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
        with pytest.raises(RuntimeError):
            _ = c.model.get_binding("foo").network
        add_network("foo", None, Network(private_address="42.42.42.42"))

        _ = c.model.get_binding("foo").network

        # model caches stuff..
        del c.model._bindings._data["foo"]

        remove_network("foo", None)
        with pytest.raises(RuntimeError):
            _ = c.model.get_binding("foo").network
