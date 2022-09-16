import json as jsn
import logging
import re
from dataclasses import dataclass
from subprocess import Popen, PIPE
from typing import Dict, Optional, Tuple, List
from juju.model import Model

import yaml

logger = logging.getLogger(__file__)

JUJU_COMMAND = "/snap/bin/juju"
_JUJU_DATA_CACHE = {}
_JUJU_KEYS = ("egress-subnets", "ingress-address", "private-address")


def _purge(data: dict):
    for key in _JUJU_KEYS:
        if key in data:
            del data[key]


def _juju_status(app_name, model: str = None, json: bool = False):
    cmd = f'{JUJU_COMMAND} status{" " + app_name if app_name else ""} --relations'
    if model:
        cmd += f' -m {model}'
    if json:
        cmd += ' --format json'
    proc = Popen(cmd.split(), stdout=PIPE, stderr=PIPE)
    raw = proc.stdout.read().decode('utf-8')
    if json:
        return jsn.loads(raw)
    return raw


def _show_unit(unit_name, model: str = None):
    if model:
        proc = Popen(f"{JUJU_COMMAND} show-unit -m {model} {unit_name}".split(),
                     stdout=PIPE)
    else:
        proc = Popen(f"{JUJU_COMMAND} show-unit {unit_name}".split(),
                     stdout=PIPE)
    return proc.stdout.read().decode("utf-8").strip()


def _get_unit_info(unit_name: str, model: str = None) -> dict:
    """Returns unit-info data structure.

     for example:

    traefik-k8s/0:
      opened-ports: []
      charm: local:focal/traefik-k8s-1
      leader: true
      relation-info:
      - endpoint: ingress-per-unit
        related-endpoint: ingress
        application-data:
          _supported_versions: '- v1'
        related-units:
          prometheus-k8s/0:
            in-scope: true
            data:
              egress-subnets: 10.152.183.150/32
              ingress-address: 10.152.183.150
              private-address: 10.152.183.150
      provider-id: traefik-k8s-0
      address: 10.1.232.144
    """
    if cached_data := _JUJU_DATA_CACHE.get(unit_name):
        return cached_data

    raw_data = _show_unit(unit_name, model=model)
    if not raw_data:
        raise ValueError(
            f"no unit info could be grabbed for {unit_name}; "
            f"are you sure it's a valid unit name?"
        )

    data = yaml.safe_load(raw_data)
    if unit_name not in data:
        raise KeyError(f"{unit_name} not in {data!r}")

    unit_data = data[unit_name]
    _JUJU_DATA_CACHE[unit_name] = unit_data
    return unit_data


def _get_relation_by_endpoint(relations, local_endpoint, remote_endpoint,
                              remote_obj, peer: bool):
    matches = [
        r for r in relations if
        ((r["endpoint"] == local_endpoint and
          r["related-endpoint"] == remote_endpoint) or
         (r["endpoint"] == remote_endpoint and
          r["related-endpoint"] == local_endpoint))
    ]
    if not peer:
        matches = [r for r in matches if remote_obj in r["related-units"]]

    if not matches:
        raise ValueError(
            f"no relations found with remote endpoint={remote_endpoint!r} "
            f"and local endpoint={local_endpoint!r} "
            f"in {remote_obj!r}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"multiple relations found with remote endpoint={remote_endpoint!r} "
            f"and local endpoint={local_endpoint!r} "
            f"in {remote_obj!r} (relations={matches})"
        )
    return matches[0]


@dataclass
class Metadata:
    scale: int
    units: Tuple[int, ...]
    leader_id: int
    interface: str


@dataclass
class AppRelationData:
    app_name: str
    relation_id: int
    meta: Metadata
    endpoint: str
    application_data: dict
    units_data: Dict[int, dict]


def _get_metadata_from_status(app_name, relation_name, other_app_name,
                              other_relation_name, model: str = None):
    # line example: traefik-k8s           active      3  traefik-k8s             0  10.152.183.73  no
    status = _juju_status(app_name, model=model, json=True)
    # machine status json output apparently has no 'scale'... -_-
    scale = len(status['applications'][app_name]['units'])

    leader_id: int = None
    unit_ids: List[int] = []

    for u, v in status['applications'][app_name]['units'].items():
        unit_id = int(u.split('/')[1])
        if v.get('leader', False):
            leader_id = unit_id
        unit_ids.append(unit_id)
    if leader_id is None:
        raise RuntimeError(f'could not identify leader among units {unit_ids}. '
                           f'You might need to wait for all units to be allocated.')

    # we gotta do this because json status --format json does not include the interface
    raw_text_status = _juju_status(app_name, model=model)

    re_safe_app_name = app_name.replace('-', r'\-')
    intf_re = fr"(({re_safe_app_name}:{relation_name}\s+{other_app_name}:{other_relation_name})|({other_app_name}:{other_relation_name}\s+{app_name}:{relation_name}))\s+([\w\-]+)"
    interface = re.compile(intf_re).findall(raw_text_status)[0][-1]
    return Metadata(scale, tuple(unit_ids), leader_id, interface)


