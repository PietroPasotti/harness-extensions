"""How we'd like user code to look like.
This is a "real" scenario.
"""
import sys
from pathlib import Path
from unittest.mock import Mock

from ops.framework import Framework
from ops.charm import CharmBase
import typing
from evt_sequences import (
    Scenario, Playbook, RelationMeta, RelationSpec, Context, NetworkSpec, Network, Scene, Event,
    CharmSpec, ContainerSpec)

lib_root = Path(__file__).parent.parent
sys.path.append(str(lib_root))


def test_scenario_api():
    events_ran = []

    class MyCharm(CharmBase):
        def __init__(self, framework: Framework, key: typing.Optional = None):
            super().__init__(framework, key)
            for evt in self.on.events().values():
                self.framework.observe(evt, self._record)

        def _record(self, e):
            events_ran.append(e)

    # play a builtin scenario
    # this is the new begin_with_initial_hooks()
    Scenario.builtins.startup()(MyCharm).play_until_complete()
    Scenario.builtins.startup(leader=False)(MyCharm).play_until_complete()

    # this is like a simulate_teardown_sequence()
    Scenario.builtins.teardown()(MyCharm).play_until_complete()

    assert len(events_ran) == 10


def _test_context_stepping():
    events_ran = []

    class MyCharm(CharmBase):
        def __init__(self, framework: Framework, key: typing.Optional = None):
            super().__init__(framework, key)
            for evt in self.on.events().values():
                self.framework.observe(evt, self._record)

        def _record(self, e):
            events_ran.append(e)

    # once you have a Scenario defined, you can step through it
    # and run your assertions in between
    with Scenario.builtins.STARTUP_LEADER(MyCharm) as seq:
        seq.play_next()  # this will be an 'install'
        seq.play_next()  # leader-elected
        seq.play_next()  # config-changed
        seq.play_next()  # start
        seq.play_next()  # error! no more events in the scenario.

    # alternatively you can declare a scenario as you go, e.g. in REPL:
    with Scenario(MyCharm) as seq:
        ctx = Context(leader=True)
        from dataclasses import replace
        seq.play('update-status', context=ctx, add_to_playbook=True)
        seq.play('leader-settings-changed',
                 context=replace(ctx, leader=False),
                 add_to_playbook=True)
        seq.play('container-pebble-ready', add_to_playbook=True)
        seq.play('upgrade', add_to_playbook=True)

    # and at the end you could serialize it to file for later use:
    # seq.playbook.dump()


def test_playbook_serialization():
    events_ran = []

    class MyCharm(CharmBase):
        def __init__(self, framework: Framework, key: typing.Optional = None):
            super().__init__(framework, key)
            for evt in self.on.events().values():
                self.framework.observe(evt, self._record)

        def _record(self, e):
            events_ran.append(e)

    srl_scenario = Scenario.builtins.startup().playbook.dump()
    scenario = Scenario(MyCharm, playbook=Playbook.load(srl_scenario))
    scenario.play_until_complete()

    assert len(events_ran) == 4


def test_complex_scenario():
    events_ran = []

    class MyCharm(CharmBase):
        check_container_can_connect = True

        def __init__(self, framework: Framework, key: typing.Optional = None):
            super().__init__(framework, key)
            for evt in self.on.events().values():
                self.framework.observe(evt, self._record)

            assert self.unit.get_container('foo').can_connect() == self.check_container_can_connect

        def _record(self, e):
            events_ran.append(e)

    relation_mock = Mock(id=1)
    relation_mock.name = 'remote-db'

    relation_meta = RelationMeta(remote_app_name='remote', relation_id=2, endpoint='remote-db',
                                 remote_unit_ids=(0,), interface='db')

    meta = {'requires': {'remote-db': {'interface': 'db'}},
            'containers': {'foo': {}}}

    initial_ctx = Context(
                networks=(NetworkSpec(
                    name='endpoint', bind_id=2,
                    network=Network(private_address='0.0.0.2')),),
                relations=(RelationSpec(
                    application_data={'foo': 'bar'},
                    units_data={0: {'baz': 'qux'}},
                    meta=relation_meta),),
                leader=True,
                containers=(
                    ContainerSpec('foo', can_connect=True),
                ))

    MyCharm.check_container_can_connect = True
    with Scenario(
        CharmSpec(MyCharm, meta=meta),
    ) as scenario:
        scenario.play(
            context=initial_ctx,
            event=Event('remote-db-relation-changed'))

    assert len(events_ran) == 1

    MyCharm.check_container_can_connect = False
    with Scenario(
        CharmSpec(MyCharm, meta=meta),
    ) as scenario:
        scenario.play(
            context=initial_ctx.replace_container_connectivity('foo', False),
            event=Event('remote-db-relation-changed'))

    assert len(events_ran) == 2