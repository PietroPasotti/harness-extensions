from ops.charm import InstallEvent, StartEvent, CharmBase

from declarative_charm_tester import harness_factory


def test_tester():
    h = harness_factory()
    h.begin()
    c = h.charm

    @c.listener(c.on.install)
    def _on_install(self, _):
        pass

    @c.listener(c.on.start)
    def _on_start(self, _):
        pass

    assert not _on_install.called
    c.on.install.emit()
    assert isinstance(_on_install.called, InstallEvent)

    assert not _on_start.called
    c.on.start.emit()
    assert isinstance(_on_start.called, StartEvent)

    @c.run
    def _foo(self: CharmBase):
        self.ipu = object()

    assert c.ipu