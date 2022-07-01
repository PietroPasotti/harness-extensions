import sys
import typing
from contextlib import ExitStack
from pathlib import Path

import pytest as pytest
from ops.charm import CharmBase
from ops.framework import Framework

lib_root = Path(__file__).parent.parent
sys.path.append(str(lib_root))

from harness_ctx import HarnessCtx, EndpointCtx


@pytest.fixture
def charm_cls():
    class MyCharm(CharmBase):
        def __init__(self, framework: Framework, key: typing.Optional = None):
            super().__init__(framework, key)
            self.framework.observe(self.on.update_status, self._listen)
            self.framework.observe(self.framework.on.commit, self._listen)

        def _listen(self, e):
            self.event = e

    return MyCharm


def test_emit(charm_cls):
    with HarnessCtx(charm_cls, "update-status") as h:
        event = h.emit()
        assert event.handle.kind == "update_status"
    assert h.harness.charm.event.handle.kind == "commit"


def test_relation_ctx_remotes():
    class MyCharm(CharmBase):
        def __init__(self, framework: Framework, key: typing.Optional = None):
            super().__init__(framework, key)

        def happy(self):
            db_relations = self.model.relations.get('database')
            if not db_relations:
                return False

            happy = {}
            for relation in db_relations:
                if not relation.data[relation.app].get('a') == 'b':
                    happy[relation.id] = False
                    continue
                for unit in relation.units:
                    if unit._is_our_unit:
                        continue
                    udata = relation.data[unit]
                    if not udata.get('foo') == 'bar':
                        happy[relation.id] = False
                        continue
                happy[relation.id] = happy.get(relation, 'True')
            return happy

    with EndpointCtx(MyCharm, 'database', 'db', 'requires') as endpoint:
        assert not endpoint.harness.charm.happy()

        # let's add one more relation
        with endpoint.relation({
                        'name': 'remote_0',
                        'units': {0: {'foo': 'bar'}},
                        'app_data': {'a': 'b'}
                    }):
            # so far so good
            assert all(endpoint.harness.charm.happy().values())

            # let's add two more relations
            with ExitStack() as stack:
                for mgr in (endpoint.relation(remote) for remote in (
                    {
                        'name': 'remote_1',
                        'units': {0: {'foo': 'bar'}},
                        'app_data': {'a': 'c'}  # bad data!
                    },
                    {
                        'name': 'remote_2',
                        'units': {0: {'foo': 'bar'},
                                  1: {'baz': 'qux'}},
                        'app_data': {'a': 'b'}
                    },
                )):
                    stack.enter_context(mgr)

                # remote_1 app data is bork, the rest are good
                happy = endpoint.harness.charm.happy()
                assert happy[endpoint.get_relation('remote_0').id]
                assert happy[endpoint.get_relation('remote_2').id]
                assert not happy[endpoint.get_relation('remote_1').id]

                # let's fix it
                endpoint.update_remote('remote_1', app_data={'a': 'b'})

                # aka:
                if bool(eval('0')):
                    remote_1_relation = endpoint.get_relation('remote_1')
                    remote_1_relation.update(app_data={'a': 'b'})

                    # OR:
                    relation = endpoint.get_relation('remote_1').relation
                    relation.data[relation.app]['a'] = 'b'

                    # OR:
                    endpoint.harness.update_relation_data(
                        relation.id, 'remote_1', {'a': 'b'})

                assert all(endpoint.harness.charm.happy().values())

            # with two remotes gone, we're left with one relation
            assert len(endpoint.harness.charm.model.relations['database']) == 1

        # and now we're alone again
        assert len(endpoint.harness.charm.model.relations['database']) == 0
