# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from collections import defaultdict
from contextlib import contextmanager
from copy import deepcopy
from typing import Dict, List, Optional, TypedDict, Union

from ops.model import Relation

log = logging.getLogger("networking")

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
}

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


def apply_harness_patch(juju_info_network: "_Network" = JUJU_INFO):
    """Patches harness.backend.network_get and initializes the juju-info binding."""
    global PATCH_ACTIVE, _NETWORKS
    if PATCH_ACTIVE:
        raise RuntimeError("patch already active")

    from ops.testing import _TestingModelBackend

    _NETWORKS = defaultdict(dict)
    _TestingModelBackend.network_get = _network_get
    _NETWORKS["juju-info"][None] = juju_info_network

    PATCH_ACTIVE = True


def retract_harness_patch():
    """Undoes the patch."""
    global PATCH_ACTIVE, _NETWORKS
    assert PATCH_ACTIVE, "patch not active"

    PATCH_ACTIVE = False
    _NETWORKS = None


_NETWORKS = None  # type: Dict[str, Dict[Optional[int], _Network]]
PATCH_ACTIVE = False


def _network_get(_, endpoint_name, relation_id=None) -> _Network:
    if not PATCH_ACTIVE:
        raise NotImplementedError("network-get")

    try:
        endpoints = _NETWORKS[endpoint_name]
        if not endpoints:
            raise KeyError(endpoint_name)
        network = endpoints.get(relation_id)
        if not network:
            # fall back to 'default' binding for relation:
            return endpoints[None]
        return network
    except KeyError as e:
        raise RuntimeError(
            f"No network for {endpoint_name} -r ({relation_id}); "
            f"try `add_network({endpoint_name}, {relation_id}, Network(...))`"
        ) from e


def add_network(endpoint_name: str, relation_id: Optional[int], network: _Network):
    """Add a network to the harness.

    - `endpoint_name`: the relation name this network belongs to
    - `relation_id`: ID of the relation this network belongs to. If None, this will
        become the default network for the relation.
    - `network`: network data.
    """
    if _NETWORKS[endpoint_name].get(relation_id):
        log.warning(
            f"Endpoint {endpoint_name} is already bound "
            f"to a network for relation id {relation_id}."
            f"Overwriting..."
        )
    _NETWORKS[endpoint_name][relation_id] = network


def remove_network(endpoint_name: str, relation_id: int):
    """Remove a network from the harness."""
    del _NETWORKS[endpoint_name][relation_id]
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
    juju_info_network: Optional[_Network] = _not_given,
    networks: Optional[Dict[Union[str, Relation], _Network]] = None,
):
    """Context manager to activate/deactivate networking within a scope.

    Example usage:
    >>> with networking():
    >>>     assert charm.model.get_binding('juju-info').network.private_address

    >>> foo_relation = harness.model.get_relation('foo', 1)
    >>> bar_relation = harness.model.get_relation('bar', 2)
    >>> with networking(networks={
    ...         foo_relation: Network(private_address='42.42.42.42')}
    ...         'bar': Network(private_address='50.50.50.1')}
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

    networks = networks or {}
    if not PATCH_ACTIVE:
        patch_was_inactive = True
        apply_harness_patch(juju_info_network)
    elif juju_info_network:
        _NETWORKS["juju-info"][None] = juju_info_network

    for binding, network in networks.items():
        if isinstance(binding, str):
            name = binding
            bind_id = None
        elif isinstance(binding, Relation):
            name = binding.name
            bind_id = binding.id
        else:
            raise TypeError(binding)

        _NETWORKS[name][bind_id] = network

    yield

    _NETWORKS = old
    if patch_was_inactive:
        retract_harness_patch()
