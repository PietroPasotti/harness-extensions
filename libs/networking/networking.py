# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from typing import Dict, List, Optional, TypedDict, Union

from ops.model import Relation

log = logging.getLogger("networking")


class NetworkingError(RuntimeError):
    """Base class for errors raised from this module."""


JUJU_INFO = {
    "bind-addresses": [
        {
            "mac-address": "",
            "interface-name": "",
            "interfacename": "",
            "addresses": [{"hostname": "", "value": "1.1.1.1", "cidr": ""}],
        }
    ],
    "bind-address": "1.1.1.1",
    "egress-subnets": ["1.1.1.2/32"],
    "ingress-addresses": ["1.1.1.2"],
}  # type: _Network

_Address = TypedDict("_Address", {"hostname": str, "value": str, "cidr": str})
_BindAddress = TypedDict(
    "_BindAddress",
    {
        "mac-address": str,
        "interface-name": str,
        "interfacename": str,  # ?
        "addresses": List[_Address],
    },
)
_Network = TypedDict(
    "_Network",
    {
        "bind-addresses": List[_BindAddress],
        "bind-address": str,
        "egress-subnets": List[str],
        "ingress-addresses": List[str],
    },
)


def activate(juju_info_network: "_Network" = JUJU_INFO):
    """Patches harness.backend.network_get and initializes the juju-info binding."""
    global PATCH_ACTIVE, _NETWORKS
    if PATCH_ACTIVE:
        raise NetworkingError("patch already active")
    assert not _NETWORKS  # type guard

    from ops.testing import _TestingModelBackend

    _NETWORKS = defaultdict(dict)
    _TestingModelBackend.network_get = _network_get  # type: ignore
    _NETWORKS["juju-info"][None] = juju_info_network

    PATCH_ACTIVE = True


def deactivate():
    """Undoes the patch."""
    global PATCH_ACTIVE, _NETWORKS
    assert PATCH_ACTIVE, "patch not active"

    PATCH_ACTIVE = False
    _NETWORKS = None  # type: ignore


_NETWORKS = None  # type: Optional[Dict[str, Dict[Optional[int], _Network]]]
PATCH_ACTIVE = False


def _network_get(_, endpoint_name, relation_id=None) -> _Network:
    if not PATCH_ACTIVE:
        raise NotImplementedError("network-get")
    assert _NETWORKS  # type guard

    try:
        endpoints = _NETWORKS[endpoint_name]
        network = endpoints.get(relation_id)
        if not network:
            # fall back to default binding for relation:
            return endpoints[None]
        return network
    except KeyError as e:
        raise NetworkingError(
            f"No network for {endpoint_name} -r {relation_id}; "
            f"try `add_network({endpoint_name}, {relation_id} | None, Network(...))`"
        ) from e


def add_network(
    endpoint_name: str,
    relation_id: Optional[int],
    network: _Network,
    make_default=False,
):
    """Add a network to the harness.

    - `endpoint_name`: the relation name this network belongs to
    - `relation_id`: ID of the relation this network belongs to. If None, this will
        be the default network for the relation.
    - `network`: network data.
    - `make_default`: Make this the default network for the endpoint.
       Equivalent to calling this again with `relation_id==None`.
    """
    if not PATCH_ACTIVE:
        raise NetworkingError("module not initialized; " "run activate() first.")
    assert _NETWORKS  # type guard

    if _NETWORKS[endpoint_name].get(relation_id):
        log.warning(
            f"Endpoint {endpoint_name} is already bound "
            f"to a network for relation id {relation_id}."
            f"Overwriting..."
        )

    _NETWORKS[endpoint_name][relation_id] = network

    if relation_id and make_default:
        # make it default as well
        _NETWORKS[endpoint_name][None] = network


def remove_network(endpoint_name: str, relation_id: Optional[int]):
    """Remove a network from the harness."""
    if not PATCH_ACTIVE:
        raise NetworkingError("module not initialized; " "run activate() first.")
    assert _NETWORKS  # type guard

    _NETWORKS[endpoint_name].pop(relation_id)
    if not _NETWORKS[endpoint_name]:
        del _NETWORKS[endpoint_name]


def Network(
    private_address: str = "1.1.1.1",
    mac_address: str = "",
    hostname: str = "",
    cidr: str = "",
    interface_name: str = "",
    egress_subnets=("1.1.1.2/32",),
    ingress_addresses=("1.1.1.2",),
) -> _Network:
    """Construct a network object."""
    return {
        "bind-addresses": [
            {
                "mac-address": mac_address,
                "interface-name": interface_name,
                "interfacename": interface_name,
                "addresses": [
                    {"hostname": hostname, "value": private_address, "cidr": cidr}
                ],
            }
        ],
        "bind-address": private_address,
        "egress-subnets": list(egress_subnets),
        "ingress-addresses": list(ingress_addresses),
    }


_not_given = object()  # None is meaningful, but JUJU_INFO is mutable


@contextmanager
def networking(
    juju_info_network: Optional[_Network] = _not_given,  # type: ignore
    networks: Optional[Dict[Union[str, Relation], _Network]] = None,
    make_default: bool = False,
):
    """Context manager to activate/deactivate networking within a scope.

    Arguments:
        - `juju_info_network`: network assigned to the implicit 'juju-info' endpoint.
        - `networks`: mapping from endpoints (names, or relations) to networks.
        - `make_default`: whether the networks passed as relations should also
          be interpreted as default networks for the endpoint.

    Example usage:
    >>> with networking():
    >>>     assert charm.model.get_binding('juju-info').network.private_address

    >>> foo_relation = harness.model.get_relation('foo', 1)
    >>> bar_relation = harness.model.get_relation('bar', 2)
    >>> with networking(networks={
    ...         foo_relation: Network(private_address='42.42.42.42')}
    ...         'bar': Network(private_address='50.50.50.1')},
    ...         make_default=True,
    ...         ):
    >>>     assert charm.model.get_binding(foo_relation).network.private_address
    >>>     assert charm.model.get_binding('foo').network.private_address
    >>>     assert charm.model.get_binding('bar').network.private_address
    ...
    >>>     # this will raise an error! We only defined a default bar
    >>>     # network, not one specific to this relation ID.
    >>>     # assert charm.model.get_binding(bar_relation).network.private_address

    """
    global _NETWORKS
    old = deepcopy(_NETWORKS)
    patch_was_inactive = False

    if juju_info_network is _not_given:
        juju_info_network = JUJU_INFO

    if not PATCH_ACTIVE:
        patch_was_inactive = True
        activate(juju_info_network or JUJU_INFO)
    else:
        assert _NETWORKS  # type guard

        if juju_info_network:
            _NETWORKS["juju-info"][None] = juju_info_network

    for binding, network in networks.items() if networks else ():
        if isinstance(binding, str):
            name = binding
            bind_id = None
        elif isinstance(binding, Relation):
            name = binding.name
            bind_id = binding.id
        else:
            raise TypeError(binding)
        add_network(name, bind_id, network, make_default=make_default)

    yield

    _NETWORKS = old
    if patch_was_inactive:
        deactivate()
