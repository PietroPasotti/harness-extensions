# add here your unittests
import sys
from ipaddress import IPv4Address
from pathlib import Path

import pytest as pytest
import yaml
from ops.charm import CharmBase, ConfigChangedEvent, RelationEvent
from ops.model import Relation
from ops.testing import Harness

lib_root = Path(__file__).parent.parent
sys.path.append(str(lib_root))

from relation_data_wrapper import get_relation_data_from_harness

META = yaml.safe_dump({'name': 'local',
                       'requires': {'ingress': {'interface': 'foo'}}})


def test_notimpl_default():
    class Charm(CharmBase):
        pass

    h: Harness[Charm] = Harness(Charm, meta=META)
    h.begin()
    r_id = h.add_relation('ingress', 'remote')
    h.add_relation_unit(r_id, 'remote/0')
    h.add_relation_unit(r_id, 'remote/1')

    h.update_relation_data(r_id, 'local', {'lapp': 'data'})
    h.update_relation_data(r_id, 'local/0', {'lunit0': 'data0'})
    h.update_relation_data(r_id, 'remote', {'rapp': 'data'})
    h.update_relation_data(r_id, 'remote/0', {'unit0': 'data0'})
    h.update_relation_data(r_id, 'remote/1', {'unit1': 'data1'})

    rdata = get_relation_data_from_harness(
        h,
        provider_endpoint='local:ingress',
        requirer_endpoint='remote:ingress'
    )
    assert rdata.requirer.app_name == 'remote'
    assert rdata.requirer.units_data[0] == {'unit0': 'data0'}
    assert rdata.requirer.units_data[1] == {'unit1': 'data1'}
    assert len(rdata.requirer.units_data) == 2

    assert rdata.provider.app_name == 'local'
    assert rdata.provider.units_data[0] == {'lunit0': 'data0'}
    assert len(rdata.provider.units_data) == 1

