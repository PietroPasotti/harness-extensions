import asyncio

import pytest
import yaml
from pytest_operator.plugin import OpsTest

from relation_data_wrapper import get_relation_data_from_juju


@pytest.mark.abort_on_fail
async def test_deployment(ops_test: OpsTest):
    await asyncio.gather(
        ops_test.juju(
            *(f"deploy -m {ops_test.model_name} traefik-k8s --channel edge "
              f"--revision 87 trfk --config external_hostname=foo.bar".split())),
        ops_test.juju(
            *(f"deploy -m {ops_test.model_name}  prometheus-k8s --channel beta "
              f"--revision 55 -n 2 prom".split()))
    )

    await ops_test.model.relate('trfk:ingress-per-unit', 'prom:ingress')
    await ops_test.model.wait_for_idle(['prom', 'trfk'], status='active', idle_period=15)


async def test_relation_data_wrapper(ops_test: OpsTest):
    rdata = get_relation_data_from_juju(requirer_endpoint='prom:ingress',
                                        provider_endpoint='trfk:ingress-per-unit')
    assert rdata.provider.app_name == 'trfk'
    assert set(rdata.provider.units_data) == {0}
    assert not rdata.provider.units_data[0]
    assert yaml.safe_load(rdata.provider.application_data['ingress'])['prom/0']['url']

    assert rdata.requirer.app_name == 'prom'
    assert set(rdata.requirer.units_data) == {0, 1}
    for n in [0, 1]:
        assert rdata.requirer.units_data[n]['model'] == ops_test.model_name
        assert rdata.requirer.units_data[n]['mode'] == 'http'
        assert rdata.requirer.units_data[n]['name'] == f'prom/{n}'
        assert rdata.requirer.units_data[n]['port'] == '9090'
        assert rdata.requirer.units_data[n]['host'].startswith(f'prom-{n}.prom-endpoints')
    assert not rdata.requirer.application_data


async def test_relation_data_wrapper_single_unit(ops_test: OpsTest):
    rdata = get_relation_data_from_juju(requirer_endpoint='prom/1:ingress',
                                        provider_endpoint='trfk/0:ingress-per-unit')
    assert rdata.provider.app_name == 'trfk'
    assert set(rdata.provider.units_data) == {0}
    assert not rdata.provider.units_data[0]
    assert yaml.safe_load(rdata.provider.application_data['ingress'])['prom/0']['url']

    assert rdata.requirer.app_name == 'prom'
    assert set(rdata.requirer.units_data) == {1}
    assert rdata.requirer.units_data[1]['model'] == ops_test.model_name
    assert rdata.requirer.units_data[1]['mode'] == 'http'
    assert rdata.requirer.units_data[1]['name'] == 'prom/1'
    assert rdata.requirer.units_data[1]['port'] == '9090'
    assert rdata.requirer.units_data[1]['host'].startswith('prom-1.prom-endpoints')
    assert not rdata.requirer.application_data
