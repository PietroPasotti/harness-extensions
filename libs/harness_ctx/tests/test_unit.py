import sys
import typing
from pathlib import Path

import pytest as pytest
from ops.charm import CharmBase
from ops.framework import Framework

lib_root = Path(__file__).parent.parent
sys.path.append(str(lib_root))

from harness_ctx import HarnessCtx


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
