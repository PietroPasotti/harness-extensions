"""How we'd like user code to look like.
This is a "real" scenario.
"""
import sys
import typing
from pathlib import Path

from ops.charm import CharmBase
from ops.framework import Framework

lib_root = Path(__file__).parent.parent
sys.path.append(str(lib_root))

from evt_sequences import *


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
    Scenario.builtins.STARTUP_LEADER(MyCharm).play_until_complete()
    Scenario.builtins.STARTUP_FOLLOWER(MyCharm).play_until_complete()

    # this is like a simulate_teardown_sequence()
    Scenario.builtins.TEARDOWN(MyCharm).play_until_complete()

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
        seq.play('update-status', add_to_playbook=True)
        seq.play('leader-settings-changed', add_to_playbook=True)
        seq.play('container-pebble-ready', add_to_playbook=True)
        seq.play('upgrade', add_to_playbook=True)


def test_playbook_serialization():
    # you can serialize the scenario you built (and write it to file)
    scenario = Scenario.builtins.STARTUP_LEADER.playbook.dump()

    events_ran = []

    class MyCharm(CharmBase):
        def __init__(self, framework: Framework, key: typing.Optional = None):
            super().__init__(framework, key)
            for evt in self.on.events().values():
                self.framework.observe(evt, self._record)

        def _record(self, e):
            events_ran.append(e)

    # now you can write your test code like so:
    scenario = Scenario(MyCharm, playbook=Playbook.load(scenario))
    scenario.play_until_complete()

    assert len(events_ran) == 4


def test_complex_scenario():
    events_ran = []

    class MyCharm(CharmBase):
        def __init__(self, framework: Framework, key: typing.Optional = None):
            super().__init__(framework, key)
            for evt in self.on.events().values():
                self.framework.observe(evt, self._record)

        def _record(self, e):
            events_ran.append(e)

    my_scenario = Scenario.from_scenes(
        [Scene(
            context=Context(
                networks=(NetworkSpec(
                    name='endpoint', bind_id=2,
                    network=Network(private_address='0.0.0.2')),),
                relations=(AppRelationData(
                    application_data={'foo': 'bar'},
                    units_data={0: {'baz': {'qux'}}},
                    meta=Metadata(
                        app_name='remote',
                        relation_id=2,
                        endpoint='remote-db',
                        scale=1,
                        units=(0,),
                        leader_id=0,
                        interface='db')),),
                leader=True),
            event=Event('remote-db-relation-changed')),
        ]
    )

    my_scenario(MyCharm,
                meta={'requires': {'remote-db': {'interface': 'db'}}}
                ).play_until_complete()

    assert len(events_ran) == 5  # FIXME: should be 1!