def _get_app_name_and_units(url, relation_name,
                            other_app_name, other_relation_name,
                            model: str = None):
    """Get app name and unit count from url; url is either `app_name/0` or `app_name`."""
    app_name, unit_id = url.split('/') if '/' in url else (url, None)

    meta = _get_metadata_from_status(app_name, relation_name, other_app_name,
                                     other_relation_name, model=model)
    if unit_id:
        units = (int(unit_id),)
    else:
        units = meta.units
    return app_name, units, meta


def get_content(obj: str, other_obj,
                include_default_juju_keys: bool = False,
                model: str = None,
                peer: bool = False) -> AppRelationData:
    """Get the content of the databag of `obj`, as seen from `other_obj`."""
    url, endpoint = obj.split(":")
    other_url, other_endpoint = other_obj.split(":")

    other_app_name, _ = other_url.split('/') if '/' in other_url else (
        other_url, None)

    app_name, units, meta = _get_app_name_and_units(
        url, endpoint, other_app_name, other_endpoint,
        model)

    # in k8s there's always a 0 unit, in machine that's not the case.
    # so even though we need 'any' remote unit name, we still need to query the status
    # to find out what units there are.
    status = _juju_status(other_app_name, model=model, json=True)
    other_unit_name = next(
        iter(status['applications'][other_app_name]['units']))
    # we might have a different number of units and other units, and it doesn't
    # matter which 'other' we pass to get the databags for 'this one'.
    # in peer relations, show-unit luckily reports 'local-unit', so we're good.

    leader_unit_data = None
    app_data = None
    units_data = {}
    r_id = None
    for unit_id in units:
        unit_name = f"{app_name}/{unit_id}"
        unit_data, app_data, r_id_ = _get_databags(
            unit_name, other_unit_name,
            endpoint, other_endpoint,
            model=model, peer=peer)

        if r_id is not None:
            assert r_id == r_id_, f'mismatching relation IDs: {r_id, r_id_}'
        r_id = r_id_

        if not include_default_juju_keys:
            _purge(unit_data)
        units_data[unit_id] = unit_data

    return AppRelationData(
        app_name=app_name,
        meta=meta,
        endpoint=endpoint,
        application_data=app_data,
        units_data=units_data,
        relation_id=r_id)


def _get_databags(local_unit, remote_unit, local_endpoint, remote_endpoint,
                  model: str = None, peer: bool = False):
    """Gets the databags of local unit and its leadership status.

    Given a remote unit and the remote endpoint name.
    """
    local_data = _get_unit_info(local_unit, model=model)
    data = _get_unit_info(remote_unit, model=model)
    relation_info = data.get("relation-info")
    if not relation_info:
        raise RuntimeError(f"{remote_unit} has no relations")

    raw_data = _get_relation_by_endpoint(relation_info, local_endpoint,
                                         remote_endpoint, local_unit, peer=peer)
    if peer:
        unit_data = raw_data["local-unit"]["data"]
    else:
        unit_data = raw_data["related-units"][local_unit]["data"]
    app_data = raw_data["application-data"]
    return unit_data, app_data, raw_data['relation-id']


@dataclass
class RelationData:
    provider: AppRelationData
    requirer: AppRelationData


def get_peer_relation_data(
        *, endpoint: str,
        include_default_juju_keys: bool = False, model: str = None
):
    return get_content(endpoint, endpoint,
                       include_default_juju_keys, model=model,
                       peer=True)


def get_relation_data(
        *, provider_endpoint: str, requirer_endpoint: str,
        include_default_juju_keys: bool = False, model: str = None
):
    """Get relation databags for a juju relation.

    >>> get_relation_data('prometheus/0:ingress', 'traefik/1:ingress-per-unit')
    """
    provider_data = get_content(provider_endpoint, requirer_endpoint,
                                include_default_juju_keys, model=model)
    requirer_data = get_content(requirer_endpoint, provider_endpoint,
                                include_default_juju_keys, model=model)

    # sanity check: the two IDs should be identical
    if not provider_data.relation_id == requirer_data.relation_id:
        logger.warning(
            f"provider relation id {provider_data.relation_id} "
            f"not the same as requirer relation id: {requirer_data.relation_id}")

    return RelationData(provider=provider_data, requirer=requirer_data)
